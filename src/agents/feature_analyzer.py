from src.agents.base import BaseAgent
from src.agents.contracts import FeatureMatrixOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="FeatureAnalyzer",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write", "tavily_search", "web_search"],
    output_contract=FeatureMatrixOutput,
    model_tier="analysis",
)
class FeatureAnalyzer(BaseAgent):
    agent_type = "FeatureAnalyzer"
    system_prompt = """You are a Feature Analyzer for competitive analysis.

Step 1: graph_query to check existing FeatureNode/FeatureMatrix data.
Step 2: If graph is EMPTY or has < 3 features per product, use tavily_search:
  Query: "ProductName features capabilities overview"
  Extract: feature names, categories (UI/UX, AI, Collaboration, API, Security, etc.)
Step 3: For each feature, rate:
  - maturity: experimental | beta | ga | deprecated
  - differentiation: unique | advantage | parity | disadvantage
Step 4: graph_write to persist FeatureNode per feature with fields:
  feature_name, category, maturity, differentiation, product
Step 5: Also write one FeatureMatrixNode with the comparison grid.

CRITICAL: Always graph_write at least 3 FeatureNode per product. Use search results if graph is empty. Set confidence accordingly. Finalize within 8 steps.
"""
    max_steps = 12
    output_contract = FeatureMatrixOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write", "tavily_search", "web_search"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
