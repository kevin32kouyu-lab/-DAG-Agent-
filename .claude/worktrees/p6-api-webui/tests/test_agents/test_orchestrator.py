import json
import pytest
from unittest.mock import AsyncMock, patch
from src.agents.orchestrator import OrchestratorAgent
from src.llm_gateway.gateway import LLMGateway, LLMResponse
from src.knowledge_graph.store import GraphStore


@pytest.fixture
def orch(temp_db_path):
    store = GraphStore(db_path=temp_db_path)
    gateway = AsyncMock(spec=LLMGateway)
    return OrchestratorAgent(gateway=gateway, store=store, tool_registry=None)


def test_orchestrator_parse_dag_json():
    dag_json = {
        "task_id": "task_1",
        "targets": ["Notion", "Confluence", "Linear"],
        "nodes": [
            {"node_id": "source_disc", "agent_type": "SourceDiscovery", "depends_on": []},
            {"node_id": "c1", "agent_type": "Collector", "depends_on": ["source_disc"]},
            {"node_id": "c2", "agent_type": "Collector", "depends_on": ["source_disc"]},
            {"node_id": "feat", "agent_type": "FeatureAnalyzer", "depends_on": ["c1", "c2"]},
        ],
    }
    assert len(dag_json["nodes"]) == 4
    assert dag_json["nodes"][0]["depends_on"] == []
    assert "c1" in dag_json["nodes"][3]["depends_on"]


@pytest.mark.asyncio
async def test_orchestrator_generates_dag(orch):
    orch.gateway.chat = AsyncMock(return_value=LLMResponse(
        content=json.dumps({
            "task_id": "t1",
            "targets": ["Notion"],
            "nodes": [
                {"node_id": "s1", "agent_type": "SourceDiscovery", "depends_on": []},
                {"node_id": "c1", "agent_type": "Collector", "depends_on": ["s1"]},
                {"node_id": "f1", "agent_type": "FeatureAnalyzer", "depends_on": ["c1"]},
            ],
        }),
        model="claude-sonnet-4-6", tokens_in=200, tokens_out=100, cost=0.002,
    ))

    task = {"task_id": "t1", "targets": ["Notion"], "schema": {"industry": "saas"}}
    dag, traces = await orch.execute(task)
    assert dag is not None
    assert len(dag.nodes) == 3
    assert dag.nodes[0].agent_type == "SourceDiscovery"
