"""测试 Analyst Agent 的维度切换逻辑。"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.agents.analyst import AnalystAgent, _DIMENSION_CONFIGS, _build_analyst_system_prompt, _get_analyst_tools, _get_analyst_model_tier


@pytest.fixture
def mock_deps():
    gateway = MagicMock()
    gateway.chat = AsyncMock(return_value=MagicMock(content='{"reasoning":"test","action":"finalize","result":{"summary":"done"},"confidence":0.8}', tokens_in=10, tokens_out=10, cost=0.0))
    gateway.cost_tracker = MagicMock()
    gateway.cost_tracker.total_tokens = 0
    store = MagicMock()
    store.query_nodes = MagicMock(return_value=[])
    tool_registry = MagicMock()
    tool_registry.describe_tools.return_value = []
    tool_registry.get.return_value = None
    tool_registry.list_tools.return_value = []
    return gateway, store, tool_registry


@pytest.fixture
def analyst(mock_deps):
    gateway, store, tool_registry = mock_deps
    return AnalystAgent(gateway=gateway, store=store, tool_registry=tool_registry)


class TestDimensionConfigs:
    """测试：6 种分析维度配置完整性。"""

    def test_all_dimensions_exist(self):
        expected = {"feature", "sentiment", "pricing", "techstack", "market_position", "cross_review"}
        assert set(_DIMENSION_CONFIGS.keys()) == expected

    def test_each_dimension_has_prompt(self):
        for dim, config in _DIMENSION_CONFIGS.items():
            assert "prompt" in config, f"{dim} missing prompt"
            assert len(config["prompt"]) > 100, f"{dim} prompt too short"

    def test_each_dimension_has_tools(self):
        for dim, config in _DIMENSION_CONFIGS.items():
            assert "tools" in config, f"{dim} missing tools"
            assert len(config["tools"]) >= 2, f"{dim} needs at least 2 tools"

    def test_each_dimension_has_model_tier(self):
        for dim, config in _DIMENSION_CONFIGS.items():
            assert "model_tier" in config, f"{dim} missing model_tier"

    def test_feature_has_firecrawl(self):
        """feature 维度主力 Firecrawl + web_scrape 兜底。"""
        tools = _DIMENSION_CONFIGS["feature"]["tools"]
        assert "firecrawl" in tools
        assert "web_scrape" in tools

    def test_pricing_uses_web_scrape_not_firecrawl_first(self):
        """pricing 维度优先 web_scrape 节省 Firecrawl 配额。"""
        tools = _DIMENSION_CONFIGS["pricing"]["tools"]
        assert "web_scrape" in tools
        # 不应直接列 firecrawl（节省配额，用 tavily 兜底）
        assert "firecrawl" not in tools

    def test_sentiment_uses_api_only(self):
        """sentiment 维度纯 API：reddit + producthunt + social_media。"""
        tools = _DIMENSION_CONFIGS["sentiment"]["tools"]
        assert "reddit" in tools
        assert "producthunt" in tools
        assert "social_media" in tools
        # 不应该爬网页
        assert "web_scrape" not in tools
        assert "firecrawl" not in tools

    def test_techstack_has_github(self):
        assert "github" in _DIMENSION_CONFIGS["techstack"]["tools"]
        assert "gitee" in _DIMENSION_CONFIGS["techstack"]["tools"]
        assert "npm" in _DIMENSION_CONFIGS["techstack"]["tools"]

    def test_market_position_has_newsapi(self):
        """market_position 维度主力 newsapi + google_trends。"""
        tools = _DIMENSION_CONFIGS["market_position"]["tools"]
        assert "newsapi" in tools
        assert "google_trends" in tools

    def test_cross_review_only_reads_graph(self):
        """交叉审查只读写图谱，不需要外部搜索工具。"""
        tools = _DIMENSION_CONFIGS["cross_review"]["tools"]
        assert tools == ["graph_query", "graph_write"]

    def test_no_dimension_exceeds_4_tools_plus_graph(self):
        """每个维度工具数 ≤ 6（含 graph_query/write 共 2 个）。"""
        for dim, config in _DIMENSION_CONFIGS.items():
            assert len(config["tools"]) <= 6, f"{dim} has too many tools: {config['tools']}"


class TestDimensionSwitching:
    """测试：维度切换时 prompt/tools/model_tier 正确更新。"""

    @pytest.mark.asyncio
    async def test_default_dimension_is_feature(self, analyst):
        """没有指定 dimension 时，默认用 feature。"""
        task = {"input_query": {}, "context": {}}
        await analyst.execute(task)
        assert analyst._dimension == "feature"

    @pytest.mark.asyncio
    async def test_reads_dimension_from_input_query(self, analyst):
        """从 input_query.dimension 读取维度。"""
        task = {"input_query": {"dimension": "pricing"}, "context": {}}
        await analyst.execute(task)
        assert analyst._dimension == "pricing"

    @pytest.mark.asyncio
    async def test_reads_dimension_from_context(self, analyst):
        """从 context.dimension 读取维度（input_query 没有时）。"""
        task = {"input_query": {}, "context": {"dimension": "sentiment"}}
        await analyst.execute(task)
        assert analyst._dimension == "sentiment"

    def test_build_prompt_for_known_dimension(self):
        prompt = _build_analyst_system_prompt("feature")
        assert "Feature Analyzer" in prompt

    def test_build_prompt_for_unknown_dimension(self):
        prompt = _build_analyst_system_prompt("unknown_dim")
        assert "Unknown dimension" in prompt

    def test_get_tools_for_feature(self):
        tools = _get_analyst_tools("feature")
        assert "graph_query" in tools
        assert "firecrawl" in tools
        assert "web_scrape" in tools
        assert "tavily" not in tools  # feature 不用 tavily

    def test_get_tools_for_unknown(self):
        tools = _get_analyst_tools("unknown")
        assert tools == ["graph_query", "graph_write"]

    def test_get_model_tier_for_cross_review(self):
        tier = _get_analyst_model_tier("cross_review")
        assert tier == "analysis"

    def test_get_model_tier_for_sentiment(self):
        tier = _get_analyst_model_tier("sentiment")
        assert tier == "analysis"


class TestAnalystConfig:
    """测试：Analyst 基础配置。"""

    def test_agent_type(self, analyst):
        assert analyst.agent_type == "Analyst"

    def test_depends_on_collector(self):
        """Analyst 应该依赖 Collector（在 registry 中注册）。"""
        from src.agents.registry import agent_registry
        info = agent_registry.get("Analyst")
        assert info is not None
        assert "Collector" in info["depends_on"]

    def test_registry_has_all_dimension_tools(self):
        """Analyst 注册的 tools 应包含所有维度的工具合集。"""
        from src.agents.registry import agent_registry
        info = agent_registry.get("Analyst")
        assert info is not None
        registered_tools = set(info["tools"])
        all_tools = set()
        for config in _DIMENSION_CONFIGS.values():
            all_tools.update(config["tools"])
        assert all_tools.issubset(registered_tools)
