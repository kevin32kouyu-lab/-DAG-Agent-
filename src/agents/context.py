from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    task_id: str = ""
    node_id: str = ""
    agent_type: str = ""
    max_steps: int = 15
    history: list[dict[str, Any]] = field(default_factory=list)
    previous_outputs: dict[str, Any] = field(default_factory=dict)
    schema_overrides: dict[str, Any] = field(default_factory=dict)

    def init(self, task: dict[str, Any]) -> None:
        self.task_id = task.get("task_id", "")
        self.node_id = task.get("node_id", "")
        self.agent_type = task.get("agent_type", "")
        self.history = []
        self.previous_outputs = task.get("context", {})

    def add(self, thought: Any, result: Any) -> None:
        self.history.append({"thought": thought, "result": result})
