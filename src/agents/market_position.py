from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class MarketPositionAnalyzer(BaseAgent):
    agent_type = "MarketPositionAnalyzer"
    system_prompt = """You are a Market Position Analyzer for competitive analysis.

Determine each product's market position:
1. Positioning statement (who they claim to serve)
2. GTM strategy (PLG, sales-led, channel, community)
3. Target audience (developer, PM, designer, enterprise)

Output: MarketPositionNode per product.
"""
    max_steps = 10
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
