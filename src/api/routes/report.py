import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from src.api.deps import get_store, get_gateway, get_scheduler
from src.dag.models import NodeState

router = APIRouter()

# Chinese font path — falls back to built-in on non-Windows
import platform
import os

_CHINESE_FONT_PATH = None
if platform.system() == "Windows":
    for candidate in [
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
    ]:
        if os.path.exists(candidate):
            _CHINESE_FONT_PATH = candidate
            break


async def _translate_sections(sections: list[dict]) -> list[dict]:
    """将报告章节从中文翻译为英文，保留 markdown 结构。"""
    import logging
    logger = logging.getLogger(__name__)
    gateway = get_gateway()

    translated: list[dict] = []
    for s in sections:
        cn_content = s.get("content", "")
        cn_section = s.get("section", "")
        if not cn_content.strip():
            translated.append({**s, "section": cn_section, "content": cn_content})
            continue

        prompt = (
            "Translate the following Chinese competitive analysis report section to English. "
            "Preserve all markdown formatting (headings, lists, bold, tables, etc.). "
            "Keep all product names, technical terms, and numbers exactly as-is. "
            "Only translate the text, do not add or remove content.\n\n"
            f"## {cn_section}\n\n{cn_content}"
        )

        try:
            resp = await gateway.chat(
                system="You are a professional translator. Translate Chinese to English accurately while preserving markdown formatting.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="analysis",
                max_tokens=4096,
                temperature=0.2,
            )
            en_content = resp.content

            # 从翻译结果中提取英文 section 名称（首行 ## heading）
            en_section = cn_section
            lines = en_content.strip().split("\n")
            if lines:
                first = lines[0].strip()
                if first.startswith("## "):
                    en_section = first[3:].strip()
                    lines.pop(0)
                    if lines and not lines[0].strip():
                        lines.pop(0)
                    en_content = "\n".join(lines)
        except Exception as e:
            logger.warning(f"translation failed for section '{cn_section}': {e}")
            en_content = cn_content

        translated.append({**s, "section": en_section, "content": en_content.strip()})

    return translated


def _build_pdf(task_id: str, sections: list[dict]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # register Chinese font if available
    font_name = "Helvetica"
    if _CHINESE_FONT_PATH:
        try:
            pdf.add_font("CJK", "", _CHINESE_FONT_PATH)
            pdf.add_font("CJK", "B", _CHINESE_FONT_PATH)
            font_name = "CJK"
        except Exception:
            pass

    # ── cover page ──
    pdf.add_page()
    pdf.ln(60)
    if font_name == "CJK":
        pdf.set_font("CJK", "B", 28)
        pdf.cell(0, 14, "竞品分析报告", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("CJK", "", 12)
        pdf.ln(8)
        pdf.cell(0, 8, f"Report ID: {task_id}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 8, f"生成日期: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.cell(0, 8, f"共 {len(sections)} 个章节", align="C", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("Helvetica", "B", 24)
        pdf.cell(0, 14, "Competitive Analysis Report", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(8)
        pdf.cell(0, 8, f"Report ID: {task_id}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.cell(0, 8, f"Sections: {len(sections)}", align="C", new_x="LMARGIN", new_y="NEXT")

    # ── table of contents ──
    pdf.ln(12)
    if font_name == "CJK":
        pdf.set_font("CJK", "B", 14)
        pdf.cell(0, 10, "目  录", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.set_font("CJK", "", 11)
    else:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Contents", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)
        pdf.set_font("Helvetica", "", 11)

    for i, s in enumerate(sections):
        title = s.get("section", f"Section {i}")
        # sanitize: truncate long titles
        display_title = title[:60] + ("..." if len(title) > 60 else "")
        pdf.cell(0, 7, f"{i + 1}.  {display_title}", new_x="LMARGIN", new_y="NEXT")

    # ── section content ──
    for i, s in enumerate(sections):
        pdf.add_page()
        title = s.get("section", f"Section {i}")
        content = s.get("content", "")

        if font_name == "CJK":
            pdf.set_font("CJK", "B", 14)
        else:
            pdf.set_font("Helvetica", "B", 14)

        pdf.multi_cell(0, 8, title)

        pdf.ln(4)
        # separator
        pdf.ln(2)

        if font_name == "CJK":
            pdf.set_font("CJK", "", 10.5)
        else:
            pdf.set_font("Helvetica", "", 10)

        # split content into paragraphs and render
        for para in content.split("\n"):
            para = para.strip()
            if not para:
                pdf.ln(3)
                continue
            # handle potential markdown heading leftovers
            if para.startswith("### "):
                if font_name == "CJK":
                    pdf.set_font("CJK", "B", 11)
                else:
                    pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(0, 6.5, para[4:])
                if font_name == "CJK":
                    pdf.set_font("CJK", "", 10.5)
                else:
                    pdf.set_font("Helvetica", "", 10)
            elif para.startswith("## "):
                if font_name == "CJK":
                    pdf.set_font("CJK", "B", 12)
                else:
                    pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(0, 7, para[3:])
                if font_name == "CJK":
                    pdf.set_font("CJK", "", 10.5)
                else:
                    pdf.set_font("Helvetica", "", 10)
            elif para.startswith("- ") or para.startswith("* "):
                pdf.multi_cell(0, 6, f"  • {para[2:]}")
            else:
                pdf.multi_cell(0, 6, para)

    return bytes(pdf.output())


def _extract_metadata(node) -> dict:
    metadata = getattr(node, "metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return metadata or {}


def _layer1_report_sections(store, task_id: str) -> list[dict]:
    """Primary: read ReportSection nodes from the knowledge graph."""
    all_sections = store.query_nodes(node_type="ReportSection", layer=3)
    sections = []
    for s in all_sections:
        node_id = getattr(s, "id", "")
        metadata = _extract_metadata(s)
        if not metadata or metadata.get("task_id") != task_id:
            continue
        sections.append({
            "node_id": node_id,
            "section": getattr(s, "section", ""),
            "content": getattr(s, "content", ""),
            "order": getattr(s, "order", 0),
        })
    sections.sort(key=lambda x: x["order"])
    return sections


def _layer2_report_generator_output(scheduler, task_id: str) -> list[dict] | None:
    """Fallback 1: ReportGenerator completed but didn't persist to graph."""
    dag = scheduler.get_task_dag(task_id)
    if not dag:
        return None
    rg_nodes = [n for n in dag.nodes if n.agent_type == "ReportGenerator"]
    if not rg_nodes:
        return None
    rg = rg_nodes[0]
    if rg.state == NodeState.FAILED:
        error_msg = rg.context.get("error", "")
        return [{"node_id": "error", "section": "报告生成失败",
                 "content": f"ReportGenerator agent 执行失败: {error_msg}", "order": 0}]
    output_data = rg.context.get("_output_data", {})
    if not isinstance(output_data, dict):
        return None
    report_md = output_data.get("report_markdown", "")
    sections_data = output_data.get("sections", [])
    if report_md:
        return [{"node_id": "rg_output", "section": "完整报告",
                 "content": report_md, "order": 0}]
    if sections_data:
        return sections_data
    return None


def _layer3_assembled_report(scheduler, task_id: str) -> list[dict]:
    """Fallback 2: assemble partial report from all completed agent outputs."""
    dag = scheduler.get_task_dag(task_id)
    if not dag:
        return None
    parts: list[dict] = []
    missing_dimensions: list[str] = []
    order = 0

    for node in sorted(dag.nodes, key=lambda n: n.node_id):
        if node.state != NodeState.COMPLETED:
            if node.agent_type not in ("ReportGenerator", "QA_FactCheck", "QA_LogicCheck",
                                        "Orchestrator", "SourceDiscovery", "Collector",
                                        "DataEnricher"):
                missing_dimensions.append(node.agent_type)
            continue
        output_data = node.context.get("_output_data", {})
        summary = ""
        if isinstance(output_data, dict):
            summary = output_data.get("summary", "") or json.dumps(output_data, default=str)
        elif output_data:
            summary = str(output_data)
        if summary and len(summary) > 20:
            parts.append({
                "node_id": node.node_id,
                "section": f"{node.agent_type} 分析结果",
                "content": summary,
                "order": order,
            })
            order += 1

    if not parts:
        return None

    header = "## 部分报告（自动拼接）\n\n"
    header += f"> 以下维度缺失或未完成: {', '.join(missing_dimensions) if missing_dimensions else '无'}\n\n"
    header += "---\n\n"
    parts.insert(0, {"node_id": "header", "section": "报告状态",
                      "content": header.strip(), "order": -1})
    return parts


def _layer4_error_state(scheduler, task_id: str) -> list[dict]:
    """Fallback 3: no data anywhere — return error with current task state."""
    dag = scheduler.get_task_dag(task_id)
    if not dag:
        return [{"node_id": "not_found", "section": "任务未找到",
                 "content": f"任务 {task_id} 不存在或尚未创建。", "order": 0}]
    states = {}
    for n in dag.nodes:
        states.setdefault(n.state.value, []).append(n.agent_type)
    state_desc = ", ".join(f"{st}: {', '.join(agents)}" for st, agents in states.items())
    has_rg = any(n.agent_type == "ReportGenerator" for n in dag.nodes)
    msg = f"报告尚未生成。当前 DAG 状态: {state_desc}。"
    if not has_rg:
        msg += " DAG 中缺少 ReportGenerator 节点，请联系管理员检查 Orchestrator 配置。"
    return [{"node_id": "error", "section": "报告未就绪", "content": msg, "order": 0}]


def _resolve_sections(task_id: str) -> list[dict]:
    """Run the 4-layer resolution pipeline; always returns a list."""
    store = get_store()
    scheduler = get_scheduler()

    sections = _layer1_report_sections(store, task_id)
    if not sections:
        sections = _layer2_report_generator_output(scheduler, task_id)
    if not sections:
        sections = _layer3_assembled_report(scheduler, task_id)
    if not sections:
        sections = _layer4_error_state(scheduler, task_id)
    return sections


@router.get("/report/{task_id}")
async def get_report(task_id: str, format: str = Query("markdown"), lang: str = Query("zh")):
    sections = _resolve_sections(task_id)

    # 翻译为英文
    if lang == "en":
        sections = await _translate_sections(sections)

    if format == "json":
        return {"task_id": task_id, "format": "json", "sections": sections, "lang": lang}

    if format == "pdf":
        try:
            pdf_bytes = _build_pdf(task_id, sections)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="competitive-analysis-{task_id}.pdf"',
                    "Content-Length": str(len(pdf_bytes)),
                },
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"PDF 生成失败: {e}")

    # default: markdown
    md = "\n\n".join(f"## {s['section']}\n\n{s['content']}" for s in sections)
    return {"task_id": task_id, "format": "markdown", "content": md, "sections": sections, "lang": lang}


# ── Analytics endpoint ────────────────────────────────────────────


def _get_task_products(task_id: str) -> list[str]:
    """Extract target products from the DAG input query."""
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag:
        for node in dag.nodes:
            targets = node.input_query.get("targets", [])
            if targets:
                return targets
    return []


def _belongs_to_task(node, task_id: str, products: list[str]) -> bool:
    """Check if a knowledge graph node belongs to this task."""
    meta = _extract_metadata(node)
    if meta.get("task_id") == task_id:
        return True
    product = getattr(node, "product", "") or meta.get("product", "")
    if product and products:
        for t in products:
            if t.lower() in product.lower() or product.lower() in t.lower():
                return True
    return False


def _build_scoring_data(nodes: list) -> list[dict]:
    result = []
    for n in nodes:
        meta = _extract_metadata(n)
        product = getattr(n, "product", "") or meta.get("product", "") or "Unknown"
        dimension = getattr(n, "dimension", "") or ""
        score = getattr(n, "score", None)
        weight = getattr(n, "weight", 1.0)
        if score is not None:
            result.append({
                "product": product,
                "dimension": dimension,
                "score": float(score),
                "weight": float(weight),
            })
    return result


def _build_feature_data(nodes: list) -> dict:
    products_set: set[str] = set()
    features: list[dict] = []

    for n in nodes:
        meta = _extract_metadata(n)
        product = getattr(n, "product", "") or meta.get("product", "") or "Unknown"
        feature_name = getattr(n, "feature_name", "") or getattr(n, "label", "")
        category = getattr(n, "category", "") or ""
        maturity = getattr(n, "maturity", "unknown")
        differentiation = getattr(n, "differentiation", "unknown")

        if not feature_name:
            continue
        products_set.add(product)
        key_base = product
        features.append({
            "feature_name": feature_name,
            "category": category,
            f"{key_base}_maturity": maturity,
            f"{key_base}_differentiation": differentiation,
        })

    # merge same feature_name across products
    merged: dict[str, dict] = {}
    for f in features:
        fn = f["feature_name"]
        if fn not in merged:
            merged[fn] = {"feature_name": fn, "category": f["category"]}
        merged[fn].update({k: v for k, v in f.items() if k not in ("feature_name", "category")})

    return {
        "products": sorted(products_set),
        "features": list(merged.values()),
    }


def _build_sentiment_data(nodes: list) -> dict:
    products_set: set[str] = set()
    topics: dict[str, dict] = {}

    for n in nodes:
        meta = _extract_metadata(n)
        product = getattr(n, "product", "") or meta.get("product", "") or "Unknown"
        topic = getattr(n, "topic", "") or getattr(n, "label", "")
        sentiment_score = getattr(n, "sentiment_score", None)
        trend = getattr(n, "trend", "stable")

        if not topic or sentiment_score is None:
            continue
        products_set.add(product)
        if topic not in topics:
            topics[topic] = {"topic": topic}
        topics[topic][f"{product}_score"] = round(float(sentiment_score), 3)
        topics[topic][f"{product}_trend"] = trend

    return {
        "products": sorted(products_set),
        "topics": list(topics.values()),
    }


def _build_pricing_data(pricing_nodes: list, model_nodes: list) -> dict:
    plans = []
    for n in pricing_nodes:
        meta = _extract_metadata(n)
        product = getattr(n, "product", "") or meta.get("product", "") or "Unknown"
        plans.append({
            "plan_name": getattr(n, "plan_name", "") or getattr(n, "label", ""),
            "product": product,
            "price": float(getattr(n, "price", 0) or 0),
            "billing_cycle": getattr(n, "billing_cycle", "") or "",
        })

    value_scores = []
    for n in model_nodes:
        meta = _extract_metadata(n)
        product = getattr(n, "product", "") or meta.get("product", "") or "Unknown"
        vs = getattr(n, "value_score", None)
        if vs is not None:
            value_scores.append({
                "product": product,
                "value_score": round(float(vs), 3),
                "strategy": getattr(n, "strategy", "") or "",
                "target_segment": getattr(n, "target_segment", "") or "",
            })

    return {"plans": plans, "value_scores": value_scores}


def _build_swot_data(nodes: list) -> list[dict]:
    result = []
    for n in nodes:
        meta = _extract_metadata(n)
        product = getattr(n, "product", "") or meta.get("product", "") or "Unknown"
        result.append({
            "product": product,
            "strengths_count": len(getattr(n, "strengths", []) or []),
            "weaknesses_count": len(getattr(n, "weaknesses", []) or []),
            "opportunities_count": len(getattr(n, "opportunities", []) or []),
            "threats_count": len(getattr(n, "threats", []) or []),
        })
    return result


def _build_techstack_data(nodes: list) -> dict:
    languages: list[dict] = []
    frameworks: list[dict] = []
    infra: list[dict] = []

    for n in nodes:
        meta = _extract_metadata(n)
        product = getattr(n, "product", "") or meta.get("product", "") or "Unknown"
        for item in (getattr(n, "languages", None) or []):
            languages.append({"name": item, product: True})
        for item in (getattr(n, "frameworks", None) or []):
            frameworks.append({"name": item, product: True})
        for item in (getattr(n, "infra", None) or []):
            infra.append({"name": item, product: True})

    return {
        "languages": languages,
        "frameworks": frameworks,
        "infra": infra,
    }


@router.get("/report/{task_id}/analytics")
async def get_report_analytics(task_id: str):
    """Returns chart-ready structured metrics for the task."""
    store = get_store()
    products = _get_task_products(task_id)

    node_types = ["ScoringNode", "FeatureNode", "SentimentNode",
                  "PricingData", "PricingModel", "SWOTNode", "TechStack"]
    all_by_type: dict[str, list] = {}
    for ntype in node_types:
        all_by_type[ntype] = store.query_nodes(node_type=ntype)

    def filt(nodes):
        return [n for n in nodes if _belongs_to_task(n, task_id, products)]

    scoring = filt(all_by_type.get("ScoringNode", []))
    features = filt(all_by_type.get("FeatureNode", []))
    sentiment = filt(all_by_type.get("SentimentNode", []))
    pricing_data = filt(all_by_type.get("PricingData", []))
    pricing_model = filt(all_by_type.get("PricingModel", []))
    swot = filt(all_by_type.get("SWOTNode", []))
    tech_stack = filt(all_by_type.get("TechStack", []))

    return {
        "task_id": task_id,
        "products": products,
        "scoring": _build_scoring_data(scoring),
        "features": _build_feature_data(features),
        "sentiment": _build_sentiment_data(sentiment),
        "pricing": _build_pricing_data(pricing_data, pricing_model),
        "swot": _build_swot_data(swot),
        "tech_stack": _build_techstack_data(tech_stack),
    }
