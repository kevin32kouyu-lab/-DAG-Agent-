import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.dag.models import DAGNode, TaskDAG, NodeState
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool
from src.agents.source_discovery import SourceDiscoveryAgent
from src.agents.collector import CollectorAgent
from src.agents.data_enricher import DataEnricherAgent


@pytest.mark.asyncio
async def test_full_collection_pipeline(temp_db_path):
    """Source Discovery → Collector → Data Enricher, all writing to shared KG."""
    store = GraphStore(db_path=temp_db_path)
    gateway = MagicMock(spec=LLMGateway)

    # Shared tool registry
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebSearchTool)
    tools.register(WebScrapeTool)

    sd_agent = SourceDiscoveryAgent(gateway=gateway, store=store, tool_registry=tools)
    col_agent = CollectorAgent(gateway=gateway, store=store, tool_registry=tools)
    enrich_agent = DataEnricherAgent(gateway=gateway, store=store, tool_registry=tools)

    # Build DAG
    sd_node = DAGNode(node_id="sd", agent_type="SourceDiscovery", input_query={"targets": ["Notion"]}, depends_on=[])
    col_node = DAGNode(node_id="c1", agent_type="Collector", input_query={"urls": ["https://notion.so"]}, depends_on=["sd"])
    enrich_node = DAGNode(node_id="enrich", agent_type="DataEnricher", input_query={}, depends_on=["c1"])
    dag = TaskDAG(task_id="p3_test", nodes=[sd_node, col_node, enrich_node])

    # Mock LLM: 3 agents × 2 steps = 6 calls, alternating [tool, finalize]
    non_final = json.dumps({"reasoning": "Working", "action": "graph_query", "params": {"layer": 1}, "confidence": 0.7})
    final = json.dumps({"reasoning": "Done", "action": "finalize", "result": {"summary": "collected data", "nodes_created": [], "edges_created": []}, "confidence": 0.8})
    responses = []
    for _ in range(3):
        responses.append(non_final)
        responses.append(final)
    call_idx = [0]
    def side_effect(*args, **kwargs):
        idx = call_idx[0]
        call_idx[0] += 1
        return LLMResponse(content=responses[idx], model="test", tokens_in=50, tokens_out=30, cost=0.001)
    gateway.chat = AsyncMock(side_effect=side_effect)

    # Manual sequential execution to verify data flow
    task_sd = {"task_id": "p3_test", "node_id": "sd", "agent_type": "SourceDiscovery", "input_query": {"targets": ["Notion"]}, "context": {}}
    sd_output, _ = await sd_agent.execute(task_sd)
    assert sd_output.status == "completed"
    sd_node.state = NodeState.COMPLETED

    task_col = {"task_id": "p3_test", "node_id": "c1", "agent_type": "Collector", "input_query": {"urls": ["https://notion.so"]}, "context": {"previous_output": sd_output.model_dump()}}
    col_output, _ = await col_agent.execute(task_col)
    assert col_output.status == "completed"

    task_enrich = {"task_id": "p3_test", "node_id": "enrich", "agent_type": "DataEnricher", "input_query": {}, "context": {}}
    enrich_output, _ = await enrich_agent.execute(task_enrich)
    assert enrich_output.status == "completed"
