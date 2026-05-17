"""
Replay-based integration tests (Plan A).

Fixtures are recorded once with real LLM, then replayed deterministically.
To record:  RECORD_FIXTURES=1 pytest tests/test_agents/test_replay.py -v -s
To replay:               pytest tests/test_agents/test_replay.py -v
"""
import os
import pytest
from pathlib import Path
from dotenv import load_dotenv

from tests.replay_gateway import ReplayGateway, FIXTURE_DIR, record_agent_fixture
from src.llm_gateway.gateway import LLMGateway
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    WebPageNode, SourceInfoNode, ReviewEntryNode, PricingDataNode,
    FeatureNode, FeatureMatrixNode, SentimentNode, PricingModelNode,
    TechStackNode, MarketPositionNode, CrossReviewFlagNode,
    SWOTNode, InsightNode, ReportSectionNode,
    GraphEdge, EdgeType,
)
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebSearchTool, WebScrapeTool
from src.agents.tools.company_scope import CompanyScopeTool

# Analyzers (already covered)
from src.agents.feature_analyzer import FeatureAnalyzer
from src.agents.sentiment_analyzer import SentimentAnalyzer
from src.agents.pricing_analyst import PricingAnalyst
from src.agents.techstack_analyzer import TechStackAnalyzer
from src.agents.market_position import MarketPositionAnalyzer

# Upstream (new)
from src.agents.source_discovery import SourceDiscoveryAgent
from src.agents.collector import CollectorAgent
from src.agents.data_enricher import DataEnricherAgent

# Downstream (new)
from src.agents.cross_review import CrossReviewAgent
from src.agents.swot_synthesizer import SWOTAnalyzer
from src.agents.writer import WriterAgent

# QA (new)
from src.agents.qa_fact_check import QAFactCheckAgent
from src.agents.qa_logic_check import QALogicCheckAgent

_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

RECORD_MODE = os.getenv("RECORD_FIXTURES", "").lower() in ("1", "true", "yes")


# ── Fixture definitions: name → (agent_cls, seed_fn, task_input_query) ──
# seed_fn is None → use default Layer 1 seed

def _seed_layer1(store):
    """Basic Layer 1 data: web pages, sources, reviews, pricing for 3 products."""
    for product, price in [("Notion", 10.0), ("Confluence", 5.75), ("Linear", 8.0)]:
        store.create_node(WebPageNode(
            url=f"https://{product.lower()}.com",
            title=f"{product} Official",
            text=f"{product} is a collaborative tool for teams. "
                 f"It offers project management, documentation, and workflow automation features.",
        ))
        store.create_node(SourceInfoNode(
            url=f"https://{product.lower()}.com",
            domain=f"{product.lower()}.com",
            credibility_score=0.9,
        ))
        store.create_node(ReviewEntryNode(
            source="G2", rating=4.0,
            text=f"Great {product} features for collaboration and project tracking.",
            verified=True,
        ))
        store.create_node(PricingDataNode(
            product=product, plan_name="Standard",
            price=price, currency="USD", billing_cycle="monthly",
        ))


def _seed_layer12(store):
    """Layer 1 + Layer 2 analysis data for downstream agents."""
    _seed_layer1(store)
    # Layer 2: Feature, Sentiment, Pricing, TechStack, MarketPosition
    for product in ["Notion", "Confluence", "Linear"]:
        feat = FeatureNode(product=product, name="Real-time Collaboration", category="Core",
                           maturity="ga", differentiation="advantage")
        store.create_node(feat)
        sent = SentimentNode(product=product, topic="Ease of Use",
                             sentiment_score=0.75, trend="stable")
        store.create_node(sent)
        price_m = PricingModelNode(product=product, strategy="per-seat",
                                   target_segment="SMB", value_score=0.6)
        store.create_node(price_m)
        tech = TechStackNode(product=product, languages=["TypeScript"],
                             frameworks=["React"], infra=["AWS"], confidence=0.5)
        store.create_node(tech)
        mkt = MarketPositionNode(product=product, positioning="Team workspace",
                                 gtm_strategy="PLG", target_audience="PM/Designer")
        store.create_node(mkt)


def _seed_layers_full(store):
    """Layer 1 + 2 + 3 + CrossReview for writer/QA."""
    _seed_layer12(store)
    # CrossReview flags
    crf = CrossReviewFlagNode(flag_type="conflict", severity="medium",
                              involved_agents=["FeatureAnalyzer", "SentimentAnalyzer"],
                              description="Sentiment disagrees with feature rating")
    store.create_node(crf)
    # SWOT
    swot = SWOTNode(product="Notion",
                    strengths=["All-in-one workspace", "Strong brand"],
                    weaknesses=["Per-seat pricing can be expensive"],
                    opportunities=["AI features", "Enterprise expansion"],
                    threats=["Microsoft Loop", "Linear growing fast"])
    store.create_node(swot)
    # Report sections for QA
    insight = InsightNode(insight="Notion leads in all-in-one workspace category",
                          confidence=0.8, importance="high")
    store.create_node(insight)
    report = ReportSectionNode(section="Pricing Analysis",
                               content="Notion's per-seat pricing at $10/mo...", order=3)
    store.create_node(report)


ALL_FIXTURES = {
    # ── Analyzers (existing) ──
    "feature_analyzer": (FeatureAnalyzer, _seed_layer1,
                         {"products": ["Notion", "Confluence", "Linear"]}),
    "sentiment_analyzer": (SentimentAnalyzer, _seed_layer1,
                           {"products": ["Notion", "Confluence", "Linear"]}),
    "pricing_analyst": (PricingAnalyst, _seed_layer1,
                        {"products": ["Notion", "Confluence", "Linear"]}),
    "techstack_analyzer": (TechStackAnalyzer, _seed_layer1,
                           {"products": ["Notion", "Confluence", "Linear"]}),
    "market_position": (MarketPositionAnalyzer, _seed_layer1,
                        {"products": ["Notion", "Confluence", "Linear"]}),

    # ── Upstream collection ──
    "source_discovery": (SourceDiscoveryAgent, lambda s: None,
                         {"targets": ["Notion"]}),
    "collector": (CollectorAgent, lambda s: _seed_layer1(s),
                  {"urls": ["https://notion.so"], "product": "Notion"}),
    "data_enricher": (DataEnricherAgent, _seed_layer1,
                      {"products": ["Notion"]}),

    # ── Downstream synthesis ──
    "cross_review": (CrossReviewAgent, _seed_layer12,
                     {"products": ["Notion"]}),
    "swot_synthesizer": (SWOTAnalyzer, _seed_layer12,
                         {"products": ["Notion"]}),
    "writer": (WriterAgent, _seed_layers_full,
               {"targets": ["Notion"]}),

    # ── QA ──
    "qa_fact_check": (QAFactCheckAgent, _seed_layers_full, {}),
    "qa_logic_check": (QALogicCheckAgent, _seed_layers_full, {}),

    # ── Edge cases ──
    "feature_analyzer_empty": (FeatureAnalyzer, lambda s: None,
                               {"products": ["Notion"]}),
}


# ── Shared tool setup ──

def _build_tools(store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebSearchTool)
    tools.register(WebScrapeTool)
    tools.register(CompanyScopeTool)
    return tools


def _make_gateway():
    return LLMGateway(
        default_model="deepseek-chat",
        model_map={"reasoning": "deepseek-chat", "analysis": "deepseek-chat", "batch": "deepseek-chat"},
        provider_map={"deepseek-chat": "openai_compatible"},
    )


# ── Record mode ──

@pytest.mark.skipif(not RECORD_MODE, reason="Set RECORD_FIXTURES=1 to record")
@pytest.mark.parametrize("fixture_name", list(ALL_FIXTURES.keys()))
@pytest.mark.asyncio
async def test_record_all(fixture_name, temp_db_path):
    api_key = os.getenv("OPENAI_API_KEY_DEEPSEEK_CHAT")
    if not api_key:
        pytest.skip("OPENAI_API_KEY_DEEPSEEK_CHAT not set")

    agent_cls, seed_fn, input_query = ALL_FIXTURES[fixture_name]
    gateway = _make_gateway()
    store = GraphStore(db_path=temp_db_path)
    seed_fn(store)
    tools = _build_tools(store)

    task = {
        "task_id": f"rec_{fixture_name}",
        "node_id": f"{fixture_name}_1",
        "agent_type": agent_cls.agent_type,
        "input_query": input_query,
        "context": {},
    }

    fixture_path = FIXTURE_DIR / f"{fixture_name}.json"
    saved_path = await record_agent_fixture(
        agent_cls, fixture_name, gateway, store, tools, task, fixture_path,
    )
    print(f"  Recorded {fixture_name} -> {saved_path}")
    assert saved_path.exists()


# ── Replay mode ──

@pytest.mark.skipif(RECORD_MODE, reason="Recording mode — skip replay")
@pytest.mark.parametrize("fixture_name", list(ALL_FIXTURES.keys()))
@pytest.mark.asyncio
async def test_replay_all(fixture_name, temp_db_path):
    fixture_path = FIXTURE_DIR / f"{fixture_name}.json"
    if not fixture_path.exists():
        pytest.skip(f"Fixture missing: {fixture_path}. Run RECORD_FIXTURES=1 first.")

    agent_cls, seed_fn, input_query = ALL_FIXTURES[fixture_name]
    gateway = ReplayGateway(fixture_path)
    store = GraphStore(db_path=temp_db_path)
    seed_fn(store)
    tools = _build_tools(store)

    agent = agent_cls(gateway=gateway, store=store, tool_registry=tools)
    task = {
        "task_id": f"replay_{fixture_name}",
        "node_id": f"{fixture_name}_1",
        "agent_type": agent_cls.agent_type,
        "input_query": input_query,
        "context": {},
    }

    output, traces = await agent.execute(task)

    assert output.status in ("completed", "degraded"), \
        f"{fixture_name}: expected completed|degraded, got {output.status}"
    assert len(traces) >= 1, f"{fixture_name}: expected at least 1 trace"
    assert output.agent_type == agent_cls.agent_type
    assert output.summary, f"{fixture_name}: expected non-empty summary"


if __name__ == "__main__":
    print("Record:  RECORD_FIXTURES=1 pytest tests/test_agents/test_replay.py -v -s")
    print("Replay:  pytest tests/test_agents/test_replay.py -v")
