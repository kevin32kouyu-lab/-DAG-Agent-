import httpx
from typing import Any
from bs4 import BeautifulSoup
from src.agents.tools.base import ToolBase


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
        try:
            # follow_redirects=True, longer timeout
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers=self._HEADERS)
                if resp.status_code >= 400:
                    return {"url": url, "error": f"HTTP {resp.status_code}", "title": "", "text": ""}
                resp.raise_for_status()

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
            }
        except Exception as e:
            return {"url": url, "error": str(e), "title": "", "text": ""}


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
