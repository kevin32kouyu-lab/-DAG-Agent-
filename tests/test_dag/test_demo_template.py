"""测试 Demo 工作流模板 — 验证 6 节点结构、依赖关系、跳过 cross_review/QA。"""

import pytest

from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
from src.dag.templates import (
    get_default_template_registry,
    _demo_pipeline_nodes,
    WorkflowTemplate,
)


class TestDemoTemplate:
    """Demo 模板结构应该是 6 节点（collector + 4 analyst + report），无 cross_review/qa。"""

    def test_template_registered(self):
        registry = get_default_template_registry()
        template = registry.get("demo_competitor_analysis")
        assert template is not None
        assert template.template_id == "demo_competitor_analysis"

    def test_template_has_6_nodes(self):
        nodes = _demo_pipeline_nodes()
        assert len(nodes) == 6

    def test_no_cross_review_node(self):
        nodes = _demo_pipeline_nodes()
        node_ids = {n.node_id for n in nodes}
        assert "cross_review" not in node_ids

    def test_no_qa_node(self):
        nodes = _demo_pipeline_nodes()
        node_ids = {n.node_id for n in nodes}
        assert "qa" not in node_ids

    def test_no_techstack_node(self):
        """Demo 砍掉 techstack，4 维度足够。"""
        nodes = _demo_pipeline_nodes()
        node_ids = {n.node_id for n in nodes}
        assert "techstack_analysis" not in node_ids

    def test_has_all_expected_nodes(self):
        nodes = _demo_pipeline_nodes()
        node_ids = {n.node_id for n in nodes}
        expected = {
            "collector",
            "feature_analysis", "pricing_analysis",
            "sentiment_analysis", "market_position",
            "report",
        }
        assert node_ids == expected

    def test_all_analysts_depend_on_collector(self):
        nodes = _demo_pipeline_nodes()
        analyst_nodes = [n for n in nodes if n.agent_type == "Analyst"]
        assert len(analyst_nodes) == 4
        for node in analyst_nodes:
            assert node.depends_on == ["collector"], (
                f"{node.node_id} should depend only on collector"
            )

    def test_report_depends_on_all_analysts(self):
        nodes = _demo_pipeline_nodes()
        report = next(n for n in nodes if n.node_id == "report")
        expected_deps = {
            "feature_analysis", "pricing_analysis",
            "sentiment_analysis", "market_position",
        }
        assert set(report.depends_on) == expected_deps

    def test_metadata_marks_demo_depth(self):
        registry = get_default_template_registry()
        template = registry.get("demo_competitor_analysis")
        assert template.metadata.get("default_depth") == "demo"
        # 预期 3 分钟内完成
        assert template.metadata.get("expected_duration_seconds", 999) <= 300


class TestDemoCompilation:
    """编译 Demo 模板成可执行 DAG。"""

    def test_compile_with_demo_depth_uses_demo_template(self):
        """当 collection_depth='demo' 时，应该自动路由到 demo 模板。"""
        compiler = WorkflowCompiler()
        dag = compiler.compile(WorkflowCompileRequest(
            task_id="test-task-1",
            targets=["飞书", "钉钉"],
            scenario="saas",
            collection_depth="demo",
        ))
        assert dag.workflow_template_id == "demo_competitor_analysis"
        assert len(dag.nodes) == 6

    def test_compile_with_standard_depth_uses_saas_template(self):
        """非 demo depth 仍然使用旧 saas 模板（不影响生产）。"""
        compiler = WorkflowCompiler()
        dag = compiler.compile(WorkflowCompileRequest(
            task_id="test-task-2",
            targets=["飞书"],
            scenario="saas",
            collection_depth="standard",
        ))
        assert dag.workflow_template_id == "saas_competitor_analysis"
        # 旧模板有 9 节点（collector + 5 analyst + cross_review + report + qa）
        assert len(dag.nodes) == 9

    def test_demo_dag_has_correct_dimensions(self):
        compiler = WorkflowCompiler()
        dag = compiler.compile(WorkflowCompileRequest(
            task_id="test-task-3",
            targets=["飞书", "钉钉"],
            scenario="saas",
            collection_depth="demo",
        ))
        dimensions = []
        for node in dag.nodes:
            if node.agent_type == "Analyst":
                dim = node.input_query.get("dimension")
                dimensions.append(dim)
        assert set(dimensions) == {"feature", "pricing", "sentiment", "market_position"}

    def test_demo_dag_targets_propagated(self):
        compiler = WorkflowCompiler()
        dag = compiler.compile(WorkflowCompileRequest(
            task_id="test-task-4",
            targets=["飞书", "钉钉", "企业微信"],
            scenario="saas",
            collection_depth="demo",
        ))
        assert dag.targets == ["飞书", "钉钉", "企业微信"]
        for node in dag.nodes:
            assert node.input_query["targets"] == ["飞书", "钉钉", "企业微信"]


class TestOldTemplatesUntouched:
    """确保 demo 改动没破坏旧 saas/app 模板。"""

    def test_saas_template_still_9_nodes(self):
        registry = get_default_template_registry()
        template = registry.get("saas_competitor_analysis")
        assert len(template.nodes) == 9

    def test_app_template_still_9_nodes(self):
        registry = get_default_template_registry()
        template = registry.get("app_competitor_analysis")
        assert len(template.nodes) == 9

    def test_saas_still_has_cross_review_and_qa(self):
        registry = get_default_template_registry()
        template = registry.get("saas_competitor_analysis")
        node_ids = {n.node_id for n in template.nodes}
        assert "cross_review" in node_ids
        assert "qa" in node_ids
