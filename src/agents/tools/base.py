from abc import ABC
from typing import Any


class ToolBase(ABC):
    name: str = ""
    description: str = ""
    param_schema: dict[str, Any] = {}

    async def execute(self, **kwargs) -> dict[str, Any]:
        return {"error": "not implemented"}


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, type[ToolBase]] = {}
        self._instances: dict[str, ToolBase] = {}
        self._deps: dict[str, dict] = {}

    def register(self, tool_cls: type[ToolBase], **deps) -> None:
        name = tool_cls.name
        self._tools[name] = tool_cls
        self._deps[name] = deps
        if deps:
            self._instances[name] = tool_cls(**deps)

    def create_instance(self, name: str, **deps) -> ToolBase:
        cls = self._tools.get(name)
        if cls is None:
            raise KeyError(f"Tool '{name}' not registered")
        instance = cls(**deps)
        self._instances[name] = instance
        self._deps[name] = deps
        return instance

    def get(self, name: str) -> ToolBase | None:
        inst = self._instances.get(name)
        if inst is not None:
            return inst
        cls = self._tools.get(name)
        if cls is not None:
            deps = self._deps.get(name, {})
            inst = cls(**deps)
            self._instances[name] = inst
            return inst
        return None

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def describe_tools(self) -> list[dict[str, Any]]:
        result = []
        for name, cls in self._tools.items():
            inst = self._instances.get(name)
            if inst:
                result.append({"name": inst.name, "description": inst.description, "params": inst.param_schema})
            else:
                result.append({"name": cls.name, "description": cls.description, "params": cls.param_schema})
        return result


tool_registry = ToolRegistry()
