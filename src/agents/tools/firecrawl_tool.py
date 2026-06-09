"""
Firecrawl 工具 — 高质量网页搜索和抓取。

通过 Firecrawl API 搜索网页和抓取页面内容，返回干净的 markdown 文本。
内置代理池和反爬处理，搜索质量远优于 DuckDuckGo HTML 爬取。

免费额度: 500 页/月
需要 API Key: FIRECRAWL_API_KEY 环境变量
"""

import os
import logging
from typing import Any
from src.agents.tools.base import ToolBase

logger = logging.getLogger(__name__)


class FirecrawlTool(ToolBase):
    name = "firecrawl"
    description = (
        "Search the web and scrape pages using Firecrawl API. "
        "Returns clean markdown content with built-in anti-bot bypass. "
        "Much better search quality than DuckDuckGo, especially for Chinese content. "
        "Use action='search' to find pages, action='scrape' to extract content from a URL. "
        "Free tier: 500 pages/month. Requires FIRECRAWL_API_KEY env var."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "search (web search), scrape (extract content from URL), "
                           "map (discover all URLs on a site)",
        },
        "query": {"type": "string", "description": "Search query (for action=search)"},
        "url": {"type": "string", "description": "URL to scrape or map (for action=scrape/map)"},
        "limit": {"type": "integer", "description": "Max results (default 5, max 10)"},
    }

    def _get_client(self):
        api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        if not api_key:
            return None
        from firecrawl import Firecrawl
        return Firecrawl(api_key=api_key)

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "search")

        client = self._get_client()
        if client is None:
            return {
                "error": "FIRECRAWL_API_KEY not configured. Set it in .env file.",
                "results": [],
            }

        try:
            if action == "search":
                return await self._search(client, kwargs.get("query", ""), kwargs.get("limit", 5))
            elif action == "scrape":
                return await self._scrape(client, kwargs.get("url", ""))
            elif action == "map":
                return await self._map(client, kwargs.get("url", ""), kwargs.get("limit", 10))
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            logger.warning("Firecrawl %s failed: %s", action, e)
            return {"error": f"Firecrawl {action} failed: {type(e).__name__}: {e}", "results": []}

    def _run_sync(self, func, *args):
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, func, *args)

    async def _search(self, client, query: str, limit: int) -> dict[str, Any]:
        if not query:
            return {"error": "query is required", "results": []}

        def _do():
            return client.search(query, limit=limit)

        result = await self._run_sync(_do)

        web = result.web or []
        results = []
        for r in web:
            results.append({
                "title": getattr(r, "title", "") or "",
                "url": getattr(r, "url", "") or "",
                "snippet": getattr(r, "description", "") or "",
                "source": "firecrawl",
            })

        return {"query": query, "results": results}

    async def _scrape(self, client, url: str) -> dict[str, Any]:
        if not url:
            return {"error": "url is required"}

        def _do():
            return client.scrape(url, formats=["markdown"])

        result = await self._run_sync(_do)

        metadata = result.metadata or {}
        return {
            "url": url,
            "title": getattr(metadata, "title", "") or "",
            "markdown": (result.markdown or "")[:15000],
            "source": "firecrawl",
        }

    async def _map(self, client, url: str, limit: int) -> dict[str, Any]:
        if not url:
            return {"error": "url is required"}

        def _do():
            return client.map(url, limit=limit)

        result = await self._run_sync(_do)

        links = result.links if hasattr(result, "links") else []
        return {
            "url": url,
            "links": links[:limit],
            "total": len(links),
        }
