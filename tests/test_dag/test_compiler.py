import pytest

from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
from src.dag.models import NodeState
from src.dag.templates import get_default_template_registry


def test_compile_saas_template_to_task_dag():
    compiler = WorkflowCompiler(get_default_template_registry())
    dag = compiler.compile(WorkflowCompileRequest(
        task_id="task_saas",
        targets=["Notion", "ClickUp", "飞书"],
        scenario="saas",
        collection_depth="standard",
        schema={
            "report_audience": "product_manager",
            "exclude_dimensions": ["sentiment"],
            "benchmark_product": "Notion",
            "report_sections": ["summary", "opportunities"],
        },
    ))

    assert dag.task_id == "task_saas"
    assert dag.workflow_template_id == "saas_competitor_analysis"
    assert dag.scenario == "saas"
    assert dag.targets == ["Notion", "ClickUp", "飞书"]
    assert dag.metadata["planning_mode"] == "template"
    assert dag.metadata["schema"]["benchmark_product"] == "Notion"
    assert all(node.state == NodeState.PENDING for node in dag.nodes)

    report = dag.get_node("report")
    assert report is not None
    assert report.agent_type == "ReportGenerator"
    assert report.stage == "reporting"
    assert report.role_group == "reporting"
    assert report.input_query["targets"] == ["Notion", "ClickUp", "飞书"]
    assert report.input_query["scenario"] == "saas"
    assert report.input_query["benchmark_product"] == "Notion"
    assert report.input_query["report_sections"] == ["summary", "opportunities"]


def test_compile_app_template_to_task_dag():
    compiler = WorkflowCompiler(get_default_template_registry())
    dag = compiler.compile(WorkflowCompileRequest(
        task_id="task_app",
        targets=["小红书", "B站", "抖音"],
        scenario="app",
        collection_depth="deep",
        schema={"report_audience": "founder"},
    ))

    assert dag.workflow_template_id == "app_competitor_analysis"
    assert dag.scenario == "app"
    assert dag.metadata["collection_depth"] == "deep"
    assert dag.get_node("sentiment_analysis").display_name == "用户口碑分析"


def test_compile_rejects_empty_targets():
    compiler = WorkflowCompiler(get_default_template_registry())

    with pytest.raises(ValueError, match="targets"):
        compiler.compile(WorkflowCompileRequest(
            task_id="task_empty",
            targets=[],
            scenario="saas",
        ))


def test_compile_rejects_unknown_scenario():
    compiler = WorkflowCompiler(get_default_template_registry())

    with pytest.raises(ValueError, match="scenario"):
        compiler.compile(WorkflowCompileRequest(
            task_id="task_unknown",
            targets=["Notion"],
            scenario="retail",
        ))
