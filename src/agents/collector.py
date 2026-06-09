"""URL 发现 Agent：用 serper 找到每个目标产品的关键 URL，写入 SourceInfo 节点。

重构自旧的 CollectorAgent（曾经做"搜索 + 抓取 + 写图"三件事，跑 3.5 分钟 degraded）。
现在职责收缩到"只做 URL 发现"，5 步内 finalize。下游 Analyst 负责抓取和分析。
"""

import logging
from typing import Any

from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry
from src.infrastructure.degradation import DegradationHandler
from src.infrastructure.config import config

logger = logging.getLogger(__name__)


_COLLECTOR_SYSTEM_PROMPT = """You are a URL Discovery agent for competitive analysis.

Your ONLY job: for EACH target product, find and persist the following URLs as
`SourceInfo` nodes in the knowledge graph:
  - homepage     — 官网首页
  - pricing      — 定价页
  - review       — 第三方评测/口碑页（最多 2 个）
  - news         — 近期新闻报道（可选，最多 1 个）

Tools:
  1. serper_search  — Google 搜索（首选），返回干净的 URL 列表
  2. tavily         — 备份搜索工具
  3. graph_write    — 写入 SourceInfo 节点
  4. graph_query    — 检查图谱中已有数据（避免重复）

Execution flow per product:
  Step A: serper_search(query="ProductName 官网 定价")  → 拿到 URL 列表
  Step B: graph_write 多个 SourceInfo 节点，每个包含:
            { url, domain, product, url_type, label }
          其中 url_type ∈ {"homepage", "pricing", "review", "news"}
  Step C: 对下一个产品重复 A-B

CRITICAL RULES:
  - 每个产品至少写 3 个 SourceInfo 节点（homepage + pricing + 1 review）
  - DO NOT scrape any page. DO NOT write WebPage / FeatureNode / 其它任何分析节点
  - 下游 Analyst agents 会基于你写入的 SourceInfo 列表去抓取和分析
  - Finalize within 5 steps, do NOT loop
  - 如果某个产品 serper 搜不到，用 tavily 重试一次后立刻 finalize（不要纠结）

输出格式（finalize 时）:
  {"summary": "Discovered N URLs across M products", "nodes_created": [...]}
"""


@agent_registry.register(
    agent_type="Collector",
    depends_on=[],
    tools=["serper_search", "tavily", "graph_write", "graph_query"],
    output_contract=AgentOutput,
    model_tier="analysis",
)
class CollectorAgent(BaseAgent):
    """URL 发现 Agent：5 步内完成所有目标产品的 URL 搜集。"""

    agent_type = "Collector"
    system_prompt = _COLLECTOR_SYSTEM_PROMPT
    max_steps = 5
    token_budget = 100_000
    output_contract = AgentOutput
    model_tier = "analysis"
    allowed_tools = ["serper_search", "tavily", "graph_write", "graph_query"]

    def __init__(self, gateway, store, tool_registry, audit_logger=None,
                 degradation_handler=None):
        super().__init__(gateway, store, tool_registry, audit_logger)
        self.degradation_handler = degradation_handler or DegradationHandler(
            config=config, audit=audit_logger
        )
        self._actions_taken: list[str] = []

    async def execute(self, task: dict) -> tuple:
        """注入降级上下文后执行 URL 发现。"""
        self._inject_degradation_context(task)
        self._actions_taken = []
        return await super().execute(task)

    async def _think(self, observation: dict[str, Any]) -> dict[str, Any]:
        """在 observation 注入"动作历史 + finalize 前置提醒"，并阻止未 graph_write 的 finalize。"""
        observation["_actions_taken"] = self._actions_taken.copy()
        has_written = "graph_write" in self._actions_taken
        step_count = len(self._actions_taken)

        # 友好提示：超过 3 步还没写图，明确提示要 finalize 前 graph_write
        if step_count >= 3 and not has_written:
            observation["_warning"] = (
                "你已经执行了 %d 步，但还没有 graph_write 任何 SourceInfo 节点。"
                "请立即调用 graph_write，写入已搜到的 URL；然后 finalize。"
            ) % step_count

        result = await super()._think(observation)

        # 阻止未 graph_write 的 finalize（干净版 — 不注入垃圾占位）
        if result.get("action") == "finalize" and not has_written:
            result["action"] = "retry"
            result["params"] = {}
            result["reasoning"] = (
                "[SYSTEM BLOCK] 你试图 finalize 但还没有调用 graph_write 写入任何 SourceInfo 节点。"
                "请先用 graph_write 写入你搜到的 URL（homepage, pricing, review 各至少 1 个/产品），"
                "然后再 finalize。"
            )

        return result

    async def _act(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """记录每次动作，便于后续提示生成。处理 retry 动作。"""
        if action == "retry":
            return {
                "error": "FINALIZE BLOCKED: 你还没有调用 graph_write。"
                         "请先用 graph_write 写入你搜到的 SourceInfo 节点，然后再 finalize。",
            }
        result = await super()._act(action, params)
        self._actions_taken.append(action)
        return result

    def _inject_degradation_context(self, task: dict) -> None:
        """注入数据源降级信息（保留旧版能力，supplementary）。"""
        sources = task.get("context", {}).get("sources", [])
        if not sources:
            return
        degradation_hints = {}
        for src in sources:
            src_name = src if isinstance(src, str) else src.get("name", "")
            if src_name and self.degradation_handler:
                tiers = self.degradation_handler.get_tiers(src_name)
                if tiers:
                    degradation_hints[src_name] = tiers
        if degradation_hints:
            task["context"]["degradation_tiers"] = degradation_hints
            task["context"]["current_tiers"] = {s: 0 for s in degradation_hints}