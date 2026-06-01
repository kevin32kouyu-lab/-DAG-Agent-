from src.agents.base import BaseAgent
from src.agents.contracts import TechStackOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="TechStackAnalyzer",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write", "web_search", "tavily_search", "github", "wayback_machine"],
    output_contract=TechStackOutput,
    model_tier="analysis",
)
class TechStackAnalyzer(BaseAgent):
    agent_type = "TechStackAnalyzer"
    system_prompt = """You are a Tech Stack Analyzer for competitive analysis.

Step 1: graph_query ONCE to check existing TechStack/WebPage data.
Step 2: For EACH product, do independent searches (do NOT skip):
  - tavily_search: "ProductName tech stack programming language framework"
  - github action="search" query="ProductName" (to find open-source repos)
  - wayback_machine action="changes" url="productdomain.com" (website evolution)
Step 3: Identify: languages[], frameworks[], infra[] (cloud/database/CDN/monitoring)
Step 4: graph_write to persist TechStackNode per product with:
  product, languages, frameworks, infra, confidence, sources

CRITICAL: Even if the graph is empty, use tavily_search + github results.
ALWAYS graph_write at least one TechStackNode per product.
Set confidence=0.2 if data is thin. Finalize within 10 steps.
"""
    max_steps = 10
    output_contract = TechStackOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write", "web_search", "tavily_search", "github", "wayback_machine"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
