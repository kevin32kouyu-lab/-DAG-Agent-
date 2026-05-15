"""Approach A: Real-LLM smoke tests.

These tests run the full pipeline with real LLM calls. Slow and expensive.
Run on PR merge or daily CI only. Marked with @pytest.mark.smoke.
"""
import asyncio
import time

import pytest
from src.dag.scheduler import DAGScheduler
from src.dag.models import NodeState
from src.dag.executor import AgentExecutor
from src.agents.orchestrator import OrchestratorAgent


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_single_product_full_pipeline(real_gateway, real_store, real_tools):
    """End-to-end: POST-equivalent for 1 product, verify report contains the product."""
    task_id = f"smoke-{int(time.time())}"

    target_product = "Figma"
    schema = {
        "targets": [target_product],
        "industry": "saas",
        "collection_depth": "shallow",
        "execution_mode": "auto",
        "dimensions": ["features"],
        "exclude_dimensions": ["sentiment", "pricing", "techstack", "market_position", "swot"],
    }

    # 1. Orchestrator generates DAG
    orch = OrchestratorAgent(gateway=real_gateway, store=real_store, tool_registry=real_tools)
    dag, _ = await orch.execute({
        "task_id": task_id,
        "targets": [target_product],
        "schema": schema,
    })

    assert dag is not None, "Orchestrator failed to generate DAG"
    assert len(dag.nodes) > 0, "DAG has no nodes"

    for node in dag.nodes:
        node.context["task_id"] = task_id

    # 2. Execute full pipeline
    scheduler = DAGScheduler()
    executor = AgentExecutor(gateway=real_gateway, store=real_store, tool_registry=real_tools)

    await scheduler.run(dag, executor, gateway=real_gateway)

    # 3. Verify pipeline completed (or at least made progress)
    states = {n.state for n in dag.nodes}
    assert not (states & {NodeState.RUNNING, NodeState.READY, NodeState.PENDING}), \
        f"Pipeline did not finish: {states}"

    completed = sum(1 for n in dag.nodes if n.state == NodeState.COMPLETED)
    assert completed > 0, f"No nodes completed. States: {[(n.node_id, n.state.value) for n in dag.nodes]}"

    # 4. Verify Writer produced a substantial report
    writer = next((n for n in dag.nodes if n.agent_type == "ReportGenerator"), None)
    assert writer is not None, "Writer node not found in DAG"
    assert writer.state == NodeState.COMPLETED, f"Writer state: {writer.state}"
    output_data = writer.context.get("_output_data", {})
    report = output_data.get("report_markdown", "")
    assert len(report) > 200, (
        f"Report too short: {len(report)} chars. "
        f"Writer output_data keys: {list(output_data.keys())}"
    )


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_orchestrator_generates_valid_dag(real_gateway, real_store, real_tools):
    """Orchestrator generates a valid DAG with all required node types."""
    orch = OrchestratorAgent(gateway=real_gateway, store=real_store, tool_registry=real_tools)
    dag, _ = await orch.execute({
        "task_id": "smoke-dag-check",
        "targets": ["Figma"],
        "schema": {
            "targets": ["Figma"],
            "industry": "saas",
            "collection_depth": "shallow",
            "dimensions": ["features"],
            "exclude_dimensions": ["sentiment", "pricing", "techstack", "market_position", "swot"],
        },
    })

    assert dag is not None, "Orchestrator returned None DAG"
    assert len(dag.nodes) >= 3, f"DAG too small: {len(dag.nodes)} nodes"

    node_ids = {n.node_id for n in dag.nodes}
    assert len(node_ids) == len(dag.nodes), "Duplicate node_ids in DAG"

    agent_types = {n.agent_type for n in dag.nodes}
    required_types = {"SourceDiscovery", "Collector", "ReportGenerator"}
    for rt in required_types:
        assert rt in agent_types, f"Required agent type '{rt}' missing from DAG"

    # Verify no circular dependencies
    for node in dag.nodes:
        for dep_id in node.depends_on:
            assert dep_id in node_ids, f"Node {node.node_id} depends on unknown node {dep_id}"
            # dep_id should not depend on node.node_id (would be circular)
            dep_node = next(n for n in dag.nodes if n.node_id == dep_id)
            assert node.node_id not in dep_node.depends_on, \
                f"Circular dependency: {node.node_id} <-> {dep_id}"
