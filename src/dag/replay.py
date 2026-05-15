import json
from src.dag.models import DAGNode, TaskDAG
from src.dag.executor import AgentExecutor
from src.agents.contracts import AgentOutput


class ReplayAgentExecutor(AgentExecutor):
    """AgentExecutor that replays recorded agent outputs instead of running real agents.

    Used for fast, deterministic integration testing. The fixture file contains
    a recorded DAG and per-node outputs from a previous real-LLM run.

    In replay mode, execute() looks up the node_id in the fixture and returns
    the recorded output without making any LLM calls.
    """

    def __init__(self, gateway, store, tool_registry,
                 audit_logger=None, degradation_handler=None,
                 fixture_path=None):
        super().__init__(gateway, store, tool_registry,
                        audit_logger=audit_logger,
                        degradation_handler=degradation_handler)
        self._outputs: dict[str, dict] = {}
        self._dag_json: dict | None = None

        if fixture_path:
            with open(fixture_path, encoding="utf-8") as f:
                data = json.load(f)
            self._dag_json = data.get("dag", {})
            for entry in data.get("outputs", []):
                self._outputs[entry["node_id"]] = entry

    def get_recorded_dag(self) -> TaskDAG | None:
        """Reconstruct TaskDAG from the recorded fixture (no LLM needed)."""
        if not self._dag_json:
            return None
        nodes = [
            DAGNode(
                node_id=n["node_id"],
                agent_type=n["agent_type"],
                input_query=n.get("input_query", {}),
                depends_on=n.get("depends_on", []),
                priority=n.get("priority", 0),
            )
            for n in self._dag_json.get("nodes", [])
        ]
        dag = TaskDAG(task_id=self._dag_json.get("task_id", ""), nodes=nodes)
        for node in dag.nodes:
            node.context["task_id"] = dag.task_id
        return dag

    async def execute(self, node: DAGNode) -> None:
        if node.node_id in self._outputs:
            recorded = self._outputs[node.node_id]

            # Reconstruct AgentOutput
            output_data = recorded.get("output", {})
            output = AgentOutput(
                agent_type=output_data.get("agent_type", node.agent_type),
                node_id=output_data.get("node_id", node.node_id),
                summary=output_data.get("summary", ""),
                confidence=output_data.get("confidence", 0.8),
                data=output_data.get("data", {}),
                nodes_created=output_data.get("nodes_created", []),
                edges_created=output_data.get("edges_created", []),
                status=output_data.get("status", "completed"),
            )

            # Store output data on node context for feedback handlers and report
            if output.data:
                node.context["_output_data"] = output.data

            # Reconstruct traces
            traces = []
            for t in recorded.get("traces", []):
                from src.agents.base import StepTrace
                traces.append(StepTrace(
                    task_id=t.get("task_id", ""),
                    node_id=t.get("node_id", node.node_id),
                    agent_type=t.get("agent_type", node.agent_type),
                    step_number=t.get("step_number", 0),
                    reasoning=t.get("reasoning", ""),
                    confidence=t.get("confidence", 0.8),
                    action=t.get("action", ""),
                    action_params=t.get("action_params", {}),
                    nodes_read=t.get("nodes_read", []),
                    nodes_written=t.get("nodes_written", []),
                    llm_tokens=t.get("llm_tokens", 0),
                    llm_cost=t.get("llm_cost", 0.0),
                ))

            if output.status == "failed":
                node.max_retries = 0  # prevent infinite retry loop in replay
                raise RuntimeError(f"{node.agent_type} failed: {output.summary}")

            return

        await super().execute(node)
