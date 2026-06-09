"""测试 Orchestrator 把任务规划成 DAG 的解析和兜底行为。"""

import logging

import pytest

from src.agents.orchestrator import OrchestratorAgent
from src.dag.models import NodeState
from src.llm_gateway.gateway import LLMResponse


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
async def test_generate_dag_logs_invalid_llm_output(caplog):
    """LLM 返回无法解析的内容时，应记录原因并返回空结果。"""

    class DummyGateway:
        """提供固定 LLM 响应，避免测试访问真实模型。"""

        async def chat(self, **_kwargs):
            """返回不可解析的 DAG 文本。"""
            return LLMResponse(content="not a dag", model="dummy")

    agent = OrchestratorAgent(gateway=DummyGateway(), store=None, tool_registry=None)

    with caplog.at_level(logging.WARNING):
        result = await agent._generate_dag(["Notion"], {"industry": "saas"})

    assert result is None
    assert "compiled template mode" in caplog.text


def test_json_to_dag_logs_skipped_invalid_nodes(caplog):
    """DAG 节点字段不完整时，应记录被跳过的原因。"""
    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    dag_json = {
        "task_id": "task_bad_nodes",
        "nodes": [
            {"agent_type": "Collector"},
            "bad node",
            {"node_id": "source_disc", "agent_type": "SourceDiscovery", "depends_on": []},
        ],
    }

    with caplog.at_level(logging.WARNING):
        dag = agent._json_to_dag(dag_json)

    assert [node.node_id for node in dag.nodes] == ["source_disc"]
    assert "DAG 节点跳过" in caplog.text


@pytest.mark.asyncio
async def test_execute_compiles_template_dag_without_llm_dependency():
    class DummyGateway:
        async def chat(self, **_kwargs):
            raise AssertionError("should not be called")

    agent = OrchestratorAgent(gateway=DummyGateway(), store=None, tool_registry=None)
    dag, traces = await agent.execute({
        "task_id": "task_compiled",
        "targets": ["Notion"],
        "schema": {"industry": "saas", "exclude_dimensions": ["swot"]},
    })

    assert traces == []
    assert dag is not None
    assert dag.workflow_template_id == "saas_competitor_analysis"
    assert dag.get_node("report") is not None
    assert dag.get_node("qa") is not None


@pytest.mark.asyncio
async def test_execute_returns_template_dag_and_ignores_llm_node_ids(caplog):
    class DummyGateway:
        async def chat(self, **_kwargs):
            return LLMResponse(
                content="""
                {
                  "task_id": "task_bad_execute",
                  "nodes": [
                    {"agent_type": "Collector"},
                    "bad node",
                    {"node_id": "source_disc", "agent_type": "SourceDiscovery", "depends_on": []}
                  ]
                }
                """,
                model="dummy",
            )

    agent = OrchestratorAgent(gateway=DummyGateway(), store=None, tool_registry=None)

    with caplog.at_level(logging.WARNING):
        dag, traces = await agent.execute({
            "task_id": "task_bad_execute",
            "targets": ["Notion"],
            "schema": {"industry": "saas"},
        })

    assert traces == []
    assert dag is not None
    assert dag.get_node("collector") is not None
    assert dag.get_node("report") is not None
    assert dag.get_node("qa") is not None
    assert "DAG 节点跳过" not in caplog.text


def test_ensure_mandatory_nodes_swot_excluded_preserves_existing():
    """When SWOT is excluded, existing nodes plus ReportGenerator/QA should be present."""
    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    dag_json = {
        "task_id": "t3",
        "nodes": [
            {"node_id": "c1", "agent_type": "Collector", "depends_on": []},
            {"node_id": "f1", "agent_type": "Analyst", "depends_on": ["c1"]},
        ],
    }
    schema = {"exclude_dimensions": ["swot"]}
    result = agent._ensure_mandatory_nodes(dag_json, schema)
    types = {n["agent_type"] for n in result["nodes"]}
    assert "ReportGenerator" in types
    assert "QA" in types
    writer = next(n for n in result["nodes"] if n["agent_type"] == "ReportGenerator")
    deps = writer["depends_on"]
    assert "f1" in deps or "c1" in deps
