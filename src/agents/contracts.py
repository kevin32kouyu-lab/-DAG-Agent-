from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    """所有 Agent 的基础输出类型。"""
    agent_type: str
    node_id: str
    status: str = "completed"
    summary: str = ""
    nodes_created: list[str] = Field(default_factory=list)
    edges_created: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    confidence: float = 0.0


class ReportOutput(AgentOutput):
    """报告撰写 Agent 的输出类型。"""
    agent_type: str = "ReportGenerator"
    report_markdown: str = ""
    sections: list[dict] = Field(default_factory=list)


class QAOutput(AgentOutput):
    """质检 Agent 的输出类型，包含事实校验和逻辑校验结果。"""
    agent_type: str = "QA"
    fact_issues: list[dict] = Field(default_factory=list)
    logic_issues: list[dict] = Field(default_factory=list)
    overall_pass: bool = True
    rejection_reason: str = ""


# ── 以下为旧版输出类型，保留以兼容旧测试和 fixtures ──

class FeatureMatrixOutput(AgentOutput):
    agent_type: str = "FeatureAnalyzer"
    matrix: dict = Field(default_factory=dict)


class SentimentOutput(AgentOutput):
    agent_type: str = "SentimentAnalyzer"
    sentiments: list[dict] = Field(default_factory=list)


class PricingOutput(AgentOutput):
    agent_type: str = "PricingAnalyst"
    models: list[dict] = Field(default_factory=list)


class TechStackOutput(AgentOutput):
    agent_type: str = "TechStackAnalyzer"
    stacks: list[dict] = Field(default_factory=list)


class MarketPositionOutput(AgentOutput):
    agent_type: str = "MarketPositionAnalyzer"
    positions: list[dict] = Field(default_factory=list)


class CrossReviewOutput(AgentOutput):
    agent_type: str = "CrossReviewAgent"
    flags: list[dict] = Field(default_factory=list)


class SWOTOutput(AgentOutput):
    agent_type: str = "SWOTAnalyzer"
    swot: dict = Field(default_factory=dict)
