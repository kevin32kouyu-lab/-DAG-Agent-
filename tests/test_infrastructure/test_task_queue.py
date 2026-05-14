import pytest
from src.dag.models import DAGNode, NodeState
from src.infrastructure.task_queue import TaskQueue


@pytest.fixture
def queue():
    return TaskQueue()


@pytest.mark.asyncio
async def test_enqueue_and_dequeue(queue):
    node = DAGNode(node_id="n1", agent_type="Test", input_query={}, priority=1)
    await queue.enqueue(node)
    assert queue.size() == 1
    dequeued = await queue.dequeue()
    assert dequeued.node_id == "n1"
    assert queue.size() == 0


@pytest.mark.asyncio
async def test_priority_ordering(queue):
    low = DAGNode(node_id="low", agent_type="Test", input_query={}, priority=10)
    high = DAGNode(node_id="high", agent_type="Test", input_query={}, priority=1)
    mid = DAGNode(node_id="mid", agent_type="Test", input_query={}, priority=5)
    await queue.enqueue(low)
    await queue.enqueue(high)
    await queue.enqueue(mid)
    assert (await queue.dequeue()).node_id == "high"
    assert (await queue.dequeue()).node_id == "mid"
    assert (await queue.dequeue()).node_id == "low"


@pytest.mark.asyncio
async def test_queue_empty_size(queue):
    assert queue.size() == 0
