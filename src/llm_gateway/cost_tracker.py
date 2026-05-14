from dataclasses import dataclass, field


@dataclass
class CostTracker:
    total_tokens: int = 0
    total_cost: float = 0.0
    llm_calls: int = 0
    per_agent: dict[str, dict] = field(default_factory=dict)

    def record(self, agent_type: str, tokens: int, cost: float) -> None:
        self.total_tokens += tokens
        self.total_cost += cost
        self.llm_calls += 1
        if agent_type not in self.per_agent:
            self.per_agent[agent_type] = {"tokens": 0, "cost": 0.0, "calls": 0}
        self.per_agent[agent_type]["tokens"] += tokens
        self.per_agent[agent_type]["cost"] += cost
        self.per_agent[agent_type]["calls"] += 1

    def summary(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 4),
            "total_calls": self.llm_calls,
            "per_agent": self.per_agent,
        }
