from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="QA_FactCheck",
    depends_on=["Writer"],
    tools=["graph_query", "graph_write"],
    output_contract=AgentOutput,
    model_tier="reasoning",
)
class QAFactCheckAgent(BaseAgent):
    agent_type = "QA_FactCheck"
    system_prompt = """You are QA Agent #1 — Fact Checker. Verify every claim in the report against the knowledge graph.

For each InsightNode and ReportSection:
1. BFS trace along derived_from edges to verify each claim has a complete evidence chain
2. Check that evidence nodes (WebPage, ReviewEntry, PricingData) actually exist
3. Flag claims with broken or missing trace chains
4. Flag suspicious patterns: high confidence with few sources, old data

Output your findings in the data field of your finalize result:
- data.failed_nodes: list of node_ids that failed fact-check
- data.issues: list of {node_id, reason, severity}
"""
    max_steps = 15
    output_contract = AgentOutput
    model_tier = "reasoning"
    allowed_tools = ["graph_query", "graph_write"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
