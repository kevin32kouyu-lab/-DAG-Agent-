"""报告 PDF 生成模块，供 report 路由调用。"""

from __future__ import annotations

import os
import platform
import re
import logging
from datetime import datetime

from fpdf import FPDF as _FPDFBase


logger = logging.getLogger(__name__)

_CHINESE_FONT_PATH = None
if platform.system() == "Windows":
    for candidate in [
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
    ]:
        if os.path.exists(candidate):
            _CHINESE_FONT_PATH = candidate
            break


def _find_chinese_font() -> str | None:
    """查找可用的中文字体，返回路径。"""
    candidates: list[str] = []
    if platform.system() == "Windows":
        candidates = [
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\msyhbd.ttc",
            r"C:\Windows\Fonts\simsun.ttc",
            r"C:\Windows\Fonts\simkai.ttf",
        ]
    elif platform.system() == "Darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Light.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


class _ReportFPDF(_FPDFBase):
    """带页脚的 FPDF 子类。"""

    def __init__(self, task_id: str, font_name: str, is_cjk: bool):
        super().__init__()
        self._task_id = task_id
        self._font_name = font_name
        self._is_cjk = is_cjk
        self.set_auto_page_break(auto=True, margin=18)

    def footer(self):
        """在每页底部显示报告 ID 和页码。"""
        self.set_y(-15)
        if self._is_cjk:
            self.set_font(self._font_name, "", 7)
        else:
            self.set_font("Helvetica", "", 7)
        self.set_text_color(140, 140, 140)
        text = f"CompAgent · {self._task_id[:8]} · {self.page_no()}"
        self.cell(0, 8, text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)


class _MarkdownPDF:
    """把报告章节渲染成 PDF。"""

    def __init__(self, task_id: str, sections: list[dict]):
        self.task_id = task_id
        self.sections = self._dedup_sections(sections)
        self._font_path = _CHINESE_FONT_PATH or _find_chinese_font()
        self._font = "CJK" if self._font_path else "Helvetica"
        self.pdf = _ReportFPDF(task_id, self._font, bool(self._font_path))
        self._register_fonts()

    def _dedup_sections(self, sections: list[dict]) -> list[dict]:
        """按章节标题和正文开头去重。"""
        seen: set[str] = set()
        out: list[dict] = []
        for section in sections:
            key = f"{section.get('section', '')}|{section.get('content', '')[:100]}"
            if key in seen:
                continue
            seen.add(key)
            out.append(section)
        return out

    def _register_fonts(self) -> None:
        """注册中文字体，失败时回退到 Helvetica。"""
        if not self._font_path:
            return
        try:
            self.pdf.add_font("CJK", "", self._font_path)
            self.pdf.add_font("CJK", "B", self._font_path)
            self._font = "CJK"
            self.pdf._font_name = "CJK"
            self.pdf._is_cjk = True
        except Exception as exc:
            logger.warning("PDF 中文字体注册失败，已回退到 Helvetica: path=%s, reason=%s", self._font_path, exc)
            self._font = "Helvetica"
            self.pdf._font_name = "Helvetica"
            self.pdf._is_cjk = False

    def _use_cjk(self) -> bool:
        """判断当前是否使用中文字体。"""
        return self._font == "CJK"

    def _f(self, bold: bool = False, size: int = 10):
        """设置当前字体。"""
        if self._use_cjk():
            self.pdf.set_font("CJK", "B" if bold else "", size)
            return
        self.pdf.set_font("Helvetica", "B" if bold else "", size)

    def _ln(self, h: int = 5):
        """换行。"""
        self.pdf.ln(h)

    def _heading(self, text: str, level: int):
        """渲染标题行。"""
        sizes = {1: 18, 2: 14, 3: 12, 4: 11, 5: 10, 6: 10}
        self._ln(6 if level <= 2 else 4)
        self._f(bold=True, size=sizes.get(level, 10))
        self.pdf.multi_cell(0, sizes.get(level, 10) * 0.45, text)
        self._f(size=10)
        self._ln(2)

    def _para(self, text: str):
        """渲染普通段落。"""
        self.pdf.multi_cell(0, 5.5, text)
        self._ln(1)

    def _bullet(self, text: str, indent: int = 1):
        """渲染列表项。"""
        prefix = "    " * indent + "• "
        self.pdf.multi_cell(0, 5.5, prefix + text)
        self._ln(0.5)

    def _hr(self):
        """渲染分隔线。"""
        self._ln(3)
        self.pdf.cell(0, 0, "", new_x="LMARGIN", new_y="NEXT")
        self._f(size=7)
        self.pdf.cell(0, 4, "—" * 60, align="C", new_x="LMARGIN", new_y="NEXT")
        self._f(size=10)
        self._ln(3)

    def _render_inline(self, text: str) -> str:
        """剥离常见 Markdown 内联标记，返回纯文本。"""
        text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
        return text

    def _render_line(self, line: str) -> None:
        """按 Markdown 行类型渲染一行内容。"""
        stripped = line.strip()
        if not stripped:
            self._ln(3)
            return

        if stripped in ("---", "***", "___", "- - -", "* * *") or (
            len(stripped) >= 3 and all(c in "-*_ " for c in stripped)
        ):
            self._hr()
            return

        if stripped.startswith("```"):
            return

        for level in range(6, 0, -1):
            prefix = "#" * level + " "
            if stripped.startswith(prefix):
                self._heading(self._render_inline(stripped[len(prefix):]), level)
                return

        if stripped.startswith("> "):
            self._f(size=9)
            self.pdf.set_text_color(80, 80, 80)
            self.pdf.multi_cell(0, 5, "  |  " + self._render_inline(stripped[2:]))
            self.pdf.set_text_color(0, 0, 0)
            self._f(size=10)
            return

        for marker in ("- ", "* ", "+ "):
            if stripped.startswith(marker):
                self._bullet(self._render_inline(stripped[len(marker):]))
                return

        ol_match = re.match(r"^(\d+)[.)]\s+(.+)", stripped)
        if ol_match:
            self.pdf.multi_cell(
                0,
                5.5,
                f"    {ol_match.group(1)}. {self._render_inline(ol_match.group(2))}",
            )
            self._ln(0.5)
            return

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
            if all(cell.startswith("---") or cell.startswith(":--") for cell in cells):
                return
            self._f(size=9)
            self.pdf.multi_cell(0, 5, "  |  " + "  |  ".join(self._render_inline(cell) for cell in cells))
            self._f(size=10)
            return

        self._para(self._render_inline(stripped))

    def _cover(self):
        """生成封面和基础信息。"""
        self.pdf.add_page()
        self._ln(55)
        if self._use_cjk():
            self._f(bold=True, size=28)
            self.pdf.cell(0, 14, "竞 品 分 析 报 告", align="C", new_x="LMARGIN", new_y="NEXT")
            self._ln(12)
            self._f(size=12)
            self.pdf.cell(0, 8, f"Report ID: {self.task_id}", align="C", new_x="LMARGIN", new_y="NEXT")
            self.pdf.cell(
                0,
                8,
                f"生成日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                align="C",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            self._ln(4)
            self.pdf.cell(0, 8, f"共 {len(self.sections)} 个章节", align="C", new_x="LMARGIN", new_y="NEXT")
            return

        self._f(bold=True, size=26)
        self.pdf.cell(0, 14, "Competitive Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")
        self._ln(12)
        self._f(size=11)
        self.pdf.cell(0, 8, f"Report ID: {self.task_id}", align="C", new_x="LMARGIN", new_y="NEXT")
        self._ln(4)
        self.pdf.cell(0, 8, f"Sections: {len(self.sections)}", align="C", new_x="LMARGIN", new_y="NEXT")

    def _toc(self):
        """生成目录。"""
        self._ln(16)
        title = "目  录" if self._use_cjk() else "Table of Contents"
        self._f(bold=True, size=16)
        self.pdf.cell(0, 10, title, align="C", new_x="LMARGIN", new_y="NEXT")
        self._ln(8)
        self._f(size=11)
        for i, section in enumerate(self.sections):
            sec_title = section.get("section", f"Section {i}")
            display = sec_title[:70] + ("…" if len(sec_title) > 70 else "")
            self.pdf.cell(0, 7, f"  {i + 1}.  {display}", new_x="LMARGIN", new_y="NEXT")
        self._ln(4)

    def _render_section(self, section: dict, index: int):
        """生成单个报告章节。"""
        self.pdf.add_page()
        title = section.get("section", f"Section {index}")
        content = section.get("content", "")

        self._f(bold=True, size=15)
        self.pdf.multi_cell(0, 9, title)
        self._ln(1)
        y = self.pdf.get_y()
        self.pdf.line(15, y, self.pdf.w - 15, y)
        self._ln(6)

        self._f(size=10)
        for line in content.split("\n"):
            self._render_line(line)

    def build(self) -> bytes:
        """构建完整 PDF 字节。"""
        self._cover()
        self._toc()
        for i, section in enumerate(self.sections):
            self._render_section(section, i)
        return bytes(self.pdf.output())


def build_pdf(task_id: str, sections: list[dict]) -> bytes:
    """使用报告章节生成 PDF 字节。"""
    builder = _MarkdownPDF(task_id, sections)
    return builder.build()
