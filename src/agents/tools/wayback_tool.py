"""
Wayback Machine CDX API 工具 — 分析竞品网站历史变迁。

免费额度: 无限 (Internet Archive 公开服务)
API 文档: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server

提供的竞品分析数据:
  - 网站历史版本快照数量和频率 (反映产品迭代节奏)
  - 首页变更时间线 (重大改版时间点)
  - 页面首次上线时间 (产品/功能的上线历史)
  - 域名历史 (品牌策略变化)
"""

import httpx
from typing import Any
from datetime import datetime
from src.agents.tools.base import ToolBase


class WaybackTool(ToolBase):
    name = "wayback_machine"
    description = (
        "Query Wayback Machine (archive.org) for historical snapshots of competitor websites. "
        "Use to: track website redesign cadence, discover when features/products launched, "
        "see brand/pricing page history. "
        "Completely free, no API key required."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "snapshots (list snapshots for URL), first (earliest snapshot), "
                           "changes (summary of major changes over time)",
        },
        "url": {"type": "string", "description": "Target URL or domain (e.g. 'notion.so' or 'notion.so/pricing')"},
        "from_year": {"type": "integer", "description": "Start year filter (default 2015)"},
        "limit": {"type": "integer", "description": "Max snapshots returned (default 10, max 50)"},
    }

    CDX_API = "https://web.archive.org/cdx/search/cdx"
    # The "Available" API for checking snapshot availability
    AVAILABLE_API = "https://archive.org/wayback/available"

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "snapshots")
        url = kwargs.get("url", "").strip()
        if not url:
            return {"error": "url is required (e.g. 'notion.so' or 'notion.so/pricing')"}

        limit = min(int(kwargs.get("limit", 10)), 50)
        from_year = int(kwargs.get("from_year", 2015))

        try:
            if action == "first":
                return await self._first_snapshot(url)
            elif action == "changes":
                return await self._change_summary(url, from_year, limit)
            else:
                return await self._list_snapshots(url, from_year, limit)
        except Exception as e:
            return {"error": f"Wayback Machine query failed: {e}", "results": []}

    async def _list_snapshots(self, url: str, from_year: int, limit: int) -> dict:
        """List snapshots for a URL with yearly sampling."""
        async with httpx.AsyncClient(timeout=30) as client:
            # Get all snapshots with yearly grouping
            resp = await client.get(
                self.CDX_API,
                params={
                    "url": f"*.{url}/*" if not url.startswith("http") else url,
                    "output": "json",
                    "from": f"{from_year}",
                    "fl": "timestamp,statuscode,digest",
                    "collapse": "timestamp:10",  # Group by year-month
                    "limit": limit,
                    "filter": "statuscode:200",
                },
                headers={"User-Agent": "CompAgent/1.0"},
            )
            if resp.status_code != 200:
                return {"error": f"CDX API returned HTTP {resp.status_code}", "snapshots": []}

            rows = resp.json()
            if not rows or len(rows) <= 1:
                return {"url": url, "snapshots": [], "note": "No snapshots found"}

            snapshots = []
            for row in rows[1:]:  # Skip header row
                ts = row[0]
                status = row[1]
                dt = datetime.strptime(ts[:8], "%Y%m%d")
                snapshots.append({
                    "timestamp": ts,
                    "date": dt.strftime("%Y-%m-%d"),
                    "status": status,
                    "view_url": f"https://web.archive.org/web/{ts}/{url}",
                })

            # Deduplicate by date
            seen_dates = set()
            unique = []
            for s in snapshots:
                if s["date"] not in seen_dates:
                    seen_dates.add(s["date"])
                    unique.append(s)

            return {
                "url": url,
                "total_snapshots": len(unique),
                "snapshots": unique[:limit],
            }

    async def _first_snapshot(self, url: str) -> dict:
        """Get the first-ever snapshot of a URL."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self.CDX_API,
                params={
                    "url": url,
                    "output": "json",
                    "fl": "timestamp,statuscode",
                    "limit": 1,
                    "filter": "statuscode:200",
                    "sort": "ascending",
                },
                headers={"User-Agent": "CompAgent/1.0"},
            )
            if resp.status_code != 200:
                return {"error": f"CDX API returned HTTP {resp.status_code}"}

            rows = resp.json()
            if not rows or len(rows) <= 1:
                return {"url": url, "note": "No snapshots found", "first_seen": None}

            ts = rows[1][0]
            dt = datetime.strptime(ts[:8], "%Y%m%d")
            return {
                "url": url,
                "first_seen": dt.strftime("%Y-%m-%d"),
                "first_view_url": f"https://web.archive.org/web/{ts}/{url}",
                "age_days": (datetime.now() - dt).days,
            }

    async def _change_summary(self, url: str, from_year: int, limit: int) -> dict:
        """Generate a change summary showing how many snapshots per year."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                self.CDX_API,
                params={
                    "url": f"*.{url}/*" if not url.startswith("http") else url,
                    "output": "json",
                    "from": f"{from_year}",
                    "fl": "timestamp",
                    "collapse": "timestamp:8",  # Group by day
                    "limit": -1,  # Get all for counting
                    "filter": "statuscode:200",
                },
                headers={"User-Agent": "CompAgent/1.0"},
            )
            if resp.status_code != 200:
                return {"error": f"CDX API returned HTTP {resp.status_code}"}

            rows = resp.json()
            if not rows or len(rows) <= 1:
                return {"url": url, "note": "No snapshots found", "yearly_counts": {}}

            # Count by year
            yearly: dict[str, int] = {}
            for row in rows[1:]:
                year = row[0][:4]
                yearly[year] = yearly.get(year, 0) + 1

            total = sum(yearly.values())

            return {
                "url": url,
                "total_snapshots": total,
                "yearly_snapshot_counts": yearly,
                "first_year": min(yearly.keys()) if yearly else None,
                "interpretation": (
                    f"Website has {total} snapshots since {from_year}. "
                    f"Higher counts = more active website updates and redesigns."
                ),
                "recent_snapshots_years": [
                    {
                        "year": y,
                        "count": c,
                        "activity": "high" if c > 50 else ("medium" if c > 10 else "low"),
                    }
                    for y, c in sorted(yearly.items(), reverse=True)[:5]
                ],
            }
