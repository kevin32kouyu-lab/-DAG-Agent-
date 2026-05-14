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
    n_writer = DAGNode(node_id="writer", agent_type="Writer", input_query={}, depends_on=["swot"])
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
