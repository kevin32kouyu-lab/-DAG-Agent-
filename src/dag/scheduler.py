import asyncio
from src.dag.models import TaskDAG, DAGNode, NodeState
from src.dag.feedback import FeedbackHandler

CHECKPOINT_AGENT = "DataEnricher"
CHECKPOINT_TIMEOUT = 30 * 60  # 30 minutes auto-release

QA_AGENT_TYPES = {"QA_FactCheck", "QA_LogicCheck"}
CROSS_REVIEW_AGENT = "CrossReviewAgent"


class DAGScheduler:
    def __init__(self, review_mode: bool = False,
                 feedback_handler: FeedbackHandler | None = None):
        self._event_callbacks: dict[str, list] = {}
        self._checkpoint_event: asyncio.Event | None = None
        self._dag_registry: dict[str, TaskDAG] = {}
        self.review_mode = review_mode
        self.feedback = feedback_handler or FeedbackHandler()

    def get_task_dag(self, task_id: str) -> TaskDAG | None:
        return self._dag_registry.get(task_id)

    def on(self, event: str, callback):
        self._event_callbacks.setdefault(event, []).append(callback)

    async def _emit(self, event: str, *args, **kwargs):
        for cb in self._event_callbacks.get(event, []):
            await cb(*args, **kwargs)

    def release_checkpoint(self) -> None:
        if self._checkpoint_event:
            self._checkpoint_event.set()

    async def run(self, dag: TaskDAG, executor) -> None:
        self._dag_registry[dag.task_id] = dag
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

            # Check if any failed nodes can be retried before declaring terminal
            retriable = any(
                n.state == NodeState.FAILED and n.retries < n.max_retries
                for n in dag.nodes
            )
            if dag.is_terminal() and not retriable:
                break

    async def _run_node(self, node: DAGNode, executor, dag: TaskDAG):
        try:
            await executor.execute(node)
            node.state = NodeState.COMPLETED
            await self._emit("node_completed", node)
            await self._emit("node_state_change", node)

            # Feedback: check QA output for failed nodes
            if node.agent_type in QA_AGENT_TYPES:
                output_data = node.context.get("_output_data", {})
                failed_nodes = output_data.get("failed_nodes", [])
                if failed_nodes:
                    next_round = node.qa_round + 1
                    affected = self.feedback.handle_qa_rejection(
                        dag, qa_node_id=node.node_id,
                        failed_nodes=failed_nodes,
                        reasons=output_data.get("issues", []),
                        qa_round=next_round,
                    )
                    if affected:
                        await self._emit("qa_reject",
                            dag.task_id, node.agent_type,
                            failed_nodes,
                            output_data.get("issues", []),
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
            if node.agent_type == CROSS_REVIEW_AGENT:
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
                    pass
                self._checkpoint_event = None
                await self._emit("checkpoint_released", node, dag.task_id)

        except Exception as e:
            node.state = NodeState.FAILED
            node.context["error"] = str(e)
            await self._emit("node_failed", node)
            await self._emit("node_state_change", node)
