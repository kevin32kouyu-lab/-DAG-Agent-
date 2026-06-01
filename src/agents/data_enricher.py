from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry


@agent_registry.register(
    agent_type="DataEnricher",
    depends_on=["Collector"],
    tools=["graph_query", "graph_write", "web_search", "tavily_search", "company_scope", "app_store", "producthunt", "wayback_machine"],
    output_contract=AgentOutput,
    model_tier="batch",
)
class DataEnricherAgent(BaseAgent):
    agent_type = "DataEnricher"
    system_prompt = """You are a Data Enricher agent. Review collected data and add business context from external sources.

1. Use graph_query ONCE to see what data was collected
2. Use company_scope ONCE with action="profile" to get external intelligence.
   If company_scope returns an error, MOVE ON immediately — do NOT retry.
3. Use app_store action="lookup" or "reviews" to get structured app data if applicable.
4. Use producthunt action="search" to find launch metrics and community validation.
5. Use wayback_machine action="changes" to see website evolution history.
6. If gaps remain, do ONE tavily_search or web_search for extra context.
7. FINALIZE — do NOT exceed 5 tool calls total.

CRITICAL: You MUST finalize within 7 steps. If any tool returns an error or empty data, note it and finalize anyway. NEVER call the same tool twice."""
    max_steps = 9
    token_budget = 180_000
    output_contract = AgentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write", "web_search", "tavily_search", "company_scope", "app_store", "producthunt", "wayback_machine"]

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
