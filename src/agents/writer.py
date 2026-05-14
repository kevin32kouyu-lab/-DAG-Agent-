from typing import Any
from src.agents.base import BaseAgent
from src.agents.contracts import ReportOutput
from src.agents.registry import agent_registry

WRITER_PROMPT = """You are a Report Writer agent. Generate a structured competitive analysis report.

Read all Layer 2 and Layer 3 nodes. Write each report section to the graph, then finalize.

Workflow:
1. graph_query to read all Layer 2 and Layer 3 nodes
2. For each section below, call graph_write to create a ReportSection node — the section content will be stored in the graph, so your finalize only needs a brief summary
3. Call finalize when done

Report sections to create:
1. Executive Summary
2. Feature Comparison Matrix
3. Pricing Analysis
4. User Sentiment Analysis
5. Technical Capabilities
6. Market Position
7. SWOT Analysis (per product)
8. Strategic Recommendations

CRITICAL — ReportSection node via graph_write requires:
- node_type: "ReportSection"
- data.section: section title string, e.g. "Executive Summary"
- data.content: full markdown content for this section
- data.order: section number (0-7)
- source_id: ID of a SWOT or analysis node this section derives from
- edge_type: "derived_from"
"""


@agent_registry.register(
    agent_type="Writer",
    depends_on=["SWOTAnalyzer"],
    tools=["graph_query", "graph_write"],
    output_contract=ReportOutput,
    model_tier="analysis",
)
class WriterAgent(BaseAgent):
    agent_type = "Writer"
    system_prompt = WRITER_PROMPT
    max_steps = 20
    output_contract = ReportOutput
    model_tier = "analysis"
    allowed_tools = ["graph_query", "graph_write"]

    def _build_output(self, result: dict[str, Any]) -> Any:
        # Read ReportSection nodes from graph to assemble the report.
        # This is reliable — it doesn't depend on the LLM including
        # the full markdown in its finalize result.
        section_nodes = self.store.query_nodes(node_type="ReportSection", layer=3)
        sections: list[dict] = []
        md_parts: list[str] = []

        for node in sorted(section_nodes, key=lambda n: getattr(n, "order", 0)):
            sec = getattr(node, "section", "")
            content = getattr(node, "content", "")
            order = getattr(node, "order", 0)
            sections.append({"section": sec, "content": content, "order": order})
            if sec and content:
                md_parts.append(f"## {sec}\n\n{content}")

        report_markdown = "\n\n".join(md_parts)
        summary = result.get("summary", "Report generated")

        return ReportOutput(
            agent_type=self.agent_type,
            node_id=self.context.node_id,
            summary=summary,
            report_markdown=report_markdown,
            sections=sections,
            status="completed",
            data={"report_markdown": report_markdown, "sections": sections},
        )
