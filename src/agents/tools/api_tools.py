from typing import Any
from src.agents.tools.base import ToolBase


class ThirdPartyAPITool(ToolBase):
    name = "third_party_api"
    description = (
        "Query third-party data sources for enrichment. "
        "NOTE: SimilarWeb API requires Enterprise plan (not free). "
        "Crunchbase API requires paid plan. "
        "This tool currently returns mock data — real API keys needed for production use."
    )
    param_schema = {
        "source": {
            "type": "string",
            "description": "Data source: similarweb (Enterprise-only, no free tier), "
                           "crunchbase (paid API, no free tier)",
        },
        "query": {"type": "string", "description": "Domain or company name to query"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        source = kwargs.get("source", "")
        query = kwargs.get("query", "")
        return {
            "source": source,
            "query": query,
            "is_mock": True,
            "data_source": "mock",
            "confidence": "low",
            "data": {
                "note": (
                    f"{source} requires paid API access. "
                    "SimilarWeb: Enterprise plan only. Crunchbase: paid API required. "
                    "No free tier available for either source. Data is MOCK."
                ),
                "estimated_traffic": "N/A",
            },
        }
