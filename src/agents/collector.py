from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry
from src.infrastructure.degradation import DegradationHandler
from src.infrastructure.config import config

_COLLECTOR_SYSTEM_PROMPT = """You are a Collector agent. Scrape assigned URLs and summarize the content found.

For each URL: call web_scrape → extract key information → FINALIZE with a summary of what was found.

If a URL returns an error or empty content:
1. Check if the source has a degradation_tier hint in the task context
2. If tier=0 (primary) failed, note the failure and suggest trying tier=1
3. If tier=1 failed, suggest tier=2
4. If all tiers exhausted, mark the source as DATA_DEGRADED in your summary
5. Do NOT retry failed URLs more than once per tier

FINALIZE after at most 5 tool calls.
"""


@agent_registry.register(
    agent_type="Collector",
    depends_on=["SourceDiscovery"],
    tools=["graph_query", "graph_write", "web_scrape", "tavily_search", "app_store", "github"],
    output_contract=AgentOutput,
    model_tier="batch",
)
class CollectorAgent(BaseAgent):
    agent_type = "Collector"
    system_prompt = _COLLECTOR_SYSTEM_PROMPT
    max_steps = 6
    token_budget = 100_000
    output_contract = AgentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write", "web_scrape", "tavily_search", "app_store", "github"]

    def __init__(self, gateway, store, tool_registry, audit_logger=None,
                 degradation_handler=None):
        super().__init__(gateway, store, tool_registry, audit_logger)
        self.degradation_handler = degradation_handler or DegradationHandler(
            config=config, audit=audit_logger
        )

    async def execute(self, task: dict) -> tuple:
        # Inject source degradation tier context into the task
        self._inject_degradation_context(task)
        return await super().execute(task)

    def _inject_degradation_context(self, task: dict) -> None:
        sources = task.get("context", {}).get("sources", [])
        if not sources:
            return
        degradation_hints = {}
        for src in sources:
            src_name = src if isinstance(src, str) else src.get("name", "")
            if src_name and self.degradation_handler:
                tiers = self.degradation_handler.get_tiers(src_name)
                if tiers:
                    degradation_hints[src_name] = tiers
        if degradation_hints:
            task["context"]["degradation_tiers"] = degradation_hints
            task["context"]["current_tiers"] = {s: 0 for s in degradation_hints}
