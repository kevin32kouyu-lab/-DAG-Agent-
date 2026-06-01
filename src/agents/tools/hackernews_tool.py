import httpx
from typing import Any
from src.agents.tools.base import ToolBase


class HackerNewsTool(ToolBase):
    name = "hackernews"
    description = (
        "Search Hacker News for product discussions, launches, and developer mindshare. "
        "Use to gauge developer community interest, find Show HN launches, and track tech product mentions. "
        "Completely free, no API key required."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "search (find product mentions by keyword), top (current top stories), "
                           "item (get a specific item by ID), user (get user profile)",
        },
        "query": {"type": "string", "description": "Search query (for action=search)"},
        "limit": {"type": "integer", "description": "Max results (default 15, max 30)"},
    }

    BASE_FIREBASE = "https://hacker-news.firebaseio.com/v0"
    BASE_SEARCH = "https://hn.algolia.com/api/v1"

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "search")
        query = kwargs.get("query", "")
        limit = min(int(kwargs.get("limit", 15)), 30)

        try:
            if action == "search":
                return await self._search(query, limit)
            elif action == "top":
                return await self._top_stories(limit)
            elif action == "item":
                item_id = kwargs.get("query", "")
                return await self._get_item(item_id)
            elif action == "user":
                return await self._get_user(query)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": f"HackerNews query failed: {e}", "results": []}

    async def _search(self, query: str, limit: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE_SEARCH}/search",
                params={"query": query, "tags": "story", "hitsPerPage": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for hit in data.get("hits", []):
            results.append({
                "title": hit.get("title", ""),
                "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "author": hit.get("author", ""),
                "created_at": hit.get("created_at", ""),
                "object_id": hit.get("objectID", ""),
            })

        return {
            "query": query,
            "total_hits": data.get("nbHits", 0),
            "results": results,
        }

    async def _top_stories(self, limit: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.BASE_FIREBASE}/topstories.json")
            resp.raise_for_status()
            ids = resp.json()[:limit]

        stories = []
        async with httpx.AsyncClient(timeout=30) as client:
            for sid in ids:
                try:
                    r = await client.get(f"{self.BASE_FIREBASE}/item/{sid}.json")
                    r.raise_for_status()
                    item = r.json()
                    if item:
                        stories.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                            "score": item.get("score", 0),
                            "descendants": item.get("descendants", 0),
                            "by": item.get("by", ""),
                            "time": item.get("time", 0),
                        })
                except Exception:
                    continue

        return {"action": "top", "results": stories}

    async def _get_item(self, item_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.BASE_FIREBASE}/item/{item_id}.json")
            resp.raise_for_status()
            item = resp.json()
        return {"item": item} if item else {"error": "Item not found"}

    async def _get_user(self, user_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.BASE_FIREBASE}/user/{user_id}.json")
            resp.raise_for_status()
            user = resp.json()
        return {"user": user} if user else {"error": "User not found"}
