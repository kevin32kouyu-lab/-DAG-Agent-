"""
Component-level deterministic tests for agent internals (Plan B).

These test the non-LLM components of the agent system:
- JSON extraction from real LLM output formats
- Output normalization in _build_output
- Tool routing and allowed_tools enforcement
- Output contract Pydantic validation
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.base import BaseAgent, StepTrace
from src.agents.contracts import (
    AgentOutput, FeatureMatrixOutput, SentimentOutput,
    PricingOutput, TechStackOutput, MarketPositionOutput,
)
from src.agents.tools.base import ToolBase, ToolRegistry
from src.knowledge_graph.store import GraphStore


# ── _extract_json tests ──


class TestExtractJson:
    """Test _extract_json against real LLM output patterns (not mock JSON)."""

    def test_clean_json(self):
        result = BaseAgent._extract_json('{"action": "finalize", "confidence": 0.9}')
        assert result["action"] == "finalize"
        assert result["confidence"] == 0.9

    def test_markdown_fenced_json(self):
        """LLM frequently wraps JSON in ```json blocks."""
        text = """Here's my response:
```json
{"action": "graph_query", "params": {"layer": 1}, "confidence": 0.8}
```
Let me know if you need more."""
        result = BaseAgent._extract_json(text)
        assert result["action"] == "graph_query"
        assert result["params"]["layer"] == 1

    def test_markdown_fenced_no_lang_tag(self):
        text = """```
{"action": "finalize", "result": {"summary": "done"}, "confidence": 0.9}
```"""
        result = BaseAgent._extract_json(text)
        assert result["action"] == "finalize"

    def test_multiple_json_objects_prefers_action(self):
        """When multiple JSON objects exist, prefer the one with 'action' key."""
        text = '''{"description": "some data"}
        {"action": "graph_write", "params": {"node_type": "FeatureNode"}, "confidence": 0.7}'''
        result = BaseAgent._extract_json(text)
        assert result["action"] == "graph_write"

    def test_json_with_newlines_in_strings(self):
        """LLM sometimes puts newlines inside JSON string values."""
        text = json.dumps({
            "reasoning": "Line 1\nLine 2\nLine 3",
            "action": "finalize",
            "result": {"summary": "Multi-line\nsummary here"},
            "confidence": 0.8,
        })
        result = BaseAgent._extract_json(text)
        assert result["action"] == "finalize"
        assert "Line 1" in result["reasoning"]

    def test_json_with_unicode_escapes(self):
        text = '{"reasoning": "分析完成 \\u2713", "action": "finalize", "confidence": 0.9}'
        result = BaseAgent._extract_json(text)
        assert result["action"] == "finalize"
        assert "分析完成" in result["reasoning"]

    def test_empty_string_returns_empty_dict(self):
        assert BaseAgent._extract_json("") == {}
        assert BaseAgent._extract_json("   ") == {}

    def test_no_json_returns_empty_dict(self):
        assert BaseAgent._extract_json("Just some regular text without any JSON") == {}

    def test_nested_braces(self):
        """Correctly handles nested JSON objects."""
        text = json.dumps({
            "action": "finalize",
            "result": {
                "nodes_created": [{"id": "n1", "type": "FeatureNode"}],
                "summary": "nested objects",
            },
            "confidence": 0.9,
        })
        result = BaseAgent._extract_json(text)
        assert result["action"] == "finalize"
        assert isinstance(result["result"]["nodes_created"], list)
        assert result["result"]["nodes_created"][0]["id"] == "n1"

    def test_llm_xml_hallucination(self):
        """LLM sometimes outputs XML tags instead of JSON — should still extract."""
        text = '''<function>
<parameter name="action">graph_query</parameter>
</function>
{"action": "graph_query", "params": {"layer": 1}}'''
        result = BaseAgent._extract_json(text)
        assert result["action"] == "graph_query"

    def test_single_brace_in_string_value(self):
        """Brace inside a JSON string value should not confuse the parser."""
        text = json.dumps({
            "reasoning": "Use {braces} in text",
            "action": "finalize",
            "confidence": 0.8,
        })
        result = BaseAgent._extract_json(text)
        assert result["action"] == "finalize"

    def test_partial_json_due_to_truncation(self):
        """When LLM output is truncated mid-JSON, the brace-matcher should handle it."""
        text = '{"action": "graph_query", "params": {"layer": 1}, "confiden'
        # Brace-balanced extraction will fail to find complete JSON
        # but won't crash — returns empty or partial
        result = BaseAgent._extract_json(text)
        # Should not crash; may return {} if no complete JSON found
        assert isinstance(result, dict)

    def test_deepseek_real_output_pattern(self):
        """Pattern observed from real DeepSeek output: JSON after explanatory text."""
        text = """I need to analyze the features. Let me query the graph first.

{"reasoning": "Querying Layer 2 for existing features", "action": "graph_query", "params": {"layer": 2}, "confidence": 0.85}"""
        result = BaseAgent._extract_json(text)
        assert result["action"] == "graph_query"


# ── _build_output tests ──


class TestBuildOutput:
    """Test _build_output normalization against real LLM patterns."""

    def setup_method(self):
        # Create minimal agent for _build_output testing
        # Use plain MagicMock (no spec) since context is an instance attr set in __init__
        self.agent = MagicMock()
        self.agent.agent_type = "TestAgent"
        self.agent.context.node_id = "test_node_1"
        self.agent.output_contract = None

    def test_normalizes_nodes_created_from_dicts(self):
        """LLM puts full node dicts in nodes_created → normalize to string IDs."""
        self.agent.output_contract = FeatureMatrixOutput
        result = {
            "summary": "done",
            "nodes_created": [
                {"id": "node_abc", "node_type": "FeatureNode", "product": "Notion"},
                "node_def",
            ],
            "edges_created": [],
            "matrix": {"Notion": {}},
        }
        output = BaseAgent._build_output(self.agent, result)
        assert output.nodes_created == ["node_abc", "node_def"]

    def test_normalizes_edges_created_from_dicts(self):
        self.agent.output_contract = SentimentOutput
        result = {
            "summary": "done",
            "nodes_created": [],
            "edges_created": [
                {"id": "edge_1", "source_id": "a", "target_id": "b"},
                "edge_2",
            ],
            "sentiments": [],
        }
        output = BaseAgent._build_output(self.agent, result)
        assert output.edges_created == ["edge_1", "edge_2"]

    def test_moves_unknown_keys_to_data(self):
        """LLM adds extra keys → should go to data dict, not crash Pydantic."""
        self.agent.output_contract = PricingOutput
        result = {
            "summary": "done",
            "nodes_created": [],
            "edges_created": [],
            "models": [],
            "extra_field_1": {"nested": "value"},
            "extra_field_2": 42,
        }
        output = BaseAgent._build_output(self.agent, result)
        assert output.data.get("extra_field_1") == {"nested": "value"}
        assert output.data.get("extra_field_2") == 42

    def test_handles_missing_result_keys(self):
        """LLM forgets to include certain fields → Pydantic defaults should fill."""
        self.agent.output_contract = MarketPositionOutput
        result = {
            "summary": "positions analyzed",
            "nodes_created": [],
            "edges_created": [],
            # missing 'positions' → Pydantic fills with default_factory=list
        }
        output = BaseAgent._build_output(self.agent, result)
        assert output.positions == []

    def test_preserves_confidence(self):
        self.agent.output_contract = AgentOutput
        result = {
            "summary": "done",
            "nodes_created": ["n1"],
            "edges_created": [],
            "confidence": 0.85,
        }
        output = BaseAgent._build_output(self.agent, result)
        # confidence is a contract field, should be preserved
        assert output.confidence == 0.85

    def test_no_output_contract_returns_raw_dict(self):
        self.agent.output_contract = None
        result = {"summary": "done", "nodes_created": [{"id": "n1"}]}
        output = BaseAgent._build_output(self.agent, result)
        assert output == result  # unchanged


# ── _act / tool routing tests ──


class DummyTool(ToolBase):
    name = "dummy_tool"
    description = "A test tool"

    async def execute(self, **kwargs):
        return {"status": "ok", "received": kwargs}


class TestActToolRouting:
    """Test _act method for tool routing and allowed_tools enforcement."""

    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()
        reg.register(DummyTool)
        return reg

    @pytest.fixture
    def agent(self):
        a = MagicMock()
        a.agent_type = "TestAgent"
        a.allowed_tools = []
        a.tool_registry = None
        return a

    @pytest.mark.asyncio
    async def test_allowed_tool_succeeds(self, agent, registry):
        agent.allowed_tools = ["dummy_tool"]
        agent.tool_registry = registry
        result = await BaseAgent._act(agent, "dummy_tool", {"param1": "value"})
        assert result["status"] == "ok"
        assert result["received"]["param1"] == "value"

    @pytest.mark.asyncio
    async def test_disallowed_tool_returns_error_with_available_list(self, agent, registry):
        agent.allowed_tools = ["graph_query", "graph_write"]
        agent.tool_registry = registry
        result = await BaseAgent._act(agent, "dummy_tool", {})
        assert "error" in result
        assert "not available" in result["error"].lower()
        assert "graph_query" in result["error"]
        assert "graph_write" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, agent, registry):
        agent.allowed_tools = []
        agent.tool_registry = registry
        result = await BaseAgent._act(agent, "nonexistent_tool", {})
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_no_allowed_tools_skips_check(self, agent, registry):
        agent.allowed_tools = []  # empty = no restriction
        agent.tool_registry = registry
        result = await BaseAgent._act(agent, "dummy_tool", {"param1": "value"})
        assert result["status"] == "ok"


# ── Output contract validation tests ──


class TestOutputContracts:
    """Verify output contracts enforce the right shapes."""

    def test_feature_matrix_requires_matrix(self):
        with pytest.raises(Exception):
            FeatureMatrixOutput(agent_type="FeatureAnalyzer", node_id="n1", matrix=None)
        # matrix has default_factory=dict, so it's OK with missing
        output = FeatureMatrixOutput(agent_type="FeatureAnalyzer", node_id="n1")
        assert output.matrix == {}

    def test_sentiment_output_accepts_valid_data(self):
        output = SentimentOutput(
            agent_type="SentimentAnalyzer", node_id="n1",
            sentiments=[{"product": "Notion", "topic": "pricing", "sentiment_score": 0.7}],
        )
        assert len(output.sentiments) == 1
        assert output.status == "completed"

    def test_pricing_output(self):
        output = PricingOutput(
            agent_type="PricingAnalyst", node_id="n1",
            models=[{"product": "Notion", "strategy": "freemium"}],
        )
        assert len(output.models) == 1

    def test_techstack_output(self):
        output = TechStackOutput(
            agent_type="TechStackAnalyzer", node_id="n1",
            stacks=[{"product": "Notion", "languages": ["TypeScript", "Go"]}],
        )
        assert len(output.stacks) == 1

    def test_market_position_output(self):
        output = MarketPositionOutput(
            agent_type="MarketPositionAnalyzer", node_id="n1",
            positions=[{"product": "Notion", "positioning": "All-in-one workspace"}],
        )
        assert len(output.positions) == 1

    def test_agent_output_base_defaults(self):
        output = AgentOutput(agent_type="Test", node_id="n1")
        assert output.status == "completed"
        assert output.summary == ""
        assert output.nodes_created == []
        assert output.edges_created == []

    def test_degraded_status(self):
        """Ensure 'degraded' is a valid status for max_steps exhaustion."""
        output = AgentOutput(agent_type="Test", node_id="n1", status="degraded", confidence=0.05)
        assert output.status == "degraded"
        assert output.confidence == 0.05


# ── StepTrace tests ──


class TestStepTrace:
    def test_default_values(self):
        trace = StepTrace(
            task_id="t1", node_id="n1", agent_type="Test", step_number=0,
        )
        assert trace.task_id == "t1"
        assert trace.action == ""
        assert trace.confidence is None

    def test_full_trace(self):
        trace = StepTrace(
            task_id="t1", node_id="n1", agent_type="Test", step_number=1,
            observation_summary="Found 5 nodes",
            reasoning="Query Layer 2 data",
            confidence=0.85,
            action="graph_query",
            action_params={"layer": 2},
            action_result_summary="3 FeatureNodes returned",
            llm_tokens=500,
            llm_cost=0.005,
        )
        assert trace.step_number == 1
        assert trace.llm_tokens == 500
        assert trace.action == "graph_query"


# ── _think JSON correction retry tests ──


class TestThinkCorrectionRetry:
    """Test the JSON parse failure → correction retry → fallback chain in _think."""

    @pytest.fixture
    def agent(self):
        a = MagicMock()
        a.agent_type = "TestAgent"
        a.model_tier = "analysis"
        a.tool_registry = None
        a.system_prompt = "You are a test agent."
        a._extract_json = BaseAgent._extract_json  # use real JSON parser
        return a

    @pytest.mark.asyncio
    async def test_first_parse_succeeds_no_retry(self, agent):
        """Normal path: first response is valid JSON → return immediately, no retry."""
        from src.llm_gateway.gateway import LLMResponse
        resp = LLMResponse(
            content='{"action": "finalize", "result": {"summary": "ok"}, "confidence": 0.9}',
            model="test", tokens_in=10, tokens_out=5, cost=0.001,
        )
        agent.gateway = MagicMock()
        agent.gateway.chat = AsyncMock(return_value=resp)

        observation = {"nodes": [], "task": {}, "previous_actions": []}
        result = await BaseAgent._think(agent, observation)
        assert result["action"] == "finalize"
        assert result["tokens"] == 15
        assert result["cost"] == 0.001

    @pytest.mark.asyncio
    async def test_first_parse_fails_correction_succeeds(self, agent):
        """First response is garbage → retry with correction → second succeeds."""
        from src.llm_gateway.gateway import LLMResponse
        resp1 = LLMResponse(
            content="Sure, let me think about this...\n<reasoning>Maybe query graph?</reasoning>",
            model="test", tokens_in=10, tokens_out=20, cost=0.001,
        )
        resp2 = LLMResponse(
            content='{"action": "graph_query", "params": {"layer": 1}, "confidence": 0.8}',
            model="test", tokens_in=30, tokens_out=15, cost=0.002,
        )
        agent.gateway = MagicMock()
        agent.gateway.chat = AsyncMock(side_effect=[resp1, resp2])

        observation = {"nodes": [], "task": {}, "previous_actions": []}
        result = await BaseAgent._think(agent, observation)
        assert result["action"] == "graph_query"
        assert "correction retry" in result["_prompt"]
        assert result["tokens"] == 45  # resp2 tokens

    @pytest.mark.asyncio
    async def test_both_attempts_fail_fallback_finalize(self, agent):
        """Both attempts produce unparseable output → fallback finalize with low confidence."""
        from src.llm_gateway.gateway import LLMResponse
        resp1 = LLMResponse(
            content="I'll need to analyze this step by step. First, let me understand...",
            model="test", tokens_in=10, tokens_out=20, cost=0.001,
        )
        resp2 = LLMResponse(
            content="Here is my analysis:\n- point 1\n- point 2\n- point 3",
            model="test", tokens_in=30, tokens_out=25, cost=0.002,
        )
        agent.gateway = MagicMock()
        agent.gateway.chat = AsyncMock(side_effect=[resp1, resp2])

        observation = {"nodes": [], "task": {}, "previous_actions": []}
        result = await BaseAgent._think(agent, observation)
        assert result["action"] == "finalize"
        assert result["confidence"] == 0.1
        assert "JSON parse failed after retry" in result["reasoning"]
        assert result["result"]["summary"] == "LLM response could not be parsed as JSON"

    @pytest.mark.asyncio
    async def test_json_in_markdown_fence_no_retry_needed(self, agent):
        """_extract_json handles markdown fences itself → no unnecessary retry."""
        from src.llm_gateway.gateway import LLMResponse
        resp = LLMResponse(
            content='Sure! Here is the result:\n```json\n{"action": "finalize", "result": {"summary": "done"}, "confidence": 0.9}\n```',
            model="test", tokens_in=10, tokens_out=30, cost=0.001,
        )
        agent.gateway = MagicMock()
        agent.gateway.chat = AsyncMock(return_value=resp)

        observation = {"nodes": [], "task": {}, "previous_actions": []}
        result = await BaseAgent._think(agent, observation)
        assert result["action"] == "finalize"
        # No retry needed — _extract_json handled the fence


# ── DAG executor error path tests ──


class TestDagExecutorErrors:
    """Test the error handling paths in AgentExecutor.execute()."""

    @pytest.fixture
    def executor(self):
        from src.dag.executor import AgentExecutor
        mock_gateway = MagicMock()
        mock_store = MagicMock()
        mock_tools = MagicMock()
        return AgentExecutor(gateway=mock_gateway, store=mock_store, tool_registry=mock_tools)

    @pytest.fixture
    def node(self):
        from src.dag.models import DAGNode
        return DAGNode(
            node_id="test_node", agent_type="FeatureAnalyzer",
            input_query={"products": ["Notion"]}, depends_on=[],
        )

    @pytest.mark.asyncio
    async def test_agent_returns_none_raises(self, executor, node):
        """Agent returning None → RuntimeError."""
        executor._build_agent = MagicMock()
        executor._build_task = MagicMock()
        mock_agent = MagicMock()
        mock_agent.execute = AsyncMock(return_value=(None, []))  # output=None
        executor._build_agent.return_value = mock_agent

        with pytest.raises(RuntimeError, match="returned None"):
            await executor.execute(node)

    @pytest.mark.asyncio
    async def test_agent_returns_failed_status_raises(self, executor, node):
        """Agent returns status='failed' → RuntimeError."""
        executor._build_agent = MagicMock()
        executor._build_task = MagicMock()
        mock_output = MagicMock()
        mock_output.status = "failed"
        mock_output.summary = "something broke"
        mock_agent = MagicMock()
        mock_agent.execute = AsyncMock(return_value=(mock_output, []))
        executor._build_agent.return_value = mock_agent

        with pytest.raises(RuntimeError, match="failed"):
            await executor.execute(node)

    @pytest.mark.asyncio
    async def test_agent_returns_degraded_passes(self, executor, node):
        """Agent returns status='degraded' → should NOT raise."""
        executor._build_agent = MagicMock()
        executor._build_task = MagicMock()
        mock_output = MagicMock()
        mock_output.status = "degraded"
        mock_output.data = {}
        mock_agent = MagicMock()
        mock_agent.execute = AsyncMock(return_value=(mock_output, []))
        executor._build_agent.return_value = mock_agent

        # Should not raise
        await executor.execute(node)

    @pytest.mark.asyncio
    async def test_unknown_agent_type_has_clear_error(self, executor):
        """未注册 Agent 类型会给出可读错误。"""
        from src.dag.models import DAGNode
        node = DAGNode(
            node_id="bad", agent_type="NonExistentAgent",
            input_query={}, depends_on=[],
        )
        with pytest.raises(RuntimeError, match="未知 Agent 类型"):
            executor._resolve_agent_class("NonExistentAgent")

    def test_build_task_populates_all_fields(self, executor):
        """_build_task correctly maps node fields to task dict."""
        from src.dag.models import DAGNode
        node = DAGNode(
            node_id="n1", agent_type="FeatureAnalyzer",
            input_query={"products": ["Notion"]},
            depends_on=["c1"],
        )
        node.context["task_id"] = "t123"
        task = executor._build_task(node, task_id="override_id")
        assert task["task_id"] == "override_id"
        assert task["node_id"] == "n1"
        assert task["agent_type"] == "FeatureAnalyzer"
        assert task["input_query"] == {"products": ["Notion"]}
        assert task["context"]["task_id"] == "t123"
