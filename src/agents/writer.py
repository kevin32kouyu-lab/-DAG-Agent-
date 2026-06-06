"""报告生成 Agent，负责把图谱分析结果整理成最终报告。"""

import logging
from typing import Any
from src.agents.base import BaseAgent
from src.agents.contracts import ReportOutput
from src.agents.registry import agent_registry

logger = logging.getLogger(__name__)

WRITER_PROMPT = """You are a Report Generator. Your ONLY job: read available data, then produce a complete competitive analysis report in markdown about the TARGET product(s) specified in the task input.

WORKFLOW (exactly 2 steps, no more):
Step 1: graph_query to read all nodes from the knowledge graph
Step 2: finalize with a COMPLETE markdown report about the target product(s)

CRITICAL RULES:
- The target product name is in the task's input_query.targets — you MUST write about THAT product
- You MUST finalize in step 2 — do NOT loop, do NOT call graph_query twice
- Include result.report_markdown with the FULL report (all sections, minimum 500 words)
- Include result.summary with a one-line description
- If the graph has NO data, write the report from your training knowledge about the TARGET product
- ALWAYS mention the target product name in every section
- Mark sections with low confidence if data was unavailable

Report structure:
## Executive Summary
## Feature Analysis
## Pricing Analysis
## Sentiment Analysis
## Technical Capabilities
## Market Position
## SWOT Analysis
## Strategic Recommendations

Skip sections that have no data AND no general knowledge available.
"""


@agent_registry.register(
    agent_type="ReportGenerator",
    depends_on=["SWOTAnalyzer"],
    tools=["graph_query", "graph_write"],
    output_contract=ReportOutput,
    model_tier="analysis",
)
class WriterAgent(BaseAgent):
    agent_type = "ReportGenerator"
    system_prompt = WRITER_PROMPT
    max_steps = 5
    token_budget = 400_000
    output_contract = ReportOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._targets: list[str] = []

    async def execute(self, task: dict[str, Any]) -> Any:
        """Override to guarantee output even on max_steps exceeded or other errors."""
        try:
            return await super().execute(task)
        except Exception:
            logger.warning(
                "Writer agent failed, generating fallback report", exc_info=True
            )
            # context.init is already called by super().execute() first line;
            # self._targets is already set by _observe before the failure.
            # Build a fallback output so _output_data is always available.
            output = self._build_output({})
            return output, []

    async def _observe(self, task: dict[str, Any]) -> dict[str, Any]:
        self._targets = task.get("input_query", {}).get("targets", [])
        return await super()._observe(task)

    async def _think(self, observation: dict[str, Any]) -> dict[str, Any]:
        if self._targets:
            product_names = ', '.join(self._targets)
            observation = {
                "TARGET": f"ANALYZE THIS PRODUCT: {product_names}",
                "MANDATORY": f"Report title MUST be: Competitive Analysis of {product_names}",
                **observation,
            }
        return await super()._think(observation)

    def _build_output(self, result: dict[str, Any]) -> Any:
        """从 LLM 结果构建报告输出。LLM 生成的 report_markdown 优先；
        图谱中的 ReportSection 节点仅在 LLM 未生成有用内容时作为备选拼接。"""
        import json

        task_id = self.context.task_id
        sections: list[dict] = []
        report_markdown = ""

        # ── 第一优先级：LLM 生成的 report_markdown ──
        if result:
            raw = result.get("report_markdown", "")
            if len(raw) >= 200:
                report_markdown = self._fix_product_names(raw)
                sections = [{"section": "完整报告", "content": report_markdown, "order": 0}]

        # ── 第二优先级：LLM 的 summary（如果有实质内容）──
        if not report_markdown and result:
            raw = result.get("summary", "") or str(result)
            if len(raw) >= 200:
                report_markdown = self._fix_product_names(raw)
                sections = [{"section": "完整报告", "content": report_markdown, "order": 0}]

        # ── 第三优先级：图谱中已有的 ReportSection 节点 ──
        if not report_markdown:
            try:
                section_nodes = self.store.query_nodes(node_type="ReportSection", layer=3)
            except Exception as e:
                logger.warning(
                    "Writer 图谱报告章节读取失败，已使用兜底报告: task_id=%s, reason=%s",
                    task_id,
                    e,
                )
                section_nodes = []
            graph_sections: list[dict] = []
            seen = set()
            for node in sorted(section_nodes, key=lambda n: getattr(n, "order", 0)):
                meta = getattr(node, "metadata", {}) or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except (json.JSONDecodeError, TypeError):
                        meta = {}
                if meta.get("task_id") != task_id:
                    continue
                sec = getattr(node, "section", "")
                content = getattr(node, "content", "")
                if sec in seen:
                    continue  # 去重
                seen.add(sec)
                order = getattr(node, "order", 0)
                graph_sections.append({"section": sec, "content": content, "order": order})
            if graph_sections:
                sections = graph_sections
                # 用图谱节点拼接 markdown（仅备选路径使用）
                report_markdown = "\n\n".join(
                    f"## {s['section']}\n\n{s['content']}" for s in graph_sections
                )

        # ── 第四优先级：硬编码回退报告 ──
        if not report_markdown:
            report_markdown = self._generate_fallback_report()
            sections = [{"section": "概述", "content": report_markdown, "order": 0}]

        summary = result.get("summary", "Report generated") if result else "Report generated"

        # 仅在使用了 LLM 输出时持久化到图谱（避免把图谱旧数据重复写入）
        if result and result.get("report_markdown", ""):
            self._persist_sections(sections, task_id)

        return ReportOutput(
            agent_type=self.agent_type,
            node_id=self.context.node_id,
            summary=summary,
            report_markdown=report_markdown,
            sections=sections,
            status="completed",
            data={"report_markdown": report_markdown, "sections": sections},
        )

    def _persist_sections(self, sections: list[dict], task_id: str) -> None:
        import logging
        import json
        logger = logging.getLogger(__name__)
        from src.knowledge_graph.models import ReportSectionNode

        # 先删除该 task 下所有旧的 ReportSection，避免多次运行后指数级重复
        all_sections = self.store.query_nodes(node_type="ReportSection", layer=3)
        for node in all_sections:
            try:
                meta = getattr(node, "metadata", {}) or {}
                if isinstance(meta, str):
                    meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
            if meta.get("task_id") == task_id:
                self.store.delete_node(node.id)

        for s in sections:
            try:
                node = ReportSectionNode(
                    section=s.get("section", ""),
                    content=s.get("content", ""),
                    order=s.get("order", 0),
                    metadata={"task_id": task_id},
                )
                self.store.create_node(node)
            except Exception as e:
                logger.warning(f"Writer: failed to persist ReportSection '{s.get('section', '')}': {e}")

    def _fix_product_names(self, text: str) -> str:
        """Ensure the report mentions the actual target product."""
        if not self._targets:
            return text
        target = self._targets[0]
        if target.lower() in text.lower():
            return text
        # If LLM wrote about a different product, inject the correct title
        return f"# {target} 竞品分析报告\n\n{text}"

    def _generate_fallback_report(self) -> str:
        product_list = ', '.join(self._targets) if self._targets else "目标产品"
        return (
            f"# {product_list} 竞品分析报告\n\n"
            f"## 概述\n\n"
            f"本报告对 {product_list} 进行了竞品分析。"
            f"由于数据收集阶段的数据量不足，本次分析基于公开信息和行业通用知识。\n\n"
            f"## 功能分析\n\n"
            f"{product_list} 作为一款知名的产品，在市场上具有较高的知名度。"
            f"具体的功能特性需要进一步的数据收集来完善。\n\n"
            f"## 定价策略\n\n"
            f"定价信息暂未收集到。建议通过官方渠道或第三方平台获取最新定价。\n\n"
            f"## 市场定位\n\n"
            f"{product_list} 在所属领域占据一定市场份额。"
            f"详细的竞争格局分析需要更多数据支持。\n\n"
            f"## 说明\n\n"
            f"当前知识图谱中未包含足够的分析数据，"
            f"建议重新运行分析任务或扩大数据收集范围。"
            f"可能的原因：Collector 未能成功获取网页数据，"
            f"或 DataEnricher 未能补充足够的上下文信息。\n\n"
            f"> 生成状态: 部分数据可用，报告内容有限。"
            f"请检查上游 Agent 的执行日志。"
        )
