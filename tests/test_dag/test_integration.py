import asyncio
import pytest
from unittest.mock import AsyncMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.scheduler import DAGScheduler
from src.knowledge_graph.store import GraphStore


@pytest.mark.asyncio
async def test_full_dag_simulation(temp_db_path):
    """Simulates the 8-node DAG: collector → 5x analyst → cross_review → report → qa"""
    store = GraphStore(db_path=temp_db_path)

    n_col = DAGNode(node_id="collector", agent_type="Collector", input_query={"targets": ["Notion"]}, depends_on=[])
    n_feat = DAGNode(node_id="feature_analysis", agent_type="Analyst", input_query={"dimension": "feature"}, depends_on=["collector"])
    n_price = DAGNode(node_id="pricing_analysis", agent_type="Analyst", input_query={"dimension": "pricing"}, depends_on=["collector"])
    n_sent = DAGNode(node_id="sentiment_analysis", agent_type="Analyst", input_query={"dimension": "sentiment"}, depends_on=["collector"])
    n_tech = DAGNode(node_id="techstack_analysis", agent_type="Analyst", input_query={"dimension": "techstack"}, depends_on=["collector"])
    n_mkt = DAGNode(node_id="market_position", agent_type="Analyst", input_query={"dimension": "market_position"}, depends_on=["collector"])
    n_cr = DAGNode(node_id="cross_review", agent_type="Analyst", input_query={"dimension": "cross_review"},
                   depends_on=["feature_analysis", "pricing_analysis", "sentiment_analysis", "techstack_analysis", "market_position"])
    n_writer = DAGNode(node_id="report", agent_type="ReportGenerator", input_query={}, depends_on=["cross_review"])
    n_qa = DAGNode(node_id="qa", agent_type="QA", input_query={}, depends_on=["report"])

    dag = TaskDAG(task_id="full_test", nodes=[n_col, n_feat, n_price, n_sent, n_tech, n_mkt, n_cr, n_writer, n_qa])

    async def mock_execute(node):
        node.state = NodeState.COMPLETED

    executor = AsyncMock()
    executor.execute = AsyncMock(side_effect=mock_execute)
    scheduler = DAGScheduler()
    await scheduler.run(dag, executor)

    assert all(n.state == NodeState.COMPLETED for n in dag.nodes)
    assert dag.is_terminal()


@pytest.mark.asyncio
async def test_template_compiled_dag_runs_with_mock_executor():
    from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
    from src.dag.scheduler import DAGScheduler

    compiler = WorkflowCompiler()
    dag = compiler.compile(WorkflowCompileRequest(
        task_id="task_template_run",
        targets=["Notion", "ClickUp", "飞书"],
        scenario="saas",
    ))

    executed = []

    class MockExecutor:
        gateway = type("_Gateway", (), {"cost_tracker": type("_Tracker", (), {"total_tokens": 0, "total_cost": 0.0})()})()
        store = type("_Store", (), {"query_nodes": lambda **kw: []})()

        async def execute(self, node):
            executed.append(node.node_id)

    scheduler = DAGScheduler()
    await scheduler.run(dag, MockExecutor())

    assert dag.is_terminal() is True
    assert "collector" in executed
    assert "report" in executed
    assert "qa" in executed
    assert executed.index("collector") < executed.index("feature_analysis")
    assert executed.index("report") > executed.index("cross_review")
