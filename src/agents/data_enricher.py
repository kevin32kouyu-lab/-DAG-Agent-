from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class DataEnricherAgent(BaseAgent):
    agent_type = "DataEnricher"
    system_prompt = """You are a Data Enricher agent. After raw data collection, enrich the knowledge graph with:
- Industry context and market trends
- Company background information
- Competitive landscape context

Read all Layer 1 nodes, identify gaps, and add MetricData, NewsArticle nodes with contextual information.
"""
    max_steps = 8
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
