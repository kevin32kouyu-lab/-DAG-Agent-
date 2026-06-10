"""构建报告仪表盘数据，关联 report 路由、知识图谱和图表转换模块。"""

from __future__ import annotations

import json
import logging
import os

from src.api.analytics_fallback import (
    build_report_fallback,
    derive_scoring,
    infer_products_from_sections,
    merge_products_from_payload,
    payload_has_chart_data,
    unique_products,
)
from src.api.analytics_structured import (
    belongs_to_task,
    build_feature_data,
    build_insight_data,
    build_pricing_data,
    build_scoring_data,
    build_sentiment_data,
    build_swot_data,
    build_techstack_data,
    extract_metadata,
    normalize_product_name,
)


logger = logging.getLogger(__name__)


def build_analytics_payload(store, scheduler, task_id: str) -> dict:
    """构建图表接口完整响应。"""
    sections = _task_report_sections(store, task_id)
    products = _get_task_products(scheduler, task_id, sections)
    nodes_by_type = {
        node_type: _task_nodes(store, node_type, task_id)
        for node_type in [
            "ScoringNode",
            "FeatureNode",
            "SentimentNode",
            "PricingData",
            "PricingModel",
            "SWOTNode",
            "TechStack",
            "MarketPosition",
        ]
    }

    scoring = build_scoring_data(nodes_by_type["ScoringNode"])
    features = build_feature_data(nodes_by_type["FeatureNode"])
    sentiment = build_sentiment_data(nodes_by_type["SentimentNode"])
    pricing = build_pricing_data(nodes_by_type["PricingData"], nodes_by_type["PricingModel"])
    swot = build_swot_data(nodes_by_type["SWOTNode"])
    tech_stack = build_techstack_data(nodes_by_type["TechStack"])
    market_position = _build_market_position_data(nodes_by_type["MarketPosition"])

    structured_has_data = _has_structured_data(scoring, features, sentiment, pricing, swot, tech_stack)
    warnings: list[str] = []
    data_source = "structured" if structured_has_data else "empty"

    if structured_has_data:
        if not products:
            products = merge_products_from_payload(features, sentiment, pricing, swot, scoring)
        if not scoring:
            scoring = derive_scoring(products, features, sentiment, pricing, swot)
            if scoring:
                warnings.append("当前任务没有结构化评分节点，维度评分由已有结构化数据推断。")
    elif sections:
        fallback = build_report_fallback(products, sections)
        if payload_has_chart_data(fallback):
            features = fallback["features"]
            sentiment = fallback["sentiment"]
            pricing = fallback["pricing"]
            swot = fallback["swot"]
            scoring = fallback["scoring"]
            data_source = "report_fallback"
            warnings.append("部分图表基于报告正文推断，可信度低于结构化节点。")

    if not products:
        products = merge_products_from_payload(features, sentiment, pricing, swot, scoring)
    if data_source == "empty":
        warnings.append("当前任务没有可用的结构化图表数据。")

    # 构建洞察摘要 + 数据来源统计
    insights = build_insight_data(swot, sentiment, features, pricing, products) if swot else []
    source_stats = _build_source_stats(store, task_id)

    return {
        "task_id": task_id,
        "products": products,
        "scoring": scoring,
        "features": features,
        "sentiment": sentiment,
        "pricing": pricing,
        "swot": swot,
        "tech_stack": tech_stack,
        "market_position": market_position,
        "insights": insights,
        "source_stats": source_stats,
        "data_source": data_source,
        "warnings": warnings,
    }


def _has_structured_data(scoring: list, features: dict, sentiment: dict, pricing: dict, swot: list, tech_stack: dict) -> bool:
    """判断当前任务是否已有结构化图表数据。"""
    return any([
        scoring,
        features["features"],
        sentiment["topics"],
        pricing["plans"],
        pricing["value_scores"],
        swot,
        tech_stack["languages"],
        tech_stack["frameworks"],
        tech_stack["infra"],
    ])


def _task_nodes(store, node_type: str, task_id: str) -> list:
    """查询当前任务节点。"""
    return [node for node in store.query_nodes(node_type=node_type) if belongs_to_task(node, task_id)]


def _task_report_sections(store, task_id: str) -> list:
    """查询当前任务报告正文节点。"""
    sections = [
        node for node in store.query_nodes(node_type="ReportSection", layer=3)
        if belongs_to_task(node, task_id)
    ]
    return sorted(sections, key=lambda node: getattr(node, "order", 0))


def _get_task_products(scheduler, task_id: str, sections: list) -> list[str]:
    """按 DAG、落盘记录、报告正文顺序获取产品列表。"""
    products: list[str] = []
    dag = scheduler.get_task_dag(task_id) if scheduler else None
    if dag:
        products.extend(getattr(dag, "targets", []) or [])
        for node in getattr(dag, "nodes", []):
            products.extend(node.input_query.get("targets", []) or [])

    if not products:
        products.extend(_read_task_targets_file(task_id))
    if not products:
        products.extend(infer_products_from_sections(sections))
    return unique_products(products)


def _read_task_targets_file(task_id: str) -> list[str]:
    """从 task_targets.json 恢复产品列表。"""
    path = os.path.join("data", "task_targets.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        return data.get(task_id, []) if isinstance(data, dict) else []
    except Exception as exc:
        logger.warning("任务目标缓存读取失败: task_id=%s, path=%s, reason=%s", task_id, path, exc)
        return []


def _build_source_stats(store, task_id: str) -> dict:
    """统计当前任务的数据来源：网页数量、API 来源、节点类型分布。"""
    all_nodes = store.query_nodes()
    stats = {"total_nodes": 0, "by_layer": {"L1": 0, "L2": 0, "L3": 0}, "details": []}
    for node in all_nodes:
        meta = getattr(node, "metadata", {}) or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if meta.get("task_id") != task_id:
            continue
        stats["total_nodes"] += 1
        layer = getattr(node, "layer", 0)
        layer_key = f"L{layer}" if layer in (1, 2, 3) else "L?"
        stats["by_layer"][layer_key] = stats["by_layer"].get(layer_key, 0) + 1

    # 按节点类型统计
    type_counts: dict[str, int] = {}
    for node in all_nodes:
        if belongs_to_task(node, task_id):
            t = node.node_type.value if hasattr(node.node_type, "value") else str(node.node_type)
            type_counts[t] = type_counts.get(t, 0) + 1
    stats["details"] = [{"type": t, "count": c} for t, c in sorted(type_counts.items(), key=lambda x: -x[1])[:10]]
    return stats


def _build_market_position_data(nodes: list) -> list[dict]:
    """把 MarketPosition 转成定位速览数据。"""
    result = []
    for node in nodes:
        product = normalize_product_name(getattr(node, "product", "") or "Unknown")
        result.append({
            "product": product,
            "positioning": getattr(node, "positioning", "") or "",
            "gtm_strategy": getattr(node, "gtm_strategy", "") or "",
            "target_audience": getattr(node, "target_audience", "") or "",
        })
    return result
