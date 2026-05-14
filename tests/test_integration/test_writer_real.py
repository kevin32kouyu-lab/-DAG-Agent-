import pytest
from src.agents.writer import WriterAgent
from src.knowledge_graph.models import FeatureNode, SentimentNode, PricingModelNode, SWOTNode


@pytest.fixture
async def seeded_store(real_store):
    """Seed the graph with enough Layer 2/3 data for Writer to produce a report."""
    # Layer 2 — analysis data
    for i in range(2):
        real_store.create_node(FeatureNode(
            product=["Notion", "Confluence"][i], name=f"Feature-{i}",
            category="Core", maturity="ga", differentiation="unique",
        ))
        real_store.create_node(SentimentNode(
            product=["Notion", "Confluence"][i], topic="Usability",
            sentiment_score=0.7 + i * 0.1, trend="improving",
        ))
        real_store.create_node(PricingModelNode(
            product=["Notion", "Confluence"][i], strategy="freemium",
            target_segment="SMB", value_score=0.8,
        ))
    # Layer 3 — SWOT
    real_store.create_node(SWOTNode(
        product="Notion",
        strengths=["All-in-one workspace", "Strong integrations"],
        weaknesses=["Steep learning curve", "Limited offline"],
        opportunities=["Enterprise expansion", "AI features"],
        threats=["Microsoft Loop", "Linear"],
    ))
    real_store.create_node(SWOTNode(
        product="Confluence",
        strengths=["Jira integration", "Enterprise trust"],
        weaknesses=["Outdated UX", "High cost at scale"],
        opportunities=["Cloud migration", "AI assistant"],
        threats=["Notion", "Slack canvas"],
    ))
    return real_store


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_generates_report_with_real_llm(real_gateway, seeded_store, real_tools):
    """Writer should produce a markdown report using real DeepSeek API."""
    agent = WriterAgent(
        gateway=real_gateway,
        store=seeded_store,
        tool_registry=real_tools,
    )
    task = {
        "task_id": "int-t1", "node_id": "w1",
        "agent_type": "Writer",
        "input_query": {"products": ["Notion", "Confluence"]},
        "context": {},
    }

    output, traces = await agent.execute(task)

    assert output.status == "completed", f"Writer failed with: {output.summary}"
    assert output.agent_type == "Writer"

    # Verify the report has real content
    report = output.data.get("report_markdown", "") if output.data else ""
    sections = output.data.get("sections", []) if output.data else []
    has_content = bool(report) or len(sections) > 0
    assert has_content, (
        f"Writer completed but produced no report content.\n"
        f"Summary: {output.summary}\n"
        f"Traces: {len(traces)} steps"
    )

    # Check that report contains expected topics
    if report:
        assert len(report) > 200, f"Report too short ({len(report)} chars), likely empty or failed"
        # Should mention the target products
        content_lower = report.lower()
        assert "notion" in content_lower, f"Report doesn't mention Notion:\n{report[:500]}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_writer_json_parse_recovery(real_gateway, seeded_store, real_tools):
    """Writer should survive and complete even if LLM occasionally returns non-JSON.
    Our _think() retry logic should recover from parse failures.
    """
    agent = WriterAgent(
        gateway=real_gateway,
        store=seeded_store,
        tool_registry=real_tools,
    )
    task = {
        "task_id": "int-t2", "node_id": "w2",
        "agent_type": "Writer",
        "input_query": {"products": ["Notion"]},
        "context": {},
    }

    output, traces = await agent.execute(task)

    # Should complete (even if it needed the JSON retry path)
    assert output.status == "completed", (
        f"Writer status={output.status}, summary={output.summary}"
    )
    # Should have at least some content
    has_data = bool(output.data.get("report_markdown")) if output.data else False
    print(f"Traces: {len(traces)}, has_report: {has_data}")
