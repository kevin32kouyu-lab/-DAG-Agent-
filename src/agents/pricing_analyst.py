from src.agents.base import BaseAgent
from src.agents.contracts import PricingOutput


class PricingAnalyst(BaseAgent):
    agent_type = "PricingAnalyst"
    system_prompt = """You are a Pricing Analyst for competitive analysis.

Analyze pricing models from PricingData nodes:
1. Identify pricing strategy (freemium, usage-based, per-seat, enterprise)
2. Determine target segment (individual, SMB, mid-market, enterprise)
3. Calculate value score based on features/price ratio
4. Build competitive comparison: who offers more for less?

Output: PricingModelNode per product. Include comparisons in the comparison field.
"""
    max_steps = 10
    output_contract = PricingOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
