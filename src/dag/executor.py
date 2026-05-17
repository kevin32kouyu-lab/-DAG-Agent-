from src.dag.models import DAGNode
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway
from src.agents.tools.base import ToolRegistry
from src.agents.base import BaseAgent

# Lazy import map: agent_type → (module_path, class_name)
# Agents are imported on first use so executor.py works as soon as it's created (P2),
# even though most agent files don't exist until P3-P5.
_AGENT_IMPORT_MAP: dict[str, tuple[str, str]] = {
    "Orchestrator":       ("src.agents.orchestrator",       "OrchestratorAgent"),
    "SourceDiscovery":    ("src.agents.source_discovery",   "SourceDiscoveryAgent"),
    "Collector":          ("src.agents.collector",          "CollectorAgent"),
    "DataEnricher":       ("src.agents.data_enricher",      "DataEnricherAgent"),
    "FeatureAnalyzer":    ("src.agents.feature_analyzer",   "FeatureAnalyzer"),
    "SentimentAnalyzer":  ("src.agents.sentiment_analyzer", "SentimentAnalyzer"),
    "PricingAnalyst":     ("src.agents.pricing_analyst",    "PricingAnalyst"),
    "TechStackAnalyzer":  ("src.agents.techstack_analyzer", "TechStackAnalyzer"),
    "MarketPositionAnalyzer": ("src.agents.market_position", "MarketPositionAnalyzer"),
    "CrossReviewAgent":   ("src.agents.cross_review",       "CrossReviewAgent"),
    "SWOTAnalyzer":       ("src.agents.swot_synthesizer",   "SWOTAnalyzer"),
    "ReportGenerator":    ("src.agents.writer",             "WriterAgent"),
    "QA_FactCheck":       ("src.agents.qa_fact_check",      "QAFactCheckAgent"),
    "QA_LogicCheck":      ("src.agents.qa_logic_check",     "QALogicCheckAgent"),
}


class AgentExecutor:
    """Bridges DAG scheduling to actual agent execution.

    The DAGScheduler calls executor.execute(node) for each DAG node.
    AgentExecutor resolves the agent class, builds a task dict, runs the agent,
    and raises an exception on failure so the scheduler can handle retry logic.
    """

    def __init__(self, gateway: LLMGateway, store: GraphStore, tool_registry: ToolRegistry,
                 audit_logger=None, degradation_handler=None):
        self.gateway = gateway
        self.store = store
        self.tool_registry = tool_registry
        self.audit_logger = audit_logger
        self.degradation_handler = degradation_handler
        self._agent_cache: dict[str, type[BaseAgent]] = {}

    def _resolve_agent_class(self, agent_type: str) -> type[BaseAgent]:
        if agent_type in self._agent_cache:
            return self._agent_cache[agent_type]
        import importlib
        mod_path, cls_name = _AGENT_IMPORT_MAP[agent_type]
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        self._agent_cache[agent_type] = cls
        return cls

    async def execute(self, node: DAGNode) -> None:
        agent = self._build_agent(node)
        task = self._build_task(node)
        raw_output = await agent.execute(task)

        # Orchestrator returns TaskDAG directly, bypassing ReAct loop
        from src.dag.models import TaskDAG
        if isinstance(raw_output, tuple) and len(raw_output) == 2 and isinstance(raw_output[0], TaskDAG):
            # OrchestratorAgent.execute returns (TaskDAG, [])
            # Scheduler handles state transition after execute succeeds
            return

        output, traces = raw_output
        if output is None:
            raise RuntimeError(f"{node.agent_type} returned None — DAG generation or agent execution failed")

        if hasattr(output, 'status') and output.status == "failed":
            raise RuntimeError(f"{node.agent_type} failed: {getattr(output, 'summary', 'unknown')}")

        # Store output data on node context for feedback handlers
        if hasattr(output, 'data') and output.data:
            node.context["_output_data"] = output.data

        # Scheduler handles state transition after execute succeeds

    def _build_agent(self, node: DAGNode) -> BaseAgent:
        agent_cls = self._resolve_agent_class(node.agent_type)
        return agent_cls(gateway=self.gateway, store=self.store,
                         tool_registry=self.tool_registry, audit_logger=self.audit_logger,
                         degradation_handler=self.degradation_handler)

    @staticmethod
    def _build_task(node: DAGNode, task_id: str = "") -> dict:
        return {
            "task_id": task_id or node.context.get("task_id", ""),
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "input_query": node.input_query,
            "context": node.context,
        }
