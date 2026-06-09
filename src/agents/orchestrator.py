"""这个模块负责把用户的竞品分析任务规划成可执行 DAG。"""

import logging

from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry
from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
from src.dag.models import DAGNode, TaskDAG

logger = logging.getLogger(__name__)


@agent_registry.register(
    agent_type="Orchestrator",
    depends_on=[],
    tools=[],
    output_contract=AgentOutput,
    model_tier="reasoning",
)
class OrchestratorAgent(BaseAgent):
    agent_type = "Orchestrator"
    model_tier = "reasoning"
    allowed_tools = []
    system_prompt = """You are the Orchestrator for a competitive analysis multi-agent system.

Your job: normalize task inputs and compile a stable DAG from the workflow template.
"""

    max_steps = 1
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple[TaskDAG | None, list]:
        self.context.init(task)
        targets = task.get("targets", [])
        schema = task.get("schema", {"industry": "saas"})
        request = WorkflowCompileRequest(
            task_id=task.get("task_id", self.context.task_id or ""),
            targets=targets,
            scenario=str(task.get("scenario", schema.get("industry", "saas"))),
            collection_depth=task.get("collection_depth", "standard"),
            schema=schema,
        )
        dag = WorkflowCompiler().compile(request)
        return dag, []

    async def _generate_dag(self, targets: list[str], schema: dict) -> dict | None:
        logger.warning("DAG 生成结果无法解析，已返回空结果：compiled template mode")
        return None

    @staticmethod
    def _parse_dag_json(text: str) -> dict | None:
        return None

    MANDATORY_AGENTS = ["ReportGenerator", "QA"]
    FALLBACK_REPORT_DEP = "Analyst"

    @staticmethod
    def _valid_node_dicts(raw_nodes: object) -> list[dict]:
        if not isinstance(raw_nodes, list):
            logger.warning("DAG 节点跳过：nodes 字段不是列表")
            return []

        validated: list[dict] = []
        for i, n in enumerate(raw_nodes):
            if not isinstance(n, dict):
                logger.warning("DAG 节点跳过：第 %s 个节点不是对象", i)
                continue
            if "node_id" not in n or "agent_type" not in n:
                logger.warning("DAG 节点跳过：第 %s 个节点缺少 node_id 或 agent_type", i)
                continue
            n = dict(n)
            n.setdefault("input_query", {})
            n.setdefault("depends_on", [])
            n.setdefault("priority", 0)
            validated.append(n)
        return validated

    def _json_to_dag(self, dag_json: dict) -> TaskDAG:
        raw_nodes = dag_json.get("nodes", [])
        validated = self._valid_node_dicts(raw_nodes)
        if not validated and raw_nodes:
            raise ValueError(f"All {len(raw_nodes)} nodes from LLM are missing node_id/agent_type")
        nodes = [
            DAGNode(
                node_id=n["node_id"],
                agent_type=n["agent_type"],
                input_query=n.get("input_query", {}),
                depends_on=n.get("depends_on", []),
                priority=n.get("priority", 0),
            )
            for n in validated
        ]
        return TaskDAG(task_id=dag_json.get("task_id", ""), nodes=nodes)

    def _ensure_mandatory_nodes(self, dag_json: dict, schema: dict,
                                targets: list[str] | None = None) -> dict:
        raw_nodes = dag_json.get("nodes", [])
        nodes = self._valid_node_dicts(raw_nodes)
        if not nodes and raw_nodes:
            raise ValueError(f"All {len(raw_nodes)} nodes from LLM are missing node_id/agent_type")
        dag_json["nodes"] = nodes
        existing_types = {n["agent_type"] for n in nodes}
        existing_ids = {n["node_id"] for n in nodes}
        exclude = set(schema.get("exclude_dimensions", []))
        targets = targets or []

        def _unique_id(base: str) -> str:
            cand = base
            i = 1
            while cand in existing_ids:
                cand = f"{base}_{i}"
                i += 1
            existing_ids.add(cand)
            return cand

        if "ReportGenerator" not in existing_types:
            # 找到分析层节点作为 Writer 的依赖
            writer_dep = [n["node_id"] for n in nodes
                          if n["agent_type"] == "Analyst"]
            if not writer_dep:
                writer_dep = [n["node_id"] for n in nodes
                              if n["agent_type"] == "Collector"]
            nodes.append({
                "node_id": _unique_id("report_generator"),
                "agent_type": "ReportGenerator",
                "depends_on": writer_dep,
                "input_query": {"targets": targets},
                "priority": 0,
                "auto_generated": True,
            })
            existing_types.add("ReportGenerator")

        writer_node = next((n for n in nodes if n["agent_type"] == "ReportGenerator"), None)
        if writer_node is None:
            raise RuntimeError("ReportGenerator node missing after mandatory injection")
        writer_id = writer_node["node_id"]
        if "QA" not in existing_types:
            nodes.append({
                "node_id": _unique_id("qa"),
                "agent_type": "QA",
                "depends_on": [writer_id],
                "input_query": {},
                "priority": 0,
                "auto_generated": True,
            })
            existing_types.add("QA")

        dag_json["nodes"] = nodes
        return dag_json
