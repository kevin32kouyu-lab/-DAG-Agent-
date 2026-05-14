from src.agents.base import BaseAgent
from src.agents.contracts import CrossReviewOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="CrossReviewAgent",
    depends_on=["FeatureAnalyzer", "SentimentAnalyzer", "PricingAnalyst", "TechStackAnalyzer", "MarketPositionAnalyzer"],
    tools=["graph_query", "graph_write"],
    output_contract=CrossReviewOutput,
    model_tier="analysis",
)
class CrossReviewAgent(BaseAgent):
    agent_type = "CrossReviewAgent"
    system_prompt = """You are a Cross-Review Agent. Your job is to check consistency across analysis agents.

Perform 3 checks on Layer 2 analysis nodes:

1. CONTRADICTION DETECTION: Compare conclusions from different analysis agents for the same product/dimension.
   Example: FeatureAnalyzer rates a feature as "weak" but SentimentAnalyzer shows positive user sentiment → contradiction.

2. OMISSION DETECTION: Check if one agent's data reveals information another agent should have considered.
   Example: SentimentAnalyzer found frequent "API integration" mentions, but FeatureAnalyzer didn't cover API capabilities.

3. CONFIDENCE ANOMALY: Detect when an agent assigns high confidence with very few derived_from edges.

For each finding, create a CrossReviewFlag node with:
- flag_type: "conflict", "omission", or "confidence_anomaly"
- severity: "high", "medium", or "low"
- involved_agents: list of agent types
- description: human-readable explanation

High severity contradictions should trigger re-analysis of the involved agents.

Output your flags list in the data.flags field of your finalize result.
"""
    max_steps = 12
    output_contract = CrossReviewOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
