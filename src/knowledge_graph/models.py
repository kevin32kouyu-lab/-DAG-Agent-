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


class ProductNode(GraphNode):
    node_type: NodeType = NodeType.PRODUCT
    layer: int = 1
    name: str
    category: str = ""
    url: str = ""


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
