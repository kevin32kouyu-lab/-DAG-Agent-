import time
from dataclasses import dataclass, field


@dataclass
class HealthCheck:
    agent_heartbeats: dict[str, float] = field(default_factory=dict)
    task_timeouts: dict[str, float] = field(default_factory=dict)
    heartbeat_timeout: float = 60.0
    task_timeout: float = 600.0

    def heartbeat(self, agent_id: str) -> None:
        self.agent_heartbeats[agent_id] = time.time()

    def get_unhealthy_agents(self) -> list[str]:
        now = time.time()
        return [aid for aid, ts in self.agent_heartbeats.items() if now - ts > self.heartbeat_timeout]

    def mark_task_start(self, task_id: str) -> None:
        self.task_timeouts[task_id] = time.time()

    def get_timed_out_tasks(self) -> list[str]:
        now = time.time()
        return [tid for tid, ts in self.task_timeouts.items() if now - ts > self.task_timeout]
