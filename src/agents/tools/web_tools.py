"""这个模块提供网页搜索、单页抓取和批量抓取工具。"""

import httpx
import logging
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
    description = "Search the web for information about a product or topic. Returns title, url, and snippet for each result."
    param_schema = {
        "query": {"type": "string", "description": "Search query"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        query = kwargs.get("query", "")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                )
            if resp.status_code != 200:
                return {"query": query, "error": f"HTTP {resp.status_code}", "results": []}
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for r in soup.select(".result"):
                link = r.select_one(".result__a")
                snippet = r.select_one(".result__snippet")
                if link:
                    results.append({
                        "title": link.get_text(strip=True),
                        "url": link.get("href", ""),
                        "snippet": snippet.get_text(strip=True) if snippet else "",
                    })
            if not results:
                return {
                    "query": query,
                    "error": "Search returned no results. DuckDuckGo may be blocked or the HTML structure changed.",
                    "results": [],
                }
            return {"query": query, "results": results[:15]}
        except Exception as e:
            return {"query": query, "error": f"Search failed: {e}", "results": []}


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
