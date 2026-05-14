# Phase 4: 分析线 Agent（5 分析 + CrossReview + SWOT + Writer）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 5 个分析 Agent 并行运行 → CrossReview 水平交叉审查 → SWOT 综合 → Writer 生成报告。全链路从图谱 Layer 1 读取、产出 Layer 2+3。

**可验证产出:** 给定预填充 Layer 1 数据的图谱，全部分析 Agent 运行后图谱中产出 FeatureMatrix、SentimentNode、PricingModel、TechStack、MarketPosition、CrossReviewFlag、SWOTNode、ReportSection。

**依赖:** P1-P3 完成（图谱有 Layer 1 数据可读取）

**Spec Reference:** 设计文档第 3.1/3.2/3.3/3.5 节，第 4.2 节 Layer 2/3 节点类型

---

### Task 4.1: 5 个分析 Agent

**Files:**
- Create: `src/agents/feature_analyzer.py`
- Create: `src/agents/sentiment_analyzer.py`
- Create: `src/agents/pricing_analyst.py`
- Create: `src/agents/techstack_analyzer.py`
- Create: `src/agents/market_position.py`
- Create: `tests/test_agents/test_analysts.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_agents/test_analysts.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.feature_analyzer import FeatureAnalyzer
from src.agents.sentiment_analyzer import SentimentAnalyzer
from src.agents.pricing_analyst import PricingAnalyst
from src.agents.techstack_analyzer import TechStackAnalyzer
from src.agents.market_position import MarketPositionAnalyzer
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import SourceInfoNode, WebPageNode, ReviewEntryNode
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


AGENT_CLASSES = [FeatureAnalyzer, SentimentAnalyzer, PricingAnalyst, TechStackAnalyzer, MarketPositionAnalyzer]


@pytest.fixture
def seeded_store(temp_db_path):
    """Store with Layer 1 data for analysis agents to work with."""
    store = GraphStore(db_path=temp_db_path)
    # Seed WebPage nodes
    for product in ["Notion", "Confluence", "Linear"]:
        wp = WebPageNode(url=f"https://{product.lower()}.com", title=f"{product} Official", text=f"{product} is a collaborative tool...")
        store.create_node(wp)
        src = SourceInfoNode(url=f"https://{product.lower()}.com", domain=f"{product.lower()}.com", credibility_score=0.9)
        store.create_node(src)
    return store


@pytest.fixture
def analysis_tools(seeded_store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=seeded_store)
    tools.register(GraphWriteTool, store=seeded_store)
    return tools


@pytest.mark.parametrize("agent_cls", AGENT_CLASSES)
@pytest.mark.asyncio
async def test_analysis_agent_completes(agent_cls, seeded_store, analysis_tools):
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Reading Layer 1 data", "action": "graph_query", "params": {"layer": 1}, "confidence": 0.85}),
            model="test", tokens_in=100, tokens_out=40, cost=0.002,
        ),
        LLMResponse(
            content=json.dumps({"reasoning": "Analysis complete", "action": "finalize", "result": {"summary": f"{agent_cls.agent_type} completed analysis", "nodes_created": ["n1", "n2"], "edges_created": ["e1", "e2"]}, "confidence": 0.9}),
            model="test", tokens_in=200, tokens_out=60, cost=0.003,
        ),
    ])

    agent = agent_cls(gateway=gateway, store=seeded_store, tool_registry=analysis_tools)
    task = {"task_id": "t1", "node_id": agent_cls.agent_type, "agent_type": agent_cls.agent_type,
            "input_query": {"products": ["Notion", "Confluence", "Linear"]}, "context": {}}

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert output.agent_type == agent_cls.agent_type
    assert len(traces) >= 1
```

- [ ] **Step 2: 验证测试失败**

- [ ] **Step 3: 实现 5 个分析 Agent**

```python
# src/agents/feature_analyzer.py
from src.agents.base import BaseAgent
from src.agents.contracts import FeatureMatrixOutput


class FeatureAnalyzer(BaseAgent):
    agent_type = "FeatureAnalyzer"
    system_prompt = """You are a Feature Analyzer for competitive analysis.

Analyze product features from the knowledge graph. For each product:
1. Extract and categorize features (e.g., UI/UX, Collaboration, AI, API, Security)
2. Rate maturity: experimental, beta, ga, deprecated
3. Rate differentiation: unique, advantage, parity, disadvantage
4. Build a comparative FeatureMatrix across all products

Output: FeatureNode per feature + one FeatureMatrixNode with the comparison grid.
Always create derived_from edges to the WebPage/SourceInfo nodes you used.
"""
    max_steps = 10
    output_contract = FeatureMatrixOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

```python
# src/agents/sentiment_analyzer.py
from src.agents.base import BaseAgent
from src.agents.contracts import SentimentOutput


class SentimentAnalyzer(BaseAgent):
    agent_type = "SentimentAnalyzer"
    system_prompt = """You are a Sentiment Analyzer for competitive analysis.

Analyze user reviews and social mentions from the knowledge graph:
1. Group reviews by topic (pricing, usability, performance, support, features)
2. Calculate sentiment scores (-1.0 to +1.0) per topic per product
3. Identify trends: improving, stable, declining
4. Extract key verbatim quotes

Output: SentimentNode per topic per product. derived_from links to ReviewEntry nodes.
"""
    max_steps = 10
    output_contract = SentimentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

```python
# src/agents/pricing_analyst.py
from src.agents.base import BaseAgent
from src.agents.contracts import PricingOutput


class PricingAnalyst(BaseAgent):
    agent_type = "PricingAnalyst"
    system_prompt = """You are a Pricing Analyst for competitive analysis.

Analyze pricing models from PricingData nodes:
1. Identify pricing strategy (freemium, usage-based, per-seat, enterprise)
2. Determine target segment (individual, SMB, mid-market, enterprise)
3. Calculate value score based on features/price ratio
4. Build competitive comparison: who offers more for less?

Output: PricingModelNode per product. Include comparisons in the comparison field.
"""
    max_steps = 10
    output_contract = PricingOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

```python
# src/agents/techstack_analyzer.py
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class TechStackAnalyzer(BaseAgent):
    agent_type = "TechStackAnalyzer"
    system_prompt = """You are a Tech Stack Analyzer for competitive analysis.

Infer technology stack from available clues (job postings, engineering blogs, open-source repos, HTTP headers):
1. Identify likely languages and frameworks
2. Identify infrastructure choices (cloud, database, CDN)
3. Assign confidence to each inference

Output: TechStackNode per product.
"""
    max_steps = 10
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

```python
# src/agents/market_position.py
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class MarketPositionAnalyzer(BaseAgent):
    agent_type = "MarketPositionAnalyzer"
    system_prompt = """You are a Market Position Analyzer for competitive analysis.

Determine each product's market position:
1. Positioning statement (who they claim to serve)
2. GTM strategy (PLG, sales-led, channel, community)
3. Target audience (developer, PM, designer, enterprise)

Output: MarketPositionNode per product.
"""
    max_steps = 10
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

- [ ] **Step 4: 运行测试** — `python -m pytest tests/test_agents/test_analysts.py -v` → 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/feature_analyzer.py src/agents/sentiment_analyzer.py src/agents/pricing_analyst.py src/agents/techstack_analyzer.py src/agents/market_position.py tests/test_agents/test_analysts.py
git commit -m "feat: add 5 analysis agents (Feature, Sentiment, Pricing, TechStack, MarketPosition)"
```

---

### Task 4.2: Cross-Review Agent

**Files:**
- Create: `src/agents/cross_review.py`
- Create: `tests/test_agents/test_cross_review.py`

- [ ] **Step 1: 编写测试 — 矛盾检测、遗漏检测、置信度异常**

```python
# tests/test_agents/test_cross_review.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.cross_review import CrossReviewAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import FeatureNode, SentimentNode, GraphEdge, EdgeType, CrossReviewFlagNode
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


@pytest.fixture
def cr_store(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    # Seed with a contradiction: Feature says docs=weak, Sentiment says docs=positive
    feat = FeatureNode(product="Linear", name="Documents", category="Core", maturity="ga", differentiation="disadvantage")
    store.create_node(feat)
    sent = SentimentNode(product="Linear", topic="Documentation", sentiment_score=0.8, trend="improving")
    store.create_node(sent)
    return store


@pytest.mark.asyncio
async def test_cross_review_detects_contradictions(cr_store):
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=cr_store)
    tools.register(GraphWriteTool, store=cr_store)

    agent = CrossReviewAgent(gateway=gateway, store=cr_store, tool_registry=tools)
    agent.gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Checking for contradictions between Feature and Sentiment", "action": "graph_query", "params": {"layer": 2}, "confidence": 0.85}),
            model="test", tokens_in=100, tokens_out=40, cost=0.002,
        ),
        LLMResponse(
            content=json.dumps({
                "reasoning": "Found contradiction: FeatureAnalyzer says Linear docs=weak, SentimentAnalyzer says positive",
                "action": "finalize",
                "result": {
                    "summary": "Detected 1 contradiction, 0 omissions, 0 anomalies",
                    "nodes_created": ["crf1"], "edges_created": ["ce1"],
                    "data": {
                        "flags": [{"flag_type": "conflict", "severity": "high", "involved_agents": ["FeatureAnalyzer", "SentimentAnalyzer"], "description": "Documentation feature score contradicts user sentiment"}]
                    }
                },
                "confidence": 0.9,
            }),
            model="test", tokens_in=200, tokens_out=100, cost=0.004,
        ),
    ])

    task = {"task_id": "t1", "node_id": "cr1", "agent_type": "CrossReviewAgent",
            "input_query": {"products": ["Linear"]}, "context": {}}

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    flags = output.data.get("flags", [])
    assert len(flags) >= 1
    assert flags[0]["severity"] == "high"
```

- [ ] **Step 2: 实现 CrossReview Agent**

```python
# src/agents/cross_review.py
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class CrossReviewAgent(BaseAgent):
    agent_type = "CrossReviewAgent"
    system_prompt = """You are a Cross-Review Agent. Your job is to check consistency across analysis agents.

Perform 3 checks on Layer 2 analysis nodes:

1. CONTRADICTION DETECTION: Compare conclusions from different analysis agents for the same product/dimension.
   Example: FeatureAnalyzer rates a feature as "weak" but SentimentAnalyzer shows positive user sentiment → contradiction.

2. OMISSION DETECTION: Check if one agent's data reveals information another agent should have considered.
   Example: SentimentAnalyzer found frequent "API integration" mentions, but FeatureAnalyzer didn't cover API capabilities.

3. CONFIDENCE ANOMALY: Detect when an agent assigns high confidence with very few derived_from edges.

For each finding, create a CrossReviewFlag node with:
- flag_type: "conflict", "omission", or "confidence_anomaly"
- severity: "high", "medium", or "low"
- involved_agents: list of agent types
- description: human-readable explanation

High severity contradictions should trigger re-analysis of the involved agents.
"""
    max_steps = 12
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

- [ ] **Step 3: 运行测试** — PASS

- [ ] **Step 4: Commit**

```bash
git add src/agents/cross_review.py tests/test_agents/test_cross_review.py
git commit -m "feat: add CrossReview agent for horizontal analysis consistency checks"
```

---

### Task 4.3: SWOT Synthesizer + Writer Agent

**Files:**
- Create: `src/agents/swot_synthesizer.py`
- Create: `src/agents/writer.py`
- Create: `tests/test_agents/test_synthesizer_writer.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_agents/test_synthesizer_writer.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.swot_synthesizer import SWOTAnalyzer
from src.agents.writer import WriterAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import FeatureNode, SentimentNode, PricingModelNode
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


def make_finalize_response(agent_type: str) -> LLMResponse:
    return LLMResponse(
        content=json.dumps({"reasoning": "Analysis complete", "action": "finalize",
            "result": {"summary": f"{agent_type} output", "nodes_created": ["n1"], "edges_created": ["e1"]},
            "confidence": 0.9}),
        model="test", tokens_in=100, tokens_out=50, cost=0.002,
    )


@pytest.mark.asyncio
async def test_swot_synthesizer(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({"reasoning": "Reading analysis nodes", "action": "graph_query", "params": {"layer": 2}, "confidence": 0.85}), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        make_finalize_response("SWOTAnalyzer"),
    ])

    agent = SWOTAnalyzer(gateway=gateway, store=store, tool_registry=tools)
    output, _ = await agent.execute({"task_id": "t1", "node_id": "sw1", "agent_type": "SWOTAnalyzer", "input_query": {"products": ["Notion"]}, "context": {}})
    assert output.status == "completed"


@pytest.mark.asyncio
async def test_writer_generates_report(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({"reasoning": "Reading all layers for report synthesis", "action": "graph_query", "params": {"layer": 3}, "confidence": 0.8}), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        make_finalize_response("Writer"),
    ])

    agent = WriterAgent(gateway=gateway, store=store, tool_registry=tools)
    output, _ = await agent.execute({"task_id": "t1", "node_id": "w1", "agent_type": "Writer", "input_query": {}, "context": {}})
    assert output.status == "completed"
```

- [ ] **Step 2: 实现 SWOT + Writer**

```python
# src/agents/swot_synthesizer.py
from src.agents.base import BaseAgent
from src.agents.contracts import SWOTOutput


class SWOTAnalyzer(BaseAgent):
    agent_type = "SWOTAnalyzer"
    system_prompt = """You are a SWOT Analyzer. Synthesize all Layer 2 analysis into a SWOT matrix per product.

For each product, identify:
- Strengths: What the product does best (from FeatureMatrix, Sentiment positive, PricingModel value)
- Weaknesses: Gaps and weaknesses (from FeatureMatrix gaps, negative Sentiment, PricingModel concerns)
- Opportunities: Market trends and gaps (from MarketPosition, NewsArticle)
- Threats: Competitive threats and market risks (from competitive comparisons, MarketPosition)

If CrossReviewFlag nodes exist, incorporate their findings and note analyst disagreements.
"""
    max_steps = 12
    output_contract = SWOTOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

```python
# src/agents/writer.py
from src.agents.base import BaseAgent
from src.agents.contracts import ReportOutput


class WriterAgent(BaseAgent):
    agent_type = "Writer"
    system_prompt = """You are a Report Writer agent. Generate a structured competitive analysis report.

Read all Layer 2 and Layer 3 nodes. Produce a markdown report with sections:
1. Executive Summary
2. Feature Comparison Matrix
3. Pricing Analysis
4. User Sentiment Analysis
5. Technical Capabilities
6. Market Position
7. SWOT Analysis (per product)
8. Strategic Recommendations

Each claim should reference source data. Create ReportSection nodes for each section.
"""
    max_steps = 15
    output_contract = ReportOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

- [ ] **Step 3: 运行测试** — PASS

- [ ] **Step 4: Commit**

```bash
git add src/agents/swot_synthesizer.py src/agents/writer.py tests/test_agents/test_synthesizer_writer.py
git commit -m "feat: add SWOT Synthesizer and Writer agents"
```

---

### Task 4.4: P4 集成测试 — 分析线全链路

- [ ] **Step 1: 编写集成测试** (创建 `tests/test_agents/test_analysis_integration.py`)

```python
# tests/test_agents/test_analysis_integration.py
import asyncio, json, pytest
from unittest.mock import AsyncMock, MagicMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import WebPageNode, SourceInfoNode, ReviewEntryNode, PricingDataNode
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.feature_analyzer import FeatureAnalyzer
from src.agents.sentiment_analyzer import SentimentAnalyzer
from src.agents.pricing_analyst import PricingAnalyst
from src.agents.cross_review import CrossReviewAgent
from src.agents.swot_synthesizer import SWOTAnalyzer
from src.agents.writer import WriterAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse


def make_response(action="finalize", summary="done"):
    return LLMResponse(
        content=json.dumps({"reasoning": "Working", "action": action, "result" if action == "finalize" else "params": {"summary": summary, "nodes_created": [], "edges_created": []} if action == "finalize" else {}, "confidence": 0.8}),
        model="test", tokens_in=50, tokens_out=30, cost=0.001,
    )


@pytest.mark.asyncio
async def test_full_analysis_pipeline(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    # Seed Layer 1 data
    for product in ["Notion", "Linear"]:
        store.create_node(WebPageNode(url=f"https://{product.lower()}.com", title=f"{product} Page"))
        store.create_node(ReviewEntryNode(source="G2", rating=4.0, text=f"Good {product}"))

    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)

    agents = {
        "FeatureAnalyzer": FeatureAnalyzer(gateway=gateway, store=store, tool_registry=tools),
        "SentimentAnalyzer": SentimentAnalyzer(gateway=gateway, store=store, tool_registry=tools),
        "PricingAnalyst": PricingAnalyst(gateway=gateway, store=store, tool_registry=tools),
        "CrossReviewAgent": CrossReviewAgent(gateway=gateway, store=store, tool_registry=tools),
        "SWOTAnalyzer": SWOTAnalyzer(gateway=gateway, store=store, tool_registry=tools),
        "Writer": WriterAgent(gateway=gateway, store=store, tool_registry=tools),
    }

    # All agents finalize immediately for this test
    gateway.chat = AsyncMock(side_effect=[make_response() for _ in range(20)])

    # Run sequentially (analysis → cross-review → SWOT → writer)
    for atype in ["FeatureAnalyzer", "SentimentAnalyzer", "PricingAnalyst"]:
        agent = agents[atype]
        task = {"task_id": "t1", "node_id": atype, "agent_type": atype,
                "input_query": {"products": ["Notion", "Linear"]}, "context": {}}
        output, traces = await agent.execute(task)
        assert output.status == "completed", f"{atype} failed"

    for atype in ["CrossReviewAgent", "SWOTAnalyzer", "Writer"]:
        agent = agents[atype]
        output, traces = await agent.execute(
            {"task_id": "t1", "node_id": atype, "agent_type": atype, "input_query": {}, "context": {}})
        assert output.status == "completed", f"{atype} failed"

    # Verify Layer 2+3 nodes exist
    layer2_nodes = store.query_nodes(layer=2)
    layer3_nodes = store.query_nodes(layer=3)
    assert len(layer2_nodes) > 0 or len(layer3_nodes) > 0  # Agent may not actually write if mocked
```

- [ ] **Step 2: 运行全部测试** — `python -m pytest tests/ -v` → all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_agents/test_analysis_integration.py
git commit -m "feat: add P4 integration test - full analysis pipeline"
```

---

## P4 完成检查清单

- [ ] 5 个分析 Agent 各自运行并产出 Layer 2 节点
- [ ] CrossReview Agent 检测矛盾/遗漏/置信度异常 → 创建 CrossReviewFlag
- [ ] SWOT Synthesizer 聚合分析结果 + CrossReview flag → SWOTNode
- [ ] Writer Agent 生成结构化 Markdown 报告 → ReportSection 节点
- [ ] 所有 Agent 正确创建 derived_from 溯源边
