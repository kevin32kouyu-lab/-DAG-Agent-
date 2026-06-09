"""
Serper (Google Search) API tool for web search discovery.

Free tier: 2,500 queries. Provides structured Google search results
without scraping. Used as the primary search discovery layer for
the dimension collectors.

API docs: https://serper.dev/playground
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from src.agents.tools.base import ToolBase

logger = logging.getLogger(__name__)


class SerperSearchTool(ToolBase):
    """Google Search via Serper API — structured, reliable, free tier."""

    name = "serper_search"
    description = (
        "Search the web using Serper (Google Search API) for competitor intelligence. "
        "Returns structured results with titles, URLs, snippets, and positions. "
        "Supports language/region filtering for Chinese (gl=cn) and English (gl=us) results. "
        "Use this as the primary search tool for discovering product pages, pricing, reviews, and market data."
    )
    param_schema = {
        "query": {
            "type": "string",
            "description": "Search query string (e.g. '飞书 定价', 'Notion features 2025')",
        },
        "gl": {
            "type": "string",
            "description": "Country code for search region: 'cn' for China, 'us' for US, 'global' for worldwide (default: 'cn')",
        },
        "hl": {
            "type": "string",
            "description": "Language code: 'zh-cn' for Chinese, 'en' for English (default: 'zh-cn')",
        },
        "num": {
            "type": "integer",
            "description": "Number of results to return (1-20, default 10)",
        },
        "type": {
            "type": "string",
            "description": "Search type: 'search' (default), 'news', 'images', 'videos'",
        },
    }

    BASE = "https://google.serper.dev"

    async def execute(self, **kwargs) -> dict[str, Any]:
        api_key = os.environ.get("SERPER_API_KEY", "")
        if not api_key:
            return {"error": "Serper API key not configured (set SERPER_API_KEY env var)", "results": []}

        query = kwargs.get("query", "")
        if not query:
            return {"error": "query is required", "results": []}

        gl = kwargs.get("gl", "cn")
        hl = kwargs.get("hl", "zh-cn")
        num = min(max(int(kwargs.get("num", 10)), 1), 20)
        search_type = kwargs.get("type", "search")

        # Determine endpoint: /search, /news, /images, /videos
        endpoint_map = {
            "search": "/search",
            "news": "/news",
            "images": "/images",
            "videos": "/videos",
        }
        endpoint = endpoint_map.get(search_type, "/search")

        headers = {
            "X-API-KEY": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "gl": gl,
            "hl": hl,
            "num": num,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.BASE}{endpoint}",
                    headers=headers,
                    json=payload,
                )

                if resp.status_code == 401:
                    return {"error": "Serper API key is invalid", "results": []}
                if resp.status_code == 429:
                    return {"error": "Serper API rate limit exceeded", "results": []}
                if resp.status_code == 402:
                    return {"error": "Serper API quota exhausted (2500 free queries used)", "results": []}
                resp.raise_for_status()

            data = resp.json()

            # Map results based on search type
            if search_type == "news":
                results = self._map_news(data)
            elif search_type == "images":
                results = self._map_images(data)
            else:
                results = self._map_organic(data)

            return {
                "query": query,
                "gl": gl,
                "hl": hl,
                "search_type": search_type,
                "total_results": len(results),
                "results": results,
                "answerBox": data.get("answerBox"),
                "knowledgeGraph": data.get("knowledgeGraph"),
            }

        except httpx.TimeoutException:
            logger.warning("Serper search timed out for query: %s", query)
            return {"error": "Serper search timed out", "results": []}
        except Exception as e:
            logger.warning("Serper search failed: %s", e)
            return {"error": f"Serper search failed: {type(e).__name__}: {e}", "results": []}

    def _map_organic(self, data: dict) -> list[dict]:
        """Map organic search results to standardized format."""
        results = []
        for item in data.get("organic", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", "")[:500],
                "position": item.get("position", 0),
                "sitelinks": [
                    {"title": sl.get("title", ""), "url": sl.get("link", "")}
                    for sl in item.get("sitelinks", [])
                ],
            })
        return results

    def _map_news(self, data: dict) -> list[dict]:
        """Map news search results to standardized format."""
        results = []
        for item in data.get("news", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", "")[:500],
                "source": item.get("source", ""),
                "date": item.get("date", ""),
                "imageUrl": item.get("imageUrl", ""),
            })
        return results

    def _map_images(self, data: dict) -> list[dict]:
        """Map image search results to standardized format."""
        results = []
        for item in data.get("images", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("imageUrl", ""),
                "source": item.get("source", ""),
                "thumbnail": item.get("thumbnailUrl", ""),
            })
        return results
