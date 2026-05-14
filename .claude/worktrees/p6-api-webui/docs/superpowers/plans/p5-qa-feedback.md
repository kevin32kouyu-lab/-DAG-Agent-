# Phase 5: QA 双审 + 反馈边闭环

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** QA #1（事实核查）+ QA #2（逻辑一致性）审查报告，发现问题时 DAG 反馈边触发受影响子图重跑（最多 2 轮）。

**可验证产出:** QA 审查 Writer 输出 → 标记问题节点 → DAG 仅重置受影响节点 → 重新执行 → QA 再次审查通过 or DEGRADED。

**依赖:** P1-P4 完成（有完整 Agent 链可 QA）

**Spec Reference:** 设计文档第 3.1 节 Agent #12/#13，第 5.2 节反馈边处理，第 6.4 节 QA 数据流

---

### Task 5.1: QA Agent 实现

**Files:**
- Create: `src/agents/qa_fact_check.py`
- Create: `src/agents/qa_logic_check.py`
- Create: `tests/test_agents/test_qa.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_agents/test_qa.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.qa_fact_check import QAFactCheckAgent
from src.agents.qa_logic_check import QALogicCheckAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import InsightNode, ReportSectionNode, WebPageNode, SourceInfoNode, GraphEdge, EdgeType
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


@pytest.fixture
def qa_store(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    # Seed a report section with a complete trace chain
    source = store.create_node(SourceInfoNode(url="https://g2.com", domain="g2.com", credibility_score=0.85))
    page = store.create_node(WebPageNode(url="https://g2.com/r", title="Reviews"))
    insight = store.create_node(InsightNode(insight="Linear pricing targets mid-market teams", confidence=0.82))
    report = store.create_node(ReportSectionNode(section="Pricing Analysis", content="Linear targets mid-market teams...", order=3))
    store.create_edge(GraphEdge(source_id=page.id, target_id=source.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=insight.id, target_id=page.id, edge_type=EdgeType.DERIVED_FROM))
    store.create_edge(GraphEdge(source_id=report.id, target_id=insight.id, edge_type=EdgeType.CITES))
    return store, {"source": source, "page": page, "insight": insight, "report": report}


@pytest.fixture
def qa_tools(qa_store):
    store, _ = qa_store
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    return tools


@pytest.mark.asyncio
async def test_qa_fact_check_passes_on_complete_trace(qa_store, qa_tools):
    store, nodes = qa_store
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({"reasoning": "Checking trace chain for insight", "action": "graph_query", "params": {"node_id": nodes["insight"].id}, "confidence": 0.9}), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        LLMResponse(content=json.dumps({"reasoning": "Trace chain is complete - all assertions have supporting evidence", "action": "finalize", "result": {"summary": "All claims verified", "nodes_created": [], "edges_created": [], "data": {"failed_nodes": [], "issues": []}}, "confidence": 0.95}), model="test", tokens_in=100, tokens_out=50, cost=0.002),
    ])
    agent = QAFactCheckAgent(gateway=gateway, store=store, tool_registry=qa_tools)
    output, traces = await agent.execute({"task_id": "t1", "node_id": "qa1", "agent_type": "QA_FactCheck", "input_query": {}, "context": {}})
    assert output.status == "completed"
    assert output.data.get("issues", []) == []


@pytest.mark.asyncio
async def test_qa_fact_check_fails_on_missing_trace(qa_store, qa_tools):
    store, nodes = qa_store
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({"reasoning": "Checking trace chain", "action": "graph_query", "params": {"node_id": nodes["insight"].id}, "confidence": 0.9}), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        LLMResponse(content=json.dumps({"reasoning": "Found an unverifiable claim - 'Linear targets mid-market' has no pricing data source", "action": "finalize", "result": {"summary": "1 claim unverifiable", "nodes_created": [], "edges_created": [], "data": {"failed_nodes": [nodes["insight"].id], "issues": [{"node_id": nodes["insight"].id, "reason": "Missing pricing data source", "severity": "high"}]}}, "confidence": 0.9}), model="test", tokens_in=100, tokens_out=60, cost=0.002),
    ])
    agent = QAFactCheckAgent(gateway=gateway, store=store, tool_registry=qa_tools)
    output, traces = await agent.execute({"task_id": "t1", "node_id": "qa1", "agent_type": "QA_FactCheck", "input_query": {}, "context": {}})
    assert output.status == "completed"
    assert len(output.data.get("failed_nodes", [])) > 0


@pytest.mark.asyncio
async def test_qa_logic_check_runs(qa_store, qa_tools):
    store, _ = qa_store
    gateway = MagicMock(spec=LLMGateway)
    gateway.chat = AsyncMock(side_effect=[
        LLMResponse(content=json.dumps({"reasoning": "Checking logical consistency of report", "action": "graph_query", "params": {"layer": 3}, "confidence": 0.85}), model="test", tokens_in=50, tokens_out=30, cost=0.001),
        LLMResponse(content=json.dumps({"reasoning": "No logical contradictions found in report", "action": "finalize", "result": {"summary": "Report is logically consistent", "nodes_created": [], "edges_created": [], "data": {"contradictions": []}}, "confidence": 0.95}), model="test", tokens_in=100, tokens_out=40, cost=0.002),
    ])
    agent = QALogicCheckAgent(gateway=gateway, store=store, tool_registry=qa_tools)
    output, traces = await agent.execute({"task_id": "t1", "node_id": "qa2", "agent_type": "QA_LogicCheck", "input_query": {}, "context": {}})
    assert output.status == "completed"
```

- [ ] **Step 2: 实现 QA Agent**

```python
# src/agents/qa_fact_check.py
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class QAFactCheckAgent(BaseAgent):
    agent_type = "QA_FactCheck"
    system_prompt = """You are QA Agent #1 — Fact Checker. Verify every claim in the report against the knowledge graph.

For each InsightNode and ReportSection:
1. BFS trace along derived_from edges to verify each claim has a complete evidence chain
2. Check that evidence nodes (WebPage, ReviewEntry, PricingData) actually exist
3. Flag claims with broken or missing trace chains
4. Flag suspicious patterns: high confidence with few sources, old data

Output: list of failed_node_ids and issues with severity (high/medium/low).
"""
    max_steps = 15
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

```python
# src/agents/qa_logic_check.py
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput


class QALogicCheckAgent(BaseAgent):
    agent_type = "QA_LogicCheck"
    system_prompt = """You are QA Agent #2 — Logic Checker. Verify the report contains no logical contradictions.

Read all ReportSection and InsightNode content. Check for:
1. Internal contradictions: does Section A contradict Section B?
2. Reasoning gaps: are conclusions supported by preceding evidence?
3. Missing context: are there obvious counter-arguments not addressed?

Output: list of contradictions found (empty if clean).
"""
    max_steps = 15
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple:
        return await super().execute(task)
```

- [ ] **Step 3: 运行测试** — `python -m pytest tests/test_agents/test_qa.py -v` → 3 PASS

- [ ] **Step 4: Commit**

```bash
git add src/agents/qa_fact_check.py src/agents/qa_logic_check.py tests/test_agents/test_qa.py
git commit -m "feat: add QA FactCheck and LogicCheck agents"
```

---

### Task 5.2: DAG 反馈边处理

**Files:**
- Create: `src/dag/feedback.py`
- Create: `tests/test_dag/test_feedback.py`

- [ ] **Step 1: 编写测试 — QA 拒绝后仅重置受影响子图**

```python
# tests/test_dag/test_feedback.py
import pytest
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.feedback import FeedbackHandler


def build_test_dag():
    n_sd = DAGNode(node_id="source_disc", agent_type="SourceDiscovery", input_query={}, depends_on=[])
    n_col = DAGNode(node_id="col_notion", agent_type="Collector", input_query={}, depends_on=["source_disc"])
    n_feat = DAGNode(node_id="feature", agent_type="FeatureAnalyzer", input_query={}, depends_on=["col_notion"])
    n_sent = DAGNode(node_id="sentiment", agent_type="SentimentAnalyzer", input_query={}, depends_on=["col_notion"])
    n_swot = DAGNode(node_id="swot", agent_type="SWOTAnalyzer", input_query={}, depends_on=["feature", "sentiment"])
    n_writer = DAGNode(node_id="writer", agent_type="Writer", input_query={}, depends_on=["swot"])
    n_qa = DAGNode(node_id="qa1", agent_type="QA_FactCheck", input_query={}, depends_on=["writer"])
    for n in [n_sd, n_col, n_feat, n_sent, n_swot, n_writer]:
        n.state = NodeState.COMPLETED
    n_qa.state = NodeState.PENDING
    return TaskDAG(task_id="fb_test", nodes=[n_sd, n_col, n_feat, n_sent, n_swot, n_writer, n_qa])


def test_feedback_resets_only_affected_subgraph():
    dag = build_test_dag()
    handler = FeedbackHandler()
    affected = handler.handle_qa_rejection(
        dag, qa_node_id="qa1",
        failed_nodes=["feature"],
        reasons=["FeatureMatrix uses outdated webpage"],
        qa_round=1,
    )
    assert "feature" in affected
    assert "col_notion" in affected  # upstream of feature
    assert "sentiment" not in affected  # independent branch
    assert "swot" not in affected  # downstream, will re-trigger when upstream completes


def test_feedback_max_rounds():
    dag = build_test_dag()
    handler = FeedbackHandler()
    affected1 = handler.handle_qa_rejection(dag, "qa1", ["feature"], ["stale data"], qa_round=1)
    assert len(affected1) > 0

    affected2 = handler.handle_qa_rejection(dag, "qa1", ["feature"], ["still broken"], qa_round=2)
    # 2nd round: should still process
    assert "feature" in affected2

    affected3 = handler.handle_qa_rejection(dag, "qa1", ["feature"], ["persistent issue"], qa_round=3)
    # 3rd round: should NOT reset, just mark degraded
    assert len(affected3) == 0
    qa_node = dag.get_node("qa1")
    assert qa_node.state == NodeState.DEGRADED
```

- [ ] **Step 2: 实现反馈处理**

```python
# src/dag/feedback.py
from src.dag.models import TaskDAG, NodeState


class FeedbackHandler:
    MAX_QA_ROUNDS = 2
    MAX_CROSS_REVIEW_ROUNDS = 1

    def handle_qa_rejection(self, dag: TaskDAG, qa_node_id: str,
                            failed_nodes: list[str], reasons: list[str],
                            qa_round: int) -> set[str]:
        qa_node = dag.get_node(qa_node_id)
        if qa_node is None:
            return set()

        if qa_round > self.MAX_QA_ROUNDS:
            qa_node.state = NodeState.DEGRADED
            qa_node.context["qa_notes"] = f"Max {self.MAX_QA_ROUNDS} rounds exceeded: {reasons}"
            return set()

        affected: set[str] = set()
        for nid in failed_nodes:
            upstream = dag.trace_upstream(nid)
            affected.update(upstream)
            affected.add(nid)

        for nid in affected:
            node = dag.get_node(nid)
            if node and node.state == NodeState.COMPLETED:
                node.state = NodeState.PENDING
                node.retries = 0

        return affected

    def handle_cross_review_rejection(self, dag: TaskDAG, flags: list[dict]) -> set[str]:
        high_flags = [f for f in flags if f.get("severity") == "high"]
        if not high_flags:
            return set()

        affected_agents: set[str] = set()
        for flag in high_flags:
            for agent_type in flag.get("involved_agents", []):
                affected_agents.add(agent_type)

        affected_nodes: set[str] = set()
        for agent_type in affected_agents:
            for node in dag.find_nodes_by_agent(agent_type):
                if node.cross_review_retries < self.MAX_CROSS_REVIEW_ROUNDS:
                    node.state = NodeState.PENDING
                    node.cross_review_retries += 1
                    node.context["cross_review_flags"] = [
                        f for f in high_flags if agent_type in f.get("involved_agents", [])
                    ]
                    affected_nodes.add(node.node_id)

        return affected_nodes
```

- [ ] **Step 3: 运行测试** — `python -m pytest tests/test_dag/test_feedback.py -v` → PASS

- [ ] **Step 4: Commit**

```bash
git add src/dag/feedback.py tests/test_dag/test_feedback.py
git commit -m "feat: add DAG feedback handler for QA rejection and cross-review rejection"
```

---

### Task 5.3: P5 集成测试 — QA 反馈闭环

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_dag/test_qa_integration.py
import pytest
from unittest.mock import AsyncMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.feedback import FeedbackHandler


@pytest.mark.asyncio
async def test_qa_feedback_cycle():
    """Simulates: DAG runs → QA fails → feedback resets → re-runs → QA passes"""
    n_sd = DAGNode(node_id="sd", agent_type="SourceDiscovery", input_query={}, depends_on=[])
    n_col = DAGNode(node_id="col", agent_type="Collector", input_query={}, depends_on=["sd"])
    n_feat = DAGNode(node_id="feat", agent_type="FeatureAnalyzer", input_query={}, depends_on=["col"])
    n_writer = DAGNode(node_id="writer", agent_type="Writer", input_query={}, depends_on=["feat"])
    n_qa = DAGNode(node_id="qa1", agent_type="QA_FactCheck", input_query={}, depends_on=["writer"])
    dag = TaskDAG(task_id="qa_test", nodes=[n_sd, n_col, n_feat, n_writer, n_qa])

    for n in [n_sd, n_col, n_feat, n_writer]:
        n.state = NodeState.COMPLETED

    handler = FeedbackHandler()
    # Round 1: QA fails on feat
    affected = handler.handle_qa_rejection(dag, "qa1", ["feat"], ["Missing source data"], qa_round=1)
    assert "feat" in affected
    assert "col" in affected
    assert n_feat.state == NodeState.PENDING

    # Re-run feat and col
    n_col.state = NodeState.COMPLETED
    n_feat.state = NodeState.COMPLETED

    # Round 2: QA passes
    affected2 = handler.handle_qa_rejection(dag, "qa1", [], [], qa_round=2)
    assert len(affected2) == 0  # No failures, no reset needed
```

- [ ] **Step 2: 运行** — `python -m pytest tests/test_dag/test_qa_integration.py -v` → PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_dag/test_qa_integration.py
git commit -m "feat: add P5 integration test - QA feedback loop"
```

---

## P5 完成检查清单

- [ ] QA #1: 遍历报告断言 → BFS 溯源 → 标记溯源链缺失的节点
- [ ] QA #2: 检查报告内部逻辑一致性 → 标记矛盾点
- [ ] 反馈边：QA 拒绝 → 仅重置受影响子图 → 不重跑无关节点
- [ ] 重试上限：QA 第 3 轮自动 DEGRADED + 标注
- [ ] Cross-Review 反馈：high 矛盾触发最多 1 轮局部重分析
