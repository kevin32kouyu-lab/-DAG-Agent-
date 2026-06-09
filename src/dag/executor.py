"""这个模块负责把 DAG 节点交给对应 Agent 执行。"""

from src.dag.models import DAGNode
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway
from src.agents.tools.base import ToolRegistry
from src.agents.base import BaseAgent

# Lazy import map: agent_type → (module_path, class_name)
# 重构后只有 4 个 Agent 类 + Orchestrator
_AGENT_IMPORT_MAP: dict[str, tuple[str, str]] = {
    "Orchestrator":       ("src.agents.orchestrator",  "OrchestratorAgent"),
    "Collector":          ("src.agents.collector",     "CollectorAgent"),
    "Analyst":            ("src.agents.analyst",       "AnalystAgent"),
    "ReportGenerator":    ("src.agents.writer",        "WriterAgent"),
    "QA":                 ("src.agents.qa",            "QAAgent"),
    # 旧版 agent_type 兼容映射（用于 replay fixtures 和历史 DAG）
    "SourceDiscovery":    ("src.agents.collector",     "CollectorAgent"),
    "DataEnricher":       ("src.agents.collector",     "CollectorAgent"),
    "FeatureAnalyzer":    ("src.agents.analyst",       "AnalystAgent"),
    "SentimentAnalyzer":  ("src.agents.analyst",       "AnalystAgent"),
    "PricingAnalyst":     ("src.agents.analyst",       "AnalystAgent"),
    "TechStackAnalyzer":  ("src.agents.analyst",       "AnalystAgent"),
    "MarketPositionAnalyzer": ("src.agents.analyst",   "AnalystAgent"),
    "CrossReviewAgent":   ("src.agents.analyst",       "AnalystAgent"),
    "SWOTAnalyzer":       ("src.agents.writer",        "WriterAgent"),
    "QA_FactCheck":       ("src.agents.qa",            "QAAgent"),
    "QA_LogicCheck":      ("src.agents.qa",            "QAAgent"),
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
        """解析节点对应的 Agent 类，并把懒加载错误转成可读提示。"""
        if agent_type in self._agent_cache:
            return self._agent_cache[agent_type]
        import importlib
        if agent_type not in _AGENT_IMPORT_MAP:
            available = ", ".join(sorted(_AGENT_IMPORT_MAP))
            raise RuntimeError(f"未知 Agent 类型：{agent_type}。可用类型：{available}")
        mod_path, cls_name = _AGENT_IMPORT_MAP[agent_type]
        try:
            mod = importlib.import_module(mod_path)
        except Exception as exc:
            raise RuntimeError(
                f"Agent 导入失败：{agent_type}（{mod_path}.{cls_name}）"
            ) from exc
        try:
            cls = getattr(mod, cls_name)
        except AttributeError as exc:
            raise RuntimeError(
                f"Agent 类未找到：{agent_type}（{mod_path}.{cls_name}）"
            ) from exc
        self._agent_cache[agent_type] = cls
        return cls

    async def execute(self, node: DAGNode) -> None:
        agent = self._build_agent(node)
        task = self._build_task(node)
        raw_output = await agent.execute(task)

        # Orchestrator returns TaskDAG directly, bypassing ReAct loop
        from src.dag.models import TaskDAG
        if isinstance(raw_output, tuple) and len(raw_output) == 2 and isinstance(raw_output[0], TaskDAG):
            return

        output, traces = raw_output
        if output is None:
            raise RuntimeError(f"{node.agent_type} returned None — DAG generation or agent execution failed")

        if hasattr(output, 'status') and output.status == "failed":
            raise RuntimeError(f"{node.agent_type} failed: {getattr(output, 'summary', 'unknown')}")

        # Store normalized output data on node context for feedback handlers and API routes.
        if hasattr(output, "model_dump"):
            output_data = output.model_dump(mode="json")
            if isinstance(getattr(output, "data", None), dict):
                output_data.update(output.data)
            node.context["_output_data"] = output_data
        elif hasattr(output, 'data') and output.data:
            node.context["_output_data"] = output.data

    def _build_agent(self, node: DAGNode) -> BaseAgent:
        agent_cls = self._resolve_agent_class(node.agent_type)
        return agent_cls(gateway=self.gateway, store=self.store,
                         tool_registry=self.tool_registry, audit_logger=self.audit_logger,
                         degradation_handler=self.degradation_handler)

    @staticmethod
    def _build_task(node: DAGNode, task_id: str = "") -> dict:
        task = {
            "task_id": task_id or node.context.get("task_id", ""),
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "input_query": node.input_query,
            "context": node.context,
        }
        # 注入 input_defaults 到 context（用于 Analyst Agent 的 dimension 参数）
        if hasattr(node, 'input_defaults') and node.input_defaults:
            task["context"].update(node.input_defaults)
        return task
