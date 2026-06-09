"""测试 QA Agent 的结构化输出逻辑。"""

import pytest
from unittest.mock import MagicMock

from src.agents.qa import QAAgent
from src.agents.contracts import QAOutput


@pytest.fixture
def mock_deps():
    gateway = MagicMock()
    store = MagicMock()
    tool_registry = MagicMock()
    tool_registry.describe_tools.return_value = []
    return gateway, store, tool_registry


@pytest.fixture
def qa(mock_deps):
    gateway, store, tool_registry = mock_deps
    return QAAgent(gateway=gateway, store=store, tool_registry=tool_registry)


class TestQAOutput:
    """测试：_build_output 构建正确的 QAOutput。"""

    def test_pass_when_no_issues(self, qa):
        """没有问题时应通过。"""
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {"summary": "All checks passed", "confidence": 0.9}
        output = qa._build_output(result)
        assert isinstance(output, QAOutput)
        assert output.overall_pass is True
        assert output.fact_issues == []
        assert output.logic_issues == []
        assert output.rejection_reason == ""

    def test_fail_when_high_severity_fact_issue(self, qa):
        """有高严重度事实问题时应不通过。"""
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {
            "summary": "Found issues",
            "fact_issues": [
                {"node_id": "feat_1", "claim": "Feature X exists", "reason": "No evidence found", "severity": "high"}
            ],
            "logic_issues": [],
        }
        output = qa._build_output(result)
        assert output.overall_pass is False
        assert len(output.fact_issues) == 1
        assert "事实校验" in output.rejection_reason

    def test_fail_when_high_severity_logic_issue(self, qa):
        """有高严重度逻辑问题时应不通过。"""
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {
            "summary": "Found contradictions",
            "fact_issues": [],
            "logic_issues": [
                {"section_a": "Feature Analysis", "section_b": "Pricing", "description": "Contradiction", "severity": "high"}
            ],
        }
        output = qa._build_output(result)
        assert output.overall_pass is False
        assert len(output.logic_issues) == 1
        assert "逻辑校验" in output.rejection_reason

    def test_pass_when_only_low_severity(self, qa):
        """只有低严重度问题时应通过。"""
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {
            "summary": "Minor issues",
            "fact_issues": [
                {"node_id": "feat_1", "reason": "Low confidence", "severity": "low"}
            ],
            "logic_issues": [],
        }
        output = qa._build_output(result)
        assert output.overall_pass is True

    def test_extracts_issues_from_data_field(self, qa):
        """LLM 可能把 issues 放在 data 字段里。"""
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {
            "summary": "Issues found",
            "data": {
                "fact_issues": [
                    {"node_id": "feat_1", "reason": "Missing source", "severity": "high"}
                ],
                "logic_issues": [],
            },
        }
        output = qa._build_output(result)
        assert output.overall_pass is False
        assert len(output.fact_issues) == 1


class TestQAConfig:
    """测试：QA Agent 配置。"""

    def test_agent_type(self, qa):
        assert qa.agent_type == "QA"

    def test_max_steps(self, qa):
        assert qa.max_steps == 12

    def test_model_tier(self, qa):
        assert qa.model_tier == "reasoning"

    def test_token_budget(self, qa):
        assert qa.token_budget == 400_000

    def test_depends_on_report_generator(self):
        from src.agents.registry import agent_registry
        info = agent_registry.get("QA")
        assert info is not None
        assert "ReportGenerator" in info["depends_on"]

    def test_only_graph_tools(self, qa):
        """QA 只需要读写图谱的工具。"""
        assert qa.allowed_tools == ["graph_query", "graph_write"]

    def test_output_contract_is_qa_output(self, qa):
        assert qa.output_contract == QAOutput


class TestQARejectionReason:
    """测试：拒绝理由生成。"""

    def test_reason_includes_fact_count(self, qa):
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {
            "fact_issues": [
                {"node_id": "a", "reason": "r1", "severity": "high"},
                {"node_id": "b", "reason": "r2", "severity": "high"},
            ],
            "logic_issues": [],
        }
        output = qa._build_output(result)
        assert "2" in output.rejection_reason

    def test_reason_includes_logic_count(self, qa):
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {
            "fact_issues": [],
            "logic_issues": [
                {"description": "c1", "severity": "high"},
            ],
        }
        output = qa._build_output(result)
        assert "1" in output.rejection_reason

    def test_custom_rejection_reason(self, qa):
        """LLM 可以提供自定义拒绝理由。"""
        qa.context = MagicMock()
        qa.context.node_id = "qa"
        result = {
            "overall_pass": False,
            "rejection_reason": "报告缺少定价分析数据",
        }
        output = qa._build_output(result)
        assert "定价分析" in output.rejection_reason
