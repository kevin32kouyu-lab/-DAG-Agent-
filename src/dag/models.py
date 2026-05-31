from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class NodeState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"
    REJECTED = "rejected"
    RERUNNING = "rerunning"


@dataclass
class DAGNode:
    node_id: str
    agent_type: str
    input_query: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    state: NodeState = NodeState.PENDING
    priority: int = 0
    retries: int = 0
    max_retries: int = 3
    qa_round: int = 0
    cross_review_retries: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    stage: str = ""
    role_group: str = ""
    display_name: str = ""
    description: str = ""
    output_contract: str = ""
    degradation_policy: dict[str, Any] = field(default_factory=dict)
    source_policy: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeSnapshot:
    task_id: str
    node_id: str
    state: NodeState
    kg_changeset: dict[str, Any] = field(default_factory=dict)
    agent_log: list[dict[str, Any]] = field(default_factory=list)
    checkpoint_time: datetime = field(default_factory=datetime.now)
    llm_cost: float = 0.0


@dataclass
class TaskDAG:
    task_id: str
    nodes: list[DAGNode] = field(default_factory=list)
    workflow_template_id: str = ""
    scenario: str = ""
    targets: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_nodes_by_stage(self, stage: str) -> list[DAGNode]:
        return [node for node in self.nodes if node.stage == stage]

    def get_ready_nodes(self) -> list[DAGNode]:
        # A dependency is "resolved" if COMPLETED, DEGRADED, or permanently FAILED
        resolved_ids: set[str] = set()
        for n in self.nodes:
            if n.state == NodeState.COMPLETED:
                resolved_ids.add(n.node_id)
            elif n.state == NodeState.DEGRADED:
                resolved_ids.add(n.node_id)
            elif n.state == NodeState.FAILED and n.retries >= n.max_retries:
                # Permanent failure — treat as resolved so dependents can proceed degraded
                resolved_ids.add(n.node_id)

        ready = []
        for node in self.nodes:
            if node.state != NodeState.PENDING:
                continue
            if all(dep in resolved_ids for dep in node.depends_on):
                ready.append(node)
        return ready

    def get_node(self, node_id: str) -> DAGNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def is_terminal(self) -> bool:
        return all(n.state in {NodeState.COMPLETED, NodeState.FAILED, NodeState.DEGRADED} for n in self.nodes)

    def trace_upstream(self, node_id: str) -> set[str]:
        affected: set[str] = set()
        queue = [node_id]
        visited: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            node = self.get_node(current)
            if node:
                for dep_id in node.depends_on:
                    if dep_id not in visited:
                        affected.add(dep_id)
                        queue.append(dep_id)
        return affected

    def trace_downstream(self, node_id: str) -> set[str]:
        """BFS downstream: find all nodes that transitively depend on node_id."""
        affected: set[str] = set()
        visited: set[str] = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for node in self.nodes:
                if current in node.depends_on and node.node_id not in visited:
                    affected.add(node.node_id)
                    queue.append(node.node_id)
        return affected

    def find_nodes_by_agent(self, agent_type: str) -> list[DAGNode]:
        return [n for n in self.nodes if n.agent_type == agent_type]
