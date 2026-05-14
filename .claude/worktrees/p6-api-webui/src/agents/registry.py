from typing import Any


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, dict[str, Any]] = {}
        self._classes: dict[str, type] = {}

    def register(self, agent_type: str, industry: str = "saas",
                 depends_on: list[str] | None = None,
                 tools: list[str] | None = None,
                 output_contract: Any = None,
                 model_tier: str = "analysis"):
        def decorator(cls):
            self._agents[agent_type] = {
                "agent_type": agent_type, "industry": industry,
                "depends_on": depends_on or [],
                "tools": tools or [], "output_contract": output_contract,
                "model_tier": model_tier,
            }
            self._classes[agent_type] = cls
            return cls
        return decorator

    def get(self, agent_type: str) -> dict[str, Any] | None:
        return self._agents.get(agent_type)

    def get_class(self, agent_type: str) -> type | None:
        return self._classes.get(agent_type)

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._agents.values())


agent_registry = AgentRegistry()
