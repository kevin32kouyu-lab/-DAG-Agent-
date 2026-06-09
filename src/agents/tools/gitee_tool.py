"""
Gitee API 工具 — 查询国内开源仓库信息。

免费，Token 认证。
API 文档: https://gitee.com/api/v5/doc
"""

import os
import httpx
import logging
from typing import Any
from src.agents.tools.base import ToolBase

logger = logging.getLogger(__name__)


def _safe_get(obj: Any, key: str, sub_key: str = "") -> Any:
    """Safely get a nested value from a dict, handling cases where the value might be a string."""
    val = obj.get(key)
    if val is None:
        return ""
    if isinstance(val, dict) and sub_key:
        return val.get(sub_key, "")
    if isinstance(val, str):
        return val
    return str(val) if val else ""


class GiteeTool(ToolBase):
    name = "gitee"
    description = (
        "Query Gitee (China's largest code hosting platform) for repository stats, "
        "commits, issues, and releases. Use to assess Chinese open-source project health. "
        "Free with API token. Requires GITEE_TOKEN env var."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "repo (get repo details), commits (recent commits), "
                           "issues (open issues), releases (release history), "
                           "user_repos (list user's repos)",
        },
        "owner": {"type": "string", "description": "Repo owner (for action=repo/commits/issues/releases)"},
        "repo": {"type": "string", "description": "Repo name (for action=repo/commits/issues/releases)"},
        "limit": {"type": "integer", "description": "Max results (default 10, max 30)"},
    }

    BASE = "https://gitee.com/api/v5"

    def _params(self) -> dict:
        token = os.environ.get("GITEE_TOKEN", "")
        p = {}
        if token:
            p["access_token"] = token
        return p

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "repo")
        limit = min(int(kwargs.get("limit", 10)), 30)

        try:
            if action == "repo":
                return await self._repo(kwargs.get("owner", ""), kwargs.get("repo", ""))
            elif action == "commits":
                return await self._commits(kwargs.get("owner", ""), kwargs.get("repo", ""), limit)
            elif action == "issues":
                return await self._issues(kwargs.get("owner", ""), kwargs.get("repo", ""), limit)
            elif action == "releases":
                return await self._releases(kwargs.get("owner", ""), kwargs.get("repo", ""), limit)
            elif action == "user_repos":
                return await self._user_repos(limit)
            else:
                return {"error": f"Unknown action: {action}"}
        except Exception as e:
            logger.warning("Gitee %s failed: %s", action, e)
            return {"error": f"Gitee {action} failed: {e}", "results": []}

    async def _repo(self, owner: str, repo: str) -> dict[str, Any]:
        if not owner or not repo:
            return {"error": "owner and repo are required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/repos/{owner}/{repo}",
                params=self._params(),
            )
            if resp.status_code == 404:
                return {"error": f"Repo {owner}/{repo} not found on Gitee"}
            resp.raise_for_status()
            r = resp.json()

        return {
            "full_name": r.get("full_name", ""),
            "name": r.get("name", ""),
            "description": r.get("description", ""),
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "open_issues": r.get("open_issues_count", 0),
            "watchers": r.get("watchers_count", 0),
            "language": r.get("language", ""),
            "license": _safe_get(r, "license", "name"),
            "created_at": r.get("created_at", ""),
            "updated_at": r.get("updated_at", ""),
            "pushed_at": r.get("pushed_at", ""),
            "homepage": r.get("homepage", ""),
            "html_url": r.get("html_url", ""),
            "default_branch": r.get("default_branch", ""),
            "fork": r.get("fork", False),
            "parent": _safe_get(r, "parent", "full_name"),
        }

    async def _commits(self, owner: str, repo: str, limit: int) -> dict[str, Any]:
        if not owner or not repo:
            return {"error": "owner and repo are required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/repos/{owner}/{repo}/commits",
                params={**self._params(), "per_page": limit},
            )
            if resp.status_code == 404:
                return {"error": f"Repo {owner}/{repo} not found"}
            resp.raise_for_status()
            commits = resp.json()

        results = []
        for c in commits:
            commit_data = c.get("commit", {})
            results.append({
                "sha": c.get("sha", "")[:8],
                "message": (commit_data.get("message") or "")[:200],
                "author": (commit_data.get("author") or {}).get("name", ""),
                "date": (commit_data.get("author") or {}).get("date", ""),
                "html_url": c.get("html_url", ""),
            })

        return {"owner": owner, "repo": repo, "commits": results}

    async def _issues(self, owner: str, repo: str, limit: int) -> dict[str, Any]:
        if not owner or not repo:
            return {"error": "owner and repo are required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/repos/{owner}/{repo}/issues",
                params={**self._params(), "state": "all", "per_page": limit, "sort": "created", "direction": "desc"},
            )
            if resp.status_code == 404:
                return {"error": f"Repo {owner}/{repo} not found"}
            resp.raise_for_status()
            issues = resp.json()

        results = []
        for i in issues:
            results.append({
                "number": i.get("number", 0),
                "title": i.get("title", ""),
                "state": i.get("state", ""),
                "comments": i.get("comments", 0),
                "created_at": i.get("created_at", ""),
                "html_url": i.get("html_url", ""),
                "labels": [l.get("name", "") for l in i.get("labels", [])],
            })

        return {"owner": owner, "repo": repo, "issues": results}

    async def _releases(self, owner: str, repo: str, limit: int) -> dict[str, Any]:
        if not owner or not repo:
            return {"error": "owner and repo are required"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/repos/{owner}/{repo}/releases",
                params={**self._params(), "per_page": limit},
            )
            if resp.status_code == 404:
                return {"error": f"Repo {owner}/{repo} not found"}
            resp.raise_for_status()
            releases = resp.json()

        results = []
        for rel in releases:
            results.append({
                "tag_name": rel.get("tag_name", ""),
                "name": rel.get("name", ""),
                "published_at": rel.get("created_at", ""),
                "prerelease": rel.get("prerelease", False),
                "body": (rel.get("body") or "")[:500],
                "html_url": rel.get("html_url", ""),
            })

        return {"owner": owner, "repo": repo, "releases": results}

    async def _user_repos(self, limit: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.BASE}/user/repos",
                params={**self._params(), "sort": "updated", "per_page": limit, "type": "all"},
            )
            resp.raise_for_status()
            repos = resp.json()

        results = []
        for r in repos:
            results.append({
                "full_name": r.get("full_name", ""),
                "description": r.get("description", ""),
                "stars": r.get("stargazers_count", 0),
                "forks": r.get("forks_count", 0),
                "language": r.get("language", ""),
                "updated_at": r.get("updated_at", ""),
                "html_url": r.get("html_url", ""),
            })

        return {"repos": results}
