"""
Diagnostic script: run all 5 analyzers with real DeepSeek LLM, capture full traces.
Usage: python -m pytest tests/test_agents/test_diagnose_analyzers.py -v -s
"""
import json
import os
import sys
import pytest
import asyncio
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

API_KEY = os.getenv("OPENAI_API_KEY_DEEPSEEK_CHAT")
if not API_KEY:
    pytest.skip("需要 OPENAI_API_KEY_DEEPSEEK_CHAT", allow_module_level=True)

from src.llm_gateway.gateway import LLMGateway
from src.knowledge_graph.store import GraphStore
from src.knowledge_graph.models import (
    SourceInfoNode, WebPageNode, ReviewEntryNode, PricingDataNode,
)
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebSearchTool, WebScrapeTool
from src.agents.feature_analyzer import FeatureAnalyzer
from src.agents.sentiment_analyzer import SentimentAnalyzer
from src.agents.pricing_analyst import PricingAnalyst
from src.agents.techstack_analyzer import TechStackAnalyzer
from src.agents.market_position import MarketPositionAnalyzer


# ── Fixtures ──

@pytest.fixture
def live_gateway():
    return LLMGateway(
        default_model="deepseek-chat",
        model_map={
            "reasoning": "deepseek-chat",
            "analysis": "deepseek-chat",
            "batch": "deepseek-chat",
        },
        provider_map={"deepseek-chat": "openai_compatible"},
    )


@pytest.fixture
def live_store(temp_db_path):
    return GraphStore(db_path=temp_db_path)


@pytest.fixture
def live_tools(live_store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=live_store)
    tools.register(GraphWriteTool, store=live_store)
    tools.register(WebSearchTool)
    tools.register(WebScrapeTool)
    return tools


def seed_store(store):
    """Simulate a successful upstream pipeline with Layer 1 data for 3 products."""
    for product in ["Notion", "Confluence", "Linear"]:
        store.create_node(WebPageNode(
            url=f"https://{product.lower()}.com",
            title=f"{product} Official",
            text=f"{product} is a collaborative tool for teams. "
                 f"It offers project management, documentation, and workflow automation features.",
            key_paragraphs=[
                f"{product} helps teams collaborate effectively.",
                f"Key features include real-time editing, integrations, and custom workflows.",
            ],
        ))
        store.create_node(SourceInfoNode(
            url=f"https://{product.lower()}.com",
            domain=f"{product.lower()}.com",
            credibility_score=0.9,
        ))
        store.create_node(ReviewEntryNode(
            source="G2",
            rating=4.0 + (0.3 if product == "Notion" else 0),
            text=f"Great {product} features for collaboration and project tracking. "
                 f"Some users wish the pricing was more flexible.",
            verified=True,
        ))
        store.create_node(PricingDataNode(
            product=product,
            plan_name="Standard",
            price={"Notion": 10.0, "Confluence": 5.75, "Linear": 8.0}[product],
            currency="USD",
            billing_cycle="monthly",
            features=["Unlimited pages", "Collaboration", "API access"],
        ))
    print(f"  Seeded {len(store.query_nodes())} nodes in knowledge graph")


# ── Diagnostic runner ──

AGENTS = [
    (FeatureAnalyzer, "FeatureAnalyzer", {"products": ["Notion", "Confluence", "Linear"]}),
    (SentimentAnalyzer, "SentimentAnalyzer", {"products": ["Notion", "Confluence", "Linear"]}),
    (PricingAnalyst, "PricingAnalyst", {"products": ["Notion", "Confluence", "Linear"]}),
    (TechStackAnalyzer, "TechStackAnalyzer", {"products": ["Notion", "Confluence", "Linear"]}),
    (MarketPositionAnalyzer, "MarketPositionAnalyzer", {"products": ["Notion", "Confluence", "Linear"]}),
]


async def run_agent(agent_cls, agent_name, input_query, gateway, store, tools):
    """Run a single agent and return detailed diagnostics."""
    agent = agent_cls(gateway=gateway, store=store, tool_registry=tools)
    task = {
        "task_id": f"diag_{agent_name}",
        "node_id": f"{agent_name}_1",
        "agent_type": agent_name,
        "input_query": input_query,
        "context": {},
    }

    try:
        output, traces = await agent.execute(task)
        return {
            "agent": agent_name,
            "status": "PASS",
            "output_status": output.status,
            "summary": output.summary[:200] if output.summary else "(empty)",
            "steps": len(traces),
            "traces": [
                {
                    "step": t.step_number,
                    "action": t.action,
                    "reasoning": t.reasoning[:150],
                    "confidence": t.confidence,
                    "llm_tokens": t.llm_tokens,
                    "nodes_created": t.nodes_created,
                    "edges_created": t.edges_created,
                }
                for t in traces
            ],
        }
    except Exception as e:
        return {
            "agent": agent_name,
            "status": "FAIL",
            "error": str(e),
            "error_type": type(e).__name__,
            "steps": 0,
            "traces": [],
        }


# ── Tests ──

@pytest.mark.asyncio
async def test_diagnose_all_analyzers_with_data(live_gateway, live_store, live_tools):
    """Run all 5 analyzers with seeded data and report detailed results."""
    seed_store(live_store)

    results = []
    for agent_cls, name, input_query in AGENTS:
        print(f"\n{'='*60}")
        print(f"  Running {name}...")
        print(f"{'='*60}")
        result = await run_agent(agent_cls, name, input_query, live_gateway, live_store, live_tools)
        results.append(result)

        # Print detailed trace
        if result["status"] == "PASS":
            print(f"  [PASS] {name}: {result['steps']} steps, status={result['output_status']}")
            for t in result["traces"]:
                print(f"    Step {t['step']}: action={t['action']}, conf={t['confidence']}, "
                      f"tokens={t['llm_tokens']}, reason={t['reasoning'][:100]}")
            print(f"    Summary: {result['summary']}")
        else:
            print(f"  [FAIL] {name}: {result['error_type']}: {result['error'][:300]}")

    # Summary
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] != "PASS"]
    print(f"\n{'='*60}")
    print(f"  DIAGNOSTIC SUMMARY: {len(passed)}/{len(results)} passed")
    print(f"{'='*60}")
    for r in passed:
        print(f"  [PASS] {r['agent']}: {r['steps']} steps, summary={r['summary'][:100]}")
    for r in failed:
        print(f"  [FAIL] {r['agent']}: {r.get('error', 'unknown')[:200]}")
    print()

    if failed:
        pytest.fail(f"{len(failed)} analyzers failed: {[r['agent'] for r in failed]}")


@pytest.mark.asyncio
async def test_diagnose_analyzer_with_empty_graph(live_gateway, live_store, live_tools):
    """Run FeatureAnalyzer with EMPTY knowledge graph to test fallback behavior."""
    print(f"\n{'='*60}")
    print(f"  Running FeatureAnalyzer with EMPTY graph (testing fallback)...")
    print(f"{'='*60}")

    result = await run_agent(
        FeatureAnalyzer, "FeatureAnalyzer",
        {"products": ["Notion"]},
        live_gateway, live_store, live_tools,
    )

    if result["status"] == "PASS":
        print(f"  [PASS] Fallback works: {result['steps']} steps, summary={result['summary']}")
        for t in result["traces"]:
            print(f"    Step {t['step']}: action={t['action']}, conf={t['confidence']}")
    else:
        print(f"  [FAIL] Fallback failed: {result['error_type']}: {result['error'][:300]}")
        # Don't fail the test — this is diagnostic, the fallback might genuinely have issues


if __name__ == "__main__":
    # Allow running directly without pytest
    async def main():
        from src.knowledge_graph.store import GraphStore
        import tempfile, os

        gateway = LLMGateway(
            default_model="deepseek-chat",
            model_map={"reasoning": "deepseek-chat", "analysis": "deepseek-chat", "batch": "deepseek-chat"},
            provider_map={"deepseek-chat": "openai_compatible"},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            store = GraphStore(db_path=db_path)
            tools = ToolRegistry()
            tools.register(GraphQueryTool, store=store)
            tools.register(GraphWriteTool, store=store)
            tools.register(WebSearchTool)
            tools.register(WebScrapeTool)

            # Seed with data
            for product in ["Notion", "Confluence", "Linear"]:
                store.create_node(WebPageNode(
                    url=f"https://{product.lower()}.com",
                    title=f"{product} Official",
                    text=f"{product} is a collaborative tool for teams.",
                ))
                store.create_node(SourceInfoNode(
                    url=f"https://{product.lower()}.com",
                    domain=f"{product.lower()}.com",
                    credibility_score=0.9,
                ))
                store.create_node(ReviewEntryNode(
                    source="G2", rating=4.0,
                    text=f"Great {product} features",
                ))
                store.create_node(PricingDataNode(
                    product=product, plan_name="Standard",
                    price=10.0, currency="USD", billing_cycle="monthly",
                ))
            print(f"Seeded {len(store.query_nodes())} nodes\n")

            for agent_cls, name, input_query in AGENTS:
                print(f"\n{'='*60}")
                print(f"  {name}")
                print(f"{'='*60}")
                result = await run_agent(agent_cls, name, input_query, gateway, store, tools)
                if result["status"] == "PASS":
                    print(f"  ✓ {result['steps']} steps, status={result['output_status']}")
                    for t in result["traces"]:
                        print(f"    Step {t['step']}: action={t['action']}, conf={t['confidence']}, "
                              f"tokens={t['llm_tokens']}")
                    print(f"    Summary: {result['summary']}")
                else:
                    print(f"  ✗ FAILED: {result['error_type']}: {result['error'][:500]}")

    asyncio.run(main())
