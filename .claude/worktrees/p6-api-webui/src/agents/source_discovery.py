from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="SourceDiscovery",
    depends_on=[],
    tools=["graph_query", "graph_write", "web_search"],
    output_contract=AgentOutput,
    model_tier="batch",
)
class SourceDiscoveryAgent(BaseAgent):
    agent_type = "SourceDiscovery"
    system_prompt = """You are a Source Discovery agent for competitive analysis.

Your job: for each target product, search for information sources using web_search, then finalize with a summary of discovered sources.

Workflow:
1. Call web_search 1-2 times with different queries to find sources
2. Evaluate credibility: official sites=0.9+, G2/TrustRadius=0.8+, ProductHunt=0.7+
3. FINALIZE after 2-3 tool calls maximum — summarize what you found in the "result" field

IMPORTANT: You do NOT need to create graph nodes yourself. Just discover URLs and finalize with the list of sources found.
"""
    max_steps = 4
    output_contract = AgentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write", "web_search"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
