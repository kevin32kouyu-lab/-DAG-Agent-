"""这个模块提供网页搜索、单页抓取和批量抓取工具。"""

import httpx
import logging
import os
from typing import Any
from bs4 import BeautifulSoup
from src.agents.tools.base import ToolBase

logger = logging.getLogger(__name__)


class WebScrapeTool(ToolBase):
    name = "web_scrape"
    description = "Scrape a webpage and extract title, text content, and key paragraphs."
    param_schema = {
        "url": {"type": "string", "description": "The URL to scrape"},
    }

    # 更真实的浏览器 headers — 减少被反爬虫拦截的概率
    _HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        url = kwargs.get("url", "")
        if not url:
            return {"url": url, "error": "URL is empty or missing", "title": "", "text": ""}
            
        import os
        error_msg = ""
        fallback_errors: list[str] = []
        
        # ── Defense Line 1: Direct highly-optimized browser-impersonation scrape ──
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers=self._HEADERS)
                if resp.status_code < 400:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in soup(["script", "style", "nav", "footer", "header"]):
                        tag.decompose()

                    title = soup.title.string.strip() if soup.title else ""
                    text = soup.get_text(separator="\n", strip=True)
                    paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]

                    return {
                        "url": url,
                        "title": title,
                        "text": text[:10000],
                        "key_paragraphs": paragraphs[:20],
                        "source": "direct"
                    }
                else:
                    error_msg = f"HTTP {resp.status_code}"
        except Exception as e:
            error_msg = str(e)
            
        # ── Defense Line 2: Tavily extract (API-based bypass) ──
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if api_key:
            try:
                async with httpx.AsyncClient(timeout=25) as client:
                    resp = await client.post(
                        "https://api.tavily.com/extract",
                        json={"urls": [url], "extract_depth": "basic"},
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        }
                    )
                    if resp.status_code == 200:
                        res_data = resp.json()
                        results = res_data.get("results", [])
                        if results and not results[0].get("error"):
                            res = results[0]
                            title = res.get("title", "")
                            raw_content = res.get("raw_content", "")
                            paragraphs = [p.strip() for p in raw_content.split("\n\n") if len(p.strip()) > 40]
                            return {
                                "url": url,
                                "title": title,
                                "text": raw_content[:10000],
                                "key_paragraphs": paragraphs[:20],
                                "source": "tavily_extract"
                            }
            except Exception as e_tav:
                tavily_error = str(e_tav)
                fallback_errors.append(f"Tavily: {tavily_error}")
                logger.warning("Tavily 兜底抓取失败: url=%s, reason=%s", url, tavily_error)
                
        # ── Defense Line 3: Wayback historical snapshot ──
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                avail_resp = await client.get(
                    "https://archive.org/wayback/available",
                    params={"url": url},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                if avail_resp.status_code == 200:
                    avail_data = avail_resp.json()
                    snapshots = avail_data.get("archived_snapshots", {})
                    closest = snapshots.get("closest", {})
                    if closest.get("available") and closest.get("url"):
                        snapshot_url = closest["url"]
                        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as web_client:
                            snap_resp = await web_client.get(snapshot_url, headers=self._HEADERS)
                            if snap_resp.status_code == 200:
                                soup = BeautifulSoup(snap_resp.text, "html.parser")
                                for tag in soup(["script", "style", "nav", "footer", "header"]):
                                    tag.decompose()
                                title = soup.title.string.strip() if soup.title else ""
                                text = soup.get_text(separator="\n", strip=True)
                                paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]
                                return {
                                    "url": url,
                                    "title": title,
                                    "text": text[:10000],
                                    "key_paragraphs": paragraphs[:20],
                                    "source": "wayback_snapshot",
                                    "snapshot_url": snapshot_url
                                }
        except Exception as e_wb:
            wayback_error = str(e_wb)
            fallback_errors.append(f"Wayback: {wayback_error}")
            logger.warning("Wayback 兜底抓取失败: url=%s, reason=%s", url, wayback_error)
            
        fallback_summary = f"; fallback errors: {', '.join(fallback_errors)}" if fallback_errors else ""
        return {
            "url": url,
            "error": f"Failed to scrape URL through all 3 defense lines. Line 1 error: {error_msg}{fallback_summary}",
            "title": "",
            "text": ""
        }


class WebSearchTool(ToolBase):
    name = "web_search"
    description = (
        "Search the web for information about a product or topic. "
        "Returns title, url, and snippet for each result. "
        "Aggregates from Firecrawl (best quality, needs API key), DuckDuckGo (reliable), "
        "Sogou and Baidu (best-effort). All free."
    )
    param_schema = {
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Max results (default 10, max 20)"},
        "backends": {
            "type": "array",
            "description": "Search backends: 'firecrawl', 'ddgs', 'sogou', 'baidu'. Default: all available.",
        },
    }

    _UA_LIST = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    ]

    def _get_ua(self, index: int = 0) -> str:
        return self._UA_LIST[index % len(self._UA_LIST)]

    async def execute(self, **kwargs) -> dict[str, Any]:
        import asyncio

        query = kwargs.get("query", "")
        max_results = min(int(kwargs.get("max_results", 10)), 20)
        # Default: try firecrawl first (if key configured), then ddgs, then sogou/baidu
        default_backends = ["ddgs", "sogou", "baidu"]
        if os.environ.get("FIRECRAWL_API_KEY"):
            default_backends.insert(0, "firecrawl")
        backends = kwargs.get("backends", default_backends)

        if not query:
            return {"query": query, "error": "query is required", "results": []}

        # Run backends with stagger to avoid concurrent-request detection
        async def _run_with_delay(delay, coro):
            await asyncio.sleep(delay)
            return await coro

        # Use hash of query to pick different UAs for each backend
        ua_offset = hash(query) % len(self._UA_LIST)
        # Each backend fetches more than needed so merged results have diversity
        per_backend = max(max_results, 8)
        tasks = []
        if "firecrawl" in backends:
            tasks.append(_run_with_delay(0, self._search_firecrawl(query, per_backend)))
        if "ddgs" in backends:
            tasks.append(_run_with_delay(0, self._search_ddgs(query, per_backend)))
        if "sogou" in backends:
            tasks.append(_run_with_delay(0.5, self._search_sogou(query, per_backend, ua_offset)))
        if "baidu" in backends:
            tasks.append(_run_with_delay(1.0, self._search_baidu(query, per_backend, ua_offset + 1)))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Merge and deduplicate, interleaving results from each backend
        seen_urls = set()
        merged = []
        batches = []
        for batch in all_results:
            if isinstance(batch, Exception):
                logger.warning("Search backend error: %s", batch)
                continue
            batches.append(batch)

        # Round-robin merge: take one from each backend in turn
        max_len = max((len(b) for b in batches), default=0)
        for i in range(max_len):
            for batch in batches:
                if i < len(batch):
                    r = batch[i]
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        merged.append(r)
                    elif not url:
                        # Some results may have empty URLs (e.g. from Baidu)
                        merged.append(r)

        if not merged:
            return {
                "query": query,
                "error": "All search backends returned no results.",
                "results": [],
            }

        return {"query": query, "results": merged[:max_results]}

    async def _search_firecrawl(self, query: str, max_results: int) -> list[dict]:
        """Firecrawl search API — best quality, especially for Chinese content."""
        api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        if not api_key:
            return []
        try:
            import asyncio
            loop = asyncio.get_event_loop()

            def _do():
                from firecrawl import Firecrawl
                client = Firecrawl(api_key=api_key)
                result = client.search(query, limit=max_results)
                web = result.web or []
                return [
                    {
                        "title": getattr(r, "title", "") or "",
                        "url": getattr(r, "url", "") or "",
                        "snippet": getattr(r, "description", "") or "",
                        "source": "firecrawl",
                    }
                    for r in web
                ]

            return await loop.run_in_executor(None, _do)
        except Exception as e:
            logger.warning("Firecrawl search failed: %s", e)
            return []

    async def _search_ddgs(self, query: str, max_results: int) -> list[dict]:
        """DuckDuckGo via ddgs library."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, lambda: _ddgs_search(query, max_results)
            )
        except Exception as e:
            logger.warning("ddgs search failed: %s", e)
            return []

    async def _search_sogou(self, query: str, max_results: int, ua_offset: int = 0) -> list[dict]:
        """Sogou web search via HTML scraping."""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    "https://www.sogou.com/web",
                    params={"query": query},
                    headers={"User-Agent": self._get_ua(ua_offset)},
                )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for item in soup.select(".vrwrap"):
                link = item.select_one("h3 a")
                if not link:
                    continue
                # Extract snippet from various possible containers
                snippet_el = (
                    item.select_one(".str_info")
                    or item.select_one(".str-text-info")
                    or item.select_one("p")
                    or item.select_one(".space-txt")
                )
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                href = link.get("href", "")
                # Sogou may use relative or redirect URLs
                results.append({
                    "title": link.get_text(strip=True),
                    "url": href,
                    "snippet": snippet[:300],
                    "source": "sogou",
                })
            return results[:max_results]
        except Exception as e:
            logger.warning("Sogou search failed: %s", e)
            return []

    async def _search_baidu(self, query: str, max_results: int, ua_offset: int = 1) -> list[dict]:
        """Baidu web search via mobile HTML scraping (avoids desktop CAPTCHA)."""
        try:
            mobile_ua = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                        "Mobile/15E148 Safari/604.1")
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    "https://m.baidu.com/s",
                    params={"wd": query},
                    headers={
                        "User-Agent": mobile_ua,
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                    },
                )
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []

            for container in soup.select(".c-result"):
                # Title: first significant link text
                title = ""
                url = ""
                for a_tag in container.select("a"):
                    text = a_tag.get_text(strip=True)
                    if len(text) > 4 and text not in ("大家还在搜",):
                        title = text[:100]
                        url = a_tag.get("href", "")
                        break

                if not title:
                    continue

                # Snippet: summary text elements
                snippet = ""
                for sel in [".summary-text_560AW", ".cu-line-clamp-3", ".c-color",
                            "span[class*='summary']", "div[class*='summary']"]:
                    el = container.select_one(sel)
                    if el:
                        text = el.get_text(strip=True)
                        if len(text) > 10:
                            snippet = text[:300]
                            break

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": "baidu",
                })
            return results[:max_results]
        except Exception as e:
            logger.warning("Baidu search failed: %s", e)
            return []


def _ddgs_search(query: str, max_results: int) -> list[dict]:
    """Synchronous DuckDuckGo search via ddgs library."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []

    results = []
    for r in DDGS().text(query, max_results=max_results):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
            "source": "ddgs",
        })
    return results


class BatchWebScrapeTool(ToolBase):
    name = "batch_web_scrape"
    description = "Scrape multiple webpages concurrently and extract title, text content, and key paragraphs in parallel."
    param_schema = {
        "urls": {"type": "array", "items": {"type": "string"}, "description": "List of URLs to scrape concurrently"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        import asyncio
        urls = kwargs.get("urls", [])
        if isinstance(urls, str):
            # Fallback if LLM passes a single string instead of list
            if "," in urls:
                urls = [u.strip() for u in urls.split(",") if u.strip()]
            elif urls.strip():
                urls = [urls.strip()]

        if not urls:
            return {"error": "urls is required and must be a list of strings", "results": []}

        # Deduplicate and limit to max 10 to protect resources, recommend max 5
        urls = list(dict.fromkeys([u.strip() for u in urls if u and u.strip()]))[:10]
        
        # Concurrent limit semaphore
        sem = asyncio.Semaphore(5)
        scraper = WebScrapeTool()

        async def _sc(url: str) -> dict:
            async with sem:
                res = await scraper.execute(url=url)
                return res

        tasks = [asyncio.create_task(_sc(url)) for url in urls]
        results = await asyncio.gather(*tasks)
        
        return {
            "urls": urls,
            "results": results,
            "total_requested": len(urls),
            "successful": sum(1 for r in results if "error" not in r),
        }
