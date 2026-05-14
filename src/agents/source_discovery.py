from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class SourceDiscoveryAgent(BaseAgent):
    agent_type = "SourceDiscovery"
    system_prompt = """You are a Source Discovery agent for competitive analysis.

Your job: for each target product, search for and evaluate information sources. You have access to web_search, graph_query, and graph_write tools.

For each source found:
1. Evaluate credibility (0.0-1.0): official sites=0.9+, G2/TrustRadius=0.8+, ProductHunt=0.7+, blogs=0.5+
2. Prioritize: official pricing pages, G2 reviews, ProductHunt, tech blogs
3. Create SourceInfo nodes with url, domain, credibility_score

Output all discovered sources as SourceInfo nodes in the knowledge graph.
"""
    max_steps = 8
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
