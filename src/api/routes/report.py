import json
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from src.api import analytics_builder
from src.api.deps import get_store, get_gateway, get_scheduler
from src.api.report_pdf import build_pdf
from src.dag.models import NodeState

router = APIRouter()
logger = logging.getLogger(__name__)


def _detect_language(text: str) -> str:
    """简单语言检测：统计 CJK 字符比例。"""
    if not text:
        return "en"
    cjk = sum(1 for c in text if '一' <= c <= '鿿' or '぀' <= c <= 'ヿ')
    return "zh" if cjk > len(text.replace(' ', '')) * 0.08 else "en"


def _first_section_content(sections: list[dict]) -> str:
    for s in sections:
        c = s.get("content", "")
        if c.strip():
            return c
    return ""


async def _translate_sections_impl(sections: list[dict], direction: str) -> list[dict]:
    """翻译报告章节，保留 markdown 结构。direction: 'zh2en' | 'en2zh'"""
    import logging
    logger = logging.getLogger(__name__)
    gateway = get_gateway()

    if direction == "zh2en":
        system_prompt = "You are a professional translator. Translate Chinese to English accurately while preserving markdown formatting."
        prompt_prefix = (
            "Translate the following Chinese competitive analysis report section to English. "
            "Preserve all markdown formatting (headings, lists, bold, tables, etc.). "
            "Keep all product names, technical terms, and numbers exactly as-is. "
            "Only translate the text, do not add or remove content.\n\n"
        )
    else:
        system_prompt = "You are a professional translator. Translate English to Chinese accurately while preserving markdown formatting."
        prompt_prefix = (
            "Translate the following English competitive analysis report section to Chinese. "
            "Preserve all markdown formatting (headings, lists, bold, tables, etc.). "
            "Keep all product names, technical terms, and numbers exactly as-is. "
            "Only translate the text, do not add or remove content.\n\n"
        )

    translated: list[dict] = []
    for s in sections:
        src_content = s.get("content", "")
        src_section = s.get("section", "")
        if not src_content.strip():
            translated.append({**s, "section": src_section, "content": src_content})
            continue

        prompt = prompt_prefix + f"## {src_section}\n\n{src_content}"

        try:
            resp = await gateway.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                model_tier="analysis",
                max_tokens=4096,
                temperature=0.2,
            )
            out_content = resp.content

            out_section = src_section
            lines = out_content.strip().split("\n")
            if lines:
                first = lines[0].strip()
                if first.startswith("## "):
                    out_section = first[3:].strip()
                    lines.pop(0)
                    if lines and not lines[0].strip():
                        lines.pop(0)
                    out_content = "\n".join(lines)
        except Exception as e:
            logger.warning(f"translation failed for section '{src_section}': {e}")
            out_content = src_content

        translated.append({**s, "section": out_section, "content": out_content.strip()})

    return translated


def _extract_metadata(node) -> dict:
    metadata = getattr(node, "metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return metadata or {}


def _collect_evidence_sources(store, node_id: str, max_depth: int) -> list[dict]:
    """读取节点的上游一层证据来源，失败时记录日志并返回空列表。"""
    evidence_chain = []
    try:
        edges = store.trace_upstream(node_id, max_depth=max_depth)
        source_ids = {edge.target_id for edge in edges}
        for source_id in source_ids:
            src_node = store.get_node(source_id)
            if src_node and src_node.layer == 1:
                evidence_chain.append({
                    "id": src_node.id,
                    "node_type": src_node.node_type.value if hasattr(src_node.node_type, "value") else str(src_node.node_type),
                    "url": getattr(src_node, "url", ""),
                    "title": getattr(src_node, "title", getattr(src_node, "label", "Source Info")),
                })
    except Exception as exc:
        logger.warning("证据链读取失败: node_id=%s, reason=%s", node_id, exc)
    return evidence_chain


def _layer1_report_sections(store, task_id: str) -> list[dict]:
    """Primary: read ReportSection nodes from the knowledge graph (dedup by section name)."""
    all_sections = store.query_nodes(node_type="ReportSection", layer=3)
    sections: list[dict] = []
    seen: set[str] = set()
    for s in all_sections:
        node_id = getattr(s, "id", "")
        metadata = _extract_metadata(s)
        if not metadata or metadata.get("task_id") != task_id:
            continue
        sec_name = getattr(s, "section", "")
        content = getattr(s, "content", "")
        # 按 section 名 + content 前 80 字符去重，防止指数级重复节点
        dedup_key = f"{sec_name}|{content[:80]}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        evidence_chain = _collect_evidence_sources(store, node_id, max_depth=5)

        sections.append({
            "node_id": node_id,
            "section": sec_name,
            "content": content,
            "order": getattr(s, "order", 0),
            "evidence_sources": evidence_chain,
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
                 "content": report_md, "order": 0, "evidence_sources": []}]
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
    store = get_store()

    # 基础节点不需要作为报告章节展示，ReportGenerator 由 layer 2 处理
    skip_types = {"ReportGenerator", "Orchestrator", "SourceDiscovery", "Collector", "DataEnricher"}

    for node in sorted(dag.nodes, key=lambda n: n.node_id):
        if node.state != NodeState.COMPLETED:
            if node.agent_type not in skip_types.union({"QA_FactCheck", "QA_LogicCheck"}):
                missing_dimensions.append(node.agent_type)
            continue
        if node.agent_type in skip_types:
            continue
        output_data = node.context.get("_output_data", {})
        summary = ""
        if isinstance(output_data, dict):
            summary = output_data.get("summary", "") or json.dumps(output_data, default=str)
        elif output_data:
            summary = str(output_data)

        evidence_chain = _collect_evidence_sources(store, node.node_id, max_depth=4)

        if summary and len(summary) > 20:
            parts.append({
                "node_id": node.node_id,
                "section": f"{node.agent_type} 分析结果",
                "content": summary,
                "order": order,
                "evidence_sources": evidence_chain,
            })
            order += 1

    if not parts:
        return None

    header = "## 部分报告（自动拼接）\n\n"
    header += f"> 以下维度缺失或未完成: {', '.join(missing_dimensions) if missing_dimensions else '无'}\n\n"
    header += "---\n\n"
    parts.insert(0, {"node_id": "header", "section": "报告状态",
                      "content": header.strip(), "order": -1, "evidence_sources": []})
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

    # 按需双向翻译：检测内容语言，仅在需要时翻译
    sample = _first_section_content(sections)
    content_lang = _detect_language(sample)
    if lang == "zh" and content_lang == "en":
        sections = await _translate_sections_impl(sections, "en2zh")
    elif lang == "en" and content_lang == "zh":
        sections = await _translate_sections_impl(sections, "zh2en")

    if format == "json":
        return {"task_id": task_id, "format": "json", "sections": sections, "lang": lang}

    if format == "pdf":
        try:
            pdf_bytes = build_pdf(task_id, sections)
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


@router.get("/report/{task_id}/analytics")
async def get_report_analytics(task_id: str):
    """Returns chart-ready structured metrics for the task."""
    store = get_store()
    scheduler = get_scheduler()
    return analytics_builder.build_analytics_payload(store, scheduler, task_id)
