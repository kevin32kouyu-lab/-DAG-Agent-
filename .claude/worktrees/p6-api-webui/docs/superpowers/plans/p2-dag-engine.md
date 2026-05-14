# Phase 2: DAG 引擎 + Orchestrator Agent

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** DAG 引擎能调度多节点并行执行，Orchestrator Agent 将用户请求转为 DAG 拓扑。断点续传和反馈边处理留到 P5/P7。

**可验证产出:** 多个模拟 Agent 节点被 DAG 引擎按依赖关系并行调度执行；Orchestrator 接收用户目标→输出完整 DAG JSON。

**依赖:** P1 完成（知识图谱 + Agent 框架可用）

**Spec Reference:** 设计文档第 5 章 DAG 引擎设计

---

### Task 2.1: DAG 模型

**Files:**
- Create: `src/dag/__init__.py`
- Create: `src/dag/models.py`
- Create: `tests/test_dag/__init__.py`
- Create: `tests/test_dag/test_models.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_dag/test_models.py
import pytest
from src.dag.models import DAGNode, TaskDAG, NodeState, NodeSnapshot


def test_dag_node_initial_state():
    node = DAGNode(
        node_id="collector_1",
        agent_type="Collector",
        input_query={"url": "https://example.com"},
        depends_on=[],
    )
    assert node.state == NodeState.PENDING
    assert node.retries == 0
    assert node.max_retries == 3


def test_dag_node_state_transitions():
    node = DAGNode(node_id="n1", agent_type="Test", input_query={}, depends_on=[])
    node.state = NodeState.READY
    node.state = NodeState.RUNNING
    node.state = NodeState.COMPLETED
    assert node.state == NodeState.COMPLETED


def test_task_dag_get_ready_nodes():
    n1 = DAGNode(node_id="source_disc", agent_type="SourceDiscovery", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="collector_1", agent_type="Collector", input_query={}, depends_on=["source_disc"])
    n3 = DAGNode(node_id="collector_2", agent_type="Collector", input_query={}, depends_on=["source_disc"])
    n1.state = NodeState.COMPLETED

    dag = TaskDAG(task_id="task_1", nodes=[n1, n2, n3])
    ready = dag.get_ready_nodes()
    assert len(ready) == 2
    assert {n.node_id for n in ready} == {"collector_1", "collector_2"}


def test_task_dag_is_terminal():
    n1 = DAGNode(node_id="n1", agent_type="Test", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="n2", agent_type="Test", input_query={}, depends_on=["n1"])
    dag = TaskDAG(task_id="task_1", nodes=[n1, n2])

    n1.state = NodeState.COMPLETED
    n2.state = NodeState.COMPLETED
    assert dag.is_terminal() is True

    n2.state = NodeState.FAILED
    assert dag.is_terminal() is True


def test_dag_find_upstream():
    n1 = DAGNode(node_id="n1", agent_type="A", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="n2", agent_type="B", input_query={}, depends_on=["n1"])
    n3 = DAGNode(node_id="n3", agent_type="C", input_query={}, depends_on=["n2"])
    dag = TaskDAG(task_id="task_1", nodes=[n1, n2, n3])

    affected = dag.trace_upstream("n3")
    assert "n1" in affected
    assert "n2" in affected
    assert "n3" not in affected  # only upstream, not self
```

- [ ] **Step 2: 验证测试失败** — `python -m pytest tests/test_dag/test_models.py -v` → FAIL

- [ ] **Step 3: 实现 DAG 模型**

```python
# src/dag/models.py
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class NodeState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


@dataclass
class DAGNode:
    node_id: str
    agent_type: str
    input_query: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    state: NodeState = NodeState.PENDING
    priority: int = 0
    retries: int = 0
    max_retries: int = 3
    cross_review_retries: int = 0
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeSnapshot:
    task_id: str
    node_id: str
    state: NodeState
    kg_changeset: dict[str, Any] = field(default_factory=dict)
    checkpoint_time: datetime = field(default_factory=datetime.now)
    llm_cost: float = 0.0


@dataclass
class TaskDAG:
    task_id: str
    nodes: list[DAGNode] = field(default_factory=list)

    def get_ready_nodes(self) -> list[DAGNode]:
        completed_ids = {n.node_id for n in self.nodes if n.state == NodeState.COMPLETED}
        ready = []
        for node in self.nodes:
            if node.state != NodeState.PENDING:
                continue
            if all(dep in completed_ids for dep in node.depends_on):
                ready.append(node)
        return ready

    def get_node(self, node_id: str) -> DAGNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def is_terminal(self) -> bool:
        return all(n.state in {NodeState.COMPLETED, NodeState.FAILED, NodeState.DEGRADED} for n in self.nodes)

    def trace_upstream(self, node_id: str) -> set[str]:
        affected: set[str] = set()
        queue = [node_id]
        visited: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            node = self.get_node(current)
            if node:
                for dep_id in node.depends_on:
                    if dep_id not in visited:
                        affected.add(dep_id)
                        queue.append(dep_id)
        return affected

    def trace_downstream(self, node_id: str) -> set[str]:
        affected: set[str] = set()
        for node in self.nodes:
            if node_id in node.depends_on:
                affected.add(node.node_id)
        return affected

    def find_nodes_by_agent(self, agent_type: str) -> list[DAGNode]:
        return [n for n in self.nodes if n.agent_type == agent_type]
```

- [ ] **Step 4: 运行测试** — `python -m pytest tests/test_dag/test_models.py -v` → 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/dag/ tests/test_dag/
git commit -m "feat: add DAG node, TaskDAG models with state machine and trace"
```

---

### Task 2.2: DAG 调度器

**Files:**
- Create: `src/dag/scheduler.py`
- Create: `tests/test_dag/test_scheduler.py`

- [ ] **Step 1: 编写调度器测试**

```python
# tests/test_dag/test_scheduler.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.scheduler import DAGScheduler


@pytest.fixture
def scheduler():
    return DAGScheduler()


@pytest.mark.asyncio
async def test_scheduler_runs_simple_dag(scheduler):
    n1 = DAGNode(node_id="n1", agent_type="Collector", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="n2", agent_type="Analyzer", input_query={}, depends_on=["n1"])
    dag = TaskDAG(task_id="task_1", nodes=[n1, n2])

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=lambda node: setattr(node, "state", NodeState.COMPLETED))

    await scheduler.run(dag, executor)

    assert n1.state == NodeState.COMPLETED
    assert n2.state == NodeState.COMPLETED


@pytest.mark.asyncio
async def test_scheduler_parallel_execution(scheduler):
    n1 = DAGNode(node_id="source", agent_type="SourceDisc", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="c1", agent_type="Collector", input_query={}, depends_on=["source"])
    n3 = DAGNode(node_id="c2", agent_type="Collector", input_query={}, depends_on=["source"])
    dag = TaskDAG(task_id="task_2", nodes=[n1, n2, n3])

    call_order = []
    async def track_exec(node):
        call_order.append(node.node_id)
        node.state = NodeState.COMPLETED

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=track_exec)

    await scheduler.run(dag, executor)
    assert n2.state == NodeState.COMPLETED
    assert n3.state == NodeState.COMPLETED
    assert call_order[0] == "source"


@pytest.mark.asyncio
async def test_scheduler_handles_failure_with_retry(scheduler):
    n1 = DAGNode(node_id="n1", agent_type="Flaky", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_3", nodes=[n1])

    call_count = [0]
    async def flaky_exec(node):
        call_count[0] += 1
        if call_count[0] < 2:
            node.state = NodeState.FAILED
        else:
            node.state = NodeState.COMPLETED

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=flaky_exec)

    await scheduler.run(dag, executor)
    assert n1.state == NodeState.COMPLETED
    assert n1.retries == 1
```

- [ ] **Step 2: 验证测试失败** — FAIL

- [ ] **Step 3: 实现 DAGScheduler**

```python
# src/dag/scheduler.py
import asyncio
from src.dag.models import TaskDAG, DAGNode, NodeState

CHECKPOINT_AGENT = "DataEnricher"  # Agent type that triggers review checkpoint
CHECKPOINT_TIMEOUT = 30 * 60       # 30 minutes auto-release


class DAGScheduler:
    def __init__(self, review_mode: bool = False):
        self._event_callbacks: dict[str, list] = {}
        self._checkpoint_event: asyncio.Event | None = None
        self.review_mode = review_mode

    def on(self, event: str, callback):
        self._event_callbacks.setdefault(event, []).append(callback)

    async def _emit(self, event: str, *args, **kwargs):
        for cb in self._event_callbacks.get(event, []):
            await cb(*args, **kwargs)

    def release_checkpoint(self) -> None:
        """Called via API when user approves collected data in review mode."""
        if self._checkpoint_event:
            self._checkpoint_event.set()

    async def run(self, dag: TaskDAG, executor) -> None:
        while not dag.is_terminal():
            ready = dag.get_ready_nodes()
            for node in ready:
                node.state = NodeState.READY

            if not ready:
                for node in dag.nodes:
                    if node.state == NodeState.FAILED and node.retries < node.max_retries:
                        node.retries += 1
                        node.state = NodeState.PENDING
                        ready.append(node)

            if not ready:
                break

            tasks = []
            for node in ready:
                node.state = NodeState.RUNNING
                await self._emit("node_state_change", node)
                tasks.append(self._run_node(node, executor, dag))

            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in tasks:
                if not t.done():
                    await t

    async def _run_node(self, node: DAGNode, executor, dag: TaskDAG):
        try:
            await executor.execute(node)
            node.state = NodeState.COMPLETED
            await self._emit("node_completed", node)
            await self._emit("node_state_change", node)

            # Review mode checkpoint: pause after DataEnricher completes
            if self.review_mode and node.agent_type == CHECKPOINT_AGENT:
                self._checkpoint_event = asyncio.Event()
                await self._emit("checkpoint_reached", node, dag.task_id)
                try:
                    await asyncio.wait_for(
                        self._checkpoint_event.wait(),
                        timeout=CHECKPOINT_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    pass  # Auto-release after timeout
                self._checkpoint_event = None
                await self._emit("checkpoint_released", node, dag.task_id)

        except Exception as e:
            node.state = NodeState.FAILED
            node.context["error"] = str(e)
            await self._emit("node_failed", node)
            await self._emit("node_state_change", node)
```

Note: `_run_node` now sets `node.state = NodeState.COMPLETED` on success and records the error on failure. The executor is responsible for raising an exception on failure — not setting node state directly.

- [ ] **Step 4: 运行测试** — `python -m pytest tests/test_dag/test_scheduler.py -v` → 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/dag/scheduler.py tests/test_dag/test_scheduler.py
git commit -m "feat: add DAG scheduler with parallel dispatch and retry"
```

---

### Task 2.3: Agent Executor 桥接层

**Files:**
- Create: `src/dag/executor.py`
- Create: `tests/test_dag/test_executor.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_dag/test_executor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.dag.models import DAGNode, NodeState
from src.dag.executor import AgentExecutor
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool


@pytest.fixture
def executor(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    return AgentExecutor(gateway=gateway, store=store, tool_registry=tools)


def test_executor_resolves_agent_class():
    ex = AgentExecutor.__new__(AgentExecutor)
    ex._agent_classes = {}
    cls = ex._resolve_agent_class("SourceDiscovery")
    assert cls is not None


def test_executor_builds_task_from_node():
    node = DAGNode(
        node_id="collector_1", agent_type="Collector",
        input_query={"url": "https://notion.so"}, depends_on=["source_disc"],
        context={"schema_override": {"depth": "standard"}},
    )
    task = AgentExecutor._build_task(node, task_id="task_1")
    assert task["task_id"] == "task_1"
    assert task["node_id"] == "collector_1"
    assert task["agent_type"] == "Collector"
    assert task["input_query"]["url"] == "https://notion.so"


@pytest.mark.asyncio
async def test_executor_runs_node_and_returns_traces(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)
    # Mock the agent's execute to return immediately
    mock_agent = MagicMock()
    mock_agent.execute = AsyncMock(return_value=(MagicMock(status="completed"), []))

    ex = AgentExecutor(gateway=gateway, store=store, tool_registry=ToolRegistry())
    ex._build_agent = MagicMock(return_value=mock_agent)

    node = DAGNode(node_id="c1", agent_type="Collector",
                   input_query={"url": "https://test.com"}, depends_on=[])
    await ex.execute(node)

    mock_agent.execute.assert_called_once()
    assert node.state == NodeState.COMPLETED  # AgentExecutor sets COMPLETED on success
```

- [ ] **Step 2: 验证测试失败** — `python -m pytest tests/test_dag/test_executor.py -v` → FAIL

- [ ] **Step 3: 实现 AgentExecutor**

```python
# src/dag/executor.py
from src.dag.models import DAGNode, NodeState
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway
from src.agents.tools.base import ToolRegistry
from src.agents.base import BaseAgent

# Lazy import map: agent_type → (module_path, class_name)
# Agents are imported on first use so executor.py works as soon as it's created (P2),
# even though most agent files don't exist until P3-P5.
_AGENT_IMPORT_MAP: dict[str, tuple[str, str]] = {
    "Orchestrator":       ("src.agents.orchestrator",       "OrchestratorAgent"),
    "SourceDiscovery":    ("src.agents.source_discovery",   "SourceDiscoveryAgent"),
    "Collector":          ("src.agents.collector",          "CollectorAgent"),
    "DataEnricher":       ("src.agents.data_enricher",      "DataEnricherAgent"),
    "FeatureAnalyzer":    ("src.agents.feature_analyzer",   "FeatureAnalyzer"),
    "SentimentAnalyzer":  ("src.agents.sentiment_analyzer", "SentimentAnalyzer"),
    "PricingAnalyst":     ("src.agents.pricing_analyst",    "PricingAnalyst"),
    "TechStackAnalyzer":  ("src.agents.techstack_analyzer", "TechStackAnalyzer"),
    "MarketPositionAnalyzer": ("src.agents.market_position", "MarketPositionAnalyzer"),
    "CrossReviewAgent":   ("src.agents.cross_review",       "CrossReviewAgent"),
    "SWOTAnalyzer":       ("src.agents.swot_synthesizer",   "SWOTAnalyzer"),
    "Writer":             ("src.agents.writer",             "WriterAgent"),
    "QA_FactCheck":       ("src.agents.qa_fact_check",      "QAFactCheckAgent"),
    "QA_LogicCheck":      ("src.agents.qa_logic_check",     "QALogicCheckAgent"),
}


class AgentExecutor:
    """Bridges DAG scheduling to actual agent execution.

    The DAGScheduler calls executor.execute(node) for each DAG node.
    AgentExecutor resolves the agent class, builds a task dict, runs the agent,
    and raises an exception on failure so the scheduler can handle retry logic.
    """

    def __init__(self, gateway: LLMGateway, store: GraphStore, tool_registry: ToolRegistry,
                 audit_logger=None):
        self.gateway = gateway
        self.store = store
        self.tool_registry = tool_registry
        self.audit_logger = audit_logger
        self._agent_cache: dict[str, type[BaseAgent]] = {}

    def _resolve_agent_class(self, agent_type: str) -> type[BaseAgent]:
        if agent_type in self._agent_cache:
            return self._agent_cache[agent_type]
        import importlib
        mod_path, cls_name = _AGENT_IMPORT_MAP[agent_type]
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
        self._agent_cache[agent_type] = cls
        return cls

    async def execute(self, node: DAGNode) -> None:
        agent = self._build_agent(node)
        task = self._build_task(node)
        output, traces = await agent.execute(task)

        if output.status == "failed":
            raise RuntimeError(f"{node.agent_type} failed: {output.summary}")

        node.state = NodeState.COMPLETED

    def _build_agent(self, node: DAGNode) -> BaseAgent:
        agent_cls = self._resolve_agent_class(node.agent_type)
        return agent_cls(gateway=self.gateway, store=self.store,
                         tool_registry=self.tool_registry, audit_logger=self.audit_logger)

    @staticmethod
    def _build_task(node: DAGNode, task_id: str = "") -> dict:
        return {
            "task_id": task_id or node.context.get("task_id", ""),
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "input_query": node.input_query,
            "context": node.context,
        }
```

- [ ] **Step 4: 更新 DAGScheduler 测试** — 修改 executor mock 让它 raise 来模拟失败，而非直接改状态

更新 `test_scheduler_handles_failure_with_retry`:

```python
@pytest.mark.asyncio
async def test_scheduler_handles_failure_with_retry(scheduler):
    n1 = DAGNode(node_id="n1", agent_type="Flaky", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_3", nodes=[n1])

    call_count = [0]
    async def flaky_exec(node):
        call_count[0] += 1
        if call_count[0] < 2:
            raise RuntimeError("simulated failure")
        # On success, scheduler sets COMPLETED — executor just returns

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=flaky_exec)

    await scheduler.run(dag, executor)
    assert n1.state == NodeState.COMPLETED
    assert n1.retries == 1
```

- [ ] **Step 5: 运行测试** — `python -m pytest tests/test_dag/ -v` → all PASS

- [ ] **Step 6: Commit**

```bash
git add src/dag/executor.py tests/test_dag/test_executor.py src/dag/scheduler.py tests/test_dag/test_scheduler.py
git commit -m "feat: add AgentExecutor bridge and fix DAGScheduler state management"
```

---

### Task 2.4: Orchestrator Agent

**Files:**
- Create: `src/agents/orchestrator.py`
- Create: `tests/test_agents/test_orchestrator.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_agents/test_orchestrator.py
import json
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.orchestrator import OrchestratorAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore


@pytest.fixture
def orch(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = AsyncMock(spec=LLMGateway)
    return OrchestratorAgent(gateway=gateway, store=store, tool_registry=None)


def test_orchestrator_parse_dag_json():
    # Simulate a valid DAG JSON response
    dag_json = {
        "task_id": "task_1",
        "targets": ["Notion", "Confluence", "Linear"],
        "nodes": [
            {"node_id": "source_disc", "agent_type": "SourceDiscovery", "depends_on": []},
            {"node_id": "c1", "agent_type": "Collector", "depends_on": ["source_disc"]},
            {"node_id": "c2", "agent_type": "Collector", "depends_on": ["source_disc"]},
            {"node_id": "feat", "agent_type": "FeatureAnalyzer", "depends_on": ["c1", "c2"]},
        ],
    }
    # Basic validation
    assert len(dag_json["nodes"]) == 4
    assert dag_json["nodes"][0]["depends_on"] == []
    assert "c1" in dag_json["nodes"][3]["depends_on"]


@pytest.mark.asyncio
async def test_orchestrator_generates_dag(orch):
    from src.dag.models import TaskDAG
    orch.gateway.chat = AsyncMock(return_value=LLMResponse(
        content=json.dumps({
            "task_id": "t1",
            "targets": ["Notion"],
            "nodes": [
                {"node_id": "s1", "agent_type": "SourceDiscovery", "depends_on": []},
                {"node_id": "c1", "agent_type": "Collector", "depends_on": ["s1"]},
                {"node_id": "f1", "agent_type": "FeatureAnalyzer", "depends_on": ["c1"]},
            ],
        }),
        model="claude-sonnet-4-6", tokens_in=200, tokens_out=100, cost=0.002,
    ))

    task = {"task_id": "t1", "targets": ["Notion"], "schema": {"industry": "saas"}}
    result = await orch._generate_dag(task["targets"], task["schema"])
    assert result is not None
    assert "nodes" in result
```

- [ ] **Step 2: 验证测试失败** — FAIL

- [ ] **Step 3: 实现 Orchestrator Agent**

```python
# src/agents/orchestrator.py
import json
from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.dag.models import TaskDAG, DAGNode


class OrchestratorAgent(BaseAgent):
    agent_type = "Orchestrator"
    system_prompt = """You are the Orchestrator for a competitive analysis multi-agent system.

Your job: given target products and analysis schema, generate a DAG (directed acyclic graph) of agent tasks.

Available agent types and their dependencies:
- SourceDiscovery: no dependencies, single instance per task
- Collector: depends_on [SourceDiscovery], one per URL group
- DataEnricher: depends_on [Collector, ...], single instance
- FeatureAnalyzer: depends_on [DataEnricher]
- SentimentAnalyzer: depends_on [DataEnricher]
- PricingAnalyst: depends_on [DataEnricher]
- TechStackAnalyzer: depends_on [DataEnricher]
- MarketPosition: depends_on [DataEnricher]
- CrossReviewAgent: depends_on [FeatureAnalyzer, SentimentAnalyzer, PricingAnalyst, TechStackAnalyzer, MarketPosition]
- SWOTAnalyzer: depends_on [CrossReviewAgent] (or analysis agents if no cross-review)
- Writer: depends_on [SWOTAnalyzer]
- QA_FactCheck: depends_on [Writer]
- QA_LogicCheck: depends_on [Writer]

Output ONLY valid JSON in this exact structure:
{
  "task_id": "...",
  "targets": [...],
  "nodes": [
    {"node_id": "...", "agent_type": "...", "depends_on": [...], "input_query": {...}, "priority": 0}
  ]
}

Rules:
- node_id must be unique
- depends_on must list node_ids that MUST complete before this node starts
- input_query should contain {"node_type": "..."} or {"product": "...", ...} as appropriate
- Assign priority 0 (normal) or 1 (high)
- SourceDiscovery is always the first node with no dependencies
- Collectors should be per-product (one for each target's official website) plus shared ones (G2, ProductHunt, News)
- Skip dimensions excluded in schema.exclude_dimensions
"""

    max_steps = 5
    output_contract = AgentOutput

    async def execute(self, task: dict) -> tuple[TaskDAG | None, list]:
        self.context.init(task)
        targets = task.get("targets", [])
        schema = task.get("schema", {"industry": "saas"})
        dag_json = await self._generate_dag(targets, schema)
        if dag_json is None:
            return None, []
        dag = self._json_to_dag(dag_json)
        return dag, []

    async def _generate_dag(self, targets: list[str], schema: dict) -> dict | None:
        prompt = f"""Generate a DAG for competitive analysis of: {targets}
Schema: {json.dumps(schema, default=str)}
Dimensions to include (from schema.dimensions or saas defaults):
  - FeatureAnalyzer, SentimentAnalyzer, PricingAnalyst, TechStackAnalyzer, MarketPosition
Excluded dimensions: {schema.get('exclude_dimensions', [])}
"""
        resp = await self.gateway.chat(
            system=self.system_prompt,
            messages=[{"role": "user", "content": prompt}],
            model_tier="reasoning",
            max_tokens=4096,
        )
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError:
            return None

    def _json_to_dag(self, dag_json: dict) -> TaskDAG:
        nodes = [
            DAGNode(
                node_id=n["node_id"],
                agent_type=n["agent_type"],
                input_query=n.get("input_query", {}),
                depends_on=n.get("depends_on", []),
                priority=n.get("priority", 0),
            )
            for n in dag_json.get("nodes", [])
        ]
        return TaskDAG(task_id=dag_json.get("task_id", ""), nodes=nodes)
```

- [ ] **Step 4: 运行测试** — `python -m pytest tests/test_agents/test_orchestrator.py -v` → PASS

- [ ] **Step 5: Commit**

```bash
git add src/agents/orchestrator.py tests/test_agents/test_orchestrator.py
git commit -m "feat: add Orchestrator agent that generates DAG from user targets+ schema"
```

---

### Task 2.5: P2 集成测试 — DAG 调度完整流程

**Files:**
- Create: `tests/test_dag/test_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_dag/test_integration.py
import asyncio
import pytest
from unittest.mock import AsyncMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.scheduler import DAGScheduler
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import SourceInfoNode


@pytest.mark.asyncio
async def test_full_dag_simulation(temp_db_path):
    """Simulates the SaaS analysis DAG: SourceDisc → 2x Collector → DataEnricher → FeatureAnalyzer → SWOT → Writer → QA"""
    store = GraphStore(db_path=temp_db_path)

    n_source = DAGNode(node_id="source_disc", agent_type="SourceDiscovery", input_query={"targets": ["Notion"]}, depends_on=[])
    n_col1 = DAGNode(node_id="col_notion", agent_type="Collector", input_query={"url": "https://notion.so"}, depends_on=["source_disc"])
    n_col2 = DAGNode(node_id="col_g2", agent_type="Collector", input_query={"url": "https://g2.com/notion"}, depends_on=["source_disc"])
    n_enrich = DAGNode(node_id="enricher", agent_type="DataEnricher", input_query={}, depends_on=["col_notion", "col_g2"])
    n_feat = DAGNode(node_id="feature", agent_type="FeatureAnalyzer", input_query={"product": "Notion"}, depends_on=["enricher"])
    n_swot = DAGNode(node_id="swot", agent_type="SWOTAnalyzer", input_query={}, depends_on=["feature"])
    n_writer = DAGNode(node_id="writer", agent_type="Writer", input_query={}, depends_on=["swot"])
    n_qa = DAGNode(node_id="qa1", agent_type="QA_FactCheck", input_query={}, depends_on=["writer"])

    dag = TaskDAG(task_id="full_test", nodes=[n_source, n_col1, n_col2, n_enrich, n_feat, n_swot, n_writer, n_qa])

    async def mock_execute(node):
        node.state = NodeState.COMPLETED

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=mock_execute)
    scheduler = DAGScheduler()
    await scheduler.run(dag, executor)

    assert all(n.state == NodeState.COMPLETED for n in dag.nodes)
    assert dag.is_terminal()
```

- [ ] **Step 2: 运行全部 P1+P2 测试** — `python -m pytest tests/ -v` → all PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_dag/test_integration.py
git commit -m "feat: add P2 integration test - full DAG simulation"
```

---

## P2 完成检查清单

- [ ] DAG 模型：节点状态机 + 依赖解析 + 上游追溯
- [ ] DAG 调度器：按依赖顺序并行调度，失败自动重试
- [ ] Orchestrator：输入 targets + schema → 输出完整 DAG JSON
- [ ] 集成测试：8 节点 DAG 从开始到全部 COMPLETED
