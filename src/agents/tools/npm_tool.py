"""
npm Registry API 工具 — 查询 npm 包的下载量、版本、依赖等信息。

完全免费，无需 API key。
API 文档: https://github.com/npm/registry/blob/main/docs/REGISTRY-API.md
"""

import httpx
from typing import Any
from src.agents.tools.base import ToolBase


class NpmTool(ToolBase):
    name = "npm"
    description = (
        "Query npm Registry for package stats, download counts, versions, and dependencies. "
        "Use to assess open-source project popularity, release velocity, and ecosystem health. "
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
            "description": "Download stats period: 'last-day', 'last-week', 'last-month' (default 'last-month')",
        },
    }

    REGISTRY = "https://registry.npmjs.org"
    API = "https://api.npmjs.org"

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
                    kwargs.get("period", "last-month"),
                )
            elif action == "versions":
                return await self._versions(kwargs.get("package", ""), limit)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": f"npm query failed: {type(e).__name__}: {e}", "results": []}

    async def _package_info(self, package: str) -> dict[str, Any]:
        if not package:
            return {"error": "package is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.REGISTRY}/{package}")
            if resp.status_code == 404:
                return {"error": f"Package '{package}' not found on npm"}
            resp.raise_for_status()
            data = resp.json()

        latest_version = data.get("dist-tags", {}).get("latest", "")
        latest = data.get("versions", {}).get(latest_version, {})
        time_data = data.get("time", {})

        # Extract maintainers
        maintainers = [
            m.get("name", "") for m in data.get("maintainers", [])
        ]

        # Extract keywords
        keywords = latest.get("keywords", data.get("keywords", []))

        return {
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "latest_version": latest_version,
            "license": latest.get("license", ""),
            "homepage": latest.get("homepage", ""),
            "repository": (latest.get("repository") or {}).get("url", ""),
            "keywords": keywords[:20],
            "maintainers": maintainers[:10],
            "created_at": time_data.get("created", ""),
            "modified_at": time_data.get("modified", ""),
            "latest_published": time_data.get(latest_version, ""),
            "dependencies_count": len(latest.get("dependencies", {})),
            "dev_dependencies_count": len(latest.get("devDependencies", {})),
        }

    async def _search(self, query: str, limit: int) -> dict[str, Any]:
        if not query:
            return {"error": "query is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.REGISTRY}-/v1/search",
                params={"text": query, "size": limit},
            )
            resp.raise_for_status()
            data = resp.json()

        results = []
        for obj in data.get("objects", []):
            pkg = obj.get("package", {})
            score = obj.get("score", {})
            detail = score.get("detail", {})
            results.append({
                "name": pkg.get("name", ""),
                "version": pkg.get("version", ""),
                "description": pkg.get("description", ""),
                "keywords": (pkg.get("keywords") or [])[:5],
                "publisher": (pkg.get("publisher") or {}).get("username", ""),
                "date": pkg.get("date", ""),
                "score_quality": round(detail.get("quality", 0), 3),
                "score_popularity": round(detail.get("popularity", 0), 3),
                "score_maintenance": round(detail.get("maintenance", 0), 3),
            })

        return {"query": query, "total": data.get("total", 0), "results": results}

    async def _downloads(self, package: str, period: str) -> dict[str, Any]:
        if not package:
            return {"error": "package is required"}

        valid_periods = ("last-day", "last-week", "last-month")
        if period not in valid_periods:
            period = "last-month"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.API}/downloads/point/{period}/{package}")
            if resp.status_code == 404:
                return {"error": f"Package '{package}' not found"}
            resp.raise_for_status()
            data = resp.json()

        return {
            "package": data.get("package", ""),
            "downloads": data.get("downloads", 0),
            "period": period,
            "start": data.get("start", ""),
            "end": data.get("end", ""),
        }

    async def _versions(self, package: str, limit: int) -> dict[str, Any]:
        if not package:
            return {"error": "package is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.REGISTRY}/{package}")
            if resp.status_code == 404:
                return {"error": f"Package '{package}' not found"}
            resp.raise_for_status()
            data = resp.json()

        time_data = data.get("time", {})
        versions_data = data.get("versions", {})

        # Build version list sorted by publish date (newest first)
        version_list = []
        for ver, published in sorted(time_data.items(), key=lambda x: x[1], reverse=True):
            if ver in ("created", "modified"):
                continue
            ver_info = versions_data.get(ver, {})
            version_list.append({
                "version": ver,
                "published_at": published,
                "node_version": ver_info.get("engines", {}).get("node", ""),
                "deprecated": ver_info.get("deprecated", False),
            })
            if len(version_list) >= limit:
                break

        return {
            "package": data.get("name", ""),
            "total_versions": len(versions_data),
            "versions": version_list,
        }
