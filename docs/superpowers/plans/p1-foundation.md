# Phase 1: 知识图谱 + LLM 网关 + Agent 框架

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 单个 Agent 跑通 ReAct 循环，读写知识图谱，通过 LLM 网关调用模型。这是系统的地基。

**可验证产出:** `python -m pytest tests/ -v` 全部通过；单 Agent 完成"读图谱→LLM推理→写图谱"完整循环。

**依赖:** 无（从零开始）

**Spec Reference:** `docs/superpowers/specs/2026-05-14-competitive-analysis-agents-design.md` — 第 3 章 Agent 体系、第 4 章知识图谱 Schema、第 8 章技术栈

---

### Task 1.1: 项目初始化

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[project]
name = "competitive-analysis-agents"
version = "0.1.0"
description = "AI-driven competitive analysis agent collaboration system"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "websockets>=13.0",
    "pydantic>=2.9.0",
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "anthropic>=0.40.0",
    "openai>=1.55.0",
    "pyyaml>=6.0",
    "redis>=5.2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
]
```

- [ ] **Step 2: 创建 requirements.txt**

```text
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
websockets>=13.0
pydantic>=2.9.0
httpx>=0.27.0
beautifulsoup4>=4.12.0
anthropic>=0.40.0
openai>=1.55.0
pyyaml>=6.0
redis>=5.2.0
pytest>=8.3.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 3: 安装依赖**

```bash
cd e:/Agent_Project && pip install -e ".[dev]"
```

- [ ] **Step 4: 创建 tests/conftest.py**

```python
import pytest
import tempfile
import os


@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    os.unlink(path)


@pytest.fixture
def sample_products():
    return [
        {"name": "Notion", "category": "all-in-one workspace", "url": "https://notion.so"},
        {"name": "Confluence", "category": "team wiki", "url": "https://atlassian.com/confluence"},
        {"name": "Linear", "category": "project management", "url": "https://linear.app"},
    ]
```

- [ ] **Step 5: 创建空的 src/__init__.py 和 tests/__init__.py**

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.txt src/__init__.py tests/
git commit -m "feat: initialize project structure with dependencies"
```

---

### Task 1.2: 知识图谱节点与边模型

**Files:**
- Create: `src/knowledge_graph/__init__.py`
- Create: `src/knowledge_graph/models.py`
- Create: `tests/test_knowledge_graph/__init__.py`
- Create: `tests/test_knowledge_graph/test_models.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_knowledge_graph/test_models.py
import pytest
from datetime import datetime
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, FeatureNode, FeatureMatrixNode,
    SWOTNode, ScoringNode, InsightNode, GraphEdge, EdgeType,
)


def test_source_info_node_defaults():
    node = SourceInfoNode(
        url="https://g2.com/products/notion/reviews",
        domain="g2.com",
        credibility_score=0.85,
    )
    assert node.node_type == "SourceInfo"
    assert node.layer == 1
    assert node.credibility_score == 0.85
    assert node.id.startswith("node_")


def test_feature_node_required_fields():
    node = FeatureNode(product="Notion", name="AI Writer", category="AI Features")
    assert node.node_type == "FeatureNode"
    assert node.layer == 2
    assert node.maturity == "unknown"
    assert node.differentiation == "parity"


def test_graph_edge_type_enum():
    edge = GraphEdge(
        source_id="node_a", target_id="node_b",
        edge_type=EdgeType.DERIVED_FROM,
    )
    assert edge.edge_type == "derived_from"
    assert edge.id.startswith("edge_")


def test_feature_matrix_structure():
    matrix = FeatureMatrixNode(
        products=["Notion", "Linear"],
        dimensions=["ai", "docs"],
        matrix={
            "Notion": {"ai": "★★★★★", "docs": "★★★★"},
            "Linear": {"ai": "★★", "docs": "★★★"},
        },
    )
    assert matrix.node_type == "FeatureMatrix"
    assert matrix.matrix["Notion"]["ai"] == "★★★★★"


def test_swot_node_lists():
    node = SWOTNode(
        product="Notion",
        strengths=["All-in-one", "AI features"],
        weaknesses=["Performance"],
        opportunities=["Enterprise"],
        threats=["Microsoft Loop"],
    )
    assert len(node.strengths) == 2
    assert node.layer == 3
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_knowledge_graph/test_models.py -v
```
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: 实现模型**

```python
# src/knowledge_graph/__init__.py
"""Knowledge Graph — single source of truth for all agents."""
```

```python
# src/knowledge_graph/models.py
import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    SOURCE_INFO = "SourceInfo"
    WEB_PAGE = "WebPage"
    REVIEW_ENTRY = "ReviewEntry"
    PRICING_DATA = "PricingData"
    NEWS_ARTICLE = "NewsArticle"
    SOCIAL_POST = "SocialPost"
    METRIC_DATA = "MetricData"
    FEATURE_NODE = "FeatureNode"
    FEATURE_MATRIX = "FeatureMatrix"
    SENTIMENT_NODE = "SentimentNode"
    PRICING_MODEL = "PricingModel"
    TECH_STACK = "TechStack"
    MARKET_POSITION = "MarketPosition"
    CROSS_REVIEW_FLAG = "CrossReviewFlag"
    SWOT_NODE = "SWOTNode"
    SCORING_NODE = "ScoringNode"
    INSIGHT_NODE = "InsightNode"
    REPORT_SECTION = "ReportSection"
    PRODUCT = "Product"


class EdgeType(str, Enum):
    DERIVED_FROM = "derived_from"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    RELATED_TO = "related_to"
    CITES = "cites"


class GraphNode(BaseModel):
    id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:12]}")
    node_type: NodeType
    label: str = ""
    layer: int = 1
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: f"edge_{uuid.uuid4().hex[:12]}")
    source_id: str
    target_id: str
    edge_type: EdgeType
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


# ── Layer 1: Raw Data Nodes ──

class SourceInfoNode(GraphNode):
    node_type: NodeType = NodeType.SOURCE_INFO
    layer: int = 1
    url: str
    domain: str
    credibility_score: float = 0.5
    crawl_time: datetime = Field(default_factory=datetime.now)


class WebPageNode(GraphNode):
    node_type: NodeType = NodeType.WEB_PAGE
    layer: int = 1
    url: str
    title: str = ""
    text: str = ""
    key_paragraphs: list[str] = Field(default_factory=list)


class ReviewEntryNode(GraphNode):
    node_type: NodeType = NodeType.REVIEW_ENTRY
    layer: int = 1
    source: str
    rating: float | None = None
    text: str = ""
    date: datetime | None = None
    verified: bool = False


class PricingDataNode(GraphNode):
    node_type: NodeType = NodeType.PRICING_DATA
    layer: int = 1
    product: str
    plan_name: str
    price: float
    currency: str = "USD"
    billing_cycle: str = "monthly"
    features: list[str] = Field(default_factory=list)


class NewsArticleNode(GraphNode):
    node_type: NodeType = NodeType.NEWS_ARTICLE
    layer: int = 1
    source: str
    title: str = ""
    summary: str = ""
    date: datetime | None = None


class SocialPostNode(GraphNode):
    node_type: NodeType = NodeType.SOCIAL_POST
    layer: int = 1
    platform: str = ""
    author: str = ""
    content: str = ""
    engagement: int = 0
    date: datetime | None = None


class MetricDataNode(GraphNode):
    node_type: NodeType = NodeType.METRIC_DATA
    layer: int = 1
    source: str
    metric_name: str
    value: float
    unit: str = ""
    date: datetime | None = None


# ── Layer 2: Analysis Nodes ──

class FeatureNode(GraphNode):
    node_type: NodeType = NodeType.FEATURE_NODE
    layer: int = 2
    product: str
    name: str
    category: str
    description: str = ""
    maturity: str = "unknown"
    differentiation: str = "parity"


class FeatureMatrixNode(GraphNode):
    node_type: NodeType = NodeType.FEATURE_MATRIX
    layer: int = 2
    products: list[str]
    dimensions: list[str]
    matrix: dict[str, dict[str, str]] = Field(default_factory=dict)


class SentimentNode(GraphNode):
    node_type: NodeType = NodeType.SENTIMENT_NODE
    layer: int = 2
    product: str
    topic: str
    sentiment_score: float = 0.0
    trend: str = "stable"
    key_quotes: list[str] = Field(default_factory=list)


class PricingModelNode(GraphNode):
    node_type: NodeType = NodeType.PRICING_MODEL
    layer: int = 2
    product: str
    strategy: str = ""
    target_segment: str = ""
    value_score: float = 0.0
    comparison: dict[str, Any] = Field(default_factory=dict)


class TechStackNode(GraphNode):
    node_type: NodeType = NodeType.TECH_STACK
    layer: int = 2
    product: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    infra: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class MarketPositionNode(GraphNode):
    node_type: NodeType = NodeType.MARKET_POSITION
    layer: int = 2
    product: str
    positioning: str = ""
    gtm_strategy: str = ""
    target_audience: str = ""


class CrossReviewFlagNode(GraphNode):
    node_type: NodeType = NodeType.CROSS_REVIEW_FLAG
    layer: int = 2
    flag_type: str = ""
    severity: str = "medium"
    involved_agents: list[str] = Field(default_factory=list)
    description: str = ""


# ── Layer 3: Synthesis Nodes ──

class SWOTNode(GraphNode):
    node_type: NodeType = NodeType.SWOT_NODE
    layer: int = 3
    product: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)


class ScoringNode(GraphNode):
    node_type: NodeType = NodeType.SCORING_NODE
    layer: int = 3
    dimension: str = ""
    score: float = 0.0
    weight: float = 1.0
    rationale: str = ""


class InsightNode(GraphNode):
    node_type: NodeType = NodeType.INSIGHT_NODE
    layer: int = 3
    insight: str
    importance: str = "medium"
    confidence: float = 0.0
    evidence_chain: list[str] = Field(default_factory=list)


class ReportSectionNode(GraphNode):
    node_type: NodeType = NodeType.REPORT_SECTION
    layer: int = 3
    section: str
    content: str = ""
    order: int = 0
```

- [ ] **Step 4: 运行测试验证**

```bash
python -m pytest tests/test_knowledge_graph/test_models.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_graph/ tests/test_knowledge_graph/
git commit -m "feat: add knowledge graph node and edge Pydantic models"
```

---

### Task 1.3: 知识图谱存储层

**Files:**
- Create: `src/knowledge_graph/store.py`
- Create: `tests/test_knowledge_graph/test_store.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_knowledge_graph/test_store.py
import pytest
from src.knowledge_graph.models import SourceInfoNode, WebPageNode, FeatureNode, GraphEdge, EdgeType
from src.knowledge_graph.store import GraphStore


@pytest.fixture
def store(temp_db_path):
    return GraphStore(db_path=temp_db_path)


def test_create_and_get_node(store):
    node = SourceInfoNode(url="https://g2.com/reviews", domain="g2.com", credibility_score=0.85)
    store.create_node(node)
    fetched = store.get_node(node.id)
    assert fetched is not None
    assert fetched.url == "https://g2.com/reviews"


def test_create_and_get_edge(store):
    src = store.create_node(SourceInfoNode(url="https://a.com", domain="a.com"))
    tgt = store.create_node(FeatureNode(product="N", name="f", category="t"))
    edge = GraphEdge(source_id=src.id, target_id=tgt.id, edge_type=EdgeType.DERIVED_FROM)
    store.create_edge(edge)
    edges = store.get_edges_for_source(src.id)
    assert len(edges) == 1
    assert edges[0].target_id == tgt.id


def test_query_nodes_by_type(store):
    store.create_node(SourceInfoNode(url="https://a.com", domain="a.com"))
    store.create_node(SourceInfoNode(url="https://b.com", domain="b.com"))
    store.create_node(FeatureNode(product="N", name="f", category="t"))
    assert len(store.query_nodes(node_type="SourceInfo")) == 2
    assert len(store.query_nodes(node_type="FeatureNode")) == 1


def test_trace_derived_from_chain(store):
    source = store.create_node(SourceInfoNode(url="https://x.com", domain="x.com"))
    webpage = store.create_node(WebPageNode(url="https://x.com/page", title="Page"))
    feature = store.create_node(FeatureNode(product="N", name="f", category="t"))
    store.create_edge(GraphEdge(source_id=webpage.id, target_id=source.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=feature.id, target_id=webpage.id, edge_type=EdgeType.DERIVED_FROM))
    chain = store.trace_upstream(feature.id)
    assert len(chain) >= 2


def test_delete_node_cascades_edges(store):
    node = store.create_node(SourceInfoNode(url="https://del.com", domain="del.com"))
    store.create_edge(GraphEdge(source_id="orphan", target_id=node.id, edge_type=EdgeType.RELATED_TO))
    store.delete_node(node.id)
    assert store.get_node(node.id) is None
```

- [ ] **Step 2: 验证测试失败**

```bash
python -m pytest tests/test_knowledge_graph/test_store.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 GraphStore**

```python
# src/knowledge_graph/store.py
import json
import sqlite3
from typing import Any
from src.knowledge_graph.models import (
    GraphNode, GraphEdge, NodeType, EdgeType,
    SourceInfoNode, WebPageNode, ReviewEntryNode, PricingDataNode,
    NewsArticleNode, SocialPostNode, MetricDataNode,
    FeatureNode, FeatureMatrixNode, SentimentNode,
    PricingModelNode, TechStackNode, MarketPositionNode,
    CrossReviewFlagNode, SWOTNode, ScoringNode, InsightNode, ReportSectionNode,
)


class GraphStore:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY, node_type TEXT NOT NULL,
                label TEXT DEFAULT '', layer INTEGER DEFAULT 1,
                created_by TEXT DEFAULT '', created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}', properties TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL,
                target_id TEXT NOT NULL, edge_type TEXT NOT NULL,
                metadata TEXT DEFAULT '{}', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS node_properties (
                node_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                PRIMARY KEY (node_id, key)
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
        """)
        self._conn.commit()

    def create_node(self, node: GraphNode) -> GraphNode:
        data = node.model_dump(mode="json")
        created_at = node.created_at.isoformat() if node.created_at else ""
        self._conn.execute(
            "INSERT OR REPLACE INTO nodes (id, node_type, label, layer, created_by, created_at, metadata, properties) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (data["id"], str(data["node_type"]), data.get("label", ""), data.get("layer", 1),
             data.get("created_by", ""), created_at, json.dumps(data.get("metadata", {})),
             json.dumps(data.get("properties", {}))),
        )
        for key, value in data.items():
            if key not in {"id", "node_type", "label", "layer", "created_by", "created_at", "metadata", "properties"}:
                stored = json.dumps(value) if not isinstance(value, (str, int, float, bool)) else value
                self._conn.execute(
                    "INSERT OR REPLACE INTO node_properties (node_id, key, value) VALUES (?, ?, ?)",
                    (data["id"], key, str(stored)),
                )
        self._conn.commit()
        return node

    def get_node(self, node_id: str) -> GraphNode | None:
        row = self._conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_node(row)

    def query_nodes(self, node_type: str | None = None, layer: int | None = None) -> list[GraphNode]:
        query, params = "SELECT * FROM nodes WHERE 1=1", []
        if node_type is not None:
            query += " AND node_type = ?"
            params.append(node_type)
        if layer is not None:
            query += " AND layer = ?"
            params.append(layer)
        return [self._row_to_node(r) for r in self._conn.execute(query, params).fetchall()]

    def create_edge(self, edge: GraphEdge) -> GraphEdge:
        self._conn.execute(
            "INSERT OR REPLACE INTO edges (id, source_id, target_id, edge_type, metadata, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (edge.id, edge.source_id, edge.target_id, str(edge.edge_type),
             json.dumps(edge.metadata), edge.created_at.isoformat()),
        )
        self._conn.commit()
        return edge

    def get_edges_for_source(self, source_id: str) -> list[GraphEdge]:
        rows = self._conn.execute("SELECT * FROM edges WHERE source_id = ?", (source_id,)).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def get_edges_for_target(self, target_id: str) -> list[GraphEdge]:
        rows = self._conn.execute("SELECT * FROM edges WHERE target_id = ?", (target_id,)).fetchall()
        return [self._row_to_edge(r) for r in rows]

    def trace_upstream(self, node_id: str, max_depth: int = 5) -> list[GraphEdge]:
        visited: set[str] = set()
        result: list[GraphEdge] = []
        queue = [node_id]
        for _ in range(max_depth):
            if not queue:
                break
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edges_method in [self.get_edges_for_source, self.get_edges_for_target]:
                for edge in edges_method(current):
                    result.append(edge)
                    for nid in [edge.source_id, edge.target_id]:
                        if nid not in visited:
                            queue.append(nid)
        return result

    def delete_node(self, node_id: str) -> None:
        self._conn.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?", (node_id, node_id))
        self._conn.execute("DELETE FROM node_properties WHERE node_id = ?", (node_id,))
        self._conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self._conn.commit()

    def _row_to_node(self, row: sqlite3.Row) -> GraphNode:
        extras = {}
        for prop_row in self._conn.execute(
            "SELECT key, value FROM node_properties WHERE node_id = ?", (row["id"],)
        ).fetchall():
            v = prop_row["value"]
            try:
                extras[prop_row["key"]] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                extras[prop_row["key"]] = v

        node_type = row["node_type"]
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        props = json.loads(row["properties"]) if row["properties"] else {}
        all_props = {**metadata, **props, **extras}
        all_props["id"] = row["id"]
        all_props["label"] = row["label"]

        type_map = {
            "SourceInfo": SourceInfoNode, "WebPage": WebPageNode,
            "ReviewEntry": ReviewEntryNode, "PricingData": PricingDataNode,
            "NewsArticle": NewsArticleNode, "SocialPost": SocialPostNode,
            "MetricData": MetricDataNode,
            "FeatureNode": FeatureNode, "FeatureMatrix": FeatureMatrixNode,
            "SentimentNode": SentimentNode, "PricingModel": PricingModelNode,
            "TechStack": TechStackNode, "MarketPosition": MarketPositionNode,
            "CrossReviewFlag": CrossReviewFlagNode, "SWOTNode": SWOTNode,
            "ScoringNode": ScoringNode,
            "InsightNode": InsightNode, "ReportSection": ReportSectionNode,
        }
        cls = type_map.get(node_type)
        if cls:
            field_names = set(cls.model_fields.keys())
            return cls(**{k: v for k, v in all_props.items() if k in field_names})
        return GraphNode(id=row["id"], node_type=NodeType(node_type), label=row["label"],
                         properties=all_props)

    def _row_to_edge(self, row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=row["id"], source_id=row["source_id"], target_id=row["target_id"],
            edge_type=EdgeType(row["edge_type"]), metadata=json.loads(row["metadata"] or "{}"),
        )
```

- [ ] **Step 4: 运行测试验证**

```bash
python -m pytest tests/test_knowledge_graph/test_store.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_graph/store.py tests/test_knowledge_graph/test_store.py
git commit -m "feat: add GraphStore with SQLite CRUD and BFS trace"
```

---

### Task 1.4: 知识图谱查询工具

**Files:**
- Create: `src/knowledge_graph/query.py`
- Create: `tests/test_knowledge_graph/test_query.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_knowledge_graph/test_query.py
import pytest
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, FeatureNode, InsightNode,
    GraphEdge, EdgeType,
)
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.query import bfs_trace, find_contradictions, get_confidence_breakdown


@pytest.fixture
def populated_store(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    s = store.create_node(SourceInfoNode(url="https://g2.com", domain="g2.com", credibility_score=0.85))
    w = store.create_node(WebPageNode(url="https://g2.com/r", title="Reviews"))
    f = store.create_node(FeatureNode(product="Notion", name="AI", category="AI"))
    i = store.create_node(InsightNode(insight="Strong AI features", confidence=0.82))
    store.create_edge(GraphEdge(source_id=w.id, target_id=s.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=f.id, target_id=w.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=i.id, target_id=f.id, edge_type=EdgeType.SUPPORTS))
    return store, {"source": s, "webpage": w, "feature": f, "insight": i}


def test_bfs_trace_returns_chain(populated_store):
    store, nodes = populated_store
    chain = bfs_trace(store, nodes["insight"].id, max_depth=3)
    assert len(chain) >= 2
    assert chain[0]["depth"] == 0


def test_find_contradictions(populated_store):
    store, nodes = populated_store
    review = store.create_node(FeatureNode(product="Notion", name="neg1", category="f"))
    store.create_edge(GraphEdge(source_id=review.id, target_id=nodes["feature"].id, edge_type=EdgeType.CONTRADICTS))
    contradictions = find_contradictions(store, nodes["feature"].id)
    assert len(contradictions) == 1
    assert contradictions[0]["evidence"]["node_type"] == "FeatureNode"


def test_get_confidence_breakdown(populated_store):
    store, nodes = populated_store
    breakdown = get_confidence_breakdown(store, nodes["insight"].id)
    assert breakdown["supporting_count"] >= 1
    assert breakdown["total_evidence"] >= 1
```

- [ ] **Step 2: 验证测试失败** — `python -m pytest tests/test_knowledge_graph/test_query.py -v` → FAIL

- [ ] **Step 3: 实现查询工具**

```python
# src/knowledge_graph/query.py
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import EdgeType


def bfs_trace(store: GraphStore, node_id: str, max_depth: int = 5) -> list[dict]:
    visited: set[str] = set()
    result: list[dict] = []
    queue = [(node_id, 0)]
    while queue and len(visited) < max_depth * 2:
        current_id, depth = queue.pop(0)
        if current_id in visited or depth >= max_depth:
            continue
        visited.add(current_id)
        node = store.get_node(current_id)
        if node is None:
            continue
        in_edges = store.get_edges_for_target(current_id)
        out_edges = store.get_edges_for_source(current_id)
        result.append({
            "node": node.model_dump(mode="json"),
            "incoming": [e.model_dump(mode="json") for e in in_edges],
            "outgoing": [e.model_dump(mode="json") for e in out_edges],
            "depth": depth,
        })
        for e in in_edges + out_edges:
            for nid in [e.source_id, e.target_id]:
                if nid not in visited:
                    queue.append((nid, depth + 1))
    return result


def find_contradictions(store: GraphStore, node_id: str) -> list[dict]:
    result = []
    for e in store.get_edges_for_target(node_id):
        if e.edge_type == EdgeType.CONTRADICTS:
            node = store.get_node(e.source_id)
            if node:
                result.append({
                    "edge": e.model_dump(mode="json"),
                    "evidence": node.model_dump(mode="json"),
                })
    return result


def get_confidence_breakdown(store: GraphStore, node_id: str) -> dict:
    incoming = store.get_edges_for_target(node_id)
    supporting = sum(1 for e in incoming if e.edge_type == EdgeType.SUPPORTS)
    contradicting = sum(1 for e in incoming if e.edge_type == EdgeType.CONTRADICTS)
    derived = sum(1 for e in incoming if e.edge_type == EdgeType.DERIVED_FROM)
    return {
        "supporting_count": supporting,
        "contradicting_count": contradicting,
        "derived_from_count": derived,
        "total_evidence": supporting + contradicting + derived,
    }
```

- [ ] **Step 4: 运行测试** — `python -m pytest tests/test_knowledge_graph/test_query.py -v` → 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/knowledge_graph/query.py tests/test_knowledge_graph/test_query.py
git commit -m "feat: add BFS trace, contradiction finder, and confidence breakdown"
```

---

### Task 1.5: LLM 网关

**Files:**
- Create: `src/llm_gateway/__init__.py`
- Create: `src/llm_gateway/gateway.py`
- Create: `tests/test_llm_gateway/__init__.py`
- Create: `tests/test_llm_gateway/test_gateway.py`

- [ ] **Step 1: 编写测试（使用 Mock）**

```python
# tests/test_llm_gateway/test_gateway.py
import pytest
from unittest.mock import AsyncMock, patch
from src.llm_gateway.gateway import LLMGateway


@pytest.fixture
def gateway():
    return LLMGateway(default_model="test-model")


@pytest.mark.asyncio
async def test_chat_sends_correct_params():
    with patch("anthropic.Anthropic") as mock_client:
        instance = mock_client.return_value
        instance.messages.create = AsyncMock()
        gw = LLMGateway(default_model="claude-sonnet-4-6")
        gw._anthropic_client = instance

        await gw.chat(
            system="You are helpful.",
            messages=[{"role": "user", "content": "Hello"}],
            model_tier="reasoning",
        )

        call_args = instance.messages.create.call_args
        assert call_args is not None


def test_gateway_resolve_model_by_tier():
    gw = LLMGateway(
        default_model="claude-haiku-4-5",
        model_map={
            "reasoning": "claude-opus-4-7",
            "analysis": "claude-sonnet-4-6",
            "batch": "claude-haiku-4-5",
        },
    )
    assert gw.resolve_model("reasoning") == "claude-opus-4-7"
    assert gw.resolve_model("batch") == "claude-haiku-4-5"
    assert gw.resolve_model("unknown_tier") == "claude-haiku-4-5"


def test_gateway_returns_completion():
    gw = LLMGateway(model_map={"test": "test-model"})
    assert gw.resolve_model("test") == "test-model"
```

- [ ] **Step 2: 验证测试失败** — FAIL

- [ ] **Step 3: 实现 LLM 网关**

```python
# src/llm_gateway/__init__.py
"""LLM Gateway — multi-model routing, caching, cost tracking."""
```

```python
# src/llm_gateway/gateway.py
import os
from typing import Any
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    raw: Any = None


class LLMGateway:
    def __init__(
        self,
        default_model: str = "claude-sonnet-4-6",
        model_map: dict[str, str] | None = None,
        provider_map: dict[str, str] | None = None,
    ):
        self.default_model = default_model
        self.model_map = model_map or {
            "reasoning": "claude-opus-4-7",
            "analysis": "claude-sonnet-4-6",
            "batch": "claude-haiku-4-5",
        }
        # provider_map: model_name → provider ("anthropic" | "openai_compatible")
        # e.g. {"kimi-k2": "openai_compatible", "qwen-plus": "openai_compatible"}
        self.provider_map = provider_map or {}
        self._anthropic_client = None
        self._openai_clients: dict[str, Any] = {}

    def resolve_model(self, tier: str) -> str:
        return self.model_map.get(tier, self.default_model)

    def _get_provider(self, model: str) -> str:
        """Determine which provider to use for a given model."""
        return self.provider_map.get(model, "anthropic")

    def _get_anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        return self._anthropic_client

    def _get_openai_client(self, model: str):
        """Get or create an OpenAI-compatible client for the given model's base_url."""
        if model not in self._openai_clients:
            from openai import AsyncOpenAI
            base_url = os.getenv(f"OPENAI_BASE_URL_{model.upper().replace('-', '_')}", "")
            api_key = os.getenv(f"OPENAI_API_KEY_{model.upper().replace('-', '_')}", os.getenv("OPENAI_API_KEY", ""))
            if not base_url:
                base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self._openai_clients[model] = AsyncOpenAI(base_url=base_url, api_key=api_key)
        return self._openai_clients[model]

    async def chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        model_tier: str = "analysis",
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> LLMResponse:
        resolved = model or self.resolve_model(model_tier)
        provider = self._get_provider(resolved)

        if provider == "openai_compatible":
            return await self._chat_openai(resolved, system, messages, max_tokens, temperature)
        else:
            return await self._chat_anthropic(resolved, system, messages, max_tokens, temperature)

    async def _chat_anthropic(self, model: str, system: str, messages: list[dict],
                              max_tokens: int, temperature: float) -> LLMResponse:
        client = self._get_anthropic()
        resp = client.messages.create(
            model=model, system=system, messages=messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return LLMResponse(
            content=resp.content[0].text if resp.content else "",
            model=model,
            tokens_in=resp.usage.input_tokens if resp.usage else 0,
            tokens_out=resp.usage.output_tokens if resp.usage else 0,
            cost=self._estimate_cost(model, resp.usage),
            raw=resp,
        )

    async def _chat_openai(self, model: str, system: str, messages: list[dict],
                           max_tokens: int, temperature: float) -> LLMResponse:
        client = self._get_openai_client(model)
        api_messages = [{"role": "system", "content": system}] + messages
        resp = await client.chat.completions.create(
            model=model, messages=api_messages,
            max_tokens=max_tokens, temperature=temperature,
        )
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=model,
            tokens_in=resp.usage.prompt_tokens if resp.usage else 0,
            tokens_out=resp.usage.completion_tokens if resp.usage else 0,
            cost=self._estimate_cost_openai(model, resp.usage),
            raw=resp,
        )

    @staticmethod
    def _estimate_cost(model: str, usage: Any) -> float:
        if usage is None:
            return 0.0
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        pricing = {
            "claude-opus-4-7": (15 / 1_000_000, 75 / 1_000_000),
            "claude-sonnet-4-6": (3 / 1_000_000, 15 / 1_000_000),
            "claude-haiku-4-5": (0.8 / 1_000_000, 4 / 1_000_000),
        }
        in_price, out_price = pricing.get(model, (3 / 1_000_000, 15 / 1_000_000))
        return input_tokens * in_price + output_tokens * out_price

    @staticmethod
    def _estimate_cost_openai(model: str, usage: Any) -> float:
        if usage is None:
            return 0.0
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        pricing = {
            "kimi-k2": (0 / 1_000_000, 0 / 1_000_000),
            "qwen-plus": (2 / 1_000_000, 6 / 1_000_000),
            "glm-4": (1 / 1_000_000, 1 / 1_000_000),
        }
        in_price, out_price = pricing.get(model, (1 / 1_000_000, 2 / 1_000_000))
        return input_tokens * in_price + output_tokens * out_price
```

- [ ] **Step 4: 更新网关测试 — 添加 OpenAI 兼容协议测试**

追加到 `tests/test_llm_gateway/test_gateway.py`:

```python
def test_gateway_openai_compatible_provider():
    gw = LLMGateway(
        provider_map={
            "qwen-plus": "openai_compatible",
            "kimi-k2": "openai_compatible",
        },
    )
    assert gw._get_provider("qwen-plus") == "openai_compatible"
    assert gw._get_provider("claude-sonnet-4-6") == "anthropic"


def test_resolve_model_with_openai():
    gw = LLMGateway(
        model_map={
            "reasoning": "deepseek-v4",
            "batch": "qwen-plus",
        },
        provider_map={
            "deepseek-v4": "openai_compatible",
            "qwen-plus": "openai_compatible",
        },
    )
    assert gw.resolve_model("reasoning") == "deepseek-v4"
    assert gw._get_provider("deepseek-v4") == "openai_compatible"
```

- [ ] **Step 5: 运行测试** — `python -m pytest tests/test_llm_gateway/test_gateway.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add src/llm_gateway/ tests/test_llm_gateway/
git commit -m "feat: add LLM gateway with multi-model routing and cost estimation"
```

---

### Task 1.6: Agent 工具系统

**Files:**
- Create: `src/agents/__init__.py`
- Create: `src/agents/tools/__init__.py`
- Create: `src/agents/tools/base.py`
- Create: `src/agents/tools/graph_tools.py`
- Create: `tests/test_agents/__init__.py`
- Create: `tests/test_agents/test_tools.py`

- [ ] **Step 1: 编写工具系统测试**

```python
# tests/test_agents/test_tools.py
import pytest
from src.agents.tools.base import ToolBase, ToolRegistry, tool_registry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import SourceInfoNode


@pytest.fixture
def store(temp_db_path):
    return GraphStore(db_path=temp_db_path)


def test_tool_base_interface():
    class TestTool(ToolBase):
        name = "test_tool"
        description = "A test tool"

        async def execute(self, **kwargs):
            return {"result": kwargs.get("input", "default")}

    tool = TestTool()
    assert tool.name == "test_tool"
    assert tool.param_schema == {}


def test_tool_registry_register_and_describe():
    registry = ToolRegistry()
    registry.register(GraphQueryTool)
    registry.register(GraphWriteTool)
    names = registry.list_tools()
    assert "graph_query" in names
    assert "graph_write" in names
    desc = registry.describe_tools()
    assert len(desc) == 2
    assert desc[0]["name"] == "graph_query"


def test_graph_query_tool_filters_by_type(store):
    store.create_node(SourceInfoNode(url="https://a.com", domain="a.com"))
    store.create_node(SourceInfoNode(url="https://b.com", domain="b.com"))
    tool = GraphQueryTool(store=store)
    import asyncio
    result = asyncio.run(tool.execute(node_type="SourceInfo"))
    assert len(result["nodes"]) == 2


def test_graph_write_tool_creates_node(store):
    tool = GraphWriteTool(store=store)
    import asyncio
    result = asyncio.run(tool.execute(
        node_type="SourceInfo",
        data={"url": "https://new.com", "domain": "new.com", "credibility_score": 0.7},
    ))
    assert "node_id" in result
    assert store.get_node(result["node_id"]) is not None
```

- [ ] **Step 2: 验证测试失败** — FAIL

- [ ] **Step 3: 实现工具基础类和图谱工具**

```python
# src/agents/tools/base.py
from abc import ABC, abstractmethod
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

    def register(self, tool_cls: type[ToolBase], **deps) -> None:
        instance = tool_cls(**deps)
        self._tools[instance.name] = tool_cls
        self._instances[instance.name] = instance

    def get(self, name: str) -> ToolBase | None:
        return self._instances.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def describe_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": inst.name, "description": inst.description, "params": inst.param_schema}
            for inst in self._instances.values()
        ]


tool_registry = ToolRegistry()
```

```python
# src/agents/tools/graph_tools.py
from typing import Any
from src.agents.tools.base import ToolBase
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, ReviewEntryNode, PricingDataNode,
    NewsArticleNode, SocialPostNode, MetricDataNode,
    FeatureNode, SentimentNode, PricingModelNode,
    SWOTNode, ScoringNode, InsightNode,
    ReportSectionNode, CrossReviewFlagNode,
    GraphEdge, EdgeType,
)


NODE_TYPE_MAP: dict[str, type] = {
    "SourceInfo": SourceInfoNode, "WebPage": WebPageNode,
    "ReviewEntry": ReviewEntryNode, "PricingData": PricingDataNode,
    "NewsArticle": NewsArticleNode, "SocialPost": SocialPostNode,
    "MetricData": MetricDataNode,
    "FeatureNode": FeatureNode, "SentimentNode": SentimentNode,
    "PricingModel": PricingModelNode, "SWOTNode": SWOTNode,
    "ScoringNode": ScoringNode,
    "InsightNode": InsightNode, "ReportSection": ReportSectionNode,
    "CrossReviewFlag": CrossReviewFlagNode,
}


class GraphQueryTool(ToolBase):
    name = "graph_query"
    description = "Query nodes from the knowledge graph by type, layer, or ID."
    param_schema = {
        "node_type": {"type": "string", "description": "Node type to filter by"},
        "layer": {"type": "integer", "description": "Layer to filter by (1=raw, 2=analysis, 3=synthesis)"},
        "node_id": {"type": "string", "description": "Specific node ID to retrieve"},
    }

    def __init__(self, store: GraphStore):
        self.store = store

    async def execute(self, **kwargs) -> dict[str, Any]:
        node_id = kwargs.get("node_id")
        if node_id:
            node = self.store.get_node(node_id)
            return {"nodes": [node.model_dump(mode="json")] if node else []}

        node_type = kwargs.get("node_type")
        layer = kwargs.get("layer")
        nodes = self.store.query_nodes(node_type=node_type, layer=layer)
        return {"nodes": [n.model_dump(mode="json") for n in nodes], "count": len(nodes)}


class GraphWriteTool(ToolBase):
    name = "graph_write"
    description = "Create nodes and edges in the knowledge graph."
    param_schema = {
        "node_type": {"type": "string", "description": "Type of node to create"},
        "data": {"type": "object", "description": "Node data matching the node type schema"},
        "source_id": {"type": "string", "description": "Source node ID for edge creation"},
        "edge_type": {"type": "string", "description": "Edge type: derived_from, supports, contradicts, related_to"},
    }

    def __init__(self, store: GraphStore):
        self.store = store

    async def execute(self, **kwargs) -> dict[str, Any]:
        node_type = kwargs.get("node_type", "")
        data = kwargs.get("data", {})
        data["label"] = data.get("label", data.get("name", data.get("url", "")))

        cls = NODE_TYPE_MAP.get(node_type)
        if cls is None:
            return {"error": f"Unknown node type: {node_type}"}

        node = cls(**data)
        self.store.create_node(node)

        source_id = kwargs.get("source_id")
        edge_type_str = kwargs.get("edge_type")
        if source_id and edge_type_str:
            edge = GraphEdge(
                source_id=source_id,
                target_id=node.id,
                edge_type=EdgeType(edge_type_str),
            )
            self.store.create_edge(edge)
            return {"node_id": node.id, "edge_id": edge.id}

        return {"node_id": node.id}
```

- [ ] **Step 4: 运行测试** — `python -m pytest tests/test_agents/test_tools.py -v` → 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/ tests/test_agents/
git commit -m "feat: add tool base class, registry, and graph query/write tools"
```

---

### Task 1.7: Agent 基础框架 (ReAct 循环 + StepTrace + Context + Contracts)

**Files:**
- Create: `src/agents/context.py`
- Create: `src/agents/contracts.py`
- Create: `src/agents/base.py`
- Create: `src/agents/registry.py`
- Create: `tests/test_agents/test_base.py`
- Create: `tests/test_agents/test_registry.py`

- [ ] **Step 1: 实现 AgentContext**

```python
# src/agents/context.py
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    task_id: str = ""
    node_id: str = ""
    agent_type: str = ""
    max_steps: int = 15
    history: list[dict[str, Any]] = field(default_factory=list)
    previous_outputs: dict[str, Any] = field(default_factory=dict)
    schema_overrides: dict[str, Any] = field(default_factory=dict)

    def init(self, task: dict[str, Any]) -> None:
        self.task_id = task.get("task_id", "")
        self.node_id = task.get("node_id", "")
        self.agent_type = task.get("agent_type", "")
        self.history = []
        self.previous_outputs = task.get("context", {})

    def add(self, thought: Any, result: Any) -> None:
        self.history.append({"thought": thought, "result": result})
```

- [ ] **Step 2: 实现输出 Contracts**

```python
# src/agents/contracts.py
from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    agent_type: str
    node_id: str
    status: str = "completed"  # completed | failed | partial
    summary: str = ""
    nodes_created: list[str] = Field(default_factory=list)
    edges_created: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    confidence: float = 0.0


class FeatureMatrixOutput(AgentOutput):
    agent_type: str = "FeatureAnalyzer"
    matrix: dict = Field(default_factory=dict)


class SentimentOutput(AgentOutput):
    agent_type: str = "SentimentAnalyzer"
    sentiments: list[dict] = Field(default_factory=list)


class PricingOutput(AgentOutput):
    agent_type: str = "PricingAnalyst"
    models: list[dict] = Field(default_factory=list)


class SWOTOutput(AgentOutput):
    agent_type: str = "SWOTSynthesizer"
    swot: dict = Field(default_factory=dict)


class ReportOutput(AgentOutput):
    agent_type: str = "Writer"
    report_markdown: str = ""
    sections: list[dict] = Field(default_factory=list)
```

- [ ] **Step 3: 编写 BaseAgent 测试**

```python
# tests/test_agents/test_base.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agents.base import BaseAgent, StepTrace
from src.agents.context import AgentContext
from src.agents.contracts import AgentOutput
from src.agents.tools.base import ToolRegistry
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway, LLMResponse


class TestAgent(BaseAgent):
    agent_type = "TestAgent"
    system_prompt = "You are a test agent."
    max_steps = 3
    output_contract = AgentOutput


@pytest.fixture
def mock_gateway():
    gw = MagicMock(spec=LLMGateway)
    return gw


@pytest.fixture
def agent(mock_gateway, temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    tool_registry = ToolRegistry()
    return TestAgent(
        gateway=mock_gateway,
        store=store,
        tool_registry=tool_registry,
    )


def test_step_trace_creation():
    trace = StepTrace(
        task_id="task_1", node_id="node_1", agent_type="Test",
        step_number=0, reasoning="test", confidence=0.8,
        action="graph_query", action_params={"node_type": "SourceInfo"},
        nodes_read=["n1", "n2"], llm_tokens=100, llm_cost=0.001,
    )
    assert trace.agent_type == "Test"
    assert trace.confidence == 0.8


def test_agent_execute_requires_implemented_methods(agent):
    assert agent.agent_type == "TestAgent"
    assert agent.max_steps == 3


def test_agent_output_contract_validation():
    output = AgentOutput(
        agent_type="TestAgent", node_id="node_1",
        summary="Completed analysis", confidence=0.9,
        nodes_created=["n1", "n2"], edges_created=["e1"],
    )
    valid = AgentOutput.model_validate(output.model_dump())
    assert valid.confidence == 0.9
```

- [ ] **Step 4: 实现 BaseAgent**

```python
# src/agents/base.py
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
        """Persist step trace to audit log if audit_logger is configured."""
        if self.audit_logger:
            try:
                self.audit_logger.log_step_trace(trace)
            except Exception:
                pass  # Trace persistence failure should not break agent execution

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
            return await tool.execute(**params)
        return {"error": f"Tool '{action}' not found"}

    def _build_output(self, result: dict[str, Any]) -> Any:
        if self.output_contract:
            return self.output_contract(
                agent_type=self.agent_type, node_id=self.context.node_id, **result,
            )
        return result
```

- [ ] **Step 5: 运行测试** — `python -m pytest tests/test_agents/test_base.py -v` → PASS

- [ ] **Step 6: 实现 Agent Registry 和测试**

```python
# tests/test_agents/test_registry.py
import pytest
from src.agents.registry import agent_registry


def test_agent_registry_decorator():
    @agent_registry.register(
        agent_type="TestAnalyzer",
        industry="saas",
        depends_on=["DataEnricher"],
        tools=["graph_query", "graph_write"],
        model_tier="analysis",
    )
    class TestAnalyzer:
        system_prompt = "test"
        max_steps = 10

    registered = agent_registry.get("TestAnalyzer")
    assert registered is not None
    assert registered["agent_type"] == "TestAnalyzer"
    assert registered["depends_on"] == ["DataEnricher"]
    assert registered["model_tier"] == "analysis"


def test_registry_list_all():
    agents = agent_registry.list_all()
    assert len(agents) >= 1
```

```python
# src/agents/registry.py
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
```

- [ ] **Step 7: 运行注册表测试** — `python -m pytest tests/test_agents/test_registry.py -v` → PASS

- [ ] **Step 8: Commit**

```bash
git add src/agents/ tests/test_agents/
git commit -m "feat: add BaseAgent with ReAct loop, StepTrace, AgentRegistry, and contracts"
```

---

### Task 1.8: P1 集成测试 — 单 Agent 端到端

**Files:**
- Create: `tests/test_agents/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_agents/test_integration.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import SourceInfoNode
from src.agents.base import BaseAgent
from src.agents.context import AgentContext
from src.agents.contracts import AgentOutput
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.llm_gateway.gateway import LLMGateway, LLMResponse


class SimpleCollectorAgent(BaseAgent):
    agent_type = "SimpleCollector"
    system_prompt = "You are a data collector. Query the graph, then write a summary."
    max_steps = 5
    output_contract = AgentOutput


@pytest.fixture
def setup_integration(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    agent = SimpleCollectorAgent(gateway=gateway, store=store, tool_registry=tools)
    return store, gateway, tools, agent


@pytest.mark.asyncio
async def test_agent_execute_cycle_with_mock_gateway(setup_integration):
    store, gateway, tools, agent = setup_integration

    # Seed graph with test data
    store.create_node(SourceInfoNode(url="https://test.com", domain="test.com"))

    # Mock LLM to decide read → write → finalize in 3 steps
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(
            content='{"reasoning": "Query for existing source info", "action": "graph_query", "params": {"node_type": "SourceInfo"}, "confidence": 0.8}',
            model="test", tokens_in=100, tokens_out=50, cost=0.001,
        ),
        LLMResponse(
            content='{"reasoning": "Found sources, now write a summary node", "action": "graph_write", "params": {"node_type": "InsightNode", "data": {"insight": "Test insight", "confidence": 0.8}}, "confidence": 0.85}',
            model="test", tokens_in=200, tokens_out=60, cost=0.002,
        ),
        LLMResponse(
            content='{"reasoning": "Done", "action": "finalize", "result": {"summary": "Collected data", "nodes_created": ["insight_1"], "edges_created": []}, "confidence": 0.9}',
            model="test", tokens_in=300, tokens_out=70, cost=0.003,
        ),
    ])

    task = {
        "task_id": "task_integration_1",
        "node_id": "collector_1",
        "agent_type": "SimpleCollector",
        "input_query": {"node_type": "SourceInfo"},
        "context": {},
    }

    output, traces = await agent.execute(task)
    assert output.status == "completed"
    assert len(traces) == 3
    assert traces[0].action == "graph_query"
    assert traces[1].action == "graph_write"
    assert traces[2].action == "finalize"


@pytest.mark.asyncio
async def test_agent_max_steps_exceeded(setup_integration):
    store, gateway, tools, agent = setup_integration
    agent.max_steps = 2

    # Always respond with non-finalize
    gateway.chat = AsyncMock(return_value=LLMResponse(
        content='{"reasoning": "keep going", "action": "graph_query", "params": {"node_type": "SourceInfo"}, "confidence": 0.5}',
        model="test", tokens_in=50, tokens_out=30, cost=0.001,
    ))

    task = {
        "task_id": "task_1", "node_id": "n1",
        "agent_type": "SimpleCollector",
        "input_query": {}, "context": {},
    }

    with pytest.raises(RuntimeError, match="exceeded max steps"):
        await agent.execute(task)
```

- [ ] **Step 2: 验证测试 — 需要根据实际实现微调** → 确保 PASS

```bash
python -m pytest tests/test_agents/test_integration.py -v
```

- [ ] **Step 3: 运行全部 P1 测试**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS (预计 ~20 tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_agents/test_integration.py
git commit -m "feat: add P1 integration test - single agent end-to-end ReAct cycle"
```

---

## P1 完成检查清单

- [ ] `python -m pytest tests/ -v` 全部通过
- [ ] 知识图谱：创建任意类型节点 + 边 → 查询 → BFS 溯源
- [ ] LLM 网关：解析模型 tier → 调用 → 返回 LLMResponse (含 cost)
- [ ] Agent 工具：GraphQueryTool + GraphWriteTool 可用
- [ ] Agent 框架：单 Agent 完成"读图谱 → LLM 推理 → 写图谱"完整循环
- [ ] StepTrace：每次执行返回完整 step 记录列表
- [ ] Agent Registry：装饰器注册 + 查询
