import httpx
from typing import Any
from src.agents.tools.base import ToolBase


class RedditTool(ToolBase):
    name = "reddit"
    description = (
        "Search Reddit for product discussions, user sentiment, and community feedback. "
        "Uses the free public .json endpoint — no API key or OAuth required. "
        "Works for both English subreddits (r/SaaS, r/programming) and Chinese communities."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "search (search Reddit for keywords), hot (hot posts in a subreddit), "
                           "new (newest posts), top (top posts by time range)",
        },
        "subreddit": {"type": "string", "description": "Subreddit name, e.g. 'SaaS', 'programming', 'ChinaTech' (default 'all')"},
        "query": {"type": "string", "description": "Search query (for action=search)"},
        "sort": {"type": "string", "description": "Sort: relevance, hot, top, new, comments (default relevance)"},
        "time_range": {"type": "string", "description": "Time range: hour, day, week, month, year, all (default all)"},
        "limit": {"type": "integer", "description": "Max posts (default 15, max 50)"},
    }

    BASE = "https://www.reddit.com"
    UA = "CompAgent/1.0 (competitive analysis tool)"

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "search")
        limit = min(int(kwargs.get("limit", 15)), 50)

        try:
            if action == "search":
                return await self._search(kwargs, limit)
            elif action == "hot":
                return await self._subreddit_posts(kwargs, "hot", limit)
            elif action == "new":
                return await self._subreddit_posts(kwargs, "new", limit)
            elif action == "top":
                return await self._subreddit_posts(kwargs, "top", limit)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": f"Reddit query failed: {e}", "results": []}

    async def _search(self, kwargs: dict, limit: int) -> dict[str, Any]:
        query = kwargs.get("query", "")
        if not query:
            return {"error": "query is required for search action", "results": []}

        subreddit = kwargs.get("subreddit", "all")
        sort = kwargs.get("sort", "relevance")
        t = kwargs.get("time_range", "all")

        params = {"q": query, "sort": sort, "t": t, "limit": limit, "raw_json": 1}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/r/{subreddit}/search.json",
                params=params,
                headers={"User-Agent": self.UA},
            )
            if resp.status_code != 200:
                return {"query": query, "error": f"HTTP {resp.status_code}", "results": []}

            data = resp.json()

        return self._parse_posts(data, query=query, subreddit=subreddit)

    async def _subreddit_posts(self, kwargs: dict, listing: str, limit: int) -> dict[str, Any]:
        subreddit = kwargs.get("subreddit", "all")
        t = kwargs.get("time_range", "all")

        params = {"limit": limit, "raw_json": 1}
        if listing == "top":
            params["t"] = t

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/r/{subreddit}/{listing}.json",
                params=params,
                headers={"User-Agent": self.UA},
            )
            if resp.status_code != 200:
                return {"action": listing, "error": f"HTTP {resp.status_code}", "results": []}

            data = resp.json()

        return self._parse_posts(data, subreddit=subreddit)

    def _parse_posts(self, data: dict, **meta) -> dict[str, Any]:
        results = []
        children = data.get("data", {}).get("children", [])
        for child in children:
            p = child.get("data", {})
            if not p:
                continue

            # Skip stickied posts unless they have useful content
            results.append({
                "title": p.get("title", ""),
                "subreddit": p.get("subreddit_name_prefixed", ""),
                "author": p.get("author", ""),
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "upvote_ratio": p.get("upvote_ratio", 0),
                "url": f"https://www.reddit.com{p.get('permalink', '')}",
                "external_url": p.get("url", ""),
                "selftext": (p.get("selftext", "") or "")[:500],
                "created_utc": p.get("created_utc", 0),
                "domain": p.get("domain", ""),
                "flair": p.get("link_flair_text", ""),
            })

        return {
            **meta,
            "total_results": len(results),
            "results": results,
        }
