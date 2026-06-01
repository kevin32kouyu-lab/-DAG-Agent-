"""
GitHub API tool for competitive analysis.
- Unauthenticated: 60 req/h per IP — enough for periodic analysis tasks.
- With a free Personal Access Token: 5,000 req/h.
  Set env var GITHUB_TOKEN to use authenticated access.
"""

import os
import httpx
from typing import Any
from src.agents.tools.base import ToolBase


class GitHubTool(ToolBase):
    name = "github"
    description = (
        "Query GitHub for repository stats, releases, and contributor activity. "
        "Use to assess open-source project health: stars (popularity), release frequency (velocity), "
        "open issues (maintenance), contributor count (community). "
        "Free tier: 60 req/h; set GITHUB_TOKEN env var for 5,000 req/h."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "repo (get repo stats), search (find repos), releases (latest releases), "
                           "contributors (top contributors)",
        },
        "owner": {"type": "string", "description": "Repo owner (for action=repo/releases/contributors)"},
        "repo": {"type": "string", "description": "Repo name (for action=repo/releases/contributors)"},
        "query": {"type": "string", "description": "Search query (for action=search)"},
        "limit": {"type": "integer", "description": "Max results (default 10, max 30)"},
    }

    BASE = "https://api.github.com"

    def _headers(self) -> dict:
        token = os.environ.get("GITHUB_TOKEN", "")
        h = {"Accept": "application/vnd.github+json", "User-Agent": "CompAgent/1.0"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "repo")
        limit = min(int(kwargs.get("limit", 10)), 30)

        try:
            if action == "repo":
                return await self._repo_stats(kwargs.get("owner", ""), kwargs.get("repo", ""))
            elif action == "search":
                return await self._search_repos(kwargs.get("query", ""), limit)
            elif action == "releases":
                return await self._releases(kwargs.get("owner", ""), kwargs.get("repo", ""), limit)
            elif action == "contributors":
                return await self._contributors(kwargs.get("owner", ""), kwargs.get("repo", ""), limit)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            return {"error": f"GitHub query failed: {e}", "results": []}

    async def _repo_stats(self, owner: str, repo: str) -> dict[str, Any]:
        if not owner or not repo:
            return {"error": "owner and repo are required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/repos/{owner}/{repo}", headers=self._headers()
            )
            if resp.status_code == 404:
                return {"error": f"Repo {owner}/{repo} not found"}
            if resp.status_code == 403:
                return {"error": "Rate limit exceeded. Set GITHUB_TOKEN env var for 5,000 req/h."}
            resp.raise_for_status()
            r = resp.json()

        return {
            "full_name": r.get("full_name", ""),
            "description": r.get("description", ""),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "watchers": r.get("watchers_count", 0),
            "language": r.get("language", ""),
            "topics": r.get("topics", []),
            "license": (r.get("license") or {}).get("spdx_id", ""),
            "created_at": r.get("created_at", ""),
            "updated_at": r.get("updated_at", ""),
            "pushed_at": r.get("pushed_at", ""),
            "archived": r.get("archived", False),
            "homepage": r.get("homepage", ""),
        }

    async def _search_repos(self, query: str, limit: int) -> dict[str, Any]:
        if not query:
            return {"error": "query is required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/search/repositories",
                params={"q": query, "per_page": limit, "sort": "stars", "order": "desc"},
                headers=self._headers(),
            )
            if resp.status_code == 403:
                return {"error": "Rate limit exceeded. Set GITHUB_TOKEN env var for 5,000 req/h."}
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data.get("items", []):
            results.append({
                "full_name": item.get("full_name", ""),
                "description": item.get("description", ""),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language", ""),
                "topics": item.get("topics", []),
                "url": item.get("html_url", ""),
                "updated_at": item.get("updated_at", ""),
            })

        return {"query": query, "total_count": data.get("total_count", 0), "results": results}

    async def _releases(self, owner: str, repo: str, limit: int) -> dict[str, Any]:
        if not owner or not repo:
            return {"error": "owner and repo are required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/repos/{owner}/{repo}/releases",
                params={"per_page": limit},
                headers=self._headers(),
            )
            if resp.status_code == 404:
                return {"error": f"Repo {owner}/{repo} not found"}
            if resp.status_code == 403:
                return {"error": "Rate limit exceeded. Set GITHUB_TOKEN env var for 5,000 req/h."}
            resp.raise_for_status()
            releases = resp.json()

        results = []
        for rel in releases:
            results.append({
                "tag_name": rel.get("tag_name", ""),
                "name": rel.get("name", ""),
                "published_at": rel.get("published_at", ""),
                "prerelease": rel.get("prerelease", False),
                "body": (rel.get("body") or "")[:500],
            })

        return {"owner": owner, "repo": repo, "releases": results}

    async def _contributors(self, owner: str, repo: str, limit: int) -> dict[str, Any]:
        if not owner or not repo:
            return {"error": "owner and repo are required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/repos/{owner}/{repo}/contributors",
                params={"per_page": limit},
                headers=self._headers(),
            )
            if resp.status_code == 204:
                return {"owner": owner, "repo": repo, "contributors": []}
            if resp.status_code == 403:
                return {"error": "Rate limit exceeded. Set GITHUB_TOKEN env var for 5,000 req/h."}
            resp.raise_for_status()
            contributors = resp.json()

        results = []
        for c in contributors:
            results.append({
                "login": c.get("login", ""),
                "contributions": c.get("contributions", 0),
                "url": c.get("html_url", ""),
            })

        return {"owner": owner, "repo": repo, "contributors": results}
