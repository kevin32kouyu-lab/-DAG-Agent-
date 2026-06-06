"""报告正文兜底解析模块，用于缺少结构化节点时生成低可信图表。"""

from __future__ import annotations

import re

from src.api.analytics_structured import normalize_product_name


def infer_products_from_sections(sections: list) -> list[str]:
    """从报告标题和表格头中推断产品名。"""
    text = "\n".join(getattr(section, "content", "") for section in sections)
    products: list[str] = []
    title_match = re.search(r"Competitive Analysis of ([^\n#]+)", text, re.I)
    if title_match:
        products.extend(re.split(r",|\band\b|，|、", title_match.group(1)))
    for table in _extract_tables(text):
        headers = table["headers"]
        if len(headers) > 1:
            products.extend(headers[1:])
    return unique_products(products)


def unique_products(products: list[str]) -> list[str]:
    """产品名去重。"""
    seen = set()
    out = []
    for product in products:
        normalized = normalize_product_name(str(product).strip())
        if normalized and normalized != "Unknown" and normalized.lower() not in seen:
            seen.add(normalized.lower())
            out.append(normalized)
    return out


def build_report_fallback(products: list[str], sections: list) -> dict:
    """从报告正文推断图表数据。"""
    text = "\n".join(getattr(section, "content", "") for section in sections)
    if not text.strip():
        return _empty_fallback()
    tables = _extract_tables(text)
    features = _fallback_features(products, tables)
    pricing = _fallback_pricing(products, tables)
    sentiment = _fallback_sentiment(products, text)
    swot = _fallback_swot(products, text)
    scoring = derive_scoring(products, features, sentiment, pricing, swot)
    return {
        "features": features,
        "pricing": pricing,
        "sentiment": sentiment,
        "swot": swot,
        "scoring": scoring,
    }


def payload_has_chart_data(payload: dict) -> bool:
    """判断兜底结构是否有图表数据。"""
    return bool(
        payload["features"]["features"]
        or payload["pricing"]["plans"]
        or payload["sentiment"]["topics"]
        or payload["swot"]
        or payload["scoring"]
    )


def derive_scoring(products: list[str], features: dict, sentiment: dict, pricing: dict, swot: list[dict]) -> list[dict]:
    """从当前可用图表数据派生雷达评分。"""
    scores: list[dict] = []
    for product in products:
        feature_score = _feature_score(product, features)
        if feature_score is not None:
            scores.append(_score_row(product, "features", feature_score))
        price_score = _pricing_score(product, pricing)
        if price_score is not None:
            scores.append(_score_row(product, "pricing", price_score))
        sentiment_score = _sentiment_score(product, sentiment)
        if sentiment_score is not None:
            scores.append(_score_row(product, "sentiment", sentiment_score))
        swot_score = _swot_score(product, swot)
        if swot_score is not None:
            scores.append(_score_row(product, "swot", swot_score))
    return scores


def merge_products_from_payload(features: dict, sentiment: dict, pricing: dict, swot: list, scoring: list) -> list[str]:
    """从图表数据里补齐产品列表。"""
    products: list[str] = []
    products.extend(features.get("products", []))
    products.extend(sentiment.get("products", []))
    products.extend(row.get("product", "") for row in pricing.get("plans", []))
    products.extend(row.get("product", "") for row in pricing.get("value_scores", []))
    products.extend(row.get("product", "") for row in swot)
    products.extend(row.get("product", "") for row in scoring)
    return unique_products(products)


def _empty_fallback() -> dict:
    """生成空兜底结构。"""
    return {
        "features": {"products": [], "features": []},
        "pricing": {"plans": [], "value_scores": []},
        "sentiment": {"products": [], "topics": []},
        "swot": [],
        "scoring": [],
    }


def _extract_tables(text: str) -> list[dict]:
    """提取 Markdown 表格及其前置标题。"""
    tables = []
    lines = text.splitlines()
    heading = ""
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            heading = heading_match.group(2).strip()
            i += 1
            continue
        if _is_table_row(stripped) and i + 1 < len(lines) and _is_separator_row(lines[i + 1].strip()):
            rows = [stripped]
            i += 2
            while i < len(lines) and _is_table_row(lines[i].strip()):
                rows.append(lines[i].strip())
                i += 1
            headers = _split_table_row(rows[0])
            body = [_split_table_row(row) for row in rows[1:]]
            tables.append({"heading": heading, "headers": headers, "rows": body})
            continue
        i += 1
    return tables


def _is_table_row(line: str) -> bool:
    """判断是否为 Markdown 表格行。"""
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_separator_row(line: str) -> bool:
    """判断是否为 Markdown 表格分隔行。"""
    if not _is_table_row(line):
        return False
    cells = _split_table_row(line)
    return bool(cells) and all(re.match(r"^:?-{3,}:?$", cell.strip()) for cell in cells)


def _split_table_row(line: str) -> list[str]:
    """拆分 Markdown 表格行。"""
    return [_strip_inline_markers(cell.strip()) for cell in line.strip().strip("|").split("|")]


def _strip_inline_markers(text: str) -> str:
    """去掉常见 Markdown 内联标记。"""
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def _fallback_features(products: list[str], tables: list[dict]) -> dict:
    """从功能表格推断功能矩阵。"""
    selected = [table for table in tables if _contains_any(table["heading"], ["feature", "功能"])]
    features: list[dict] = []
    products_set: set[str] = set()
    for table in selected:
        headers = table["headers"]
        if len(headers) < 2:
            continue
        table_products = _match_products(headers[1:], products)
        for row in table["rows"]:
            if len(row) < 2:
                continue
            item = {"feature_name": row[0], "category": "Report"}
            for idx, product in table_products:
                val = row[idx] if idx < len(row) else ""
                maturity, differentiation = _map_feature_value(val)
                item[f"{product}_maturity"] = maturity
                item[f"{product}_differentiation"] = differentiation
                products_set.add(product)
            features.append(item)
    return {"products": sorted(products_set), "features": features}


def _map_feature_value(value: str) -> tuple[str, str]:
    """把报告单元格文字映射为功能状态。"""
    lower = value.lower()
    if any(key in lower for key in ["advantage", "优势"]):
        return "ga", "advantage"
    if any(key in lower for key in ["parity", "持平"]):
        return "ga", "parity"
    if any(key in lower for key in ["disadvantage", "劣势", "n/a", "无"]):
        return "unknown", "disadvantage"
    return "unknown", "unknown"


def _fallback_pricing(products: list[str], tables: list[dict]) -> dict:
    """从定价表格推断价格数据。"""
    selected = [table for table in tables if _contains_any(table["heading"], ["pricing", "定价", "price"])]
    plans: list[dict] = []
    value_scores: dict[str, float] = {}
    for table in selected:
        headers = table["headers"]
        if len(headers) < 2:
            continue
        table_products = _match_products(headers[1:], products)
        for row in table["rows"]:
            if len(row) < 2:
                continue
            plan_name = row[0]
            for idx, product in table_products:
                cell = row[idx] if idx < len(row) else ""
                parsed = _parse_price(cell)
                if parsed is None:
                    continue
                price, billing_cycle = parsed
                plans.append({
                    "plan_name": plan_name,
                    "product": product,
                    "price": price,
                    "billing_cycle": billing_cycle,
                })
                current = value_scores.get(product, 0.5)
                value_scores[product] = max(current, _estimate_value_score(price))
    return {
        "plans": plans,
        "value_scores": [
            {
                "product": product,
                "value_score": round(value_score, 3),
                "strategy": "report-inferred",
                "target_segment": "",
            }
            for product, value_score in value_scores.items()
        ],
    }


def _parse_price(text: str) -> tuple[float, str] | None:
    """解析价格单元格。"""
    lower = text.lower()
    if any(key in lower for key in ["custom", "n/a", "无", "enterprise"]):
        return None
    if any(key in lower for key in ["free", "免费"]):
        return 0.0, "monthly"
    match = re.search(r"[$￥¥]\s?([0-9]+(?:\.[0-9]+)?)", text)
    if not match:
        return None
    price = float(match.group(1))
    billing_cycle = "yearly" if any(key in lower for key in ["year", "annual", "yr", "年"]) else "monthly"
    return price, billing_cycle


def _estimate_value_score(price: float) -> float:
    """根据价格粗略估算价值评分。"""
    if price <= 0:
        return 0.75
    if price <= 15:
        return 0.7
    if price <= 50:
        return 0.6
    return 0.5


def _fallback_sentiment(products: list[str], text: str) -> dict:
    """从正文里提取情感分。"""
    row = {"topic": "overall"}
    found: list[str] = []
    for product in products:
        pattern = re.compile(
            rf"{re.escape(product)}[\s\S]{{0,80}}sentiment(?: score)?[^\d-]*(-?\d+(?:\.\d+)?)",
            re.I,
        )
        match = pattern.search(text)
        if match:
            row[f"{product}_score"] = round(float(match.group(1)), 3)
            row[f"{product}_trend"] = "stable"
            found.append(product)
    return {"products": found, "topics": [row] if found else []}


def _fallback_swot(products: list[str], text: str) -> list[dict]:
    """从 SWOT 正文提取四象限数量。"""
    swot_match = re.search(r"##\s+.*?(SWOT|优势|劣势)[\s\S]*", text, re.I)
    if not swot_match:
        return []
    swot_text = swot_match.group(0)
    result = []
    for product in products:
        section_match = re.search(rf"###\s+{re.escape(product)}\s*([\s\S]*?)(?=\n###\s+|\Z)", swot_text, re.I)
        if not section_match:
            continue
        body = section_match.group(1)
        result.append({
            "product": product,
            "strengths_count": _count_labeled_items(body, ["strengths", "优势"]),
            "weaknesses_count": _count_labeled_items(body, ["weaknesses", "劣势"]),
            "opportunities_count": _count_labeled_items(body, ["opportunities", "机会"]),
            "threats_count": _count_labeled_items(body, ["threats", "威胁"]),
        })
    return result


def _count_labeled_items(text: str, labels: list[str]) -> int:
    """统计带标签列表的条目数。"""
    for label in labels:
        match = re.search(rf"\*\*{label}\s*:\*\*\s*([^\n]+)", text, re.I)
        if match:
            items = [item.strip() for item in re.split(r",|，|、|;", match.group(1)) if item.strip()]
            return len(items)
    return 0


def _score_row(product: str, dimension: str, score: float) -> dict:
    """生成单条评分。"""
    return {
        "product": product,
        "dimension": dimension,
        "score": round(max(0.0, min(1.0, score)), 3),
        "weight": 1.0,
    }


def _feature_score(product: str, features: dict) -> float | None:
    """计算功能评分。"""
    vals = [str(feature.get(f"{product}_differentiation", "")).lower() for feature in features.get("features", [])]
    vals = [value for value in vals if value]
    if not vals:
        return None
    weights = {"advantage": 1.0, "parity": 0.65, "disadvantage": 0.25, "unique": 1.0}
    return sum(weights.get(value, 0.45) for value in vals) / len(vals)


def _pricing_score(product: str, pricing: dict) -> float | None:
    """计算定价评分。"""
    for row in pricing.get("value_scores", []):
        if row.get("product") == product:
            return float(row.get("value_score", 0))
    prices = [plan["price"] for plan in pricing.get("plans", []) if plan.get("product") == product]
    return _estimate_value_score(min(prices)) if prices else None


def _sentiment_score(product: str, sentiment: dict) -> float | None:
    """计算情感评分。"""
    vals = []
    for topic in sentiment.get("topics", []):
        val = topic.get(f"{product}_score")
        if isinstance(val, (int, float)):
            score = float(val)
            vals.append((score + 1) / 2 if -1 <= score <= 1 else score)
    return sum(vals) / len(vals) if vals else None


def _swot_score(product: str, swot: list[dict]) -> float | None:
    """计算 SWOT 评分。"""
    for row in swot:
        if row.get("product") != product:
            continue
        positive = row.get("strengths_count", 0) + row.get("opportunities_count", 0)
        negative = row.get("weaknesses_count", 0) + row.get("threats_count", 0)
        total = positive + negative
        return positive / total if total else None
    return None


def _match_products(headers: list[str], products: list[str]) -> list[tuple[int, str]]:
    """把表头列匹配到产品名。"""
    matched = []
    product_keys = {product.lower() for product in products}
    for idx, header in enumerate(headers, start=1):
        normalized = normalize_product_name(header)
        if not products or normalized.lower() in product_keys:
            matched.append((idx, normalized))
    return matched


def _contains_any(text: str, needles: list[str]) -> bool:
    """大小写不敏感包含判断。"""
    lower = text.lower()
    return any(needle.lower() in lower for needle in needles)
