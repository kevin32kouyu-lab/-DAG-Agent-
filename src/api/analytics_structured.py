"""结构化知识图谱节点到图表数据的转换模块。"""

from __future__ import annotations

import json


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
    """把 FeatureNode 合并成功能成熟度矩阵。"""
    products_set: set[str] = set()
    features: list[dict] = []
    for node in nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        feature_name = getattr(node, "feature_name", "") or getattr(node, "name", "") or getattr(node, "label", "")
        category = getattr(node, "category", "") or ""
        maturity = getattr(node, "maturity", "unknown")
        differentiation = getattr(node, "differentiation", "unknown")
        if not feature_name:
            continue
        products_set.add(product)
        features.append({
            "feature_name": feature_name,
            "category": category,
            f"{product}_maturity": maturity,
            f"{product}_differentiation": differentiation,
        })

    merged: dict[str, dict] = {}
    for feature in features:
        feature_name = feature["feature_name"]
        if feature_name not in merged:
            merged[feature_name] = {"feature_name": feature_name, "category": feature["category"]}
        merged[feature_name].update({
            key: value for key, value in feature.items()
            if key not in ("feature_name", "category")
        })

    return {"products": sorted(products_set), "features": list(merged.values())}


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
    return {"products": sorted(products_set), "topics": list(topics.values())}


def build_pricing_data(pricing_nodes: list, model_nodes: list) -> dict:
    """把 PricingData/PricingModel 转成价格和价值评分数据。"""
    plans = []
    for node in pricing_nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        plans.append({
            "plan_name": getattr(node, "plan_name", "") or getattr(node, "label", ""),
            "product": product,
            "price": float(getattr(node, "price", 0) or 0),
            "billing_cycle": getattr(node, "billing_cycle", "") or "",
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
    """把 SWOTNode 转成四象限计数数据。"""
    result = []
    for node in nodes:
        meta = extract_metadata(node)
        product = normalize_product_name(getattr(node, "product", "") or meta.get("product", "") or "Unknown")
        result.append({
            "product": product,
            "strengths_count": len(getattr(node, "strengths", []) or []),
            "weaknesses_count": len(getattr(node, "weaknesses", []) or []),
            "opportunities_count": len(getattr(node, "opportunities", []) or []),
            "threats_count": len(getattr(node, "threats", []) or []),
        })
    return result


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
