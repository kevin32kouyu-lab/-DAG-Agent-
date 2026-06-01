"""
App Store / Google Play 评分与评论数据工具。

数据源:
  - iTunes Search API: https://itunes.apple.com/search (免费, 无需认证)
  - iTunes RSS: https://itunes.apple.com/rss/customerreviews (免费)
  - Google Play: 公开爬取 (无需认证)

提供的竞品分析数据:
  - App 评分 (rating)、评论数 (review count)
  - 版本更新频率 (release date)
  - 用户评论内容（最近 50 条）
"""

import re
import httpx
from typing import Any
from bs4 import BeautifulSoup
from src.agents.tools.base import ToolBase


class AppStoreTool(ToolBase):
    name = "app_store"
    description = (
        "Query App Store (iTunes) and Google Play for app ratings, reviews count, "
        "version history, and user sentiment. "
        "Use this to compare mobile app competitiveness. "
        "Completely free, no API key required."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "search (find apps by keyword), lookup (get details by app ID), "
                           "reviews (get recent reviews for an app)",
        },
        "query": {"type": "string", "description": "App name keyword (for action=search)"},
        "app_id": {"type": "string", "description": "iTunes app ID (for action=lookup/reviews)"},
        "store": {
            "type": "string",
            "description": "App store to query: 'ios' for Apple App Store, 'android' for Google Play (default 'ios')",
        },
        "country": {"type": "string", "description": "Country code for store (default 'cn')"},
        "limit": {"type": "integer", "description": "Max results (default 5, max 20)"},
    }

    ITUNES_SEARCH = "https://itunes.apple.com/search"
    ITUNES_LOOKUP = "https://itunes.apple.com/lookup"

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "search")
        store = kwargs.get("store", "ios")
        country = kwargs.get("country", "cn")

        try:
            if store == "android":
                return await self._google_play(kwargs)
            else:
                return await self._itunes(kwargs, country)
        except Exception as e:
            return {"error": f"App store query failed: {e}", "results": []}

    async def _itunes(self, kwargs: dict, country: str) -> dict[str, Any]:
        action = kwargs.get("action", "search")
        limit = min(int(kwargs.get("limit", 5)), 20)

        async with httpx.AsyncClient(timeout=15) as client:
            if action == "search":
                query = kwargs.get("query", "")
                if not query:
                    return {"error": "query is required for search", "results": []}
                resp = await client.get(
                    self.ITUNES_SEARCH,
                    params={"term": query, "entity": "software", "country": country, "limit": limit},
                )
                resp.raise_for_status()
                data = resp.json()

                results = []
                for r in data.get("results", []):
                    results.append({
                        "app_id": r.get("trackId"),
                        "name": r.get("trackName", ""),
                        "developer": r.get("artistName", ""),
                        "genre": r.get("primaryGenreName", ""),
                        "rating": r.get("averageUserRating", 0),
                        "rating_count": r.get("userRatingCount", 0),
                        "price": r.get("formattedPrice", "Free"),
                        "version": r.get("version", ""),
                        "release_date": r.get("releaseDate", ""),
                        "current_version_date": r.get("currentVersionReleaseDate", ""),
                        "description": (r.get("description", "") or "")[:500],
                        "seller_url": r.get("sellerUrl", ""),
                        "app_url": r.get("trackViewUrl", ""),
                        "screenshot_urls": (r.get("screenshotUrls", []) or [])[:3],
                    })
                return {
                    "store": "ios",
                    "country": country,
                    "query": query,
                    "total_results": data.get("resultCount", 0),
                    "results": results,
                }

            elif action == "lookup":
                app_id = kwargs.get("app_id", "")
                if not app_id:
                    return {"error": "app_id is required for lookup"}

                resp = await client.get(
                    self.ITUNES_LOOKUP,
                    params={"id": app_id, "country": country},
                )
                resp.raise_for_status()
                data = resp.json()

                results = []
                for r in data.get("results", []):
                    results.append({
                        "app_id": r.get("trackId"),
                        "name": r.get("trackName", ""),
                        "developer": r.get("artistName", ""),
                        "rating": r.get("averageUserRating", 0),
                        "rating_count": r.get("userRatingCount", 0),
                        "price": r.get("formattedPrice", "Free"),
                        "version": r.get("version", ""),
                        "release_date": r.get("releaseDate", ""),
                        "current_version_date": r.get("currentVersionReleaseDate", ""),
                        "language_codes": r.get("languageCodesISO2A", []),
                        "supported_devices": len(r.get("supportedDevices", [])),
                    })
                return {
                    "store": "ios",
                    "app_id": app_id,
                    "results": results,
                }

            elif action == "reviews":
                app_id = kwargs.get("app_id", "")
                if not app_id:
                    return {"error": "app_id is required for reviews"}

                # iTunes RSS customer reviews (free, no auth)
                resp = await client.get(
                    f"https://itunes.apple.com/{country}/rss/customerreviews/id{app_id}/sortBy=mostRecent/json",
                    timeout=15,
                )
                if resp.status_code != 200:
                    return {"error": f"Reviews RSS returned HTTP {resp.status_code}", "results": []}

                data = resp.json()
                entries = data.get("feed", {}).get("entry", [])
                reviews = []
                for entry in entries:
                    # Skip the header entry (app metadata)
                    if entry.get("im:name"):
                        continue
                    reviews.append({
                        "title": entry.get("title", {}).get("label", ""),
                        "author": entry.get("author", {}).get("name", {}).get("label", ""),
                        "rating": entry.get("im:rating", {}).get("label", ""),
                        "content": (entry.get("content", {}).get("label", "") or "")[:1000],
                        "vote_count": entry.get("im:voteCount", {}).get("label", 0),
                    })

                return {
                    "store": "ios",
                    "app_id": app_id,
                    "review_count": len(reviews),
                    "reviews": reviews[:limit],
                }
            else:
                return {"error": f"Unknown action: {action}"}

    async def _google_play(self, kwargs: dict) -> dict[str, Any]:
        """Scrape Google Play Store (free, public pages)."""
        action = kwargs.get("action", "search")
        limit = min(int(kwargs.get("limit", 5)), 20)

        async with httpx.AsyncClient(
            timeout=15,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
        ) as client:
            if action == "search":
                query = kwargs.get("query", "")
                if not query:
                    return {"error": "query is required for search"}

                resp = await client.get(
                    "https://play.google.com/store/search",
                    params={"q": query, "c": "apps", "hl": "zh"},
                )
                if resp.status_code != 200:
                    return {"error": f"Google Play returned HTTP {resp.status_code}", "results": []}

                # Parse the embedded JSON from Play Store page
                soup = BeautifulSoup(resp.text, "html.parser")
                results = []

                # Modern Play Store embeds data in script tags
                for script in soup.find_all("script"):
                    text = script.string or ""
                    if "ds:3" in text or "cluster" in text:
                        # Extract app IDs from the page
                        app_links = []
                        for link in soup.select('a[href*="/store/apps/details"]'):
                            href = link.get("href", "")
                            app_id_match = re.search(r"id=([\w.]+)", href)
                            if app_id_match and app_id_match.group(1) not in app_links:
                                app_links.append(app_id_match.group(1))

                        for i, aid in enumerate(app_links[:limit]):
                            try:
                                detail = await self._play_app_detail(client, aid)
                                if detail:
                                    results.append(detail)
                            except Exception:
                                continue
                        break

                return {
                    "store": "android",
                    "query": query,
                    "total_results": len(results),
                    "results": results,
                }

            elif action == "lookup":
                app_id = kwargs.get("app_id", "")
                if not app_id:
                    return {"error": "app_id is required"}

                detail = await self._play_app_detail(client, app_id)
                return {
                    "store": "android",
                    "app_id": app_id,
                    "results": [detail] if detail else [],
                }
            else:
                return {"error": f"Unknown action: {action}"}

    async def _play_app_detail(self, client: httpx.AsyncClient, app_id: str) -> dict | None:
        """Scrape a single Google Play app detail page."""
        try:
            resp = await client.get(
                f"https://play.google.com/store/apps/details",
                params={"id": app_id, "hl": "zh"},
            )
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, "html.parser")

            # Try to find app metadata in the page
            name_el = soup.select_one("h1")
            name = name_el.get_text(strip=True) if name_el else ""

            # Rating and reviews
            rating_el = soup.select_one('[aria-label*="星级"]') or soup.select_one('[aria-label*="star"]')
            rating_text = rating_el.get("aria-label", "") if rating_el else ""

            # Count from the page
            reviews_el = soup.select_one('[aria-label*="条评价"]') or soup.select_one('[aria-label*="reviews"]')
            reviews_text = reviews_el.get_text(strip=True) if reviews_el else "0"

            # Description
            desc_el = soup.select_one('[data-clamped-content]') or soup.select_one('[jsname="bN97Pc"]')

            return {
                "app_id": app_id,
                "name": name,
                "developer": "",
                "rating": rating_text,
                "rating_info": reviews_text,
                "url": f"https://play.google.com/store/apps/details?id={app_id}",
            }
        except Exception:
            return None
