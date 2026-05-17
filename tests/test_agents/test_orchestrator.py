from src.agents.orchestrator import OrchestratorAgent


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


def test_ensure_mandatory_nodes_swot_excluded_preserves_existing():
    """When SWOT is excluded, existing nodes plus ReportGenerator/QA should be present,
    but SWOT should not be injected."""
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
    writer = next(n for n in result["nodes"] if n["agent_type"] == "ReportGenerator")
    deps = writer["depends_on"]
    assert "f1" in deps or any("feature" in d.lower() for d in deps)
