import asyncio
import pytest
from unittest.mock import AsyncMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.dag.scheduler import DAGScheduler
from src.knowledge_graph.store import GraphStore


@pytest.mark.asyncio
async def test_full_dag_simulation(temp_db_path):
    """Simulates the SaaS analysis DAG: SourceDisc -> 2x Collector -> DataEnricher -> FeatureAnalyzer -> SWOT -> Writer -> QA"""
    store = GraphStore(db_path=temp_db_path)

    n_source = DAGNode(node_id="source_disc", agent_type="SourceDiscovery", input_query={"targets": ["Notion"]}, depends_on=[])
    n_col1 = DAGNode(node_id="col_notion", agent_type="Collector", input_query={"url": "https://notion.so"}, depends_on=["source_disc"])
    n_col2 = DAGNode(node_id="col_g2", agent_type="Collector", input_query={"url": "https://g2.com/notion"}, depends_on=["source_disc"])
    n_enrich = DAGNode(node_id="enricher", agent_type="DataEnricher", input_query={}, depends_on=["col_notion", "col_g2"])
    n_feat = DAGNode(node_id="feature", agent_type="FeatureAnalyzer", input_query={"product": "Notion"}, depends_on=["enricher"])
    n_swot = DAGNode(node_id="swot", agent_type="SWOTAnalyzer", input_query={}, depends_on=["feature"])
    n_writer = DAGNode(node_id="writer", agent_type="ReportGenerator", input_query={}, depends_on=["swot"])
    n_qa = DAGNode(node_id="qa1", agent_type="QA_FactCheck", input_query={}, depends_on=["writer"])

    dag = TaskDAG(task_id="full_test", nodes=[n_source, n_col1, n_col2, n_enrich, n_feat, n_swot, n_writer, n_qa])

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
    assert "source_discovery" in executed
    assert "report" in executed
    assert executed.index("source_discovery") < executed.index("collector")
    assert executed.index("report") > executed.index("swot")
