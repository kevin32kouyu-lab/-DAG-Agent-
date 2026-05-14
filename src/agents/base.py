from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from pydantic import BaseModel
from src.agents.context import AgentContext
from src.agents.tools.base import ToolRegistry
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway


class StepTrace(BaseModel):
    task_id: str
    node_id: str
    agent_type: str
    step_number: int
    timestamp: datetime = datetime.now()
    observation_summary: str = ""
    data_nodes_read: list[str] = []
    reasoning: str = ""
    confidence: float | None = None
    prompt_snapshot: str | None = None
    response_snapshot: str | None = None
    action: str = ""
    action_params: dict[str, Any] | None = None
    action_result_summary: str | None = None
    nodes_created: list[str] = []
    edges_created: list[str] = []
    llm_tokens: int = 0
    llm_cost: float = 0.0


class BaseAgent(ABC):
    agent_type: str = ""
    system_prompt: str = ""
    max_steps: int = 15
    output_contract: type = None

    def __init__(self, gateway: LLMGateway, store: GraphStore, tool_registry: ToolRegistry,
                 audit_logger=None):
        self.gateway = gateway
        self.store = store
        self.tool_registry = tool_registry
        self.audit_logger = audit_logger
        self.context = AgentContext()

    async def execute(self, task: dict[str, Any]) -> Any:
        self.context.init(task)
        traces: list[StepTrace] = []

        for step in range(self.max_steps):
            observation = await self._observe(task)
            trace = StepTrace(
                task_id=self.context.task_id, node_id=self.context.node_id,
                agent_type=self.agent_type, step_number=step,
                observation_summary=str(observation)[:500],
                data_nodes_read=observation.get("nodes_read", []),
            )

            thought = await self._think(observation)
            trace.reasoning = thought.get("reasoning", "")
            trace.confidence = thought.get("confidence")
            trace.llm_tokens = thought.get("tokens", 0)
            trace.llm_cost = thought.get("cost", 0.0)

            if thought.get("action") == "finalize":
                trace.action = "finalize"
                result = thought.get("result", {})
                trace.nodes_created = result.get("nodes_created", [])
                trace.edges_created = result.get("edges_created", [])
                traces.append(trace)
                self._persist_trace(trace)
                output = self._build_output(result)
                return output, traces

            action, params = thought.get("action", ""), thought.get("params", {})
            result = await self._act(action, params)
            trace.action = action
            trace.action_params = params
            trace.action_result_summary = str(result)[:500]
            traces.append(trace)
            self._persist_trace(trace)
            self.context.add(thought, result)

        raise RuntimeError(f"{self.agent_type}: exceeded max steps ({self.max_steps})")

    def _persist_trace(self, trace: StepTrace) -> None:
        if self.audit_logger:
            try:
                self.audit_logger.log_step_trace(trace)
            except Exception:
                pass

    async def _observe(self, task: dict[str, Any]) -> dict[str, Any]:
        query = task.get("input_query", {})
        nodes = self.store.query_nodes(
            node_type=query.get("node_type"),
            layer=query.get("layer"),
        )
        return {
            "nodes": [n.model_dump(mode="json") for n in nodes],
            "nodes_read": [n.id for n in nodes],
            "task": task,
        }

    async def _think(self, observation: dict[str, Any]) -> dict[str, Any]:
        tools_desc = self.tool_registry.describe_tools() if self.tool_registry else []
        prompt = f"""{self.system_prompt}

Available tools: {tools_desc}

Observation: {observation}

Respond with JSON: {{"reasoning": "...", "action": "tool_name" | "finalize", "params": {{...}}, "confidence": 0.0-1.0}}
If finalize: {{"reasoning": "...", "action": "finalize", "result": {{...}}, "confidence": 0.0-1.0}}
"""
        resp = await self.gateway.chat(
            system=self.system_prompt,
            messages=[{"role": "user", "content": str(observation)[:8000]}],
            model_tier="analysis",
        )
        import json
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError:
            return {"reasoning": resp.content, "action": "finalize", "result": {}, "confidence": 0.5}

    async def _act(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        tool = self.tool_registry.get(action)
        if tool:
            return await tool.execute(**params, _agent_type=self.agent_type)
        return {"error": f"Tool '{action}' not found"}

    def _build_output(self, result: dict[str, Any]) -> Any:
        if self.output_contract:
            return self.output_contract(
                agent_type=self.agent_type, node_id=self.context.node_id, **result,
            )
        return result
