"""这个模块处理 QA 和 Cross-Review 反馈，决定哪些 DAG 节点需要重跑或降级。"""

import logging

from src.dag.models import TaskDAG, NodeState

logger = logging.getLogger(__name__)


class FeedbackHandler:
    MAX_QA_ROUNDS = 1
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

        # 只重置 Writer 节点，让 Writer 用现有分析数据重新生成报告
        # 不重置上游分析节点，避免全链路重跑
        affected: set[str] = set()
        report_nodes = [n for n in dag.nodes if n.agent_type == "ReportGenerator"]
        for node in report_nodes:
            if node.state in {NodeState.COMPLETED, NodeState.DEGRADED, NodeState.FAILED}:
                node.state = NodeState.PENDING
                node.retries = 0
                affected.add(node.node_id)

        # 如果 QA 节点本身也需要重置
        qa_node.state = NodeState.PENDING
        qa_node.retries = 0
        affected.add(qa_node.node_id)

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
        affected_nodes: set[str] = set()

        # High severity: only reset the specific analysis node, NOT the entire upstream chain
        high_flags = [f for f in flags if f.get("severity") == "high"]
        if high_flags:
            affected_node_ids: set[str] = set()
            for flag in high_flags:
                for nid in flag.get("involved_node_ids", []):
                    affected_node_ids.add(nid)
                for agent_type in flag.get("involved_agents", []):
                    for node in dag.find_nodes_by_agent(agent_type):
                        affected_node_ids.add(node.node_id)

            for nid in affected_node_ids:
                node = dag.get_node(nid)
                if not node:
                    continue
                if node.cross_review_retries >= self.MAX_CROSS_REVIEW_ROUNDS:
                    node.state = NodeState.DEGRADED
                    node.context["cross_review_flags"] = [
                        f for f in high_flags
                        if nid in f.get("involved_node_ids", [])
                        or node.agent_type in f.get("involved_agents", [])
                    ]
                    affected_nodes.add(node.node_id)
                    continue
                node.state = NodeState.PENDING
                node.cross_review_retries += 1
                node.context["cross_review_flags"] = [
                    f for f in high_flags
                    if nid in f.get("involved_node_ids", [])
                    or node.agent_type in f.get("involved_agents", [])
                ]
                affected_nodes.add(node.node_id)

            self._audit("cross_review_rejected", {
                "flags": high_flags,
                "affected_nodes": list(affected_nodes),
            })

        # Medium severity omission: incremental supplement, target only, no upstream reset
        omission_flags = [
            f for f in flags
            if f.get("severity") == "medium" and f.get("flag_type") == "omission"
        ]
        for flag in omission_flags:
            target_node_id = flag.get("target_node_id", "")
            target_agent = flag.get("target_agent", "")
            target_nodes = []
            if target_node_id:
                node = dag.get_node(target_node_id)
                if node:
                    target_nodes = [node]
            elif target_agent:
                target_nodes = dag.find_nodes_by_agent(target_agent)
            for node in target_nodes:
                if node.state != NodeState.COMPLETED:
                    continue
                node.state = NodeState.PENDING
                node.context.setdefault("omission_context", []).append(flag)
                affected_nodes.add(node.node_id)

        if omission_flags:
            self._audit("cross_review_omission", {
                "omission_flags": omission_flags,
                "affected_nodes": list(affected_nodes),
            })

        return affected_nodes

    def _audit(self, event: str, data: dict) -> None:
        """记录反馈事件，审计失败时写日志但不阻塞反馈处理。"""
        if self.audit_logger:
            try:
                self.audit_logger.log_event("", "", "", event, data)
            except Exception as exc:
                logger.warning("反馈审计写入失败: event=%s, reason=%s", event, exc)
