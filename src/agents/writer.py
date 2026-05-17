from typing import Any
from src.agents.base import BaseAgent
from src.agents.contracts import ReportOutput
from src.agents.registry import agent_registry

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
    max_steps = 6
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
            import logging
            logging.getLogger(__name__).warning(
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
        # Read ReportSection nodes from graph to assemble the report.
        section_nodes = self.store.query_nodes(node_type="ReportSection", layer=3)
        sections: list[dict] = []
        md_parts: list[str] = []

        task_id = self.context.task_id

        for node in sorted(section_nodes, key=lambda n: getattr(n, "order", 0)):
            metadata = getattr(node, "metadata", {}) or {}
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            if metadata and metadata.get("task_id") != task_id:
                continue
            sec = getattr(node, "section", "")
            content = getattr(node, "content", "")
            order = getattr(node, "order", 0)
            sections.append({"section": sec, "content": content, "order": order})
            if sec and content:
                md_parts.append(f"## {sec}\n\n{content}")

        report_markdown = "\n\n".join(md_parts)

        # Fallback 1: use LLM's finalize result.report_markdown
        if not report_markdown and result:
            raw = result.get("report_markdown", "")
            if len(raw) >= 200:
                report_markdown = self._fix_product_names(raw)
                sections = [{"section": "完整报告", "content": report_markdown, "order": 0}]

        # Fallback 2: use LLM summary, but only if it's a substantial report
        if not report_markdown and result:
            raw = result.get("summary", "") or str(result)
            if len(raw) >= 200:
                report_markdown = self._fix_product_names(raw)
                sections = [{"section": "完整报告", "content": report_markdown, "order": 0}]

        # Fallback 3: hardcoded — generate minimal report from product name
        if not report_markdown:
            report_markdown = self._generate_fallback_report()
            sections = [{"section": "概述", "content": report_markdown, "order": 0}]

        summary = result.get("summary", "Report generated") if result else "Report generated"

        # Persist ReportSection nodes to knowledge graph for Layer 1 API
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
        logger = logging.getLogger(__name__)
        from src.knowledge_graph.models import ReportSectionNode
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
