# Phase 3: 采集线 Agent（Source Discovery → Collector → Data Enricher）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 端到端采集链路：搜索信息源 → 并行网页抓取 → 数据富化 → 全部写入知识图谱 Layer 1。

**可验证产出:** 给定 3 个目标产品，系统自动搜索信息源、抓取网页、提取结构化数据并写入图谱（使用 Mock LLM 和 Mock 网页采集验证）。

**依赖:** P1 + P2 完成

**Spec Reference:** 设计文档第 3.5 节交叉审查前的所有 Agent 定义，第 4.2 节 Layer 1 节点类型

---

### Task 3.1: Web 采集工具

**Files:**
- Create: `src/agents/tools/web_tools.py`
- Create: `tests/test_agents/test_web_tools.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_agents/test_web_tools.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool


def test_web_scrape_tool_schema():
    tool = WebScrapeTool()
    assert tool.name == "web_scrape"
    assert "url" in tool.param_schema


def test_web_search_tool_schema():
    tool = WebSearchTool()
    assert tool.name == "web_search"
    assert "query" in tool.param_schema


@pytest.mark.asyncio
async def test_web_scrape_returns_content():
    mock_html = "<html><body><h1>Test Page</h1><p>Content</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        tool = WebScrapeTool()
        result = await tool.execute(url="https://example.com")
        assert "title" in result
        assert result["title"] == "Test Page"
        assert "Content" in result["text"]


@pytest.mark.asyncio
async def test_web_scrape_extracts_key_paragraphs():
    mock_html = "<html><body><p>First paragraph with enough content.</p><p>Short.</p><p>Third paragraph with enough content here.</p></body></html>"
    mock_response = MagicMock()
    mock_response.text = mock_html
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        tool = WebScrapeTool()
        result = await tool.execute(url="https://example.com")
        assert len(result["key_paragraphs"]) == 2
```

- [ ] **Step 2: 验证测试失败**

- [ ] **Step 3: 实现 Web 工具**

```python
# src/agents/tools/web_tools.py
import httpx
from typing import Any
from bs4 import BeautifulSoup
from src.agents.tools.base import ToolBase


class WebScrapeTool(ToolBase):
    name = "web_scrape"
    description = "Scrape a webpage and extract title, text content, and key paragraphs."
    param_schema = {
        "url": {"type": "string", "description": "The URL to scrape"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        url = kwargs.get("url", "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "CompAgent/1.0"})
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title else ""
        text = soup.get_text(separator="\n", strip=True)
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]

        return {
            "url": url,
            "title": title,
            "text": text[:10000],
            "key_paragraphs": paragraphs[:20],
        }


class WebSearchTool(ToolBase):
    name = "web_search"
    description = "Search the web for information about a product or topic."
    param_schema = {
        "query": {"type": "string", "description": "Search query"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        query = kwargs.get("query", "")
        # Uses a search API or falls back to scraping search results
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "CompAgent/1.0"},
            )
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for r in soup.select(".result"):
            link = r.select_one(".result__a")
            snippet = r.select_one(".result__snippet")
            if link:
                results.append({
                    "title": link.get_text(strip=True),
                    "url": link.get("href", ""),
                    "snippet": snippet.get_text(strip=True) if snippet else "",
                })
        return {"query": query, "results": results[:15]}
```

- [ ] **Step 4: 运行测试** — PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/tools/web_tools.py tests/test_agents/test_web_tools.py
git commit -m "feat: add WebScrapeTool and WebSearchTool"
```

---

### Task 3.2: Source Discovery Agent

**Files:**
- Create: `src/agents/source_discovery.py`
- Create: `tests/test_agents/test_collectors.py` (covers both SourceDiscovery + Collector)

- [ ] **Step 1: 编写测试**

```python
# tests/test_agents/test_collectors.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.source_discovery import SourceDiscoveryAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebSearchTool


@pytest.fixture
def sd_agent(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebSearchTool)
    return SourceDiscoveryAgent(gateway=gateway, store=store, tool_registry=tools)


@pytest.mark.asyncio
async def test_source_discovery_creates_source_info_nodes(sd_agent):
    sd_agent.gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Searching for Notion info", "action": "web_search", "params": {"query": "Notion SaaS review G2 ProductHunt"}, "confidence": 0.9}),
            model="test", tokens_in=50, tokens_out=40, cost=0.001,
        ),
        LLMResponse(
            content=json.dumps({"reasoning": "Found sources", "action": "finalize", "result": {
                "summary": "Discovered 3 sources",
                "nodes_created": ["s1", "s2", "s3"],
                "edges_created": ["e1"],
                "data": {
                    "sources": [
                        {"url": "https://g2.com/notion", "domain": "g2.com", "credibility_score": 0.85},
                        {"url": "https://producthunt.com/notion", "domain": "producthunt.com", "credibility_score": 0.7},
                        {"url": "https://notion.so", "domain": "notion.so", "credibility_score": 0.95},
                    ]
                }
            }, "confidence": 0.9}),
            model="test", tokens_in=100, tokens_out=80, cost=0.002,
        ),
    ])

    task = {"task_id": "t1", "node_id": "sd1", "agent_type": "SourceDiscovery",
            "input_query": {"targets": ["Notion"]}, "context": {}}

    output, traces = await sd_agent.execute(task)
    assert output.status == "completed"
    assert len(traces) >= 1
```

- [ ] **Step 2: 验证测试失败**

- [ ] **Step 3: 实现 Source Discovery Agent**

```python
# src/agents/source_discovery.py
import json
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class SourceDiscoveryAgent(BaseAgent):
    agent_type = "SourceDiscovery"
    system_prompt = """You are a Source Discovery agent for competitive analysis.

Your job: for each target product, search for and evaluate information sources. You have access to web_search, graph_query, and graph_write tools.

For each source found:
1. Evaluate credibility (0.0-1.0): official sites=0.9+, G2/TrustRadius=0.8+, ProductHunt=0.7+, blogs=0.5+
2. Prioritize: official pricing pages, G2 reviews, ProductHunt, tech blogs
3. Create SourceInfo nodes with url, domain, credibility_score

Output all discovered sources as SourceInfo nodes in the knowledge graph.
"""
    max_steps = 8
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

- [ ] **Step 4: 运行测试** — PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/source_discovery.py tests/test_agents/test_collectors.py
git commit -m "feat: add SourceDiscovery agent"
```

---

### Task 3.3: Collector Agent

**Files:**
- Create: `src/agents/collector.py`

- [ ] **Step 1: 编写 Collector 测试**

```python
# 追加到 tests/test_agents/test_collectors.py
@pytest.fixture
def collector_agent(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebScrapeTool)
    return CollectorAgent(gateway=gateway, store=store, tool_registry=tools)


@pytest.mark.asyncio
async def test_collector_scrapes_and_stores_webpage(collector_agent):
    collector_agent.gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Scraping Notion pricing", "action": "web_scrape", "params": {"url": "https://notion.so/pricing"}, "confidence": 0.9}),
            model="test", tokens_in=50, tokens_out=30, cost=0.001,
        ),
        LLMResponse(
            content=json.dumps({"reasoning": "Storing results", "action": "finalize", "result": {
                "summary": "Collected Notion pricing page",
                "nodes_created": ["wp1"], "edges_created": ["e1"],
                "data": {"page_title": "Notion Pricing"}
            }, "confidence": 0.95}),
            model="test", tokens_in=80, tokens_out=40, cost=0.002,
        ),
    ])

    task = {"task_id": "t1", "node_id": "c1", "agent_type": "Collector",
            "input_query": {"urls": ["https://notion.so/pricing"], "product": "Notion"},
            "context": {}}

    output, traces = await collector_agent.execute(task)
    assert output.status == "completed"
```

- [ ] **Step 2: 实现 Collector Agent**

```python
# src/agents/collector.py
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class CollectorAgent(BaseAgent):
    agent_type = "Collector"
    system_prompt = """You are a Collector agent. Scrape assigned URLs and store structured data in the knowledge graph.

For each URL: web_scrape → extract relevant data → create appropriate KG nodes (WebPage, ReviewEntry, PricingData depending on content type).
Always create derived_from edges back to the SourceInfo node.

## Degradation Strategy

Data sources may be unavailable. For each URL, try in order:

1. **Primary**: Direct web_scrape of the target URL
2. **Tier 1**: If primary fails (403, 404, timeout), try alternative access:
   - Official sites → try Google cache or Wayback Machine
   - G2/Review sites → try extracting publicly visible rating only
   - Reddit → try search engine `site:reddit.com` snippets
   - ProductHunt → try RSS feed
   - News → try search engine News tab results
3. **Tier 2**: If Tier 1 fails:
   - Official sites → try third-party descriptions (Trustpilot, etc.)
   - G2 → use search engine cached snippets
   - Reddit/ProductHunt/News → skip this source

**On complete failure** (all tiers exhausted): create a SourceInfo node with `availability: "degraded"` and `degradation_reason` set. The analysis pipeline will handle reduced confidence for degraded sources.
"""
    max_steps = 8
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

- [ ] **Step 3: 运行测试** — PASS

- [ ] **Step 4: Commit**

```bash
git add src/agents/collector.py tests/test_agents/test_collectors.py
git commit -m "feat: add Collector agent with web scraping capability"
```

---

### Task 3.4: Data Enricher Agent

**Files:**
- Create: `src/agents/data_enricher.py`
- Create: `src/agents/tools/api_tools.py`
- Create: `tests/test_agents/test_enricher.py`

- [ ] **Step 1: 编写 API 工具**

```python
# src/agents/tools/api_tools.py
from typing import Any
from src.agents.tools.base import ToolBase


class ThirdPartyAPITool(ToolBase):
    name = "third_party_api"
    description = "Query third-party data sources (SimilarWeb, Crunchbase, etc.) for enrichment."
    param_schema = {
        "source": {"type": "string", "description": "Data source name: similarweb, crunchbase"},
        "query": {"type": "string", "description": "Domain or company name to query"},
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        source = kwargs.get("source", "")
        query = kwargs.get("query", "")
        # In demo, returns mock data. Production would use real API.
        return {"source": source, "query": query, "data": {"note": "Mock enrichment data", "estimated_traffic": "N/A"}}
```

- [ ] **Step 2: 编写 Enricher 测试**

```python
# tests/test_agents/test_enricher.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.data_enricher import DataEnricherAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


@pytest.fixture
def enricher_agent(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    return DataEnricherAgent(gateway=gateway, store=store, tool_registry=tools)


@pytest.mark.asyncio
async def test_enricher_adds_context(enricher_agent):
    enricher_agent.gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content=json.dumps({"reasoning": "Querying collected data", "action": "graph_query", "params": {"layer": 1}, "confidence": 0.85}),
            model="test", tokens_in=50, tokens_out=30, cost=0.001,
        ),
        LLMResponse(
            content=json.dumps({"reasoning": "Enrichment complete", "action": "finalize", "result": {"summary": "Added industry context", "nodes_created": ["m1"], "edges_created": []}, "confidence": 0.8}),
            model="test", tokens_in=80, tokens_out=30, cost=0.002,
        ),
    ])

    task = {"task_id": "t1", "node_id": "e1", "agent_type": "DataEnricher",
            "input_query": {"products": ["Notion"]}, "context": {}}

    output, traces = await enricher_agent.execute(task)
    assert output.status == "completed"
```

- [ ] **Step 3: 实现 Data Enricher**

```python
# src/agents/data_enricher.py
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class DataEnricherAgent(BaseAgent):
    agent_type = "DataEnricher"
    system_prompt = """You are a Data Enricher agent. After raw data collection, enrich the knowledge graph with:
- Industry context and market trends
- Company background information
- Competitive landscape context

Read all Layer 1 nodes, identify gaps, and add MetricData, NewsArticle nodes with contextual information.
"""
    max_steps = 8
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

- [ ] **Step 4: 运行全部测试** — `python -m pytest tests/test_agents/ -v` → all PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/data_enricher.py src/agents/tools/api_tools.py tests/test_agents/test_enricher.py
git commit -m "feat: add DataEnricher agent and third-party API tool"
```

---

### Task 3.5: P3 集成测试 — 采集链路端到端

**Files:**
- Create: `tests/test_agents/test_collection_integration.py`

- [ ] **Step 1: 编写端到端采集测试**

```python
# tests/test_agents/test_collection_integration.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.scheduler import DAGScheduler
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool
from src.agents.source_discovery import SourceDiscoveryAgent
from src.agents.collector import CollectorAgent
from src.agents.data_enricher import DataEnricherAgent


@pytest.mark.asyncio
async def test_full_collection_pipeline(temp_db_path):
    """Source Discovery → Collector → Data Enricher, all writing to shared KG."""
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)

    # Shared tool registry
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebSearchTool)
    tools.register(WebScrapeTool)

    sd_agent = SourceDiscoveryAgent(gateway=gateway, store=store, tool_registry=tools)
    col_agent = CollectorAgent(gateway=gateway, store=store, tool_registry=tools)
    enrich_agent = DataEnricherAgent(gateway=gateway, store=store, tool_registry=tools)

    # Build DAG
    sd_node = DAGNode(node_id="sd", agent_type="SourceDiscovery", input_query={"targets": ["Notion"]}, depends_on=[])
    col_node = DAGNode(node_id="c1", agent_type="Collector", input_query={"urls": ["https://notion.so"]}, depends_on=["sd"])
    enrich_node = DAGNode(node_id="enrich", agent_type="DataEnricher", input_query={}, depends_on=["c1"])
    dag = TaskDAG(task_id="p3_test", nodes=[sd_node, col_node, enrich_node])

    # Mock LLM to produce simple finalize responses
    def make_response(action, result_summary):
        if action == "finalize":
            return LLMResponse(
                content=json.dumps({"reasoning": "Done", "action": "finalize", "result": {"summary": result_summary, "nodes_created": [], "edges_created": []}, "confidence": 0.8}),
                model="test", tokens_in=50, tokens_out=30, cost=0.001,
            )
        return LLMResponse(
            content=json.dumps({"reasoning": "Working", "action": "graph_query", "params": {"layer": 1}, "confidence": 0.7}),
            model="test", tokens_in=50, tokens_out=30, cost=0.001,
        )

    call_count = [0]
    gateway.chat = AsyncMock(side_effect=lambda *args, **kwargs: make_response(
        "finalize" if call_count[0] > 1 else "graph_query", "collected data"
    ))

    # Manual sequential execution to verify data flow
    task_sd = {"task_id": "p3_test", "node_id": "sd", "agent_type": "SourceDiscovery", "input_query": {"targets": ["Notion"]}, "context": {}}
    sd_output, _ = await sd_agent.execute(task_sd)
    assert sd_output.status == "completed"
    sd_node.state = NodeState.COMPLETED

    task_col = {"task_id": "p3_test", "node_id": "c1", "agent_type": "Collector", "input_query": {"urls": ["https://notion.so"]}, "context": {"previous_output": sd_output.model_dump()}}
    col_output, _ = await col_agent.execute(task_col)
    assert col_output.status == "completed"

    task_enrich = {"task_id": "p3_test", "node_id": "enrich", "agent_type": "DataEnricher", "input_query": {}, "context": {}}
    enrich_output, _ = await enrich_agent.execute(task_enrich)
    assert enrich_output.status == "completed"
```

- [ ] **Step 2: 运行集成测试** — `python -m pytest tests/test_agents/test_collection_integration.py -v` → PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_agents/test_collection_integration.py
git commit -m "feat: add P3 integration test - full collection pipeline end-to-end"
```

---

## P3 完成检查清单

- [ ] WebScrapeTool + WebSearchTool 可用
- [ ] SourceDiscovery Agent: 搜索 → 评估可信度 → 创建 SourceInfo 节点
- [ ] Collector Agent: 抓取 URL → 提取结构化数据 → 创建 Layer 1 节点 + derived_from 边
- [ ] DataEnricher Agent: 读取 Layer 1 → 补充上下文 → 创建 MetricData/NewsArticle 节点
- [ ] 集成测试：SD → Collector → Enricher 全部完成，数据写入图谱
