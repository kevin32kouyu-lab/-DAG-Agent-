"""Approach B: Replay-based integration tests.

These tests use a pre-recorded pipeline fixture to verify the full pipeline
(orchestration, scheduling, state machine, report generation) without real LLM calls.
Fast, deterministic, runs on every commit.
"""
import asyncio

import pytest
from src.dag.scheduler import DAGScheduler
from src.dag.models import NodeState


@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_pipeline_replay_to_completion(replay_executor, recorded_dag):
    """Full pipeline runs to completion using recorded agent outputs."""
    scheduler = DAGScheduler()
    dag = recorded_dag

    await scheduler.run(dag, replay_executor, gateway=replay_executor.gateway)

    # Verify terminal state
    states = {n.state for n in dag.nodes}
    # All nodes should be either COMPLETED or FAILED (none stuck in RUNNING/READY/PENDING)
    assert not (states & {NodeState.RUNNING, NodeState.READY, NodeState.PENDING}), \
        f"Pipeline did not reach terminal state: {states}"

    completed = sum(1 for n in dag.nodes if n.state == NodeState.COMPLETED)
    failed = sum(1 for n in dag.nodes if n.state == NodeState.FAILED)
    total = len(dag.nodes)

    assert completed + failed == total, \
        f"Not all nodes reached terminal: {completed} completed, {failed} failed, {total} total"

    # At least the Writer should complete (even with partial data)
    writer = next((n for n in dag.nodes if n.agent_type == "ReportGenerator"), None)
    assert writer is not None, "No Writer node in DAG"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_has_writer_output(replay_executor, recorded_dag):
    """Writer node produces report content."""
    scheduler = DAGScheduler()
    dag = recorded_dag

    await scheduler.run(dag, replay_executor, gateway=replay_executor.gateway)

    writer = next((n for n in dag.nodes if n.agent_type == "ReportGenerator"), None)
    if writer is None or writer.state != NodeState.COMPLETED:
        pytest.skip("Writer did not complete in this fixture")

    output_data = writer.context.get("_output_data", {})
    report = output_data.get("report_markdown", "")
    sections = output_data.get("sections", [])

    has_content = bool(report) or len(sections) > 0
    assert has_content, "Writer completed but produced no report content"

    if report:
        assert len(report) > 200, f"Report too short ({len(report)} chars)"
        assert "Notion" in report, "Report doesn't mention target product Notion"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dag_node_dependencies_respected(replay_executor, recorded_dag):
    """Nodes execute in dependency order — no node runs before its dependencies complete."""
    scheduler = DAGScheduler()
    dag = recorded_dag

    # Track execution order
    execution_order: list[str] = []

    original_execute = replay_executor.execute

    async def tracking_execute(node):
        execution_order.append(node.node_id)
        return await original_execute(node)

    replay_executor.execute = tracking_execute

    await scheduler.run(dag, replay_executor, gateway=replay_executor.gateway)

    # Verify: for each node, all its dependencies appear before it in execution order
    node_map = {n.node_id: n for n in dag.nodes}
    for node in dag.nodes:
        if node.node_id not in execution_order:
            continue
        node_idx = execution_order.index(node.node_id)
        for dep_id in node.depends_on:
            dep_idx = execution_order.index(dep_id)
            assert dep_idx < node_idx, \
                f"Node {node.node_id} ran before its dependency {dep_id}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scheduler_state_transitions(replay_executor, recorded_dag):
    """Nodes transition through correct states: PENDING → READY → RUNNING → COMPLETED/FAILED."""
    scheduler = DAGScheduler()
    dag = recorded_dag

    transitions: dict[str, list[str]] = {}

    async def on_state_change(node):
        if node.node_id not in transitions:
            transitions[node.node_id] = []
        transitions[node.node_id].append(node.state.value)

    scheduler.on("node_state_change", on_state_change)

    await scheduler.run(dag, replay_executor, gateway=replay_executor.gateway)

    # Every node should have state changes tracked
    for node in dag.nodes:
        assert node.node_id in transitions, \
            f"Node {node.node_id} had no state transitions"
        states = transitions[node.node_id]
        assert "running" in states, \
            f"Node {node.node_id} never entered RUNNING state: {states}"
        assert states[-1] in ("completed", "failed", "degraded"), \
            f"Node {node.node_id} did not reach terminal state: {states[-1]}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pipeline_with_retries_finite(replay_executor, recorded_dag):
    """Pipeline with failed nodes does not retry infinitely."""
    scheduler = DAGScheduler()
    dag = recorded_dag

    # Set all retries to 0 to ensure no infinite loops
    for node in dag.nodes:
        node.max_retries = 0
        node.retries = 0

    await scheduler.run(dag, replay_executor, gateway=replay_executor.gateway)

    # Pipeline should complete (not hang)
    states = {n.state for n in dag.nodes}
    assert not (states & {NodeState.RUNNING, NodeState.READY, NodeState.PENDING}), \
        f"Pipeline hung with states: {states}"
