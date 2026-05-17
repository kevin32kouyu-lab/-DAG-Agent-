"""Diagnose SourceDiscoveryAgent failure: print step-by-step ReAct traces."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from src.llm_gateway.gateway import LLMGateway
from src.knowledge_graph.store import GraphStore
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebSearchTool, WebScrapeTool
from src.agents.tools.company_scope import CompanyScopeTool
from src.agents.source_discovery import SourceDiscoveryAgent


async def main():
    # Use a temp in-memory DB
    store = GraphStore(db_path=":memory:")

    gateway = LLMGateway(
        default_model="deepseek-chat",
        model_map={
            "reasoning": "deepseek-chat",
            "analysis": "deepseek-chat",
            "batch": "deepseek-chat",
        },
        provider_map={"deepseek-chat": "openai_compatible"},
    )

    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebSearchTool)
    tools.register(WebScrapeTool)
    tools.register(CompanyScopeTool)

    agent = SourceDiscoveryAgent(
        gateway=gateway, store=store, tool_registry=tools,
    )
    task = {
        "task_id": "diag_p1", "node_id": "sd1", "agent_type": "SourceDiscovery",
        "input_query": {"targets": ["Notion"]}, "context": {},
    }

    print("=" * 60)
    print("Running SourceDiscoveryAgent with max_steps=4...")
    print("=" * 60)

    output, traces = await agent.execute(task)

    print(f"\nFinal output: status={output.status}, confidence={output.confidence}")
    print(f"\n--- {len(traces)} step traces ---")
    for i, t in enumerate(traces):
        print(f"\nStep {i}: action={t.action}, reasoning={t.reasoning[:200]}")
        print(f"  action_params: {t.action_params}")
        print(f"  action_result: {(t.action_result_summary or '')[:300]}")
        print(f"  confidence: {t.confidence}")
        if t.nodes_created:
            print(f"  nodes_created: {t.nodes_created}")
        if t.edges_created:
            print(f"  edges_created: {t.edges_created}")

    # Also check: does the LLM support response_format json_object?
    print("\n" + "=" * 60)
    print("Test: direct gateway call with response_format json_object")
    print("=" * 60)
    resp = await gateway.chat(
        system="You are a helpful assistant. Respond with JSON.",
        messages=[{"role": "user", "content": 'Say hello, respond with {"greeting": "hello", "language": "english"}'}],
        model_tier="batch",
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    print(f"Response content: {resp.content[:500]}")
    print(f"Tokens: in={resp.tokens_in}, out={resp.tokens_out}")


if __name__ == "__main__":
    asyncio.run(main())
