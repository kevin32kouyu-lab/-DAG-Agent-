from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry
from src.infrastructure.degradation import DegradationHandler
from src.infrastructure.config import config

_COLLECTOR_SYSTEM_PROMPT = """You are a highly efficient Collector agent. Your goal is to gather raw web page data for competitive analysis.

To achieve maximum speed and efficiency, you MUST use the Flat-ReAct (batching) paradigm. Follow this 2-step execution plan:

STEP 1 (Think -> Act):
- Read the assigned URLs from the task query (or find them using graph_query).
- Use `batch_web_scrape` to concurrently scrape ALL assigned URLs at once. DO NOT scrape URLs one-by-one.
- If no URLs are assigned but a product/competitor is specified, call `tavily_search` or `web_search` ONCE to discover pages, and then batch scrape them.

STEP 2 (Observe -> Finalize):
- Review the observations returned by `batch_web_scrape`.
- Write successfully collected contents into the knowledge graph using `graph_write` as WebPage nodes. Make sure to link them to the target product.
- Call `finalize` IMMEDIATELY with a comprehensive summary of what was successfully collected and what failed/degraded.

CRITICAL CONSTRAINTS:
- You are ONLY responsible for gathering raw web pages for the target product.
- YOU ARE STRICTLY FORBIDDEN from performing more than ONE search (tavily_search/web_search) and ONE scraping action (batch_web_scrape/web_scrape) in total!
- Even if some URLs failed to scrape, DO NOT search again and DO NOT attempt to scrape them again. Accept the partial failure, write the successfully scraped pages using `graph_write`, and call `finalize` immediately!
- Retrying failed page scrapes or doing multiple rounds of search and scrape is strictly prohibited.
- Once you have called `graph_write` for any scraped page, your very next action MUST be to write other successful pages or call `finalize` immediately.
- You MUST complete execution and finalize within 5 steps maximum.
"""


@agent_registry.register(
    agent_type="Collector",
    depends_on=["SourceDiscovery"],
    tools=["graph_query", "graph_write", "web_scrape", "batch_web_scrape", "tavily_search", "app_store", "github"],
    output_contract=AgentOutput,
    model_tier="batch",
)
class CollectorAgent(BaseAgent):
    agent_type = "Collector"
    system_prompt = _COLLECTOR_SYSTEM_PROMPT
    max_steps = 12
    token_budget = 100_000
    output_contract = AgentOutput
    model_tier = "batch"
    allowed_tools = ["graph_query", "graph_write", "web_scrape", "batch_web_scrape", "tavily_search", "app_store", "github"]

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

