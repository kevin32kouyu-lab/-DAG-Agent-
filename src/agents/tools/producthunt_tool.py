"""
ProductHunt 产品数据工具。

数据获取方式 (按优先级):
  1. ProductHunt GraphQL API (v2) — 免费申请
     设置 PRODUCTHUNT_API_KEY + PRODUCTHUNT_API_SECRET 通过 OAuth 自动获取 token
     或直接设置 PRODUCTHUNT_DEVELOPER_TOKEN (永不过期的个人 token)
  2. ProductHunt RSS Feed — 免费, 无需认证, 但数据量有限
  3. 公开页面爬取 — 免费, 无需认证

生产环境:
  - OAuth client_credentials token 有效期 2 小时, 自动缓存刷新
  - API Key/Secret 存于 .env, 不会暴露在代码或日志中
"""

import os
import time
import httpx
from typing import Any
from bs4 import BeautifulSoup
from src.agents.tools.base import ToolBase

# 模块级 token 缓存 — 到期自动刷新
_cached_token: str | None = None
_cached_token_expires_at: float = 0


class ProductHuntTool(ToolBase):
    name = "producthunt"
    description = (
        "Query ProductHunt for product launches, community upvotes, and user discussions. "
        "Provides launch heat metrics (upvotes, comments), product tagline, and topic classification. "
        "Set PRODUCTHUNT_API_KEY + PRODUCTHUNT_API_SECRET env vars for full API access (free), "
        "or use without token for limited RSS/scraped data. "
        "Best for: measuring early adopter traction and community validation."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "search (find products by name/keyword), trending (top posts this week), "
                           "product (get single product by slug)",
        },
        "query": {"type": "string", "description": "Product name or keyword (for action=search)"},
        "slug": {"type": "string", "description": "ProductHunt product slug, e.g. 'notion' (for action=product)"},
        "limit": {"type": "integer", "description": "Max results (default 5, max 10)"},
    }

    PH_GRAPHQL = "https://api.producthunt.com/v2/api/graphql"
    PH_TOKEN_URL = "https://api.producthunt.com/v2/oauth/token"
    PH_RSS = "https://www.producthunt.com/feed"

    async def execute(self, **kwargs) -> dict[str, Any]:
        token = await self._resolve_token()

        if token:
            try:
                result = await self._graphql_api(token, kwargs)
            except Exception:
                result = None  # Fall through to scraping on API error
            # GraphQL 返回 errors（如 schema 变更）时也走爬虫兜底
            if result and "error" not in result:
                return result

        return await self._scrape(kwargs)

    async def _resolve_token(self) -> str | None:
        """Resolve ProductHunt API token with caching.

        Priority:
        1. PRODUCTHUNT_DEVELOPER_TOKEN — 长生命周期, 直接使用
        2. PRODUCTHUNT_API_KEY + PRODUCTHUNT_API_SECRET — OAuth client_credentials 交换
        """
        global _cached_token, _cached_token_expires_at

        # Priority 1: long-lived developer token
        dev_token = os.environ.get("PRODUCTHUNT_DEVELOPER_TOKEN", "")
        if dev_token:
            return dev_token

        # Priority 2: OAuth client_credentials exchange with caching
        api_key = os.environ.get("PRODUCTHUNT_API_KEY", "")
        api_secret = os.environ.get("PRODUCTHUNT_API_SECRET", "")

        if not api_key or not api_secret:
            return None

        # Return cached token if still valid (>60s buffer)
        if _cached_token and time.time() < _cached_token_expires_at - 60:
            return _cached_token

        # Exchange for new token
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    self.PH_TOKEN_URL,
                    json={
                        "client_id": api_key,
                        "client_secret": api_secret,
                        "grant_type": "client_credentials",
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return None

                data = resp.json()
                _cached_token = data.get("access_token", "")
                expires_in = data.get("expires_in", 7200)
                _cached_token_expires_at = time.time() + expires_in
                return _cached_token

        except Exception:
            # If exchange fails, try cached token anyway
            return _cached_token if _cached_token else None

    async def _graphql_api(self, token: str, kwargs: dict) -> dict[str, Any]:
        """Use ProductHunt v2 GraphQL API (requires Developer Token)."""
        action = kwargs.get("action", "search")
        limit = min(int(kwargs.get("limit", 5)), 10)

        if action == "search":
            query = kwargs.get("query", "")
            gql = """
            query($query: String!, $first: Int!) {
              posts(search: $query, first: $first) {
                edges {
                  node {
                    id name tagline description url website
                    votesCount commentsCount
                    createdAt featuredAt
                    topics { edges { node { name } } }
                    thumbnail { url }
                    reviewsRating
                  }
                }
              }
            }
            """
            variables = {"query": query, "first": limit}
        elif action == "trending":
            gql = """
            query($first: Int!) {
              posts(order: RANKING, first: $first) {
                edges {
                  node {
                    id name tagline description url
                    votesCount commentsCount
                    createdAt
                    topics { edges { node { name } } }
                    thumbnail { url }
                  }
                }
              }
            }
            """
            variables = {"first": limit}
        elif action == "product":
            slug = kwargs.get("slug", "")
            gql = """
            query($slug: String!) {
              post(slug: $slug) {
                id name tagline description url website
                votesCount commentsCount
                createdAt featuredAt
                topics { edges { node { name } } }
                thumbnail { url }
                reviewsRating
                reviews(first: 10) { edges { node { body rating createdAt } } }
                makers { id name headline }
              }
            }
            """
            variables = {"slug": slug}
        else:
            return {"error": f"Unknown action: {action}"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                self.PH_GRAPHQL,
                json={"query": gql, "variables": variables},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code != 200:
                return {"error": f"ProductHunt API returned HTTP {resp.status_code}", "results": []}
            data = resp.json()

        if "errors" in data:
            return {"error": f"GraphQL error: {data['errors']}", "results": []}

        return {"source": "producthunt_api", **self._parse_graphql_response(data, action)}

    def _parse_graphql_response(self, data: dict, action: str) -> dict:
        if action == "product":
            post = data.get("data", {}).get("post", {})
            if not post:
                return {"results": []}
            return {"results": [self._format_post(post)]}

        posts = data.get("data", {}).get("posts", {})
        results = []
        for edge in posts.get("edges", []):
            results.append(self._format_post(edge.get("node", {})))
        return {"total_results": len(results), "results": results}

    def _format_post(self, node: dict) -> dict:
        topics = [
            e.get("node", {}).get("name", "")
            for e in node.get("topics", {}).get("edges", [])
        ]
        return {
            "id": node.get("id", ""),
            "name": node.get("name", ""),
            "tagline": node.get("tagline", ""),
            "description": (node.get("description", "") or "")[:500],
            "url": node.get("url", ""),
            "website": node.get("website", ""),
            "votes": node.get("votesCount", 0),
            "comments": node.get("commentsCount", 0),
            "rating": node.get("reviewsRating", 0),
            "topics": topics,
            "created_at": node.get("createdAt", ""),
            "thumbnail": (node.get("thumbnail", {}) or {}).get("url", ""),
        }

    async def _scrape(self, kwargs: dict) -> dict[str, Any]:
        """Fallback: scrape ProductHunt public pages and RSS feed."""
        action = kwargs.get("action", "search")
        limit = min(int(kwargs.get("limit", 5)), 10)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }

        async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
            if action == "search":
                query = kwargs.get("query", "")
                # ProductHunt has a search redirect: /search?q=...

                # First try RSS feed
                try:
                    rss_resp = await client.get(self.PH_RSS)
                    if rss_resp.status_code == 200:
                        soup = BeautifulSoup(rss_resp.text, "xml")
                        items = soup.find_all("item")
                        results = []
                        for item in items:
                            title = (item.find("title") or {}).text if hasattr(item, "find") else ""
                            link = (item.find("link") or {}).text if hasattr(item, "find") else ""
                            desc = (item.find("description") or {}).text if hasattr(item, "find") else ""
                            pub_date = (item.find("pubDate") or {}).text if hasattr(item, "find") else ""

                            if query and query.lower() not in title.lower() and query.lower() not in desc.lower():
                                continue
                            results.append({
                                "name": title,
                                "url": link,
                                "description": desc[:500] if desc else "",
                                "date": pub_date,
                            })
                            if len(results) >= limit:
                                break
                        if results:
                            return {
                                "source": "producthunt_rss",
                                "query": query,
                                "total_results": len(results),
                                "results": results,
                                "note": "Limited data from RSS — set PRODUCTHUNT_DEVELOPER_TOKEN for full data (votes, comments, etc.)",
                            }
                except Exception:
                    pass

                # RSS didn't find it — try scraping search page
                try:
                    resp = await client.get(
                        f"https://www.producthunt.com/search",
                        params={"q": query},
                    )
                    soup = BeautifulSoup(resp.text, "html.parser")
                    results = []

                    # Parse product cards
                    for card in soup.select('[data-test="post-item"], .styles_item__')[:limit]:
                        name_el = card.select_one("h3, h2, [class*='name']")
                        tagline_el = card.select_one("[class*='tagline'], p")
                        link_el = card.select_one("a[href*='/posts/']")

                        if name_el:
                            results.append({
                                "name": name_el.get_text(strip=True),
                                "tagline": tagline_el.get_text(strip=True) if tagline_el else "",
                                "url": f"https://www.producthunt.com{link_el.get('href', '')}" if link_el else "",
                            })

                    return {
                        "source": "producthunt_scraped",
                        "query": query,
                        "total_results": len(results),
                        "results": results,
                        "note": "Scraped data — set PRODUCTHUNT_DEVELOPER_TOKEN for full API data",
                    }
                except Exception as e:
                    return {"source": "producthunt_scraped", "query": query, "error": str(e), "results": []}

            elif action == "trending":
                try:
                    resp = await client.get("https://www.producthunt.com/")
                    soup = BeautifulSoup(resp.text, "html.parser")
                    results = []

                    for card in soup.select('[data-test="post-item"]')[:limit]:
                        name_el = card.select_one("[class*='name'], h3")
                        tagline_el = card.select_one("[class*='tagline'], p")
                        if name_el:
                            results.append({
                                "name": name_el.get_text(strip=True),
                                "tagline": tagline_el.get_text(strip=True) if tagline_el else "",
                            })

                    return {
                        "source": "producthunt_scraped",
                        "total_results": len(results),
                        "results": results,
                        "note": "Scraped — set PRODUCTHUNT_DEVELOPER_TOKEN for full API data",
                    }
                except Exception as e:
                    return {"error": str(e), "results": []}

            elif action == "product":
                slug = kwargs.get("slug", "")
                if not slug:
                    return {"error": "slug is required for action=product"}

                try:
                    resp = await client.get(f"https://www.producthunt.com/posts/{slug}")
                    soup = BeautifulSoup(resp.text, "html.parser")

                    name = ""
                    tagline = ""
                    description = ""

                    title = soup.select_one("title")
                    if title:
                        title_text = title.get_text(strip=True)
                        parts = title_text.split(":")
                        name = parts[0].strip() if parts else title_text

                    meta_desc = soup.select_one('meta[name="description"]')
                    if meta_desc:
                        description = meta_desc.get("content", "")

                    return {
                        "source": "producthunt_scraped",
                        "results": [{
                            "name": name,
                            "slug": slug,
                            "description": description[:500],
                            "url": f"https://www.producthunt.com/posts/{slug}",
                        }],
                        "note": "Scraped — set PRODUCTHUNT_DEVELOPER_TOKEN for full data",
                    }
                except Exception as e:
                    return {"error": str(e), "results": []}
            else:
                return {"error": f"Unknown action: {action}"}
