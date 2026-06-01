"""
Google Trends 工具 — 搜索热度和竞品兴趣对比。

使用 pytrends 库 (非官方但稳定) 获取 Google Trends 数据。
免费, 无需 API key, 但高频请求可能触发限流。

提供的竞品分析数据:
  - 多产品搜索热度对比 (relative interest over time)
  - 地域分布 (哪些地区搜索最多)
  - 相关查询和相关主题 (用户同时搜什么)
"""

import asyncio
from typing import Any
from src.agents.tools.base import ToolBase


class GoogleTrendsTool(ToolBase):
    name = "google_trends"
    description = (
        "Compare search interest trends across competitor products using Google Trends. "
        "Returns relative interest over time (0-100 scale), regional breakdown, "
        "and related queries. "
        "Free, no API key required. Best for comparing brand awareness and market momentum."
    )
    param_schema = {
        "action": {
            "type": "string",
            "description": "compare (compare multiple products search interest), "
                           "related (find related queries/topics for a keyword)",
        },
        "keywords": {
            "type": "array",
            "description": "List of product names or keywords to compare (max 5). Use for action=compare.",
        },
        "keyword": {
            "type": "string",
            "description": "Single keyword for action=related",
        },
        "timeframe": {
            "type": "string",
            "description": "Time range: 'today 1-m', 'today 3-m', 'today 12-m', "
                           "'today 5-y', 'all' (default 'today 12-m')",
        },
        "geo": {"type": "string", "description": "Country code, e.g. 'CN', 'US', '' for worldwide (default '')"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "compare")
        timeframe = kwargs.get("timeframe", "today 12-m")
        geo = kwargs.get("geo", "")

        try:
            loop = asyncio.get_running_loop()
            if action == "compare":
                keywords = kwargs.get("keywords", [])
                if not keywords:
                    return {"error": "keywords list is required", "results": []}
                if len(keywords) > 5:
                    keywords = keywords[:5]

                return await loop.run_in_executor(
                    None, self._compare_sync, keywords, timeframe, geo
                )

            elif action == "related":
                keyword = kwargs.get("keyword", "")
                if not keyword:
                    return {"error": "keyword is required for action=related"}

                return await loop.run_in_executor(
                    None, self._related_sync, keyword, timeframe, geo
                )

            else:
                return {"error": f"Unknown action: {action}"}

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Too Many Requests" in error_msg:
                return {"error": "Google Trends 限流, 请稍后重试 (建议间隔 60 秒以上)", "results": []}
            if "pytrends" in error_msg.lower():
                return {"error": f"pytrends 调用失败: {error_msg}", "results": []}
            return {"error": f"Google Trends 查询失败: {error_msg}", "results": []}

    @staticmethod
    def _compare_sync(keywords: list[str], timeframe: str, geo: str) -> dict[str, Any]:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload(
            kw_list=keywords,
            timeframe=timeframe,
            geo=geo if geo else "",
        )

        # Get interest over time
        interest_df = pytrends.interest_over_time()
        if interest_df.empty:
            return {
                "keywords": keywords,
                "note": "Not enough data for these keywords in the selected timeframe/region",
                "timeline": [],
                "regional_data": [],
            }

        # Drop isPartial column if present
        if "isPartial" in interest_df.columns:
            interest_df = interest_df.drop(columns=["isPartial"])

        # Build timeline
        timeline = []
        for idx, row in interest_df.iterrows():
            point = {"date": idx.strftime("%Y-%m-%d")}
            for kw in keywords:
                if kw in row:
                    point[kw] = round(float(row[kw]), 1)
            timeline.append(point)

        # Calculate average interest per keyword
        averages = {}
        for kw in keywords:
            if kw in interest_df.columns:
                averages[kw] = round(float(interest_df[kw].mean()), 1)

        # Regional data
        regional: list[dict] = []
        try:
            region_df = pytrends.interest_by_region(resolution="COUNTRY", inc_low_vol=True)
            if not region_df.empty:
                for idx, row in region_df.head(10).iterrows():
                    entry = {"region": idx}
                    for kw in keywords:
                        if kw in row:
                            entry[kw] = round(float(row[kw]), 1)
                    regional.append(entry)
        except Exception:
            pass  # Regional data is best-effort

        # Find which keyword dominates
        top_keyword = max(averages, key=averages.get) if averages else ""
        lead_gap = None
        if len(keywords) >= 2 and top_keyword:
            scores = sorted(averages.values(), reverse=True)
            if len(scores) >= 2:
                lead_gap = round(scores[0] - scores[1], 1)

        return {
            "keywords": keywords,
            "timeframe": timeframe,
            "geo": geo if geo else "worldwide",
            "average_interest": averages,
            "top_keyword": top_keyword,
            "lead_gap": lead_gap,
            "trend": "rising" if timeline and timeline[-1].get(keywords[0], 0) > timeline[0].get(keywords[0], 0) else "stable",
            "timeline": timeline,
            "regional_data": regional,
        }

    @staticmethod
    def _related_sync(keyword: str, timeframe: str, geo: str) -> dict[str, Any]:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
        pytrends.build_payload(
            kw_list=[keyword],
            timeframe=timeframe,
            geo=geo if geo else "",
        )

        related_queries = pytrends.related_queries()
        related_topics = pytrends.related_topics()

        result: dict = {
            "keyword": keyword,
            "related_queries": {"top": [], "rising": []},
            "related_topics": {"top": [], "rising": []},
        }

        # Parse related queries
        queries_data = related_queries.get(keyword, {})
        if queries_data is not None:
            for qtype in ("top", "rising"):
                df = queries_data.get(qtype)
                if df is not None and not df.empty:
                    result["related_queries"][qtype] = [
                        {"query": row["query"], "value": int(row["value"])}
                        for _, row in df.head(10).iterrows()
                    ]

        # Parse related topics
        topics_data = related_topics.get(keyword, {})
        if topics_data is not None:
            for qtype in ("top", "rising"):
                df = topics_data.get(qtype)
                if df is not None and not df.empty:
                    result["related_topics"][qtype] = [
                        {"topic": row["topic_title"], "value": int(row["value"])}
                        for _, row in df.head(10).iterrows()
                    ]

        return result
