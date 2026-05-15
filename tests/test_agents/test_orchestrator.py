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
    # Mock returns 3 nodes; _ensure_mandatory_nodes injects SWOT + ReportGenerator + QA × 2 = 7
    assert len(dag.nodes) == 7
    assert dag.nodes[0].agent_type == "SourceDiscovery"
    agent_types = {n.agent_type for n in dag.nodes}
    for mandatory in OrchestratorAgent.MANDATORY_AGENTS:
        assert mandatory in agent_types, f"Missing mandatory agent: {mandatory}"
    assert "SWOTAnalyzer" in agent_types


@pytest.mark.asyncio
async def test_orchestrator_minimal_dag_all_dimensions_excluded(orch):
    """ReportGenerator and QA must be present even when all analysis dimensions are excluded."""
    orch.gateway.chat = AsyncMock(return_value=LLMResponse(
        content=json.dumps({
            "task_id": "t2",
            "targets": ["Notion"],
            "nodes": [
                {"node_id": "s1", "agent_type": "SourceDiscovery", "depends_on": []},
                {"node_id": "c1", "agent_type": "Collector", "depends_on": ["s1"]},
            ],
        }),
        model="claude-sonnet-4-6", tokens_in=150, tokens_out=80, cost=0.001,
    ))

    schema = {
        "industry": "saas",
        "exclude_dimensions": ["features", "sentiment", "pricing",
                                "techstack", "market_position", "swot"],
    }
    task = {"task_id": "t2", "targets": ["Notion"], "schema": schema}
    dag, traces = await orch.execute(task)
    assert dag is not None
    agent_types = {n.agent_type for n in dag.nodes}
    # Mandatory agents must always be present
    for mandatory in OrchestratorAgent.MANDATORY_AGENTS:
        assert mandatory in agent_types, f"Missing mandatory agent: {mandatory}"
    # SWOT should be absent since it's excluded
    assert "SWOTAnalyzer" not in agent_types
    # ReportGenerator should depend on the last available node (Collector, in this case)
    writer = next(n for n in dag.nodes if n.agent_type == "ReportGenerator")
    assert len(writer.depends_on) > 0


@pytest.mark.asyncio
async def test_ensure_mandatory_nodes_swot_excluded_preserves_existing():
    """When SWOT is excluded, existing nodes plus ReportGenerator/QA should be present,
    but SWOT should not be injected."""
    from src.agents.orchestrator import OrchestratorAgent
    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    dag_json = {
        "task_id": "t3",
        "nodes": [
            {"node_id": "s1", "agent_type": "SourceDiscovery", "depends_on": []},
            {"node_id": "c1", "agent_type": "Collector", "depends_on": ["s1"]},
            {"node_id": "f1", "agent_type": "FeatureAnalyzer", "depends_on": ["c1"]},
        ],
    }
    schema = {"exclude_dimensions": ["swot"]}
    result = agent._ensure_mandatory_nodes(dag_json, schema)
    types = {n["agent_type"] for n in result["nodes"]}
    assert "SWOTAnalyzer" not in types
    assert "ReportGenerator" in types
    assert "QA_FactCheck" in types
    assert "QA_LogicCheck" in types
    # ReportGenerator should depend on FeatureAnalyzer when SWOT is excluded
    writer = next(n for n in result["nodes"] if n["agent_type"] == "ReportGenerator")
    deps = writer["depends_on"]
    assert "f1" in deps or any("feature" in d.lower() for d in deps)
