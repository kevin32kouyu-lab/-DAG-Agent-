"""
NewsAPI 工具 — 搜索全球新闻文章和头条。

免费额度: 100 次/天，1 个月历史数据
API 文档: https://newsapi.org/docs
需要 API Key: NEWSAPI_KEY 环境变量
"""

import os
import httpx
import logging
from typing import Any
from src.agents.tools.base import ToolBase

logger = logging.getLogger(__name__)


class NewsAPITool(ToolBase):
    name = "newsapi"
    description = (
        "Search global news articles and headlines using NewsAPI. "
        "Covers 150,000+ sources worldwide in 14 languages. "
        "Use action='everything' to search articles, action='headlines' for top headlines, "
        "action='sources' to list available news sources. "
        "Free tier: 100 requests/day, 1 month history. Requires NEWSAPI_KEY env var."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "everything (search all articles), headlines (top headlines by country/category), "
                           "sources (list available news sources)",
        },
        "query": {"type": "string", "description": "Search query (for action=everything/headlines)"},
        "language": {"type": "string", "description": "Language code: 'en', 'zh', etc. (default 'zh')"},
        "country": {"type": "string", "description": "Country code for headlines: 'us', 'cn', etc. (default 'cn')"},
        "category": {
            "type": "string",
            "description": "Category for headlines: business, entertainment, general, health, science, sports, technology",
        },
        "sources": {"type": "string", "description": "Comma-separated source IDs (e.g. 'bbc-news,cnn')"},
        "sort_by": {
            "type": "string",
            "description": "Sort results: 'relevancy', 'popularity', 'publishedAt' (default 'publishedAt')",
        },
        "limit": {"type": "integer", "description": "Max results (default 10, max 20)"},
    }

    BASE = "https://newsapi.org/v2"

    async def execute(self, **kwargs) -> dict[str, Any]:
        api_key = os.environ.get("NEWSAPI_KEY", "")
        if not api_key:
            return {
                "error": "NEWSAPI_KEY not configured. Get free key at https://newsapi.org/register",
                "results": [],
            }

        action = kwargs.get("action", "everything")

        try:
            if action == "everything":
                return await self._everything(api_key, kwargs)
            elif action == "headlines":
                return await self._headlines(api_key, kwargs)
            elif action == "sources":
                return await self._sources(api_key, kwargs)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            logger.warning("NewsAPI %s failed: %s", action, e)
            return {"error": f"NewsAPI {action} failed: {e}", "results": []}

    def _headers(self, api_key: str) -> dict:
        return {"X-Api-Key": api_key, "User-Agent": "CompAgent/1.0"}

    async def _everything(self, api_key: str, kwargs: dict) -> dict[str, Any]:
        query = kwargs.get("query", "")
        if not query:
            return {"error": "query is required", "results": []}

        limit = min(int(kwargs.get("limit", 10)), 20)
        language = kwargs.get("language", "zh")
        sort_by = kwargs.get("sort_by", "publishedAt")

        params = {
            "q": query,
            "language": language,
            "sortBy": sort_by,
            "pageSize": limit,
        }

        # Add sources if specified (overrides language/country)
        sources = kwargs.get("sources")
        if sources:
            params["sources"] = sources

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/everything",
                params=params,
                headers=self._headers(api_key),
            )

        if resp.status_code == 426:
            return {"error": "NewsAPI: upgrade plan required for this request", "results": []}
        if resp.status_code == 429:
            return {"error": "NewsAPI: rate limit exceeded (100/day free)", "results": []}
        if resp.status_code != 200:
            return {"error": f"NewsAPI: HTTP {resp.status_code}", "results": []}

        data = resp.json()
        articles = data.get("articles", [])

        results = []
        for a in articles:
            results.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "description": a.get("description", ""),
                "source": (a.get("source") or {}).get("name", ""),
                "author": a.get("author", ""),
                "published_at": a.get("publishedAt", ""),
                "image_url": a.get("urlToImage", ""),
            })

        return {
            "query": query,
            "total_results": data.get("totalResults", 0),
            "results": results,
        }

    async def _headlines(self, api_key: str, kwargs: dict) -> dict[str, Any]:
        query = kwargs.get("query", "")
        limit = min(int(kwargs.get("limit", 10)), 20)
        country = kwargs.get("country", "cn")
        category = kwargs.get("category", "")
        sources = kwargs.get("sources", "")

        params = {"pageSize": limit}

        if sources:
            params["sources"] = sources
        else:
            params["country"] = country
            if category:
                params["category"] = category
        if query:
            params["q"] = query

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/top-headlines",
                params=params,
                headers=self._headers(api_key),
            )

        if resp.status_code != 200:
            return {"error": f"NewsAPI headlines: HTTP {resp.status_code}", "results": []}

        data = resp.json()
        articles = data.get("articles", [])

        results = []
        for a in articles:
            results.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "description": a.get("description", ""),
                "source": (a.get("source") or {}).get("name", ""),
                "published_at": a.get("publishedAt", ""),
            })

        return {
            "country": country,
            "category": category,
            "total_results": data.get("totalResults", 0),
            "results": results,
        }

    async def _sources(self, api_key: str, kwargs: dict) -> dict[str, Any]:
        language = kwargs.get("language", "zh")
        country = kwargs.get("country", "")
        category = kwargs.get("category", "")

        params = {"language": language}
        if country:
            params["country"] = country
        if category:
            params["category"] = category

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/top-headlines/sources",
                params=params,
                headers=self._headers(api_key),
            )

        if resp.status_code != 200:
            return {"error": f"NewsAPI sources: HTTP {resp.status_code}", "results": []}

        data = resp.json()
        sources = data.get("sources", [])

        results = []
        for s in sources:
            results.append({
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "description": s.get("description", ""),
                "url": s.get("url", ""),
                "language": s.get("language", ""),
                "country": s.get("country", ""),
                "category": s.get("category", ""),
            })

        return {"total": len(results), "results": results}
