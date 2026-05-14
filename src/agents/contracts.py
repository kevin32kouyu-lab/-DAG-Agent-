from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    agent_type: str
    node_id: str
    status: str = "completed"
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
