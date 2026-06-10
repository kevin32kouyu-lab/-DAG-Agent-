"""结构化知识图谱节点到图表数据的转换模块。"""

from __future__ import annotations

import json
import math
import re


# ── 行业通用能力白名单：将不同表述归一到标准能力名 ──
# key = 归一化后的能力名，value = 可能的原始特征名列表
FEATURE_WHITELIST: dict[str, list[str]] = {
    "AI Code Completion": [
        "ai code completion", "ai-powered code completion", "智能代码补全",
        "ai 代码补全", "code completion", "代码补全", "ai autocomplete",
        "copilot code completion", "trae ai completion", "cursor ai completion",
    ],
    "Multi-File Editing": [
        "multi-file editing", "multi-file edits", "composer multi-file edits",
        "多文件编辑", "跨文件编辑", "multi-file support",
    ],
    "Chat-based AI Assistant": [
        "chat", "chat-based ai", "ai chat", "ai assistant", "chat assistant",
        "智能对话", "ai 对话", "copilot chat", "cursor chat", "trae chat",
        "inline chat", "agent mode",
    ],
    "Git/Version Control Integration": [
        "git integration", "built-in git", "git 集成", "版本控制",
        "github integration", "github 集成", "version control",
    ],
    "Pull Request Management": [
        "pr review", "pull request review", "pull request summary",
        "pr management", "pr 审查", "pr 管理",
    ],
    "Code Review": [
        "code review", "代码审查", "code review ai", "ai code review",
    ],
    "Debugging Support": [
        "debugger", "debugging", "调试", "debug support", "ai debugging",
    ],
    "Terminal/CLI Integration": [
        "terminal", "cli", "command line", "终端集成", "内置终端",
        "terminal integration",
    ],
    "Extension/Plugin System": [
        "extensions", "plugins", "extension marketplace", "plugin system",
        "扩展", "插件", "扩展市场", "copilot extensions",
    ],
    "Custom Model Selection": [
        "model selection", "multi-model", "custom model", "bring your own model",
        "模型选择", "多模型支持", "model picker",
    ],
    "Voice Input": [
        "voice input", "voice support", "语音输入", "voice coding",
    ],
    "Skill/Command System": [
        "skill system", "command system", "custom commands", "skills",
        "技能系统", "指令系统",
    ],
    "Context Awareness": [
        "context awareness", "context window", "@mention", "上下文感知",
        "context length", "repo context",
    ],
    "Online Document Collaboration": [
        "online document", "文档协作", "在线文档", "document collaboration",
        "collaborative editing", "协同编辑", "实时协作",
    ],
    "Online Spreadsheet/Database": [
        "online spreadsheet", "multidimensional table", "多维表格", "在线表格",
        "database", "数据表", "spreadsheet",
    ],
    "Video Conferencing": [
        "video conference", "视频会议", "video call", "meeting",
        "视频通话", "在线会议",
    ],
    "Instant Messaging": [
        "instant messaging", "即时通讯", "im", "chat", "消息",
        "messaging", "群聊", "group chat",
    ],
    "Strong Notification": [
        "strong notification", "ding message", "ding 消息", "强提醒",
        "urgent notification", "紧急通知", "消息必达",
    ],
    "Third-Party Integration": [
        "third-party integration", "第三方集成", "api integration",
        "integration", "集成", "开放平台", "open platform",
    ],
    "Enterprise Security": [
        "enterprise security", "企业安全", "security compliance",
        "data encryption", "安全合规", "数据加密", "soc2", "iso27001",
    ],
    "Workflow Automation": [
        "workflow", "automation", "工作流", "自动化", "approval workflow",
        "审批流", "no-code automation",
    ],
    "AI/LLM Model": [
        "ai model", "llm", "大模型", "ai 能力", "大语言模型",
        "language model", "gpt", "claude", "doubao model",
    ],
    "Mobile Support": [
        "mobile app", "移动端", "mobile support", "ios", "android",
        "手机端", "mobile",
    ],
}


def _normalize_feature_name(raw_name: str) -> str:
    """将原始 feature name 归一化到白名单中的标准能力名。"""
    lower = raw_name.strip().lower()
    # 去除产品名前缀（如 "飞书 - xxx" → "xxx"）
    cleaned = re.sub(r"^(feishu|lark|dingtalk|wecom|trae|cursor|copilot|github)\s*[-—–]\s*", "", lower, flags=re.I)
    # 按别名长度降序匹配：优先匹配更具体的别名
    candidates: list[tuple[int, str]] = []
    for canonical, aliases in FEATURE_WHITELIST.items():
        for alias in aliases:
            if alias in cleaned or cleaned in alias:
                candidates.append((len(alias), canonical))
    if candidates:
        # 选最长匹配（更具体的别名优先）
        candidates.sort(key=lambda x: -x[0])
        return candidates[0][1]
    # 没有匹配白名单的返回原始名（但做 basic cleanup）
    return raw_name.strip()


def _normalize_plan_name(raw_name: str) -> str:
    """将定价方案名归一化到标准档位。"""
    lower = raw_name.strip().lower()
    if any(k in lower for k in ["free", "免费", "基础免费"]):
        return "Free"
    if any(k in lower for k in ["starter", "入门", "个人", "basic"]):
        return "Starter"
    if any(k in lower for k in ["pro", "专业", "professional", "商业专业", "商业版", "专业版"]):
        return "Pro"
    if any(k in lower for k in ["business", "企业", "商业", "team", "团队", "企业版"]):
        return "Business"
    if any(k in lower for k in ["enterprise", "专属", "旗舰", "专属版", "旗舰版"]):
        return "Enterprise"
    # 中文特殊名 → 估算档位
    if any(k in lower for k in ["会话", "存档", "数据保障", "安全", "增值"]):
        return "Add-on"
    return raw_name.strip()


def extract_metadata(node) -> dict:
    """读取节点 metadata，兼容字符串和字典两种存储形态。"""
    metadata = getattr(node, "metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return metadata or {}


def normalize_product_name(product: str) -> str:
    """统一产品名展示格式。"""
    if not product:
        return "Unknown"
    p = product.strip()
    if p.lower() == "notion":
        return "Notion"
    if p.islower():
        return p.capitalize()
    return p


def belongs_to_task(node, task_id: str, products: list[str] | None = None) -> bool:
    """判断节点是否属于当前任务，不再按产品名混入历史节点。"""
    return extract_metadata(node).get("task_id") == task_id


def build_scoring_data(nodes: list) -> list[dict]:
    """把 ScoringNode 转成雷达图数据。"""
    result = []
    for node in nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        dimension = getattr(node, "dimension", "") or ""
        score = getattr(node, "score", None)
        weight = getattr(node, "weight", 1.0)
        if score is not None and dimension:
            result.append({
                "product": product,
                "dimension": dimension,
                "score": float(score),
                "weight": float(weight),
            })
    return result


def build_feature_data(nodes: list) -> dict:
    """把 FeatureNode 合并成功能成熟度矩阵，做归一化 + 白名单默认。"""
    products_set: set[str] = set()
    features: list[dict] = []
    for node in nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        raw_name = getattr(node, "feature_name", "") or getattr(node, "name", "") or getattr(node, "label", "")
        category = getattr(node, "category", "") or ""
        maturity = getattr(node, "maturity", "unknown")
        differentiation = getattr(node, "differentiation", "unknown")
        if not raw_name:
            continue
        # 归一化 feature name 到通用能力名
        normalized_name = _normalize_feature_name(raw_name)
        products_set.add(product)
        features.append({
            "feature_name": normalized_name,
            "category": category,
            f"{product}_maturity": maturity,
            f"{product}_differentiation": differentiation,
        })

    merged: dict[str, dict] = {}
    for feature in features:
        feature_name = feature["feature_name"]
        if feature_name not in merged:
            merged[feature_name] = {"feature_name": feature_name, "category": feature["category"]}
        # 对于重复 entry，保留更好的 maturity（ga > beta > experimental > unknown）
        existing_keys = {k for k in merged[feature_name] if k.endswith("_maturity")}
        new_maturities = {k: v for k, v in feature.items() if k.endswith("_maturity")}
        for mk in new_maturities:
            if mk in existing_keys:
                # 保留更好的 maturity
                rank = {"ga": 3, "beta": 2, "experimental": 1, "unknown": 0}
                old_val = merged[feature_name].get(mk, "unknown")
                new_val = new_maturities[mk]
                merged[feature_name][mk] = new_val if rank.get(new_val, 0) > rank.get(old_val, 0) else old_val
            else:
                merged[feature_name][mk] = new_maturities[mk]
        # 同样保留更好的 differentiation
        for k, v in feature.items():
            if k not in ("feature_name", "category") and not k.endswith("_maturity") and not k.endswith("_differentiation"):
                merged[feature_name][k] = v
            elif k.endswith("_differentiation"):
                diff_rank = {"unique": 3, "advantage": 2, "parity": 1, "disadvantage": 0}
                old_val = merged[feature_name].get(k, "parity")
                merged[feature_name][k] = v if diff_rank.get(v, 1) > diff_rank.get(old_val, 1) else old_val

    # 归一化：为每个 feature 补全缺失产品的 maturity 和 differentiation
    # 对于白名单中的通用能力，默认 maturity=ga（而非 unknown）
    products_sorted = sorted(products_set)
    for feature_entry in merged.values():
        fname = feature_entry.get("feature_name", "")
        in_whitelist = fname in FEATURE_WHITELIST
        for p in products_sorted:
            if f"{p}_maturity" not in feature_entry:
                feature_entry[f"{p}_maturity"] = "ga" if in_whitelist else "unknown"
            if f"{p}_differentiation" not in feature_entry:
                feature_entry[f"{p}_differentiation"] = "parity"

    return {"products": products_sorted, "features": list(merged.values())}


def build_sentiment_data(nodes: list) -> dict:
    """把 SentimentNode 转成情感柱状图数据。"""
    products_set: set[str] = set()
    topics: dict[str, dict] = {}
    for node in nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        topic = getattr(node, "topic", "") or getattr(node, "label", "")
        sentiment_score = getattr(node, "sentiment_score", None)
        trend = getattr(node, "trend", "stable")
        if not topic or sentiment_score is None:
            continue
        products_set.add(product)
        topics.setdefault(topic, {"topic": topic})
        topics[topic][f"{product}_score"] = round(float(sentiment_score), 3)
        topics[topic][f"{product}_trend"] = trend

    # 归一化：为每个 topic 补全缺失的产品 score 为 0
    products_sorted = sorted(products_set)
    for topic_entry in topics.values():
        for p in products_sorted:
            key = f"{p}_score"
            if key not in topic_entry:
                topic_entry[key] = 0.0
            trend_key = f"{p}_trend"
            if trend_key not in topic_entry:
                topic_entry[trend_key] = "stable"

    return {"products": products_sorted, "topics": list(topics.values())}


def build_pricing_data(pricing_nodes: list, model_nodes: list) -> dict:
    """把 PricingData/PricingModel 转成价格和价值评分数据，增加 log_price 和 plan 归一化。"""
    # 汇率近似（CNY→USD）
    CNY_TO_USD = 0.14

    plans = []
    for node in pricing_nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        raw_plan = getattr(node, "plan_name", "") or getattr(node, "label", "")
        raw_price = float(getattr(node, "price", 0) or 0)
        currency = (getattr(node, "currency", "") or "").upper()
        billing_cycle = getattr(node, "billing_cycle", "") or ""

        # 归一化
        normalized_plan = _normalize_plan_name(raw_plan)

        # 估算 USD 价格
        price_usd = raw_price if currency == "USD" else round(raw_price * CNY_TO_USD, 2) if currency == "CNY" else raw_price

        # log_price：避免 log(0)
        log_price = round(math.log10(max(raw_price, 1)), 2)

        plans.append({
            "plan_name": normalized_plan,
            "product": product,
            "price": price_usd,
            "price_raw": raw_price,
            "currency": currency or "USD",
            "log_price": log_price,
            "billing_cycle": billing_cycle or "monthly",
        })

    value_scores = []
    for node in model_nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        value_score = getattr(node, "value_score", None)
        if value_score is None:
            continue
        value_scores.append({
            "product": product,
            "value_score": round(float(value_score), 3),
            "strategy": getattr(node, "strategy", "") or "",
            "target_segment": getattr(node, "target_segment", "") or "",
        })
    return {"plans": plans, "value_scores": value_scores}


def build_swot_data(nodes: list) -> list[dict]:
    """把 SWOTNode 转成四象限数据，含条目列表（不只是计数）。"""
    result = []
    for node in nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        strengths = getattr(node, "strengths", []) or []
        weaknesses = getattr(node, "weaknesses", []) or []
        opportunities = getattr(node, "opportunities", []) or []
        threats = getattr(node, "threats", []) or []
        result.append({
            "product": product,
            "strengths_count": len(strengths),
            "weaknesses_count": len(weaknesses),
            "opportunities_count": len(opportunities),
            "threats_count": len(threats),
            "strengths": strengths[:5],
            "weaknesses": weaknesses[:5],
            "opportunities": opportunities[:5],
            "threats": threats[:5],
        })
    return result


def build_insight_data(swot_data: list[dict], sentiment_data: dict, feature_data: dict, pricing_data: dict, products: list[str]) -> list[dict]:
    """从现有数据中提取核心洞察，每个产品 1-2 条关键发现。"""
    insights: list[dict] = []

    # 从 SWOT 提取每条产品的最关键差异化
    for sw in swot_data:
        product = sw["product"]
        items: list[dict] = []

        # Top strength
        if sw.get("strengths"):
            items.append({"type": "strength", "text": sw["strengths"][0], "icon": "✅"})
        # Top weakness
        if sw.get("weaknesses"):
            items.append({"type": "weakness", "text": sw["weaknesses"][0], "icon": "⚠️"})
        # Top opportunity
        if sw.get("opportunities"):
            items.append({"type": "opportunity", "text": sw["opportunities"][0], "icon": "🚀"})

        if items:
            insights.append({"product": product, "items": items})

    # 从情感数据提取整体印象
    for topic_entry in sentiment_data.get("topics", []):
        topic = topic_entry.get("topic", "")
        for p in products:
            score = topic_entry.get(f"{p}_score")
            if isinstance(score, (int, float)) and abs(float(score)) > 0.4:
                # 找已有 insight 追加
                existing = next((ins for ins in insights if ins["product"] == p), None)
                if existing:
                    direction = "正面" if float(score) > 0 else "负面"
                    existing.setdefault("items", []).append({
                        "type": "sentiment",
                        "text": f"用户在「{topic}」方面{direction}反馈明显",
                        "icon": "💬",
                    })

    return insights


def build_techstack_data(nodes: list) -> dict:
    """把 TechStack 转成技术项列表。"""
    languages: list[dict] = []
    frameworks: list[dict] = []
    infra: list[dict] = []
    for node in nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        for item in (getattr(node, "languages", None) or []):
            languages.append({"name": item, product: True})
        for item in (getattr(node, "frameworks", None) or []):
            frameworks.append({"name": item, product: True})
        for item in (getattr(node, "infra", None) or []):
            infra.append({"name": item, product: True})
    return {"languages": languages, "frameworks": frameworks, "infra": infra}
