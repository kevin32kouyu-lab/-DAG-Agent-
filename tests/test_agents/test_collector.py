"""测试 CollectorAgent（URL 发现层）— 验证职责精简后的核心行为。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.collector import CollectorAgent
from src.agents.contracts import AgentOutput


@pytest.fixture
def mock_deps():
    """构造 Collector 依赖的 mock 对象。"""
    gateway = MagicMock()
    store = MagicMock()
    tool_registry = MagicMock()
    tool_registry.describe_tools.return_value = []
    tool_registry.get.return_value = None
    tool_registry.list_tools.return_value = []
    return gateway, store, tool_registry


@pytest.fixture
def collector(mock_deps):
    gateway, store, tool_registry = mock_deps
    return CollectorAgent(
        gateway=gateway, store=store, tool_registry=tool_registry,
    )


class TestCollectorConfig:
    """Collector 配置应该收缩到 URL 发现职责。"""

    def test_agent_type(self, collector):
        assert collector.agent_type == "Collector"

    def test_max_steps_reduced(self, collector):
        """步数从 12 砍到 5，避免长循环。"""
        assert collector.max_steps == 5

    def test_token_budget_reduced(self, collector):
        """token 预算从 300k 降到 100k。"""
        assert collector.token_budget == 100_000

    def test_allowed_tools_only_discovery(self, collector):
        """工具清单只剩 URL 发现 + 图写入。"""
        expected = {"serper_search", "tavily", "graph_write", "graph_query"}
        assert set(collector.allowed_tools) == expected

    def test_no_scrape_tools(self, collector):
        """不应该再有抓取类工具。"""
        forbidden = {"web_scrape", "batch_web_scrape", "firecrawl"}
        assert not (set(collector.allowed_tools) & forbidden)

    def test_model_tier(self, collector):
        assert collector.model_tier == "analysis"


class TestActionTracking:
    """动作历史追踪用于 think 阶段的提示生成。"""

    @pytest.mark.asyncio
    async def test_action_recorded_after_act(self, collector):
        collector._actions_taken = []
        collector.tool_registry.get.return_value = None
        await collector._act("serper_search", {"query": "飞书"})
        assert "serper_search" in collector._actions_taken

    @pytest.mark.asyncio
    async def test_multiple_actions_tracked_in_order(self, collector):
        collector._actions_taken = []
        collector.tool_registry.get.return_value = None
        await collector._act("serper_search", {"query": "x"})
        await collector._act("graph_write", {"node_type": "SourceInfo", "data": {"url": "y"}})
        assert collector._actions_taken == ["serper_search", "graph_write"]


class TestThinkWarning:
    """think 阶段应该在 step≥3 未写入时注入警告。"""

    @pytest.mark.asyncio
    async def test_no_warning_at_step_1(self, collector):
        collector._actions_taken = ["serper_search"]
        called_with = {}

        async def fake_super_think(self, observation):
            called_with["obs"] = observation
            return {"action": "finalize", "result": {}}

        from src.agents.base import BaseAgent
        original = BaseAgent._think
        BaseAgent._think = fake_super_think
        try:
            await collector._think({"task": {}})
            assert "_warning" not in called_with["obs"]
        finally:
            BaseAgent._think = original

    @pytest.mark.asyncio
    async def test_warning_at_step_3_no_write(self, collector):
        collector._actions_taken = ["serper_search", "tavily", "serper_search"]
        called_with = {}

        async def fake_super_think(self, observation):
            called_with["obs"] = observation
            return {"action": "finalize", "result": {}}

        from src.agents.base import BaseAgent
        original = BaseAgent._think
        BaseAgent._think = fake_super_think
        try:
            await collector._think({"task": {}})
            assert "_warning" in called_with["obs"]
            assert "graph_write" in called_with["obs"]["_warning"]
        finally:
            BaseAgent._think = original

    @pytest.mark.asyncio
    async def test_no_warning_after_graph_write(self, collector):
        collector._actions_taken = ["serper_search", "serper_search", "graph_write"]
        called_with = {}

        async def fake_super_think(self, observation):
            called_with["obs"] = observation
            return {"action": "finalize", "result": {}}

        from src.agents.base import BaseAgent
        original = BaseAgent._think
        BaseAgent._think = fake_super_think
        try:
            await collector._think({"task": {}})
            assert "_warning" not in called_with["obs"]
        finally:
            BaseAgent._think = original


class TestDegradationContext:
    """降级上下文注入逻辑保留（不影响新职责）。"""

    def test_no_sources_no_injection(self, collector):
        task = {"context": {}}
        collector._inject_degradation_context(task)
        assert "degradation_tiers" not in task.get("context", {})

    def test_string_sources_handled(self, collector):
        task = {"context": {"sources": ["G2"]}}
        # 不应抛异常
        collector._inject_degradation_context(task)

    def test_dict_sources_handled(self, collector):
        task = {"context": {"sources": [{"name": "ProductHunt"}]}}
        # 不应抛异常
        collector._inject_degradation_context(task)


class TestPromptIntegrity:
    """system prompt 应该明确禁止抓取动作。"""

    def test_prompt_mentions_url_discovery(self, collector):
        assert "URL Discovery" in collector.system_prompt

    def test_prompt_forbids_scraping(self, collector):
        assert "DO NOT scrape" in collector.system_prompt

    def test_prompt_lists_url_types(self, collector):
        for ut in ("homepage", "pricing", "review"):
            assert ut in collector.system_prompt

    def test_prompt_mentions_5_steps_limit(self, collector):
        assert "5 steps" in collector.system_prompt
