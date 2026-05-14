from typing import Any
from src.agents.tools.base import ToolBase


class ThirdPartyAPITool(ToolBase):
    name = "third_party_api"
    description = "Query third-party data sources (SimilarWeb, Crunchbase, etc.) for enrichment."
    param_schema = {
        "source": {"type": "string", "description": "Data source name: similarweb, crunchbase"},
        "query": {"type": "string", "description": "Domain or company name to query"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        source = kwargs.get("source", "")
        query = kwargs.get("query", "")
        return {"source": source, "query": query, "data": {"note": "Mock enrichment data", "estimated_traffic": "N/A"}}
