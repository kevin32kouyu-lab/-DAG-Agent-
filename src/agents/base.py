from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from src.agents.context import AgentContext
from src.agents.tools.base import ToolRegistry
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway


class StepTrace(BaseModel):
    task_id: str
    node_id: str
    agent_type: str
    step_number: int
    timestamp: datetime = Field(default_factory=datetime.now)
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
    model_tier: str = "analysis"
    allowed_tools: list[str] = []

    def __init__(self, gateway: LLMGateway, store: GraphStore, tool_registry: ToolRegistry,
                 audit_logger=None, **kwargs):
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
            trace.prompt_snapshot = thought.get("_prompt")
            trace.response_snapshot = thought.get("_response")

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
        history_summary = []
        for entry in self.context.history[-5:]:
            thought = entry.get("thought", {})
            result = entry.get("result", {})
            history_summary.append({
                "action": thought.get("action", "unknown"),
                "params": thought.get("params", {}),
                "result_summary": str(result)[:500],
            })
        return {
            "nodes": [n.model_dump(mode="json") for n in nodes],
            "nodes_read": [n.id for n in nodes],
            "task": task,
            "previous_actions": history_summary,
        }

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        import json
        import re
        candidates: list[dict] = []

        # 1) Raw parse
        try:
            d = json.loads(text)
            if isinstance(d, dict):
                candidates.append(d)
        except json.JSONDecodeError:
            pass

        # 2) Extract from ```json ... ``` blocks
        for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text):
            try:
                d = json.loads(match.group(1))
                if isinstance(d, dict):
                    candidates.append(d)
            except json.JSONDecodeError:
                pass

        # 3) Extract all brace-balanced { ... } pairs
        brace_starts = [i for i, ch in enumerate(text) if ch == "{"]
        for start in brace_starts:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            d = json.loads(text[start:i + 1])
                            if isinstance(d, dict):
                                candidates.append(d)
                        except json.JSONDecodeError:
                            pass
                        break

        # Prefer candidates with "action" field, then largest
        if candidates:
            with_action = [c for c in candidates if "action" in c]
            chosen = with_action[0] if with_action else max(candidates, key=lambda c: len(c))
            return chosen
        return {}

    async def _think(self, observation: dict[str, Any]) -> dict[str, Any]:
        tools_desc = self.tool_registry.describe_tools() if self.tool_registry else []
        user_content = str(observation)[:8000]
        prompt = f"""Available tools: {tools_desc}

Current state (Observation): {observation}

CRITICAL: You MUST respond with a single JSON object and nothing else.
- No XML tags (<function>, <parameter>, <value>, etc.)
- No markdown code blocks (no ```)
- No explanatory text before or after the JSON
- Just the raw JSON object on one line

Format for tool call:
{{"reasoning": "why I chose this action", "action": "tool_name", "params": {{"param1": "value1"}}, "confidence": 0.85}}

Format for final answer:
{{"reasoning": "summary of what I found", "action": "finalize", "result": {{"summary": "...", "nodes_created": [], "edges_created": []}}, "confidence": 0.85}}

Respond with json now."""

        resp = await self.gateway.chat(
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
            model_tier=self.model_tier,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        result = self._extract_json(resp.content)
        if not result:
            result = {"reasoning": resp.content[:500], "action": "finalize", "result": {}, "confidence": 0.5}
        result["_prompt"] = prompt
        result["_response"] = resp.content
        return result

    async def _act(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if self.allowed_tools and action not in self.allowed_tools:
            return {"error": f"Tool '{action}' not in allowed_tools for {self.agent_type}"}
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
