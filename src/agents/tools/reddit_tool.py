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

    BASE = "https://old.reddit.com"
    UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    HEADERS = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "search")
        limit = min(int(kwargs.get("limit", 15)), 50)

        try:
            if action == "search":
                result = await self._search(kwargs, limit)
            elif action == "hot":
                result = await self._subreddit_posts(kwargs, "hot", limit)
            elif action == "new":
                result = await self._subreddit_posts(kwargs, "new", limit)
            elif action == "top":
                result = await self._subreddit_posts(kwargs, "top", limit)
            else:
                return {"error": f"Unknown action: {action}"}

            # 直接 API 成功就返回
            if result.get("total_results", 0) > 0 or "error" not in result:
                return result

            # 直接 API 失败（如 403），用 Serper site:reddit.com 兜底
            if action == "search":
                return await self._serper_fallback(kwargs, limit)
        except Exception as e:
            if action == "search":
                return await self._serper_fallback(kwargs, limit)
            return {"error": f"Reddit query failed: {e}", "results": []}

        return result

    async def _search(self, kwargs: dict, limit: int) -> dict[str, Any]:
        query = kwargs.get("query", "")
        if not query:
            return {"error": "query is required for search action", "results": []}

        subreddit = kwargs.get("subreddit", "all")
        sort = kwargs.get("sort", "relevance")
        t = kwargs.get("time_range", "all")

        params = {"q": query, "sort": sort, "t": t, "limit": limit}
        async with httpx.AsyncClient(timeout=15, headers=self.HEADERS, http2=True) as client:
            resp = await client.get(
                f"{self.BASE}/r/{subreddit}/search.json",
                params=params,
            )
            if resp.status_code != 200:
                return {"query": query, "error": f"HTTP {resp.status_code}", "results": []}

            data = resp.json()

        return self._parse_posts(data, query=query, subreddit=subreddit)

    async def _subreddit_posts(self, kwargs: dict, listing: str, limit: int) -> dict[str, Any]:
        subreddit = kwargs.get("subreddit", "all")
        t = kwargs.get("time_range", "all")

        params = {"limit": limit}
        if listing == "top":
            params["t"] = t

        async with httpx.AsyncClient(timeout=15, headers=self.HEADERS, http2=True) as client:
            resp = await client.get(
                f"{self.BASE}/r/{subreddit}/{listing}.json",
                params=params,
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

    async def _serper_fallback(self, kwargs: dict, limit: int) -> dict[str, Any]:
        """Reddit 直接 API 被封时，通过 Serper Google 搜索 site:reddit.com 兜底。"""
        query = kwargs.get("query", "")
        try:
            from src.agents.tools.serper_tool import SerperSearchTool
            serper = SerperSearchTool()
            result = await serper.execute(
                query=f"site:reddit.com {query}",
                num=limit,
                gl="us",
                hl="en",
            )
            if "error" not in result:
                results = []
                for r in result.get("results", [])[:limit]:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "subreddit": "",
                        "author": "",
                        "score": 0,
                        "num_comments": 0,
                        "selftext": r.get("snippet", "")[:500],
                        "source": "serper_reddit_fallback",
                    })
                return {
                    "query": query,
                    "source": "serper_reddit_fallback",
                    "total_results": len(results),
                    "results": results,
                    "note": "Fetched via Google (site:reddit.com) — Reddit direct API blocked",
                }
        except Exception:
            pass
        return {"query": query, "error": "Reddit unavailable (API blocked + Serper fallback failed)", "results": []}
