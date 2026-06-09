"""质检 Agent：合并事实校验 + 逻辑校验，输出结构化的质检结果和拒绝理由。"""

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.agents.contracts import QAOutput
from src.agents.registry import agent_registry

logger = logging.getLogger(__name__)

_QA_SYSTEM_PROMPT = """You are a Quality Assurance Agent for competitive analysis reports. You perform TWO sequential checks on the report.

═══ CHECK 1: FACT CHECK ═══
Verify every claim in the report against the knowledge graph:
1. Read all ReportSection and InsightNode content via graph_query
2. For each claim, BFS trace along derived_from edges to verify evidence chain exists
3. Check that evidence nodes (WebPage, ReviewEntry, PricingData) actually exist
4. Flag claims with broken or missing trace chains
5. Flag suspicious patterns: high confidence with few sources, old data

═══ CHECK 2: LOGIC CHECK ═══
Verify the report contains no logical contradictions:
1. Compare Section A vs Section B for internal contradictions
2. Check if conclusions are supported by preceding evidence (reasoning gaps)
3. Identify obvious counter-arguments not addressed (missing context)

═══ OUTPUT FORMAT ═══
Your finalize result MUST include:
- data.fact_issues: list of {node_id, claim, reason, severity} for fact-check failures
- data.logic_issues: list of {section_a, section_b, description, severity} for logic failures
- data.overall_pass: boolean — true ONLY if no high-severity issues found
- data.rejection_reason: string — if overall_pass is false, explain what needs to be fixed and which agent should redo the work

CRITICAL:
- Be rigorous but fair. Low-confidence sections are acceptable if marked as such.
- A report passes QA if it has NO high-severity issues.
- If the report has data gaps but acknowledges them with low confidence, that is NOT a failure.
- Finalize within 10 steps maximum.
"""


@agent_registry.register(
    agent_type="QA",
    depends_on=["ReportGenerator"],
    tools=["graph_query", "graph_write"],
    output_contract=QAOutput,
    model_tier="reasoning",
)
class QAAgent(BaseAgent):
    """质检 Agent：对报告进行事实校验 + 逻辑校验，输出结构化质检结果。

    当 overall_pass=false 时，FeedbackHandler 会根据 rejection_reason 决定
    打回 Writer 还是打回 Analyst。
    """

    agent_type = "QA"
    system_prompt = _QA_SYSTEM_PROMPT
    max_steps = 12
    token_budget = 400_000
    output_contract = QAOutput
    model_tier = "reasoning"
    allowed_tools = ["graph_query", "graph_write"]

    def _build_output(self, result: dict[str, Any]) -> QAOutput:
        """构建 QA 输出，确保 fact_issues / logic_issues / overall_pass 字段存在。"""
        task_id = self.context.task_id

        # 从 result 中提取质检结果
        fact_issues = result.get("fact_issues", [])
        logic_issues = result.get("logic_issues", [])

        # 如果 LLM 没有结构化输出，尝试从 data 字段提取
        data = result.get("data", {})
        if isinstance(data, dict):
            fact_issues = fact_issues or data.get("fact_issues", [])
            logic_issues = logic_issues or data.get("logic_issues", [])

        # 判断是否通过
        high_severity = any(
            issue.get("severity") == "high"
            for issue in fact_issues + logic_issues
        )
        overall_pass = not high_severity and result.get("overall_pass", True)

        # 构建拒绝理由
        rejection_reason = ""
        if not overall_pass:
            parts = []
            if fact_issues:
                parts.append(f"事实校验发现 {len(fact_issues)} 个问题")
            if logic_issues:
                parts.append(f"逻辑校验发现 {len(logic_issues)} 个问题")
            rejection_reason = "；".join(parts) or result.get("rejection_reason", "质检未通过")

        summary = result.get("summary", "")
        if not summary:
            if overall_pass:
                summary = f"质检通过：事实校验 {len(fact_issues)} 个问题，逻辑校验 {len(logic_issues)} 个问题"
            else:
                summary = f"质检未通过：{rejection_reason}"

        return QAOutput(
            agent_type=self.agent_type,
            node_id=self.context.node_id,
            status="completed",
            summary=summary,
            nodes_created=result.get("nodes_created", []),
            edges_created=result.get("edges_created", []),
            data=result,
            confidence=result.get("confidence", 0.8),
            fact_issues=fact_issues,
            logic_issues=logic_issues,
            overall_pass=overall_pass,
            rejection_reason=rejection_reason,
        )
