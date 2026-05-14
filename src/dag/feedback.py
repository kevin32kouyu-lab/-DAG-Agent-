from src.dag.models import TaskDAG, NodeState


class FeedbackHandler:
    MAX_QA_ROUNDS = 2
    MAX_CROSS_REVIEW_ROUNDS = 1

    def __init__(self, audit_logger=None):
        self.audit_logger = audit_logger

    def handle_qa_rejection(self, dag: TaskDAG, qa_node_id: str,
                            failed_nodes: list[str], reasons: list[str],
                            qa_round: int) -> set[str]:
        qa_node = dag.get_node(qa_node_id)
        if qa_node is None:
            return set()

        qa_node.qa_round = qa_round

        if qa_round > self.MAX_QA_ROUNDS:
            qa_node.state = NodeState.DEGRADED
            qa_node.context["qa_notes"] = (
                f"Max {self.MAX_QA_ROUNDS} QA rounds exceeded: {reasons}"
            )
            self._audit("qa_degraded", {
                "qa_agent": qa_node.agent_type,
                "qa_node_id": qa_node_id,
                "round": qa_round,
                "reasons": reasons,
            })
            return set()

        # Trace upstream (dependencies) + downstream (consumers of failed nodes)
        affected: set[str] = set()
        for nid in failed_nodes:
            affected.add(nid)
            affected.update(dag.trace_upstream(nid))
            affected.update(dag.trace_downstream(nid))

        # Reset affected nodes to PENDING
        for nid in affected:
            node = dag.get_node(nid)
            if node and node.state == NodeState.COMPLETED:
                node.state = NodeState.PENDING
                node.retries = 0

        self._audit("qa_rejected", {
            "qa_agent": qa_node.agent_type,
            "qa_node_id": qa_node_id,
            "failed_nodes": failed_nodes,
            "affected_subgraph": list(affected),
            "reasons": reasons,
            "round": qa_round,
        })

        return affected

    def handle_cross_review_rejection(self, dag: TaskDAG,
                                       flags: list[dict]) -> set[str]:
        high_flags = [f for f in flags if f.get("severity") == "high"]
        if not high_flags:
            return set()

        affected_agents: set[str] = set()
        for flag in high_flags:
            for agent_type in flag.get("involved_agents", []):
                affected_agents.add(agent_type)

        affected_nodes: set[str] = set()
        for agent_type in affected_agents:
            for node in dag.find_nodes_by_agent(agent_type):
                if node.cross_review_retries >= self.MAX_CROSS_REVIEW_ROUNDS:
                    continue
                node.state = NodeState.PENDING
                node.cross_review_retries += 1
                node.context["cross_review_flags"] = [
                    f for f in high_flags
                    if agent_type in f.get("involved_agents", [])
                ]
                # Also reset upstream dependencies
                upstream = dag.trace_upstream(node.node_id)
                for uid in upstream:
                    up_node = dag.get_node(uid)
                    if up_node and up_node.state == NodeState.COMPLETED:
                        up_node.state = NodeState.PENDING
                        affected_nodes.add(uid)
                affected_nodes.add(node.node_id)

        self._audit("cross_review_rejected", {
            "flags": high_flags,
            "affected_agents": list(affected_agents),
            "affected_nodes": list(affected_nodes),
        })

        return affected_nodes

    def _audit(self, event: str, data: dict) -> None:
        if self.audit_logger:
            try:
                self.audit_logger.log(event, data)
            except Exception:
                pass
