import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.scheduler import DAGScheduler


@pytest.fixture
def scheduler():
    return DAGScheduler()


@pytest.mark.asyncio
async def test_scheduler_runs_simple_dag(scheduler):
    n1 = DAGNode(node_id="n1", agent_type="Collector", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="n2", agent_type="Analyzer", input_query={}, depends_on=["n1"])
    dag = TaskDAG(task_id="task_1", nodes=[n1, n2])

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=lambda node: setattr(node, "state", NodeState.COMPLETED))

    await scheduler.run(dag, executor)

    assert n1.state == NodeState.COMPLETED
    assert n2.state == NodeState.COMPLETED


@pytest.mark.asyncio
async def test_scheduler_parallel_execution(scheduler):
    n1 = DAGNode(node_id="source", agent_type="SourceDisc", input_query={}, depends_on=[])
    n2 = DAGNode(node_id="c1", agent_type="Collector", input_query={}, depends_on=["source"])
    n3 = DAGNode(node_id="c2", agent_type="Collector", input_query={}, depends_on=["source"])
    dag = TaskDAG(task_id="task_2", nodes=[n1, n2, n3])

    call_order = []
    async def track_exec(node):
        call_order.append(node.node_id)
        node.state = NodeState.COMPLETED

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=track_exec)

    await scheduler.run(dag, executor)
    assert n2.state == NodeState.COMPLETED
    assert n3.state == NodeState.COMPLETED
    assert call_order[0] == "source"


@pytest.mark.asyncio
async def test_scheduler_handles_failure_with_retry(scheduler):
    n1 = DAGNode(node_id="n1", agent_type="Flaky", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_3", nodes=[n1])

    call_count = [0]
    async def flaky_exec(node):
        call_count[0] += 1
        if call_count[0] < 2:
            raise RuntimeError("simulated failure")

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=flaky_exec)

    await scheduler.run(dag, executor)
    assert n1.state == NodeState.COMPLETED
    assert n1.retries == 1
