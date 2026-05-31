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
            output_contract="FeatureMatrixOutput",
        ),
        WorkflowNodeSpec(
            node_id="pricing_analysis",
            agent_type="PricingAnalyst",
            stage="analysis",
            role_group="analysis",
            display_name="定价与商业模式分析",
            description="分析价格、套餐、商业化方式和目标客群。",
            depends_on=["data_enricher"],
            output_contract="PricingOutput",
        ),
        WorkflowNodeSpec(
            node_id="sentiment_analysis",
            agent_type="SentimentAnalyzer",
            stage="analysis",
            role_group="analysis",
            display_name="用户口碑分析",
            description="分析评论、社媒和公开反馈中的情绪与痛点。",
            depends_on=["data_enricher"],
            output_contract="SentimentOutput",
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
