from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="DataEnricher",
    depends_on=["Collector"],
    tools=["graph_query", "graph_write", "web_search", "company_scope"],
    output_contract=AgentOutput,
    model_tier="batch",
)
class DataEnricherAgent(BaseAgent):
    agent_type = "DataEnricher"
    system_prompt = """You are a Data Enricher agent. Review collected data and add business context.

1. Use graph_query ONCE to see what data was collected
2. Use company_scope ONCE with action="profile" to get external intelligence.
   If company_scope returns an error, MOVE ON immediately — do NOT retry.
3. If needed, do ONE web_search for extra context.
4. FINALIZE — do NOT exceed 4 tool calls total.

CRITICAL: You MUST finalize within 5 steps. If any tool returns an error or
empty data, note it and finalize anyway. NEVER call the same tool twice."""
    max_steps = 7
    token_budget = 150_000
    output_contract = AgentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write", "web_search", "company_scope"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
