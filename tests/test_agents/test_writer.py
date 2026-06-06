"""测试报告生成 Agent 的本地兜底路径。"""

from unittest.mock import MagicMock

import pytest

from src.agents.tools.base import ToolRegistry
from src.agents.writer import WriterAgent


@pytest.mark.asyncio
async def test_writer_fallback_survives_graph_read_failure(caplog):
    """图谱读取失败时 Writer 仍应返回兜底报告。"""
    store = MagicMock()
    store.query_nodes.side_effect = RuntimeError("graph unavailable")
    agent = WriterAgent(
        gateway=MagicMock(),
        store=store,
        tool_registry=ToolRegistry(),
    )
    task = {
        "task_id": "task_writer_fallback",
        "node_id": "writer_1",
        "agent_type": "ReportGenerator",
        "input_query": {"targets": ["Notion"]},
        "context": {},
    }

    with caplog.at_level("WARNING"):
        output, traces = await agent.execute(task)

    assert output.status == "completed"
    assert "Notion" in output.report_markdown
    assert traces == []
    assert "Writer agent failed" in caplog.text
    assert "Writer 图谱报告章节读取失败" in caplog.text
