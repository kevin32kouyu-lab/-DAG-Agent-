"""
PyPI Stats API 工具 — 查询 Python 包的下载量、版本、元数据。

完全免费，无需 API key。
数据源:
  - PyPI JSON API: https://warehouse.pypa.io/api-reference/json.html
  - PyPI Stats: https://pypistats.org/api/
"""

import httpx
from typing import Any
from src.agents.tools.base import ToolBase


class PyPITool(ToolBase):
    name = "pypi"
    description = (
        "Query PyPI for Python package stats, download counts, versions, and metadata. "
        "Use to assess Python open-source project popularity, release cadence, and ecosystem adoption. "
        "Completely free, no API key required."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "info (package details), search (find packages), downloads (download stats), "
                           "versions (release history)",
        },
        "package": {"type": "string", "description": "Package name (for action=info/downloads/versions)"},
        "query": {"type": "string", "description": "Search query (for action=search)"},
        "limit": {"type": "integer", "description": "Max results (default 10, max 30)"},
        "period": {
            "type": "string",
            "description": "Download stats period: 'day', 'week', 'month' (default 'month')",
        },
    }

    PYPI = "https://pypi.org"
    STATS = "https://pypistats.org"

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "info")
        limit = min(int(kwargs.get("limit", 10)), 30)

        try:
            if action == "info":
                return await self._package_info(kwargs.get("package", ""))
            elif action == "search":
                return await self._search(kwargs.get("query", ""), limit)
            elif action == "downloads":
                return await self._downloads(
                    kwargs.get("package", ""),
                    kwargs.get("period", "month"),
                )
            elif action == "versions":
                return await self._versions(kwargs.get("package", ""), limit)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": f"PyPI query failed: {e}", "results": []}

    async def _package_info(self, package: str) -> dict[str, Any]:
        if not package:
            return {"error": "package is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.PYPI}/pypi/{package}/json")
            if resp.status_code == 404:
                return {"error": f"Package '{package}' not found on PyPI"}
            resp.raise_for_status()
            data = resp.json()

        info = data.get("info", {})
        releases = data.get("releases", {})

        # Get latest release version
        version = info.get("version", "")

        return {
            "name": info.get("name", ""),
            "version": version,
            "summary": info.get("summary", ""),
            "description": (info.get("description") or "")[:1000],
            "author": info.get("author", ""),
            "author_email": info.get("author_email", ""),
            "license": info.get("license", ""),
            "homepage": info.get("home_page", ""),
            "project_urls": info.get("project_urls", {}),
            "requires_python": info.get("requires_python", ""),
            "keywords": info.get("keywords", ""),
            "classifiers": info.get("classifiers", [])[:10],
            "total_versions": len(releases),
            "requires_dist_count": len(info.get("requires_dist") or []),
            "created_at": data.get("urls", [{}])[0].get("upload_time", "") if data.get("urls") else "",
        }

    async def _search(self, query: str, limit: int) -> dict[str, Any]:
        """Search PyPI using the warehouse XMLRPC or fallback to simple HTML search."""
        if not query:
            return {"error": "query is required"}

        # PyPI doesn't have a REST search API; use the legacy JSON endpoint
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.PYPI}/search/",
                params={"q": query},
                headers={"Accept": "text/html"},
                follow_redirects=True,
            )
            # PyPI search redirects to results page; parse what we can
            # Fallback: use the simple API endpoint
            resp2 = await client.get(
                "https://pypi.org/simple/",
                follow_redirects=True,
            )

        # Since PyPI doesn't have a proper search API, use a different approach:
        # Query the PyPI JSON API for exact/close matches
        results = []
        # Try common patterns: exact match, then variations
        candidates = [query, query.lower(), query.replace("-", "_"), query.replace("_", "-")]
        seen = set()
        async with httpx.AsyncClient(timeout=15) as client:
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    resp = await client.get(f"{self.PYPI}/pypi/{candidate}/json")
                    if resp.status_code == 200:
                        info = resp.json().get("info", {})
                        results.append({
                            "name": info.get("name", ""),
                            "version": info.get("version", ""),
                            "summary": info.get("summary", ""),
                            "author": info.get("author", ""),
                            "requires_python": info.get("requires_python", ""),
                        })
                except Exception:
                    continue

        if not results:
            return {
                "query": query,
                "total": 0,
                "results": [],
                "note": "PyPI has no search API. Try exact package name with action=info instead.",
            }

        return {"query": query, "total": len(results), "results": results[:limit]}

    async def _downloads(self, package: str, period: str) -> dict[str, Any]:
        if not package:
            return {"error": "package is required"}

        valid_periods = {"day": "last_day", "week": "last_week", "month": "last_month"}
        stats_period = valid_periods.get(period, "last_month")

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.STATS}/api/packages/{package}/recent")
            if resp.status_code == 404:
                return {"error": f"Package '{package}' not found in PyPI Stats"}
            if resp.status_code == 429:
                return {"error": f"PyPI Stats rate limited. Try again later."}
            resp.raise_for_status()
            data = resp.json()

        stats = data.get("data", {})

        return {
            "package": package,
            "downloads_last_day": stats.get("last_day", 0),
            "downloads_last_week": stats.get("last_week", 0),
            "downloads_last_month": stats.get("last_month", 0),
        }

    async def _versions(self, package: str, limit: int) -> dict[str, Any]:
        if not package:
            return {"error": "package is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.PYPI}/pypi/{package}/json")
            if resp.status_code == 404:
                return {"error": f"Package '{package}' not found"}
            resp.raise_for_status()
            data = resp.json()

        releases = data.get("releases", {})

        # Sort versions by upload time (newest first)
        version_list = []
        for ver, files in releases.items():
            upload_time = files[0].get("upload_time", "") if files else ""
            version_list.append({
                "version": ver,
                "published_at": upload_time,
                "files_count": len(files),
                "yanked": any(f.get("yanked", False) for f in files),
            })

        # Sort by published_at descending
        version_list.sort(key=lambda v: v["published_at"], reverse=True)

        return {
            "package": data.get("info", {}).get("name", ""),
            "total_versions": len(releases),
            "versions": version_list[:limit],
        }
