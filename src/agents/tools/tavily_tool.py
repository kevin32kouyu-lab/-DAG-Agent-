"""
Tavily Search API 工具 — 替代 DuckDuckGo 的可靠搜索方案。

免费额度: 1000 次/月
API 文档: https://docs.tavily.com/

与 DuckDuckGo HTML 抓取不同，Tavily 是真正的搜索 API：
- 搜索结果稳定，不受 IP 封锁影响
- 返回结构化 JSON，含标题、URL、摘要、可信度评分
- 支持 `include_domains` / `exclude_domains` 过滤
"""

import os
import httpx
from typing import Any
from src.agents.tools.base import ToolBase


class TavilySearchTool(ToolBase):
    name = "tavily_search"
    description = (
        "Search the web using Tavily API for competitor intelligence, news, and market data. "
        "Returns structured results with titles, URLs, snippets, and relevance scores. "
        "Much more reliable than DuckDuckGo scraping. "
        "Use 'basic' depth for quick searches, 'advanced' for comprehensive results."
    )
    param_schema = {
        "query": {"type": "string", "description": "Search query string"},
        "search_depth": {
            "type": "string",
            "description": "Search depth: 'basic' (fast, up to 10 results) or 'advanced' (comprehensive, up to 20 results)",
        },
        "max_results": {
            "type": "integer",
            "description": "Max results to return (1-20, default 10)",
        },
        "include_domains": {
            "type": "array",
            "description": "Optional list of domains to include (e.g. ['docs.example.com'])",
        },
    }

    BASE = "https://api.tavily.com/search"

    async def execute(self, **kwargs) -> dict[str, Any]:
        api_key = os.environ.get("TAVILY_API_KEY", "")
        if not api_key:
            return {
                "error": (
                    "Tavily API key 未配置。请设置环境变量 TAVILY_API_KEY。"
                    "免费获取: https://app.tavily.com/home"
                ),
                "results": [],
            }

        query = kwargs.get("query", "")
        if not query:
            return {"error": "query is required", "results": []}

        search_depth = kwargs.get("search_depth", "basic")
        if search_depth not in ("basic", "advanced"):
            search_depth = "basic"

        max_results = min(int(kwargs.get("max_results", 10)), 20)
        include_domains = kwargs.get("include_domains")

        payload: dict[str, Any] = {
            "api_key": api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
        }
        if include_domains:
            payload["include_domains"] = include_domains

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    self.BASE,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 401 or resp.status_code == 403:
                    return {
                        "query": query,
                        "error": "Tavily API key 无效或已过期",
                        "results": [],
                    }
                if resp.status_code == 429:
                    return {
                        "query": query,
                        "error": f"Tavily 配额已用完 (免费额度 1000 次/月): HTTP {resp.status_code}",
                        "results": [],
                    }
                resp.raise_for_status()
                data = resp.json()

        except httpx.TimeoutException:
            return {"query": query, "error": "Tavily 请求超时 (30s)", "results": []}
        except Exception as e:
            return {"query": query, "error": f"Tavily 查询失败: {e}", "results": []}

        results = []
        for r in data.get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": (r.get("content", "") or "")[:500],
                "score": r.get("score", 0),
                "raw_content": r.get("raw_content"),
            })

        return {
            "query": query,
            "search_depth": search_depth,
            "answer": data.get("answer", ""),
            "total_results": len(results),
            "results": results,
        }
