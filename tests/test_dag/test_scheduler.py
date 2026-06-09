import asyncio
import logging
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


@pytest.mark.asyncio
async def test_scheduler_logs_snapshot_save_failure_without_failing_node(caplog):
    """快照保存失败不应把已完成节点改成失败。"""

    class BrokenSnapshotStore:
        """模拟快照存储写入失败。"""

        def load(self, _task_id):
            """没有可恢复快照。"""
            return {}

        def save(self, _snapshot):
            """模拟保存快照失败。"""
            raise RuntimeError("snapshot disk full")

    n1 = DAGNode(node_id="n1", agent_type="Collector", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_snapshot_failure", nodes=[n1])
    scheduler = DAGScheduler(snapshot_store=BrokenSnapshotStore())

    executor = AsyncMock()
    executor.execute = AsyncMock()

    with caplog.at_level(logging.WARNING):
        await scheduler.run(dag, executor)

    assert n1.state == NodeState.COMPLETED
    assert "快照保存失败" in caplog.text


@pytest.mark.asyncio
async def test_scheduler_logs_snapshot_load_failure_and_runs_fresh(caplog):
    """快照读取失败时，应记录日志并从头执行任务。"""

    class BrokenSnapshotStore:
        """模拟快照存储读取失败。"""

        def load(self, _task_id):
            """模拟读取恢复点失败。"""
            raise RuntimeError("snapshot db unavailable")

        def save(self, _snapshot):
            """写入快照不做额外动作。"""
            return None

    n1 = DAGNode(node_id="n1", agent_type="Collector", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_snapshot_load_failure", nodes=[n1])
    scheduler = DAGScheduler(snapshot_store=BrokenSnapshotStore())

    executor = AsyncMock()
    executor.execute = AsyncMock()

    with caplog.at_level(logging.WARNING):
        await scheduler.run(dag, executor)

    assert n1.state == NodeState.COMPLETED
    assert executor.execute.call_count == 1
    assert "快照读取失败" in caplog.text


@pytest.mark.asyncio
async def test_scheduler_logs_cost_update_failure_without_failing_task(caplog):
    """成本更新失败不应影响 DAG 执行结果。"""

    class ExecutorWithoutMetrics:
        """模拟缺少成本统计依赖的执行器。"""

        async def execute(self, _node):
            """节点执行成功。"""
            return None

    n1 = DAGNode(node_id="n1", agent_type="Collector", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_cost_update_failure", nodes=[n1])
    scheduler = DAGScheduler()

    with caplog.at_level(logging.WARNING):
        await scheduler.run(dag, ExecutorWithoutMetrics())

    assert n1.state == NodeState.COMPLETED
    assert "成本更新失败" in caplog.text


@pytest.mark.asyncio
async def test_scheduler_logs_event_callback_failure_without_failing_task(caplog):
    """事件回调失败不应中断 DAG 执行。"""

    class SimpleExecutor:
        """模拟节点正常执行。"""

        async def execute(self, _node):
            """节点执行成功。"""
            return None

    async def broken_callback(*_args, **_kwargs):
        """模拟 WebSocket 或监控回调失败。"""
        raise RuntimeError("callback unavailable")

    n1 = DAGNode(node_id="n1", agent_type="Collector", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_event_callback_failure", nodes=[n1])
    scheduler = DAGScheduler()
    scheduler.on("node_state_change", broken_callback)

    with caplog.at_level(logging.WARNING):
        await scheduler.run(dag, SimpleExecutor())

    assert n1.state == NodeState.COMPLETED
    assert "事件回调失败" in caplog.text


@pytest.mark.asyncio
async def test_scheduler_logs_checkpoint_timeout(monkeypatch, caplog):
    """人工检查点超时自动放行时，应记录日志。"""

    class SimpleExecutor:
        """模拟节点正常执行。"""

        async def execute(self, _node):
            """节点执行成功。"""
            return None

    monkeypatch.setattr("src.dag.scheduler.CHECKPOINT_TIMEOUT", 0.01)
    n1 = DAGNode(node_id="collector", agent_type="Collector", input_query={}, depends_on=[])
    dag = TaskDAG(task_id="task_checkpoint_timeout", nodes=[n1])
    scheduler = DAGScheduler(review_mode=True)

    with caplog.at_level(logging.WARNING):
        await scheduler.run(dag, SimpleExecutor())

    assert n1.state == NodeState.COMPLETED
    assert "检查点等待超时" in caplog.text


@pytest.mark.asyncio
async def test_emit_dag_created_includes_platform_metadata(scheduler):
    node = DAGNode(
        node_id="report",
        agent_type="ReportGenerator",
        input_query={},
        stage="reporting",
        role_group="reporting",
        display_name="报告生成",
        description="生成最终报告",
        output_contract="ReportOutput",
    )
    dag = TaskDAG(
        task_id="task_meta",
        nodes=[node],
        workflow_template_id="saas_competitor_analysis",
        scenario="saas",
        targets=["Notion", "ClickUp"],
        metadata={"planning_mode": "template"},
    )

    events = []

    async def on_dag_created(task_id, payload):
        events.append((task_id, payload))

    scheduler.on("dag_created", on_dag_created)
    await scheduler.emit_dag_created("task_meta", dag)

    assert events[0][0] == "task_meta"
    payload = events[0][1]
    assert payload["workflow_template_id"] == "saas_competitor_analysis"
    assert payload["scenario"] == "saas"
    assert payload["targets"] == ["Notion", "ClickUp"]
    assert payload["nodes"][0]["stage"] == "reporting"
    assert payload["nodes"][0]["role_group"] == "reporting"
    assert payload["nodes"][0]["display_name"] == "报告生成"
