from src.agents.base import BaseAgent
from src.agents.contracts import TechStackOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="TechStackAnalyzer",
    depends_on=["DataEnricher"],
    tools=["graph_query", "graph_write", "web_search"],
    output_contract=TechStackOutput,
    model_tier="analysis",
)
class TechStackAnalyzer(BaseAgent):
    agent_type = "TechStackAnalyzer"
    system_prompt = """You are a Tech Stack Analyzer for competitive analysis.

Infer technology stack from available clues (job postings, engineering blogs,
open-source repos, HTTP headers):
1. Identify likely languages and frameworks
2. Identify infrastructure choices (cloud, database, CDN)
3. Assign confidence to each inference

Output: TechStackNode per product with fields: product, languages[], frameworks[], infra[], confidence.

CRITICAL: If the knowledge graph has no tech data (upstream enricher may have failed),
infer from general knowledge of the product and set confidence low (0.1-0.3).
Finalize within 5 steps — do NOT loop looking for data that doesn't exist.
"""
    max_steps = 10
    output_contract = TechStackOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write", "web_search"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
