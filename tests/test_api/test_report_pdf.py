"""测试报告 PDF 生成模块，避免 PDF 逻辑继续堆在路由文件里。"""

from src.api import report_pdf
from src.api.report_pdf import build_pdf


def test_build_pdf_returns_pdf_bytes():
    sections = [
        {
            "section": "摘要",
            "content": "这是一个用于测试的竞品分析报告段落。",
            "order": 0,
        }
    ]

    result = build_pdf("task_pdf_test", sections)

    assert result.startswith(b"%PDF-")
    assert len(result) > 100


def test_build_pdf_logs_font_registration_failure(monkeypatch, caplog):
    """中文字体注册失败时应记录日志，并回退继续生成 PDF。"""
    monkeypatch.setattr(report_pdf, "_CHINESE_FONT_PATH", "missing-font.ttf")
    sections = [
        {
            "section": "Summary",
            "content": "ASCII fallback content.",
            "order": 0,
        }
    ]

    with caplog.at_level("WARNING"):
        result = build_pdf("task_pdf_font", sections)

    assert result.startswith(b"%PDF-")
    assert "PDF 中文字体注册失败" in caplog.text
