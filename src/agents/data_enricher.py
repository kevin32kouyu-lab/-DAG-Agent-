from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class DataEnricherAgent(BaseAgent):
    agent_type = "DataEnricher"
    system_prompt = """You are a Data Enricher agent. Review collected data and add business context.

1. Use graph_query ONCE to see what data was collected
2. Optionally, do ONE web_search for market context
3. FINALIZE with your enrichment analysis

You MUST finalize within 3 steps. Do NOT keep searching. If data is sparse, note that and finalize anyway.
"""
    max_steps = 8
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
