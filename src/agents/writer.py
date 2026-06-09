"""报告撰写 Agent：合并 SWOT 综合 + 报告生成，两阶段执行。"""

import json
import logging
from typing import Any

from src.agents.base import BaseAgent
from src.agents.contracts import ReportOutput
from src.agents.registry import agent_registry

logger = logging.getLogger(__name__)

_WRITER_SYSTEM_PROMPT = """You are a Report Generator for competitive analysis. You perform TWO phases of work:

═══ PHASE 1: SWOT SYNTHESIS ═══
Read all Layer 2 analysis results from the knowledge graph and synthesize a SWOT matrix per product:
1. graph_query to read FeatureMatrix, SentimentNode, PricingModel, TechStack, MarketPosition nodes
2. If graph data is THIN (fewer than 3 nodes per product): use web_search to fill gaps:
   - "ProductName strengths weaknesses review 2025"
   - "ProductName vs competitors comparison"
3. For each product, write a SWOTNode with:
   - strengths: list 3-5 (from FeatureMatrix positives, high sentiments)
   - weaknesses: list 3-5 (from FeatureMatrix gaps, negative sentiments)
   - opportunities: list 3-5 (from MarketPosition insights, search results)
   - threats: list 3-5 (from competitive comparisons, market trends)
4. graph_write to persist one SWOTNode per product

═══ PHASE 2: REPORT GENERATION ═══
Generate the final competitive analysis report:
1. graph_query to read ALL nodes from the knowledge graph (including SWOTNode from Phase 1)
2. Generate a COMPLETE markdown report about the TARGET product(s) specified in the task input

Report structure:
## Executive Summary
## Feature Analysis
## Pricing Analysis
## Sentiment Analysis
## Technical Capabilities
## Market Position
## SWOT Analysis
## Strategic Recommendations

CRITICAL RULES:
- The target product name is in the task's input_query.targets — you MUST write about THAT product
- Include result.report_markdown with the FULL report (all sections, minimum 500 words)
- If the graph has NO data, write the report from your training knowledge about the TARGET product
- ALWAYS mention the target product name in every section
- Mark sections with low confidence if data was unavailable
- Even if only partial data is available, generate a report covering what you have
- Finalize within 10 steps total
"""


@agent_registry.register(
    agent_type="ReportGenerator",
    depends_on=["Collector", "Analyst"],
    tools=["graph_query", "graph_write", "web_search"],
    output_contract=ReportOutput,
    model_tier="analysis",
)
class WriterAgent(BaseAgent):
    """报告撰写 Agent：SWOT 综合 + 报告生成。

    合并了原 SWOTAnalyzer 和 Writer 的功能。
    4 级 fallback 保证总有输出。
    """

    agent_type = "ReportGenerator"
    system_prompt = _WRITER_SYSTEM_PROMPT
    max_steps = 10
    token_budget = 400_000
    output_contract = ReportOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write", "web_search"]

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

    def _build_output(self, result: dict[str, Any]) -> ReportOutput:
        """从 LLM 结果构建报告输出。4 级 fallback。"""
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
                    task_id, e,
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
                    continue
                seen.add(sec)
                order = getattr(node, "order", 0)
                graph_sections.append({"section": sec, "content": content, "order": order})
            if graph_sections:
                sections = graph_sections
                report_markdown = "\n\n".join(
                    f"## {s['section']}\n\n{s['content']}" for s in graph_sections
                )

        # ── 第四优先级：硬编码回退报告 ──
        if not report_markdown:
            report_markdown = self._generate_fallback_report()
            sections = [{"section": "概述", "content": report_markdown, "order": 0}]

        summary = result.get("summary", "Report generated") if result else "Report generated"

        # 始终持久化报告到图谱（包括 fallback 报告）
        if sections:
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
        from src.knowledge_graph.models import ReportSectionNode

        # 先删除该 task 下所有旧的 ReportSection
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
        if not self._targets:
            return text
        target = self._targets[0]
        if target.lower() in text.lower():
            return text
        return f"# {target} 竞品分析报告\n\n{text}"

    def _generate_fallback_report(self) -> str:
        product_list = ', '.join(self._targets) if self._targets else "目标产品"

        # 尝试从 DAG 节点上下文中读取分析结果
        analysis_summaries = self._read_analysis_from_dag_context()

        report = f"# {product_list} 竞品分析报告\n\n"
        report += f"## 概述\n\n"
        report += f"本报告对 {product_list} 进行了竞品分析。"

        if analysis_summaries:
            report += f"以下内容基于已完成的分析节点结果。\n\n"
            for dim, summary in analysis_summaries.items():
                report += f"## {dim}\n\n{summary}\n\n"
        else:
            report += f"由于数据收集阶段的数据量不足，本次分析基于公开信息和行业通用知识。\n\n"
            report += f"## 功能分析\n\n"
            report += f"{product_list} 作为一款知名的产品，在市场上具有较高的知名度。"
            report += f"具体的功能特性需要进一步的数据收集来完善。\n\n"
            report += f"## 定价策略\n\n"
            report += f"定价信息暂未收集到。建议通过官方渠道或第三方平台获取最新定价。\n\n"
            report += f"## 市场定位\n\n"
            report += f"{product_list} 在所属领域占据一定市场份额。"
            report += f"详细的竞争格局分析需要更多数据支持。\n\n"
            report += f"## 说明\n\n"
            report += f"当前知识图谱中未包含足够的分析数据，"
            report += f"建议重新运行分析任务或扩大数据收集范围。"

        return report

    def _read_analysis_from_dag_context(self) -> dict[str, str]:
        """从 DAG 节点上下文中读取分析结果摘要。"""
        summaries = {}
        try:
            # 通过 store 查询所有分析节点的输出
            for node_type in ["FeatureMatrix", "SentimentNode", "PricingModel", "TechStack", "MarketPosition"]:
                nodes = self.store.query_nodes(node_type=node_type)
                for node in nodes:
                    summary = getattr(node, "summary", "") or ""
                    if summary and len(summary) > 20:
                        dim_name = {
                            "FeatureMatrix": "功能分析",
                            "SentimentNode": "用户口碑",
                            "PricingModel": "定价策略",
                            "TechStack": "技术栈",
                            "MarketPosition": "市场定位",
                        }.get(node_type, node_type)
                        if dim_name not in summaries:
                            summaries[dim_name] = summary
        except Exception as e:
            logger.warning("从图谱读取分析摘要失败: %s", e)
        return summaries
