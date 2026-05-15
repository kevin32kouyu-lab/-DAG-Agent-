import re
import httpx
from typing import Any
from bs4 import BeautifulSoup
from src.agents.tools.base import ToolBase


class CompanyScopeTool(ToolBase):
    """Free company intelligence tool aggregating 6 public data sources.

    Sources: SEC EDGAR, OpenCorporates, Cloudflare DNS, RDAP, HTML meta analysis,
    DuckDuckGo competitor search — all free, no API keys required.
    """

    name = "company_scope"
    description = (
        "Competitive intelligence: tech stack, SEC financials, company registry, "
        "domain infrastructure, competitor discovery, social presence. "
        "Use this to enrich analysis with external company data."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "What to query: tech_stack, financials, registry, domain_intel, competitors, social, profile",
        },
        "query": {
            "type": "string",
            "description": "Domain (stripe.com) for tech_stack/domain_intel/social, company name for financials/registry/competitors, either for profile",
        },
    }

    # ── public API endpoints ──
    SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{}.json"
    OPENCORP_SEARCH_URL = "https://api.opencorporates.com/v0.4/companies/search"
    DNS_OVER_HTTPS = "https://cloudflare-dns.com/dns-query"
    RDAP_URL = "https://rdap.org/domain/{}"
    DDG_SEARCH = "https://html.duckduckgo.com/html/"

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "profile")
        query = kwargs.get("query", "").strip()
        if not query:
            return {"error": "query is required"}

        domain = query if "." in query and "/" not in query else ""

        handlers = {
            "tech_stack": self._tech_stack,
            "financials": self._financials,
            "registry": self._registry,
            "domain_intel": self._domain_intel,
            "competitors": self._competitors,
            "social": self._social,
            "profile": self._profile,
        }
        handler = handlers.get(action, self._profile)
        try:
            result = await handler(query, domain)
            result["action"] = action
            return result
        except Exception as e:
            return {"action": action, "query": query, "error": str(e)}

    # ── action handlers ──

    async def _profile(self, query: str, domain: str) -> dict:
        """Aggregated company profile from multiple sources."""
        results: dict[str, Any] = {"query": query, "source": "company_scope"}

        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "CompAgent/1.0"}) as client:
            # Run all lookups in parallel
            import asyncio

            async def safe(coro, name):
                try:
                    return await coro
                except Exception as e:
                    return {"error": str(e)}

            tech, registry, domain_info, social, competitors = await asyncio.gather(
                safe(self._tech_stack(query, domain, client), "tech_stack"),
                safe(self._registry(query, domain, client), "registry"),
                safe(self._domain_intel(query, domain, client), "domain_intel"),
                safe(self._social(query, domain, client), "social"),
                safe(self._competitors(query, domain, client), "competitors"),
            )

            # SEC EDGAR only works for US public companies — don't block on it
            try:
                results["financials"] = await self._financials(query, domain, client)
            except Exception:
                results["financials"] = {"note": "Not a US public company or SEC data unavailable"}

            results["tech_stack"] = tech
            results["registry"] = registry
            results["domain_intel"] = domain_info
            results["social"] = social
            results["competitors"] = competitors

        return results

    async def _tech_stack(self, query: str, domain: str, client: httpx.AsyncClient | None = None) -> dict:
        """Detect tech stack from HTTP headers and HTML meta tags."""
        if not domain:
            domain = self._guess_domain(query)

        result: dict[str, Any] = {"domain": domain, "detected": [], "headers": {}}
        close_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=10, headers={"User-Agent": "CompAgent/1.0"})

        try:
            resp = await client.get(f"https://{domain}", follow_redirects=True)
            headers = dict(resp.headers)
            result["headers"] = {k: v for k, v in headers.items() if k.lower() in (
                "server", "x-powered-by", "cf-ray", "x-generator", "x-drupal-cache",
                "x-nextjs-cache", "x-vercel-cache", "x-shopify-stage",
            )}

            html = resp.text[:20000]
            result["detected"] = self._parse_tech_signatures(headers, html)
        except Exception as e:
            result["error"] = str(e)
        finally:
            if close_client:
                await client.aclose()

        return result

    async def _financials(self, query: str, domain: str, client: httpx.AsyncClient | None = None) -> dict:
        """Query SEC EDGAR for company financial data."""
        close_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=10, headers={"User-Agent": "CompAgent/1.0 (user@example.com)"})

        try:
            # Step 1: Find CIK from ticker/name
            tickers_resp = await client.get(self.SEC_TICKERS_URL)
            tickers_data = tickers_resp.json()

            cik = None
            matched_name = ""
            query_lower = query.lower().strip()
            for _key, entry in tickers_data.items():
                if query_lower == entry.get("ticker", "").lower():
                    cik = entry["cik_str"]
                    matched_name = entry["title"]
                    break
            if not cik:
                for _key, entry in tickers_data.items():
                    if query_lower in entry.get("title", "").lower():
                        cik = entry["cik_str"]
                        matched_name = entry["title"]
                        break

            if not cik:
                return {"note": f"No SEC filing entity found for '{query}'"}

            # Step 2: Get submissions (10-K, 10-Q)
            cik_padded = str(cik).zfill(10)
            sub_url = self.SEC_SUBMISSIONS_URL.format(cik_padded)
            sub_resp = await client.get(sub_url, headers={"User-Agent": "CompAgent/1.0 (user@example.com)"})
            sub = sub_resp.json()

            filings = []
            recent = sub.get("filings", {}).get("recent", {})
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            docs = recent.get("primaryDocument", [])
            acc_nums = recent.get("accessionNumber", [])

            for i in range(min(len(forms), 30)):
                if forms[i] in ("10-K", "10-Q", "8-K"):
                    filings.append({
                        "form": forms[i],
                        "date": dates[i] if i < len(dates) else "",
                        "doc": docs[i] if i < len(docs) else "",
                    })

            return {
                "company": matched_name,
                "cik": cik,
                "recent_filings": filings[:10],
                "note": "SEC EDGAR public data — detailed financials require parsing XBRL filings",
            }
        except Exception as e:
            return {"error": str(e)}
        finally:
            if close_client:
                await client.aclose()

    async def _registry(self, query: str, domain: str, client: httpx.AsyncClient | None = None) -> dict:
        """Look up company in OpenCorporates registry."""
        close_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=10, headers={"User-Agent": "CompAgent/1.0"})

        try:
            name = query if not domain else query
            resp = await client.get(self.OPENCORP_SEARCH_URL, params={"q": name, "per_page": 3})
            data = resp.json()
            companies = []
            for c in data.get("results", {}).get("companies", []):
                co = c.get("company", {})
                companies.append({
                    "name": co.get("name", ""),
                    "jurisdiction": co.get("jurisdiction_code", ""),
                    "incorporation_date": co.get("incorporation_date", ""),
                    "status": co.get("current_status", ""),
                    "company_number": co.get("company_number", ""),
                })
            return {"companies": companies}
        except Exception as e:
            return {"error": str(e)}
        finally:
            if close_client:
                await client.aclose()

    async def _domain_intel(self, query: str, domain: str, client: httpx.AsyncClient | None = None) -> dict:
        """DNS records and RDAP domain registration info."""
        if not domain:
            domain = self._guess_domain(query)
        if not domain:
            return {"error": "No valid domain provided or inferred"}

        close_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=10)

        result: dict[str, Any] = {"domain": domain}
        try:
            # DNS A record via Cloudflare DoH
            dns_resp = await client.get(
                self.DNS_OVER_HTTPS,
                params={"name": domain, "type": "A"},
                headers={"Accept": "application/dns-json"},
            )
            dns = dns_resp.json()
            result["dns_a"] = [a.get("data", "") for a in dns.get("Answer", []) if a.get("type") == 1]

            # RDAP domain registration
            try:
                rdap_resp = await client.get(self.RDAP_URL.format(domain))
                rdap = rdap_resp.json()
                events = rdap.get("events", [])
                result["registration"] = {
                    "registrar": rdap.get("port43", ""),
                    "created": next((e["eventDate"] for e in events if e.get("eventAction") == "registration"), ""),
                    "nameservers": [ns.get("ldhName", "") for ns in rdap.get("nameservers", [])[:5]],
                }
            except Exception:
                result["registration"] = {"note": "RDAP lookup failed"}
        except Exception as e:
            result["error"] = str(e)
        finally:
            if close_client:
                await client.aclose()

        return result

    async def _competitors(self, query: str, domain: str, client: httpx.AsyncClient | None = None) -> dict:
        """Discover competitors via DuckDuckGo search."""
        close_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=10, headers={"User-Agent": "CompAgent/1.0"})

        try:
            search_q = f"{query} competitors alternatives similar companies"
            resp = await client.get(self.DDG_SEARCH, params={"q": search_q})
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for r in soup.select(".result")[:8]:
                link = r.select_one(".result__a")
                snippet = r.select_one(".result__snippet")
                if link:
                    results.append({
                        "title": link.get_text(strip=True),
                        "url": link.get("href", ""),
                        "snippet": snippet.get_text(strip=True) if snippet else "",
                    })
            return {"competitors": results, "note": "Derived from web search — verify independently"}
        except Exception as e:
            return {"error": str(e)}
        finally:
            if close_client:
                await client.aclose()

    async def _social(self, query: str, domain: str, client: httpx.AsyncClient | None = None) -> dict:
        """Detect social media presence from company homepage."""
        if not domain:
            domain = self._guess_domain(query)
        if not domain:
            return {"error": "No valid domain provided"}

        close_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=10, headers={"User-Agent": "CompAgent/1.0"})

        social_patterns = {
            "linkedin": r"linkedin\.com/company/[\w\-]+",
            "twitter": r"(?:twitter|x)\.com/[\w\-]+",
            "github": r"github\.com/[\w\-]+",
            "youtube": r"youtube\.com/@[\w\-]+",
            "instagram": r"instagram\.com/[\w\-\.]+",
            "facebook": r"facebook\.com/[\w\-\.]+",
        }

        result: dict[str, Any] = {"domain": domain, "social_links": {}}
        try:
            resp = await client.get(f"https://{domain}", follow_redirects=True)
            html = resp.text[:50000]
            for platform, pattern in social_patterns.items():
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    result["social_links"][platform] = matches[0]
        except Exception as e:
            result["error"] = str(e)
        finally:
            if close_client:
                await client.aclose()

        return result

    # ── helpers ──

    @staticmethod
    def _guess_domain(query: str) -> str:
        """Guess domain from company name."""
        q = query.lower().strip()
        # Handle full URLs
        for prefix in ("https://", "http://"):
            if q.startswith(prefix):
                q = q.removeprefix(prefix)
        q = q.split("/")[0]  # Remove path
        if "." in q:
            return q.rstrip(".")
        # Plain company name — guess .com
        name = q.replace(" ", "").replace(",", "")
        return f"{name}.com"

    @staticmethod
    def _parse_tech_signatures(headers: dict, html: str) -> list[dict]:
        """Extract technology indicators from headers and HTML."""
        detected: list[dict] = []
        hdr_lower = {k.lower(): v for k, v in headers.items()}

        # Server / hosting
        server = hdr_lower.get("server", "")
        if "cloudflare" in server:
            detected.append({"tech": "Cloudflare", "category": "CDN", "source": "header"})
        if "nginx" in server:
            detected.append({"tech": "Nginx", "category": "Web Server", "source": "header"})
        if "apache" in server:
            detected.append({"tech": "Apache", "category": "Web Server", "source": "header"})

        # X-Powered-By
        powered = hdr_lower.get("x-powered-by", "")
        if "express" in powered:
            detected.append({"tech": "Express.js", "category": "Framework", "source": "header"})
        if "next.js" in powered:
            detected.append({"tech": "Next.js", "category": "Framework", "source": "header"})

        # HTML meta generator
        gen_match = re.search(r'<meta\s+name="generator"[^>]+content="([^"]+)"', html, re.IGNORECASE)
        if gen_match:
            detected.append({"tech": gen_match.group(1), "category": "CMS/Generator", "source": "meta"})

        # Shopify
        if "myshopify.com" in html or "cdn.shopify.com" in html:
            detected.append({"tech": "Shopify", "category": "E-commerce", "source": "html"})

        # WordPress
        if "wp-content" in html or "wp-includes" in html:
            detected.append({"tech": "WordPress", "category": "CMS", "source": "html"})

        # React
        if 'data-reactroot' in html.lower() or 'data-reactid' in html.lower():
            detected.append({"tech": "React", "category": "Frontend", "source": "html"})

        # Google Analytics
        if "googletagmanager.com" in html or "google-analytics.com" in html:
            detected.append({"tech": "Google Analytics", "category": "Analytics", "source": "html"})

        # Stripe
        if "js.stripe.com" in html:
            detected.append({"tech": "Stripe", "category": "Payments", "source": "html"})

        # Vercel
        if hdr_lower.get("x-vercel-cache"):
            detected.append({"tech": "Vercel", "category": "Hosting", "source": "header"})

        return detected
