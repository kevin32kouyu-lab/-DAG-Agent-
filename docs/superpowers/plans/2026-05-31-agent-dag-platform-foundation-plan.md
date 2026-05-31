# Agent DAG Platform Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first backend foundation for a self-developed Agent DAG platform: deterministic workflow templates, DAG compilation, richer node metadata, and API integration for one-click competitor reports.

**Architecture:** Keep the existing scheduler, AgentExecutor, knowledge graph, WebSocket, and agents. Add a template and compiler layer above the current DAG model so the one-click report flow no longer depends on LLM-generated DAG topology. This phase does not redesign the frontend, report generator, or QA feedback loop; those are later phases.

**Tech Stack:** Python 3.12+, dataclasses, FastAPI, pytest, existing `src.dag`, `src.api`, and agent runtime.

---

## Scope

This is only Phase 1 of the larger redesign. It implements:

- richer DAG node/task metadata;
- SaaS and App workflow templates;
- deterministic DAG compilation;
- API task creation through the template compiler;
- WebSocket DAG payloads with stage and role metadata;
- focused tests for the new foundation.

It does not implement:

- drag-and-drop workflow editing;
- LangGraph;
- full frontend redesign;
- report quality upgrade;
- real QA local rerun improvements;
- arbitrary industry auto-adaptation.

## Files

- Modify: `src/dag/models.py`  
  Add platform-oriented node states and metadata fields while keeping existing callers compatible.

- Create: `src/dag/templates.py`  
  Define scenario enum, node specs, workflow templates, and the default SaaS/App registry.

- Create: `src/dag/compiler.py`  
  Compile user input plus a workflow template into a concrete `TaskDAG`.

- Modify: `src/dag/scheduler.py`  
  Include new DAG/node metadata in `dag_created` events and keep terminal-state logic aligned with the new states.

- Modify: `src/api/routes/task.py`  
  Add template-based planning as the default one-click report path, while retaining legacy orchestrator planning as an explicit option.

- Create: `tests/test_dag/test_templates.py`  
  Test template registry and template integrity.

- Create: `tests/test_dag/test_compiler.py`  
  Test deterministic DAG compilation for SaaS and App scenarios.

- Modify: `tests/test_dag/test_models.py`  
  Add coverage for new metadata and states.

- Modify: `tests/test_dag/test_scheduler.py`  
  Add coverage for DAG-created payload metadata.

- Modify: `tests/test_api/test_task.py`  
  Verify API request schema accepts template planning and returns planning status.

- Modify: `CONTEXT.md`  
  Record that Phase 1 implementation planning is complete.

## Environment

Use the project virtual environment for test commands:

```powershell
if (!(Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_templates.py -v
```

---

### Task 1: Extend DAG Model Metadata

**Files:**
- Modify: `src/dag/models.py`
- Modify: `tests/test_dag/test_models.py`

- [ ] **Step 1: Write failing model tests**

Append these tests to `tests/test_dag/test_models.py`:

```python
def test_dag_node_platform_metadata_defaults():
    node = DAGNode(
        node_id="feature_analysis",
        agent_type="FeatureAnalyzer",
        input_query={"targets": ["Notion", "ClickUp"]},
    )

    assert node.stage == ""
    assert node.role_group == ""
    assert node.display_name == ""
    assert node.description == ""
    assert node.output_contract == ""
    assert node.degradation_policy == {}
    assert node.source_policy == {}


def test_task_dag_platform_metadata_and_stage_lookup():
    n1 = DAGNode(
        node_id="collector",
        agent_type="Collector",
        input_query={},
        stage="collection",
        role_group="research",
    )
    n2 = DAGNode(
        node_id="feature_analysis",
        agent_type="FeatureAnalyzer",
        input_query={},
        depends_on=["collector"],
        stage="analysis",
        role_group="analysis",
    )
    dag = TaskDAG(
        task_id="task_template",
        nodes=[n1, n2],
        workflow_template_id="saas_competitor_analysis",
        scenario="saas",
        targets=["Notion", "ClickUp"],
        metadata={"planning_mode": "template"},
    )

    assert dag.workflow_template_id == "saas_competitor_analysis"
    assert dag.scenario == "saas"
    assert dag.targets == ["Notion", "ClickUp"]
    assert dag.metadata["planning_mode"] == "template"
    assert dag.get_nodes_by_stage("analysis") == [n2]


def test_new_feedback_states_are_non_terminal_until_resolved():
    n1 = DAGNode(node_id="n1", agent_type="QA_FactCheck", input_query={})
    n2 = DAGNode(node_id="n2", agent_type="ReportGenerator", input_query={})
    dag = TaskDAG(task_id="task_feedback", nodes=[n1, n2])

    n1.state = NodeState.REJECTED
    n2.state = NodeState.RERUNNING

    assert dag.is_terminal() is False
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_models.py -v
```

Expected: 3 new tests fail because metadata fields, `get_nodes_by_stage`, `REJECTED`, and `RERUNNING` do not exist yet.

- [ ] **Step 3: Update DAG model**

Modify `src/dag/models.py` so it contains these additions while preserving existing fields:

```python
class NodeState(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"
    REJECTED = "rejected"
    RERUNNING = "rerunning"
```

Extend `DAGNode`:

```python
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
    qa_round: int = 0
    cross_review_retries: int = 0
    context: dict[str, Any] = field(default_factory=dict)
    stage: str = ""
    role_group: str = ""
    display_name: str = ""
    description: str = ""
    output_contract: str = ""
    degradation_policy: dict[str, Any] = field(default_factory=dict)
    source_policy: dict[str, Any] = field(default_factory=dict)
```

Extend `TaskDAG`:

```python
@dataclass
class TaskDAG:
    task_id: str
    nodes: list[DAGNode] = field(default_factory=list)
    workflow_template_id: str = ""
    scenario: str = ""
    targets: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_nodes_by_stage(self, stage: str) -> list[DAGNode]:
        return [node for node in self.nodes if node.stage == stage]
```

Keep `is_terminal()` terminal states limited to `COMPLETED`, `FAILED`, and `DEGRADED`:

```python
def is_terminal(self) -> bool:
    terminal_states = {NodeState.COMPLETED, NodeState.FAILED, NodeState.DEGRADED}
    return all(n.state in terminal_states for n in self.nodes)
```

- [ ] **Step 4: Run model tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_models.py -v
```

Expected: all tests in `tests/test_dag/test_models.py` pass.

- [ ] **Step 5: Commit**

```powershell
git add src/dag/models.py tests/test_dag/test_models.py
git commit -m "feat: extend DAG model metadata"
```

---

### Task 2: Add Workflow Template Registry

**Files:**
- Create: `src/dag/templates.py`
- Create: `tests/test_dag/test_templates.py`

- [ ] **Step 1: Write failing template tests**

Create `tests/test_dag/test_templates.py`:

```python
import pytest

from src.dag.templates import WorkflowScenario, get_default_template_registry


def test_default_registry_contains_saas_and_app_templates():
    registry = get_default_template_registry()

    assert registry.get("saas_competitor_analysis").scenario == WorkflowScenario.SAAS
    assert registry.get("app_competitor_analysis").scenario == WorkflowScenario.APP


def test_saas_template_has_required_pipeline_nodes():
    template = get_default_template_registry().get("saas_competitor_analysis")
    node_ids = {node.node_id for node in template.nodes}

    assert "source_discovery" in node_ids
    assert "collector" in node_ids
    assert "data_enricher" in node_ids
    assert "feature_analysis" in node_ids
    assert "pricing_analysis" in node_ids
    assert "sentiment_analysis" in node_ids
    assert "market_position" in node_ids
    assert "cross_review" in node_ids
    assert "swot" in node_ids
    assert "report" in node_ids
    assert "qa_fact_check" in node_ids
    assert "qa_logic_check" in node_ids


def test_template_dependencies_reference_existing_nodes():
    registry = get_default_template_registry()

    for template_id in registry.template_ids():
        template = registry.get(template_id)
        node_ids = {node.node_id for node in template.nodes}
        for node in template.nodes:
            assert set(node.depends_on).issubset(node_ids), node.node_id


def test_registry_raises_for_unknown_template():
    registry = get_default_template_registry()

    with pytest.raises(KeyError, match="unknown_template"):
        registry.get("unknown_template")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_templates.py -v
```

Expected: fails because `src.dag.templates` does not exist.

- [ ] **Step 3: Implement template registry**

Create `src/dag/templates.py`:

```python
"""工作流模板定义：把竞品分析场景拆成稳定的 DAG 节点规格。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class WorkflowScenario(str, Enum):
    """支持的竞品分析场景。"""

    SAAS = "saas"
    APP = "app"


@dataclass(frozen=True)
class WorkflowNodeSpec:
    """模板里的单个节点规格。"""

    node_id: str
    agent_type: str
    stage: str
    role_group: str
    display_name: str
    description: str
    depends_on: list[str] = field(default_factory=list)
    output_contract: str = ""
    input_defaults: dict[str, Any] = field(default_factory=dict)
    degradation_policy: dict[str, Any] = field(default_factory=dict)
    source_policy: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    priority: int = 0


@dataclass(frozen=True)
class WorkflowTemplate:
    """可编译为 TaskDAG 的工作流模板。"""

    template_id: str
    name: str
    scenario: WorkflowScenario
    description: str
    nodes: list[WorkflowNodeSpec]
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowTemplateRegistry:
    """按模板 ID 管理工作流模板。"""

    def __init__(self, templates: list[WorkflowTemplate]):
        self._templates = {template.template_id: template for template in templates}

    def get(self, template_id: str) -> WorkflowTemplate:
        try:
            return self._templates[template_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workflow template: {template_id}") from exc

    def template_ids(self) -> list[str]:
        return sorted(self._templates)


def _default_source_policy() -> dict[str, Any]:
    """默认公开来源策略，后续可接入更细的数据源状态。"""

    return {
        "preferred": ["official_site", "pricing_page", "docs", "reviews", "news"],
        "allow_cache": True,
        "allow_fallback": True,
    }


def _standard_degradation_policy() -> dict[str, Any]:
    """默认降级策略：单点失败不阻塞整份报告。"""

    return {
        "max_failures_before_degraded": 2,
        "continue_on_partial_data": True,
        "mark_low_confidence": True,
    }


def _shared_pipeline_nodes(scenario: WorkflowScenario) -> list[WorkflowNodeSpec]:
    """生成 SaaS 和 App 共用的主流程节点。"""

    scenario_label = "SaaS" if scenario == WorkflowScenario.SAAS else "App"
    return [
        WorkflowNodeSpec(
            node_id="source_discovery",
            agent_type="SourceDiscovery",
            stage="collection",
            role_group="research",
            display_name="信息源发现",
            description=f"发现 {scenario_label} 竞品分析需要采集的公开信息源。",
            output_contract="AgentOutput",
            source_policy=_default_source_policy(),
            degradation_policy=_standard_degradation_policy(),
        ),
        WorkflowNodeSpec(
            node_id="collector",
            agent_type="Collector",
            stage="collection",
            role_group="research",
            display_name="公开资料采集",
            description="采集官网、价格页、帮助文档、新闻和公开评论。",
            depends_on=["source_discovery"],
            output_contract="AgentOutput",
            source_policy=_default_source_policy(),
            degradation_policy=_standard_degradation_policy(),
        ),
        WorkflowNodeSpec(
            node_id="data_enricher",
            agent_type="DataEnricher",
            stage="structuring",
            role_group="research",
            display_name="资料结构化",
            description="把原始资料整理成后续分析可复用的结构化知识。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            degradation_policy=_standard_degradation_policy(),
        ),
        WorkflowNodeSpec(
            node_id="feature_analysis",
            agent_type="FeatureAnalyzer",
            stage="analysis",
            role_group="analysis",
            display_name="功能对比分析",
            description="提取功能树和功能矩阵。",
            depends_on=["data_enricher"],
            output_contract="FeatureAnalysisOutput",
        ),
        WorkflowNodeSpec(
            node_id="pricing_analysis",
            agent_type="PricingAnalyst",
            stage="analysis",
            role_group="analysis",
            display_name="定价与商业模式分析",
            description="分析价格、套餐、商业化方式和目标客群。",
            depends_on=["data_enricher"],
            output_contract="PricingAnalysisOutput",
        ),
        WorkflowNodeSpec(
            node_id="sentiment_analysis",
            agent_type="SentimentAnalyzer",
            stage="analysis",
            role_group="analysis",
            display_name="用户口碑分析",
            description="分析评论、社媒和公开反馈中的情绪与痛点。",
            depends_on=["data_enricher"],
            output_contract="SentimentAnalysisOutput",
        ),
        WorkflowNodeSpec(
            node_id="techstack_analysis",
            agent_type="TechStackAnalyzer",
            stage="analysis",
            role_group="analysis",
            display_name="技术与生态分析",
            description="从公开资料中推断技术栈、集成生态和平台能力。",
            depends_on=["data_enricher"],
            output_contract="TechStackOutput",
        ),
        WorkflowNodeSpec(
            node_id="market_position",
            agent_type="MarketPositionAnalyzer",
            stage="analysis",
            role_group="analysis",
            display_name="市场定位分析",
            description="分析定位、目标用户、差异化和增长策略。",
            depends_on=["feature_analysis", "pricing_analysis", "sentiment_analysis"],
            output_contract="MarketPositionOutput",
        ),
        WorkflowNodeSpec(
            node_id="cross_review",
            agent_type="CrossReviewAgent",
            stage="review",
            role_group="quality",
            display_name="交叉审查",
            description="检查不同分析 Agent 之间的冲突、遗漏和低可信结论。",
            depends_on=["feature_analysis", "pricing_analysis", "sentiment_analysis", "techstack_analysis", "market_position"],
            output_contract="CrossReviewOutput",
        ),
        WorkflowNodeSpec(
            node_id="swot",
            agent_type="SWOTAnalyzer",
            stage="synthesis",
            role_group="analysis",
            display_name="SWOT 综合",
            description="综合功能、定价、口碑和市场定位形成 SWOT。",
            depends_on=["cross_review"],
            output_contract="SWOTOutput",
        ),
        WorkflowNodeSpec(
            node_id="report",
            agent_type="ReportGenerator",
            stage="reporting",
            role_group="reporting",
            display_name="报告生成",
            description="基于知识图谱中的结构化结果生成竞品分析报告。",
            depends_on=["swot"],
            output_contract="ReportOutput",
        ),
        WorkflowNodeSpec(
            node_id="qa_fact_check",
            agent_type="QA_FactCheck",
            stage="qa",
            role_group="quality",
            display_name="事实校验",
            description="检查报告事实是否有证据支撑。",
            depends_on=["report"],
            output_contract="AgentOutput",
        ),
        WorkflowNodeSpec(
            node_id="qa_logic_check",
            agent_type="QA_LogicCheck",
            stage="qa",
            role_group="quality",
            display_name="逻辑校验",
            description="检查报告结论是否存在逻辑矛盾或推理断层。",
            depends_on=["qa_fact_check"],
            output_contract="AgentOutput",
        ),
    ]


def get_default_template_registry() -> WorkflowTemplateRegistry:
    """返回系统默认工作流模板注册表。"""

    saas = WorkflowTemplate(
        template_id="saas_competitor_analysis",
        name="SaaS 竞品分析",
        scenario=WorkflowScenario.SAAS,
        description="适用于协作办公、开发者工具、B2B 软件等 SaaS 产品。",
        nodes=_shared_pipeline_nodes(WorkflowScenario.SAAS),
        metadata={"default_depth": "standard"},
    )
    app = WorkflowTemplate(
        template_id="app_competitor_analysis",
        name="App / 互联网产品竞品分析",
        scenario=WorkflowScenario.APP,
        description="适用于内容社区、工具 App、消费互联网产品。",
        nodes=_shared_pipeline_nodes(WorkflowScenario.APP),
        metadata={"default_depth": "standard"},
    )
    return WorkflowTemplateRegistry([saas, app])
```

- [ ] **Step 4: Run template tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_templates.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/dag/templates.py tests/test_dag/test_templates.py
git commit -m "feat: add workflow template registry"
```

---

### Task 3: Add Template DAG Compiler

**Files:**
- Create: `src/dag/compiler.py`
- Create: `tests/test_dag/test_compiler.py`

- [ ] **Step 1: Write failing compiler tests**

Create `tests/test_dag/test_compiler.py`:

```python
import pytest

from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
from src.dag.models import NodeState
from src.dag.templates import get_default_template_registry


def test_compile_saas_template_to_task_dag():
    compiler = WorkflowCompiler(get_default_template_registry())
    dag = compiler.compile(WorkflowCompileRequest(
        task_id="task_saas",
        targets=["Notion", "ClickUp", "飞书"],
        scenario="saas",
        collection_depth="standard",
        schema={"report_audience": "product_manager"},
    ))

    assert dag.task_id == "task_saas"
    assert dag.workflow_template_id == "saas_competitor_analysis"
    assert dag.scenario == "saas"
    assert dag.targets == ["Notion", "ClickUp", "飞书"]
    assert dag.metadata["planning_mode"] == "template"
    assert all(node.state == NodeState.PENDING for node in dag.nodes)

    report = dag.get_node("report")
    assert report is not None
    assert report.agent_type == "ReportGenerator"
    assert report.stage == "reporting"
    assert report.role_group == "reporting"
    assert report.input_query["targets"] == ["Notion", "ClickUp", "飞书"]
    assert report.input_query["scenario"] == "saas"


def test_compile_app_template_to_task_dag():
    compiler = WorkflowCompiler(get_default_template_registry())
    dag = compiler.compile(WorkflowCompileRequest(
        task_id="task_app",
        targets=["小红书", "B站", "抖音"],
        scenario="app",
        collection_depth="deep",
        schema={"report_audience": "founder"},
    ))

    assert dag.workflow_template_id == "app_competitor_analysis"
    assert dag.scenario == "app"
    assert dag.metadata["collection_depth"] == "deep"
    assert dag.get_node("sentiment_analysis").display_name == "用户口碑分析"


def test_compile_rejects_empty_targets():
    compiler = WorkflowCompiler(get_default_template_registry())

    with pytest.raises(ValueError, match="targets"):
        compiler.compile(WorkflowCompileRequest(
            task_id="task_empty",
            targets=[],
            scenario="saas",
        ))


def test_compile_rejects_unknown_scenario():
    compiler = WorkflowCompiler(get_default_template_registry())

    with pytest.raises(ValueError, match="scenario"):
        compiler.compile(WorkflowCompileRequest(
            task_id="task_unknown",
            targets=["Notion"],
            scenario="retail",
        ))
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_compiler.py -v
```

Expected: fails because `src.dag.compiler` does not exist.

- [ ] **Step 3: Implement compiler**

Create `src/dag/compiler.py`:

```python
"""DAG 编译器：把用户输入和工作流模板转换为可执行 TaskDAG。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.dag.models import DAGNode, TaskDAG
from src.dag.templates import WorkflowScenario, WorkflowTemplateRegistry, get_default_template_registry


SCENARIO_TO_TEMPLATE_ID = {
    WorkflowScenario.SAAS.value: "saas_competitor_analysis",
    WorkflowScenario.APP.value: "app_competitor_analysis",
}


@dataclass(frozen=True)
class WorkflowCompileRequest:
    """编译 DAG 所需的最小请求信息。"""

    task_id: str
    targets: list[str]
    scenario: str = WorkflowScenario.SAAS.value
    collection_depth: str = "standard"
    schema: dict[str, Any] = field(default_factory=dict)


class WorkflowCompiler:
    """把模板编译成具体任务 DAG。"""

    def __init__(self, registry: WorkflowTemplateRegistry | None = None):
        self.registry = registry or get_default_template_registry()

    def compile(self, request: WorkflowCompileRequest) -> TaskDAG:
        targets = [target.strip() for target in request.targets if target and target.strip()]
        if not targets:
            raise ValueError("targets must contain at least one product")

        scenario = request.scenario.lower().strip()
        template_id = SCENARIO_TO_TEMPLATE_ID.get(scenario)
        if not template_id:
            raise ValueError(f"unsupported scenario: {request.scenario}")

        template = self.registry.get(template_id)
        nodes: list[DAGNode] = []

        for spec in template.nodes:
            input_query = {
                "targets": targets,
                "scenario": scenario,
                "stage": spec.stage,
                "role_group": spec.role_group,
                "collection_depth": request.collection_depth,
                "schema": request.schema,
                **spec.input_defaults,
            }
            nodes.append(DAGNode(
                node_id=spec.node_id,
                agent_type=spec.agent_type,
                input_query=input_query,
                depends_on=list(spec.depends_on),
                priority=spec.priority,
                max_retries=spec.max_retries,
                stage=spec.stage,
                role_group=spec.role_group,
                display_name=spec.display_name,
                description=spec.description,
                output_contract=spec.output_contract,
                degradation_policy=dict(spec.degradation_policy),
                source_policy=dict(spec.source_policy),
                context={
                    "workflow_template_id": template.template_id,
                    "workflow_template_name": template.name,
                    "scenario": scenario,
                },
            ))

        return TaskDAG(
            task_id=request.task_id,
            nodes=nodes,
            workflow_template_id=template.template_id,
            scenario=scenario,
            targets=targets,
            metadata={
                "planning_mode": "template",
                "workflow_template_name": template.name,
                "collection_depth": request.collection_depth,
                "template_description": template.description,
            },
        )
```

- [ ] **Step 4: Run compiler tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_compiler.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Run focused DAG tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_models.py tests/test_dag/test_templates.py tests/test_dag/test_compiler.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/dag/compiler.py tests/test_dag/test_compiler.py
git commit -m "feat: compile workflow templates into DAGs"
```

---

### Task 4: Emit Platform Metadata Through Scheduler Events

**Files:**
- Modify: `src/dag/scheduler.py`
- Modify: `src/api/websocket.py`
- Modify: `tests/test_dag/test_scheduler.py`

- [ ] **Step 1: Write failing scheduler payload test**

Append to `tests/test_dag/test_scheduler.py`:

```python
@pytest.mark.asyncio
async def test_emit_dag_created_includes_platform_metadata(scheduler):
    node = DAGNode(
        node_id="report",
        agent_type="ReportGenerator",
        input_query={},
        stage="reporting",
        role_group="reporting",
        display_name="报告生成",
        description="生成最终报告",
        output_contract="ReportOutput",
    )
    dag = TaskDAG(
        task_id="task_meta",
        nodes=[node],
        workflow_template_id="saas_competitor_analysis",
        scenario="saas",
        targets=["Notion", "ClickUp"],
        metadata={"planning_mode": "template"},
    )

    events = []

    async def on_dag_created(task_id, payload):
        events.append((task_id, payload))

    scheduler.on("dag_created", on_dag_created)
    await scheduler.emit_dag_created("task_meta", dag)

    assert events[0][0] == "task_meta"
    payload = events[0][1]
    assert payload["workflow_template_id"] == "saas_competitor_analysis"
    assert payload["scenario"] == "saas"
    assert payload["targets"] == ["Notion", "ClickUp"]
    assert payload["nodes"][0]["stage"] == "reporting"
    assert payload["nodes"][0]["role_group"] == "reporting"
    assert payload["nodes"][0]["display_name"] == "报告生成"
```

- [ ] **Step 2: Run scheduler test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_scheduler.py::test_emit_dag_created_includes_platform_metadata -v
```

Expected: fails because `emit_dag_created` currently emits a raw node list.

- [ ] **Step 3: Update scheduler payload**

Modify `src/dag/scheduler.py` `emit_dag_created`:

```python
async def emit_dag_created(self, task_id: str, dag) -> None:
    """Push full DAG structure to all WS clients when DAG generation completes."""
    self._dag_registry[task_id] = dag
    nodes_payload = []
    for node in dag.nodes:
        nodes_payload.append({
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state.value if hasattr(node.state, "value") else str(node.state),
            "depends_on": node.depends_on,
            "stage": getattr(node, "stage", ""),
            "role_group": getattr(node, "role_group", ""),
            "display_name": getattr(node, "display_name", ""),
            "description": getattr(node, "description", ""),
            "output_contract": getattr(node, "output_contract", ""),
        })
    payload = {
        "workflow_template_id": getattr(dag, "workflow_template_id", ""),
        "scenario": getattr(dag, "scenario", ""),
        "targets": getattr(dag, "targets", []),
        "metadata": getattr(dag, "metadata", {}),
        "nodes": nodes_payload,
    }
    await self._emit("dag_created", task_id, payload)
```

- [ ] **Step 4: Keep WebSocket compatibility**

Modify `src/api/websocket.py` `on_dag_created` so it accepts both old list payload and new dict payload:

```python
async def on_dag_created(task_id: str, nodes_payload):
    if isinstance(nodes_payload, dict):
        payload = nodes_payload
    else:
        payload = {"nodes": nodes_payload}
    await _broadcast(task_id, {"type": "dag_created", **payload})
```

- [ ] **Step 5: Run scheduler and websocket tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_scheduler.py tests/test_api/test_websocket.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/dag/scheduler.py src/api/websocket.py tests/test_dag/test_scheduler.py
git commit -m "feat: emit DAG platform metadata"
```

---

### Task 5: Use Template Compiler In Task API

**Files:**
- Modify: `src/api/routes/task.py`
- Modify: `tests/test_api/test_task.py`

- [ ] **Step 1: Write failing API schema test**

Append to `tests/test_api/test_task.py`:

```python
from src.api.routes.task import CreateTaskRequest


def test_create_task_request_defaults_to_template_planning():
    req = CreateTaskRequest(targets=["Notion", "ClickUp"], industry="saas")

    assert req.planning_mode == "template"
    assert req.industry == "saas"


def test_create_task_request_accepts_legacy_orchestrator_planning():
    req = CreateTaskRequest(
        targets=["Notion", "ClickUp"],
        industry="saas",
        planning_mode="orchestrator",
    )

    assert req.planning_mode == "orchestrator"
```

- [ ] **Step 2: Run API schema test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api/test_task.py::test_create_task_request_defaults_to_template_planning tests/test_api/test_task.py::test_create_task_request_accepts_legacy_orchestrator_planning -v
```

Expected: fails because `planning_mode` does not exist.

- [ ] **Step 3: Add planning mode field**

Modify `CreateTaskRequest` in `src/api/routes/task.py`:

```python
class CreateTaskRequest(BaseModel):
    targets: list[str]
    industry: str = "saas"
    planning_mode: str = "template"
    dimensions: list[dict] = []
    exclude_dimensions: list[str] = []
    focus_points: dict[str, list[str]] = {}
    dimension_weights: dict[str, float] = {}
    source_preferences: dict = {}
    benchmark_product: str | None = None
    report_audience: str = "product_manager"
    report_sections: list[str] = []
    output_formats: list[str] = ["markdown"]
    execution_mode: str = "auto"
    collection_depth: str = "standard"
    model_preference: str = "auto"
```

- [ ] **Step 4: Add template DAG planning helper**

Add imports:

```python
from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
```

Add helper above `_plan_and_execute`:

```python
def _compile_template_dag(task_id: str, req: CreateTaskRequest):
    compiler = WorkflowCompiler()
    return compiler.compile(WorkflowCompileRequest(
        task_id=task_id,
        targets=req.targets,
        scenario=req.industry,
        collection_depth=req.collection_depth,
        schema=req.model_dump(),
    ))
```

- [ ] **Step 5: Route default planning through compiler**

Modify the start of `_plan_and_execute` after `scheduler = get_scheduler()`:

```python
if req.planning_mode == "template":
    dag = _compile_template_dag(task_id, req)
elif req.planning_mode == "orchestrator":
    orch = OrchestratorAgent(gateway=gateway, store=store, tool_registry=tools)
    dag, _ = await orch.execute({
        "task_id": task_id,
        "targets": req.targets,
        "schema": req.model_dump(),
    })
else:
    await scheduler.emit_dag_failed(task_id, f"不支持的规划模式: {req.planning_mode}")
    return
```

Keep the existing `if dag is None` block after this branch.

For the mandatory-agent check, only apply it to orchestrator mode:

```python
if req.planning_mode == "orchestrator":
    agent_types = {n.agent_type for n in dag.nodes}
    missing_mandatory = [a for a in OrchestratorAgent.MANDATORY_AGENTS
                         if a not in agent_types]
    if missing_mandatory:
        error_msg = f"DAG 缺少强制 Agent: {', '.join(missing_mandatory)}。Orchestrator 后验证失败。"
        await scheduler.emit_dag_failed(task_id, error_msg)
        return
```

- [ ] **Step 6: Run API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api/test_task.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Run focused integration surface tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_compiler.py tests/test_api/test_task.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add src/api/routes/task.py tests/test_api/test_task.py
git commit -m "feat: plan tasks from workflow templates"
```

---

### Task 6: Add Compatibility Tests For Existing Pipeline

**Files:**
- Modify: `tests/test_dag/test_integration.py`

- [ ] **Step 1: Add compiler-to-scheduler simulation test**

Append to `tests/test_dag/test_integration.py`:

```python
@pytest.mark.asyncio
async def test_template_compiled_dag_runs_with_mock_executor():
    from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
    from src.dag.scheduler import DAGScheduler

    compiler = WorkflowCompiler()
    dag = compiler.compile(WorkflowCompileRequest(
        task_id="task_template_run",
        targets=["Notion", "ClickUp", "飞书"],
        scenario="saas",
    ))

    executed = []

    class MockExecutor:
        gateway = None
        store = None

        async def execute(self, node):
            executed.append(node.node_id)

    scheduler = DAGScheduler()
    await scheduler.run(dag, MockExecutor())

    assert dag.is_terminal() is True
    assert "source_discovery" in executed
    assert "report" in executed
    assert executed.index("source_discovery") < executed.index("collector")
    assert executed.index("report") > executed.index("swot")
```

- [ ] **Step 2: Run new integration test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag/test_integration.py::test_template_compiled_dag_runs_with_mock_executor -v
```

Expected: pass.

- [ ] **Step 3: Run replay pipeline tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_integration/test_pipeline_replay.py -v
```

Expected: replay tests pass; if fixture is missing, tests may be skipped according to the existing fixture behavior.

- [ ] **Step 4: Commit**

```powershell
git add tests/test_dag/test_integration.py
git commit -m "test: cover template DAG scheduler compatibility"
```

---

### Task 7: Update Context And Run Phase Verification

**Files:**
- Modify: `CONTEXT.md`

- [ ] **Step 1: Update context**

Update `CONTEXT.md` to:

```markdown
# CONTEXT.md

## 当前正在做什么
正在执行自研 Agent DAG 平台引擎第一阶段改造，已完成工作流模板、DAG 编译和任务 API 接入计划。

## 上次停在哪个位置
设计文档已确认；第一阶段计划聚焦 DAG 平台基础和模板化编译，不改前端主体验，不接 LangGraph，不做拖拽式编辑器。

## 近期关键决定和原因
一键报告默认使用确定性模板编译 DAG，保留 Orchestrator 作为显式 legacy 规划模式；这样可以提高稳定性，同时保留现有 Agent 和调度资产。
```

- [ ] **Step 2: Run focused backend verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dag tests/test_api/test_task.py tests/test_api/test_websocket.py -v
```

Expected: all selected tests pass.

- [ ] **Step 3: Run existing replay verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_integration/test_pipeline_replay.py -v
```

Expected: replay tests pass or skip only if the fixture is absent.

- [ ] **Step 4: Commit**

```powershell
git add CONTEXT.md
git commit -m "docs: update context for DAG platform foundation"
```

---

## Self-Review

- Spec coverage: this plan covers the first implementation slice of the redesign: DAG platform metadata, workflow templates, deterministic compiler, scheduler event metadata, task API integration, and focused verification.
- Deferred intentionally: frontend simplification, report trust upgrade, real QA local rerun, source status UI, and broader industry templates are separate later plans.
- Placeholder scan: no unresolved markers or undefined future-only functions are required by the execution steps.
- Compatibility: existing `TaskDAG`, `DAGNode`, `DAGScheduler`, and `AgentExecutor` stay in place; new fields have defaults so existing tests and replay fixtures remain compatible.
