"""测试图表构建模块拆分后的公开边界。"""

import pytest

from src.api.analytics_builder import _read_task_targets_file
from src.api.analytics_fallback import build_report_fallback
from src.api.analytics_structured import build_feature_data, normalize_product_name


class FakeNode:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_structured_module_builds_feature_matrix():
    nodes = [
        FakeNode(product="notion", name="Docs", category="Core", maturity="ga", differentiation="advantage"),
        FakeNode(product="figma", name="Docs", category="Core", maturity="beta", differentiation="parity"),
    ]

    result = build_feature_data(nodes)

    assert normalize_product_name("notion") == "Notion"
    assert result["products"] == ["Figma", "Notion"]
    assert result["features"][0]["Notion_maturity"] == "ga"
    assert result["features"][0]["Figma_differentiation"] == "parity"


def test_fallback_module_parses_report_tables():
    sections = [
        FakeNode(
            content=(
                "## Feature Analysis\n\n"
                "| Feature | Notion | Figma |\n"
                "|---------|--------|-------|\n"
                "| Docs | Advantage | Parity |\n\n"
                "## Pricing Analysis\n\n"
                "| Plan | Notion | Figma |\n"
                "|------|--------|-------|\n"
                "| Pro | $10/mo | $12/editor/mo |\n"
            )
        )
    ]

    result = build_report_fallback(["Notion", "Figma"], sections)

    assert result["features"]["features"][0]["feature_name"] == "Docs"
    assert len(result["pricing"]["plans"]) == 2


def test_read_task_targets_file_logs_invalid_cache(tmp_path, monkeypatch, caplog):
    """任务目标缓存损坏时应记录日志并返回空列表。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "task_targets.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with caplog.at_level("WARNING"):
        result = _read_task_targets_file("task_bad")

    assert result == []
    assert "任务目标缓存读取失败" in caplog.text
