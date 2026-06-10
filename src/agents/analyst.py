"""分析师 Agent：5 维度差异化工具栈，每个维度抓取+分析+写图。

重构方向（2026-06-09）：
- 每个维度用**不同的 API**，避免全部依赖 Firecrawl（500 页/月配额）
- Analyst 从 Collector 写入的 SourceInfo 节点拿到 URL 列表，再按需抓取
- 工具数收紧到 ≤4 个/维度，prompt 不爆，LLM 决策更准
- max_steps=6, token_budget=100k，避免长循环
"""

from typing import Any

from src.agents.base import BaseAgent
from src.agents.contracts import AgentOutput
from src.agents.registry import agent_registry


# 每个分析维度的差异化工具栈与 prompt
_DIMENSION_CONFIGS: dict[str, dict] = {
    # ── feature: 需要干净 markdown，主力 Firecrawl ──
    "feature": {
        "prompt": """You are a Feature Analyzer for competitive analysis.

Step 1: graph_query(node_type="SourceInfo") — 读 Collector 写入的 URL 列表。
        过滤出 url_type ∈ {"homepage", "review"} 的 URL。
Step 2: 对每个产品的官网 URL 用 firecrawl(action="scrape", url=...) 抓取功能页 markdown。
        如果 firecrawl 失败/cache_miss，用 web_scrape 兜底。
Step 3: 从抓取内容中识别 8-12 个跨产品通用能力维度（不是产品独有功能名）。
          使用中文通用能力名：如"在线表格/多维表格"而非"飞书多维表格"、"强提醒消息"而非"DING 消息"、
          "AI 代码补全"而非"Trae AI补全"、"在线文档协作"而非"企微文档协作"。
          对每个 product×capability 评估:
            - name (通用能力名)
            - category (UI/UX, AI, Collaboration, API, Security 等)
            - maturity ∈ {experimental, beta, ga, deprecated}
              行业通用能力（如 AI 代码补全）默认 ga，除非有证据表明缺失或未成熟。
              只有真正不确定时才用 unknown。
            - differentiation ∈ {unique, advantage, parity, disadvantage}
Step 4: graph_write 每个 (product, capability) 一个 FeatureNode。
""",
        "tools": ["graph_query", "graph_write", "firecrawl", "web_scrape"],
        "model_tier": "analysis",
    },

    # ── pricing: 定价页结构简单，优先轻量抓取，节省 Firecrawl 配额 ──
    "pricing": {
        "prompt": """You are a Pricing Analyst for competitive analysis.

Step 1: graph_query(node_type="SourceInfo") — 拿 URL 列表，过滤 url_type=="pricing"。
Step 2: 对每个 pricing URL 用 web_scrape 抓取。失败再用 tavily 搜 "ProductName 定价 套餐"。
Step 3: 对每个产品识别:
          - pricing strategy ∈ {freemium, usage-based, per-seat, flat-rate, hybrid}
          - target segment ∈ {individual, SMB, mid-market, enterprise}
          - plan list: [{name, price, currency, billing_cycle, features[]}, ...]
            将方案档位归一到: Free / Starter / Pro / Business / Enterprise
          - value_score (0.0-1.0)，给出 value_score 的评估理由
Step 4: graph_write 每个产品至少 1 个 PricingModel 节点 + 每个套餐 1 个 PricingData 节点。

CRITICAL:
- 优先用 web_scrape 不用 firecrawl（省配额）
- 每产品至少 1 个 PricingModel + 2 个 PricingData
- 方案名归一化到标准档位: Free / Starter / Pro / Business / Enterprise
- 标注货币单位 (CNY / USD)，价格差异 > 50x 时附加 log_price
- 没找到价格时，设 value_score=0.15 + confidence=0.15，不要瞎编
- Finalize within 6 steps
""",
        "tools": ["graph_query", "graph_write", "web_scrape", "tavily"],
        "model_tier": "analysis",
    },

    # ── sentiment: 零网页抓取，纯 API ──
    "sentiment": {
        "prompt": """You are a Sentiment Analyzer for competitive analysis.

Step 1: graph_query(node_type="SourceInfo") — 不强制读，本维度主要靠 API。
Step 2: 对每个产品并行调用以下来源（按数据丰富度排序）:
          - reddit(action="search", query="ProductName") — 英文用户讨论
          - producthunt(query="ProductName") — 产品评分
          - social_media(platform="xiaohongshu"/"zhihu", query="ProductName") — 中文社媒
Step 3: 按主题聚合: pricing / usability / performance / support / features / onboarding
        每个主题计算 sentiment_score (-1.0 ~ +1.0) + trend (improving/stable/declining)
        CRITICAL: 所有产品必须覆盖相同的主题集合，缺失的填入 0 + confidence=0.2
Step 4: graph_write 每个 (product, topic) 一个 SentimentNode。

CRITICAL:
- 至少调用 2 个数据源（reddit + producthunt 是最快的）
- social_media 较慢，cache miss 时可以跳过
- 每产品至少 2 个 SentimentNode
- Finalize within 6 steps
""",
        "tools": ["graph_query", "graph_write", "reddit", "producthunt", "social_media"],
        "model_tier": "analysis",
    },

    # ── techstack: 包/仓库 API 为主 ──
    "techstack": {
        "prompt": """You are a Tech Stack Analyzer for competitive analysis.

Step 1: graph_query(node_type="SourceInfo") — 拿 URL（主要看 homepage 域名）。
Step 2: 对每个产品并行查:
          - github(action="search", query="ProductName") — 找官方开源仓库
          - gitee(action="repo", owner=..., repo=...) — 国内开源
          - npm(action="search", query="ProductName") — JS 生态
          - pypi(action="search", query="ProductName") — Python 生态（如适用）
        从仓库 description、language、topics 推断技术栈。
Step 3: 识别 languages[], frameworks[], infra[]（cloud/database/CDN/monitoring）
Step 4: graph_write 每个产品 1 个 TechStack 节点。

CRITICAL:
- 不爬网页，纯 API 查询
- 即使开源仓库未找到，用 wayback_machine 看历史快照推断
- 每产品至少 1 个 TechStack
- 数据不足时 confidence=0.2，不要瞎编
- Finalize within 6 steps
""",
        "tools": ["graph_query", "graph_write", "github", "gitee", "npm", "wayback_machine"],
        "model_tier": "analysis",
    },

    # ── market_position: 新闻 + 趋势 API ──
    "market_position": {
        "prompt": """You are a Market Position Analyzer for competitive analysis.

Step 1: graph_query(node_type="SourceInfo") — 不强制读，本维度靠 API。
Step 2: 对每个产品调用:
          - newsapi(action="everything", query="ProductName", language="zh") — 中文新闻
          - newsapi(action="everything", query="ProductName", language="en") — 英文新闻
          - google_trends — 搜索热度趋势（若可用）
          - serper_search 作为兜底
Step 3: 识别:
          - positioning (slogan/定位陈述)
          - gtm_strategy ∈ {PLG, sales-led, channel, community}
          - target_audience (developer/PM/designer/enterprise/SMB)
          - key_competitors
Step 4: graph_write 每个产品 1 个 MarketPosition 节点。

CRITICAL:
- 优先用 newsapi（API 限额 100/天，命中缓存就够用）
- 每产品至少 1 个 MarketPosition
- Finalize within 6 steps
""",
        "tools": ["graph_query", "graph_write", "newsapi", "google_trends", "serper_search"],
        "model_tier": "analysis",
    },

    # ── cross_review: 不变 ──
    "cross_review": {
        "prompt": """You are a Cross-Review Agent. Your job is to check consistency across analysis agents.

Perform 3 checks on Layer 2 analysis nodes:

1. CONTRADICTION DETECTION: Compare conclusions from different analysis agents for the same product/dimension.
   Example: FeatureAnalyzer rates a feature as "weak" but SentimentAnalyzer shows positive user sentiment → contradiction.

2. OMISSION DETECTION: Check if one agent's data reveals information another agent should have considered.
   Example: SentimentAnalyzer found frequent "API integration" mentions, but FeatureAnalyzer didn't cover API capabilities.

3. CONFIDENCE ANOMALY: Detect when an agent assigns high confidence with very few derived_from edges.

For each finding, create a CrossReviewFlag node with:
- flag_type: "conflict", "omission", or "confidence_anomaly"
- severity: "high", "medium", or "low"
- involved_agents: list of agent types
- description: human-readable explanation

For contradiction findings, also create contradicts edges between the conflicting analysis nodes.

IMPORTANT: Only flag HIGH severity for clear, well-evidenced contradictions.
Low-confidence or thin-data situations should be flagged as LOW or MEDIUM, not HIGH.

Output your flags list in the data.flags field of your finalize result.
""",
        "tools": ["graph_query", "graph_write"],
        "model_tier": "analysis",
    },
}


def _build_analyst_system_prompt(dimension: str) -> str:
    """根据分析维度构建 system prompt。"""
    config = _DIMENSION_CONFIGS.get(dimension)
    if not config:
        return f"You are an Analyst agent. Unknown dimension: {dimension}. Use graph_query to read data and graph_write to write results."
    return config["prompt"]


def _get_analyst_tools(dimension: str) -> list[str]:
    config = _DIMENSION_CONFIGS.get(dimension)
    if not config:
        return ["graph_query", "graph_write"]
    return config["tools"]


def _get_analyst_model_tier(dimension: str) -> str:
    config = _DIMENSION_CONFIGS.get(dimension)
    if not config:
        return "analysis"
    return config["model_tier"]


@agent_registry.register(
    agent_type="Analyst",
    depends_on=["Collector"],
    # 注册所有维度可能用到的工具的并集
    tools=[
        "graph_query", "graph_write",
        "firecrawl", "web_scrape", "tavily",
        "reddit", "producthunt", "social_media",
        "github", "gitee", "npm", "wayback_machine",
        "newsapi", "google_trends", "serper_search",
    ],
    output_contract=AgentOutput,
    model_tier="analysis",
)
class AnalystAgent(BaseAgent):
    """分析师 Agent：根据 dimension 参数切换工具栈和 prompt。

    dimension 取值：feature / sentiment / pricing / techstack / market_position / cross_review
    通过 task["context"]["dimension"] 或 task["input_query"]["dimension"] 传入。

    每个维度都从 graph_query(node_type="SourceInfo") 拿 Collector 写入的 URL 列表，
    再按维度差异化用不同 API/scraper 抓取数据，最后 graph_write 对应类型的节点。
    """

    agent_type = "Analyst"
    output_contract = AgentOutput
    max_steps = 6  # 从默认 10 降到 6
    token_budget = 100_000  # 从 300k 降到 100k

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dimension: str = ""
        self._actions_taken: list[str] = []

    async def execute(self, task: dict) -> tuple:
        # 从 task input_query 或 context 中读取分析维度
        self._dimension = (
            task.get("input_query", {}).get("dimension")
            or task.get("context", {}).get("dimension")
            or "feature"
        )
        self._actions_taken = []

        # 动态设置该维度的 system_prompt、allowed_tools、model_tier
        self.system_prompt = _build_analyst_system_prompt(self._dimension)
        self.allowed_tools = _get_analyst_tools(self._dimension)
        self.model_tier = _get_analyst_model_tier(self._dimension)

        return await super().execute(task)

    async def _think(self, observation: dict[str, Any]) -> dict[str, Any]:
        """注入动作历史；如果试图 finalize 但未 graph_write，强制改为提示重试。"""
        observation["_actions_taken"] = self._actions_taken.copy()
        has_written = "graph_write" in self._actions_taken
        step_count = len(self._actions_taken)

        # cross_review 维度不需要写大量节点，免拦截
        if self._dimension == "cross_review":
            return await super()._think(observation)

        if step_count >= 3 and not has_written:
            observation["_warning"] = (
                "你已经执行了 %d 步，但还没有 graph_write 任何节点。"
                "请立即调用 graph_write 写入分析结果，然后 finalize。即使数据有限，也要写出 confidence=0.2 的节点。"
            ) % step_count

        result = await super()._think(observation)

        if result.get("action") == "finalize" and not has_written:
            result["action"] = "retry"
            result["params"] = {}
            result["reasoning"] = (
                "[SYSTEM BLOCK] %s 维度试图 finalize 但还没有 graph_write 任何节点。"
                "请基于已有的观察至少写入 1 个节点（即使 confidence 低），然后再 finalize。"
            ) % self._dimension

        return result

    async def _act(self, action: str, params: dict) -> dict:
        """记录动作历史，处理 retry 拦截。"""
        if action == "retry":
            return {
                "error": "FINALIZE BLOCKED: 你必须先调用 graph_write 写入至少 1 个分析节点，然后再 finalize。",
            }
        result = await super()._act(action, params)
        self._actions_taken.append(action)
        return result

    def _build_output(self, result: dict) -> AgentOutput:
        """在输出中注入 dimension 信息，便于下游识别。"""
        output = super()._build_output(result)
        if hasattr(output, "data") and isinstance(output.data, dict):
            output.data["dimension"] = self._dimension
        return output