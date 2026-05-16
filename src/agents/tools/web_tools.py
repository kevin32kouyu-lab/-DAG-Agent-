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

    async def execute(self, **kwargs) -> dict[str, Any]:
        url = kwargs.get("url", "")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers={"User-Agent": "CompAgent/1.0"})
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
