"""工作流模板定义：把竞品分析场景拆成稳定的 DAG 节点规格。

重构后使用 4 个 Agent 类（Collector, Analyst, Writer, QA），
DAG 上保留 8 个节点以支持独立重试和可视化。
"""

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
    """默认公开来源策略。"""
    return {
        "preferred": ["official_site", "pricing_page", "docs", "reviews", "news"],
        "allow_cache": True,
        "allow_fallback": True,
    }


def _standard_degradation_policy() -> dict[str, Any]:
    """默认降级策略：单点失败不阻塞整份报告。"""
    return {
        "max_failures_before_degraded": 3,
        "continue_on_partial_data": True,
        "mark_low_confidence": True,
    }


def _demo_pipeline_nodes() -> list[WorkflowNodeSpec]:
    """Demo 模板的精简管线（6 节点，跳过 cross_review/QA）。

    设计目标：配合 ``TOOL_CACHE_MODE=force_cache`` 在 5 分钟内出报告，用于路演录制。
    - 跳过 techstack 维度（4 维度足够呈现核心对比）
    - 跳过 cross_review + qa（节省 30-60s）
    - 所有 Analyst 节点并行依赖 Collector
    """
    return [
        # ── URL 发现层 ──
        WorkflowNodeSpec(
            node_id="collector",
            agent_type="Collector",
            stage="collection",
            role_group="research",
            display_name="URL 发现",
            description="搜索每个目标产品的官网/定价/评测页 URL，写入 SourceInfo 节点。",
            output_contract="AgentOutput",
            source_policy=_default_source_policy(),
            degradation_policy=_standard_degradation_policy(),
            max_retries=2,
        ),
        # ── 分析层：4 维度并行 ──
        WorkflowNodeSpec(
            node_id="feature_analysis",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="功能对比分析",
            description="抓取官网功能页，识别核心功能、成熟度、差异点。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "feature"},
            max_retries=2,
        ),
        WorkflowNodeSpec(
            node_id="pricing_analysis",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="定价与商业模式分析",
            description="抓取定价页，识别套餐、价格、目标客群。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "pricing"},
            max_retries=2,
        ),
        WorkflowNodeSpec(
            node_id="sentiment_analysis",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="用户口碑分析",
            description="纯 API 拉 Reddit / Product Hunt / 小红书等用户讨论。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "sentiment"},
            max_retries=2,
        ),
        WorkflowNodeSpec(
            node_id="market_position",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="市场定位分析",
            description="新闻 + 搜索趋势 API 推断定位、GTM 策略、竞争格局。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "market_position"},
            max_retries=2,
        ),
        # ── 合成层：Writer ──
        WorkflowNodeSpec(
            node_id="report",
            agent_type="ReportGenerator",
            stage="reporting",
            role_group="reporting",
            display_name="报告生成",
            description="综合 4 维度分析，生成竞品对比报告。",
            depends_on=[
                "feature_analysis", "pricing_analysis",
                "sentiment_analysis", "market_position",
            ],
            output_contract="ReportOutput",
            max_retries=1,
        ),
    ]


def _shared_pipeline_nodes(scenario: WorkflowScenario) -> list[WorkflowNodeSpec]:
    """生成 SaaS 和 App 共用的主流程节点（8 节点，4 个 Agent 类）。"""

    scenario_label = "SaaS" if scenario == WorkflowScenario.SAAS else "App"
    return [
        # ── 采集层：Collector Agent ──
        WorkflowNodeSpec(
            node_id="collector",
            agent_type="Collector",
            stage="collection",
            role_group="research",
            display_name="信息采集",
            description=f"发现 {scenario_label} 竞品信息源、抓取网页数据、结构化抽取到知识图谱。",
            output_contract="AgentOutput",
            source_policy=_default_source_policy(),
            degradation_policy=_standard_degradation_policy(),
        ),
        # ── 分析层：Analyst Agent × 5 个维度 ──
        WorkflowNodeSpec(
            node_id="feature_analysis",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="功能对比分析",
            description="提取功能树和功能矩阵。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "feature"},
            max_retries=2,
        ),
        WorkflowNodeSpec(
            node_id="pricing_analysis",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="定价与商业模式分析",
            description="分析价格、套餐、商业化方式和目标客群。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "pricing"},
            max_retries=2,
        ),
        WorkflowNodeSpec(
            node_id="sentiment_analysis",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="用户口碑分析",
            description="分析评论、社媒和公开反馈中的情绪与痛点。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "sentiment"},
            max_retries=2,
        ),
        WorkflowNodeSpec(
            node_id="techstack_analysis",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="技术与生态分析",
            description="从公开资料中推断技术栈、集成生态和平台能力。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "techstack"},
            max_retries=2,
        ),
        WorkflowNodeSpec(
            node_id="market_position",
            agent_type="Analyst",
            stage="analysis",
            role_group="analysis",
            display_name="市场定位分析",
            description="分析定位、目标用户、差异化和增长策略。",
            depends_on=["collector"],
            output_contract="AgentOutput",
            input_defaults={"dimension": "market_position"},
            max_retries=2,
        ),
        # ── 审查层：Analyst Agent（cross_review 维度）──
        WorkflowNodeSpec(
            node_id="cross_review",
            agent_type="Analyst",
            stage="review",
            role_group="quality",
            display_name="交叉审查",
            description="检查不同分析维度之间的冲突、遗漏和低可信结论。",
            depends_on=[
                "feature_analysis", "pricing_analysis",
                "sentiment_analysis", "techstack_analysis", "market_position",
            ],
            output_contract="AgentOutput",
            input_defaults={"dimension": "cross_review"},
            max_retries=1,
        ),
        # ── 合成层：Writer Agent ──
        WorkflowNodeSpec(
            node_id="report",
            agent_type="ReportGenerator",
            stage="reporting",
            role_group="reporting",
            display_name="报告生成",
            description="综合 SWOT 分析，生成竞品分析报告。",
            depends_on=["cross_review"],
            output_contract="ReportOutput",
        ),
        # ── 质检层：QA Agent ──
        WorkflowNodeSpec(
            node_id="qa",
            agent_type="QA",
            stage="qa",
            role_group="quality",
            display_name="质检校验",
            description="事实校验 + 逻辑校验，确保报告质量。",
            depends_on=["report"],
            output_contract="QAOutput",
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
    demo = WorkflowTemplate(
        template_id="demo_competitor_analysis",
        name="Demo 快速竞品分析（5 分钟）",
        scenario=WorkflowScenario.SAAS,
        description="录制 demo 用：4 维度并行，跳过 cross_review/QA，配合缓存 5 分钟出报告。",
        nodes=_demo_pipeline_nodes(),
        metadata={"default_depth": "demo", "expected_duration_seconds": 180},
    )
    return WorkflowTemplateRegistry([saas, app, demo])
