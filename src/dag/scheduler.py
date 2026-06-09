"""这个模块负责按 DAG 依赖顺序调度节点，并处理反馈、快照和状态事件。"""

import asyncio
from datetime import datetime
import logging
from src.dag.models import TaskDAG, DAGNode, NodeState, NodeSnapshot
from src.dag.feedback import FeedbackHandler

logger = logging.getLogger(__name__)

CHECKPOINT_AGENT = "Collector"
CHECKPOINT_TIMEOUT = 30 * 60  # 30 minutes auto-release
NODE_TIMEOUT = 300  # per-node timeout in seconds (5 min)

QA_AGENT_TYPES = {"QA"}
CROSS_REVIEW_NODE_ID = "cross_review"


class DAGScheduler:
    def __init__(self, review_mode: bool = False,
                 feedback_handler: FeedbackHandler | None = None,
                 snapshot_store=None):
        self._event_callbacks: dict[str, list] = {}
        self._checkpoint_event: asyncio.Event | None = None
        self._dag_registry: dict[str, TaskDAG] = {}
        self._task_errors: dict[str, str] = {}
        self.review_mode = review_mode
        self.feedback = feedback_handler or FeedbackHandler()
        self.snapshot_store = snapshot_store

    def get_task_dag(self, task_id: str) -> TaskDAG | None:
        return self._dag_registry.get(task_id)

    def on(self, event: str, callback):
        self._event_callbacks.setdefault(event, []).append(callback)

    async def _emit(self, event: str, *args, **kwargs):
        for cb in self._event_callbacks.get(event, []):
            try:
                await cb(*args, **kwargs)
            except Exception:
                logger.warning("事件回调失败，任务继续执行：event=%s", event, exc_info=True)

    def release_checkpoint(self) -> None:
        if self._checkpoint_event:
            self._checkpoint_event.set()

    async def run(self, dag: TaskDAG, executor, gateway=None) -> None:
        self._dag_registry[dag.task_id] = dag
        self._gateway = gateway

        # Restore from snapshot: skip COMPLETED nodes
        snapshots = self._load_snapshots(dag.task_id)
        if snapshots:
            for node in dag.nodes:
                if node.node_id in snapshots and snapshots[node.node_id].state == NodeState.COMPLETED:
                    node.state = NodeState.COMPLETED

        while True:
            ready = dag.get_ready_nodes()
            for node in ready:
                node.state = NodeState.READY

            if not ready:
                for node in dag.nodes:
                    if node.state == NodeState.FAILED and node.retries < node.max_retries:
                        node.retries += 1
                        node.state = NodeState.PENDING
                        ready.append(node)

            if not ready:
                break

            tasks = []
            for node in ready:
                node.state = NodeState.RUNNING
                await self._emit("node_state_change", node)
                tasks.append(asyncio.create_task(self._run_node(node, executor, dag)))

            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in tasks:
                if not t.done():
                    await t

            # Emit cost update after each batch of nodes completes
            await self._emit_cost_update(dag.task_id, executor)

            # Check if any failed nodes can be retried before declaring terminal
            retriable = any(
                n.state == NodeState.FAILED and n.retries < n.max_retries
                for n in dag.nodes
            )
            if dag.is_terminal() and not retriable:
                break

    async def _emit_cost_update(self, task_id: str, executor) -> None:
        """Emit cost_update with token count, cost, and pages collected."""
        try:
            cost_tracker = executor.gateway.cost_tracker
            tokens = cost_tracker.total_tokens
            cost = cost_tracker.total_cost
            # Count WebPage nodes in the knowledge graph (sync in prod, may be async in tests)
            result = executor.store.query_nodes(node_type="WebPage")
            if hasattr(result, '__await__'):
                result = await result
            pages = len(result) if result else 0
            await self._emit("cost_update", task_id, 0.0, cost, tokens, pages)
        except Exception:
            logger.warning("成本更新失败，任务继续执行：task_id=%s", task_id, exc_info=True)

    async def emit_dag_created(self, task_id: str, dag) -> None:
        """Push full DAG structure to all WS clients when DAG generation completes."""
        self._dag_registry[task_id] = dag
        nodes_payload = []
        for node in dag.nodes:
            nodes_payload.append({
                "node_id": node.node_id,
                "agent_type": node.agent_type,
                "state": node.state.value if hasattr(node.state, "value") else str(node.state),
                "depends_on": node.depends_on,
                "stage": getattr(node, "stage", ""),
                "role_group": getattr(node, "role_group", ""),
                "display_name": getattr(node, "display_name", ""),
                "description": getattr(node, "description", ""),
                "output_contract": getattr(node, "output_contract", ""),
            })
        payload = {
            "workflow_template_id": getattr(dag, "workflow_template_id", ""),
            "scenario": getattr(dag, "scenario", ""),
            "targets": getattr(dag, "targets", []),
            "metadata": getattr(dag, "metadata", {}),
            "nodes": nodes_payload,
        }
        await self._emit("dag_created", task_id, payload)

    async def emit_dag_failed(self, task_id: str, error: str) -> None:
        """Notify WS clients that DAG generation failed."""
        self._task_errors[task_id] = error
        await self._emit("dag_failed", task_id, error)

    def get_task_error(self, task_id: str) -> str | None:
        return self._task_errors.get(task_id)

    async def _run_node(self, node: DAGNode, executor, dag: TaskDAG):
        try:
            # Propagate DAG task_id to node context so agents can persist with correct task_id
            node.context["task_id"] = dag.task_id
            await asyncio.wait_for(executor.execute(node), timeout=NODE_TIMEOUT)
            node.state = NodeState.COMPLETED
            await self._emit("node_completed", node)
            await self._emit("node_state_change", node)

            # Snapshot after each completed node for checkpoint/resume
            self._save_snapshot(dag.task_id, node)

            # Feedback: check QA output for failed nodes
            if node.agent_type in QA_AGENT_TYPES:
                output_data = node.context.get("_output_data", {})
                overall_pass = output_data.get("overall_pass", True)
                if not overall_pass:
                    # 从 fact_issues 和 logic_issues 中提取失败节点
                    fact_issues = output_data.get("fact_issues", [])
                    logic_issues = output_data.get("logic_issues", [])
                    all_issues = fact_issues + logic_issues
                    failed_nodes = [
                        issue.get("node_id", "")
                        for issue in all_issues
                        if issue.get("node_id")
                    ]
                    failed_nodes = sorted(set(failed_nodes))
                    reasons = [
                        issue.get("reason", "") or issue.get("description", "")
                        for issue in all_issues
                    ]
                    if not failed_nodes:
                        # 如果没有具体 node_id，打回 Writer
                        report_nodes = [n.node_id for n in dag.nodes if n.agent_type == "ReportGenerator"]
                        failed_nodes = report_nodes
                    if failed_nodes:
                        next_round = node.qa_round + 1
                        affected = self.feedback.handle_qa_rejection(
                            dag, qa_node_id=node.node_id,
                            failed_nodes=failed_nodes,
                            reasons=reasons,
                            qa_round=next_round,
                        )
                        if affected:
                            await self._emit("qa_reject",
                                dag.task_id, node.agent_type,
                                failed_nodes,
                                reasons,
                                list(affected), next_round,
                            )
                            await self._emit("feedback_applied", {
                                "task_id": dag.task_id,
                                "type": "qa_rejection",
                                "qa_node_id": node.node_id,
                                "round": next_round,
                                "affected_nodes": list(affected),
                            })

            # Feedback: check CrossReview output for high-severity flags
            if node.node_id == CROSS_REVIEW_NODE_ID:
                output_data = node.context.get("_output_data", {})
                flags = output_data.get("flags", [])
                high_flags = [f for f in flags if f.get("severity") == "high"]
                if high_flags:
                    affected = self.feedback.handle_cross_review_rejection(
                        dag, high_flags,
                    )
                    if affected:
                        await self._emit("feedback_applied", {
                            "task_id": dag.task_id,
                            "type": "cross_review_rejection",
                            "cr_node_id": node.node_id,
                            "affected_nodes": list(affected),
                        })

            if self.review_mode and node.agent_type == CHECKPOINT_AGENT:
                self._checkpoint_event = asyncio.Event()
                await self._emit("checkpoint_reached", node, dag.task_id)
                try:
                    await asyncio.wait_for(
                        self._checkpoint_event.wait(),
                        timeout=CHECKPOINT_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning(
                        "检查点等待超时，任务自动继续：task_id=%s node_id=%s",
                        dag.task_id,
                        node.node_id,
                    )
                self._checkpoint_event = None
                await self._emit("checkpoint_released", node, dag.task_id)

        except Exception as e:
            node.state = NodeState.FAILED
            node.context["error"] = str(e)
            await self._emit("node_failed", node)
            await self._emit("node_state_change", node)

    def _save_snapshot(self, task_id: str, node: DAGNode) -> None:
        """保存节点完成快照；写入失败只记录日志，不影响节点完成状态。"""
        if not self.snapshot_store:
            return
        try:
            self.snapshot_store.save(NodeSnapshot(
                task_id=task_id,
                node_id=node.node_id,
                state=NodeState.COMPLETED,
                checkpoint_time=datetime.now(),
            ))
        except Exception:
            logger.warning("快照保存失败，任务继续执行：task_id=%s node_id=%s", task_id, node.node_id, exc_info=True)

    def _load_snapshots(self, task_id: str) -> dict:
        """读取任务快照；读取失败时记录日志并从头执行。"""
        if not self.snapshot_store:
            return {}
        try:
            return self.snapshot_store.load(task_id) or {}
        except Exception:
            logger.warning("快照读取失败，将从头执行任务：task_id=%s", task_id, exc_info=True)
            return {}
