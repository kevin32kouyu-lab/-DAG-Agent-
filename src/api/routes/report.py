import json

from fastapi import APIRouter, HTTPException, Query
from src.api.deps import get_store

router = APIRouter()


@router.get("/report/{task_id}")
async def get_report(task_id: str, format: str = Query("markdown")):
    store = get_store()
    all_sections = store.query_nodes(node_type="ReportSection", layer=3)
    sections = []
    for s in all_sections:
        node_id = getattr(s, "id", "")
        metadata = getattr(s, "metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        if metadata and metadata.get("task_id") != task_id:
            continue
        sections.append({
            "node_id": node_id,
            "section": getattr(s, "section", ""),
            "content": getattr(s, "content", ""),
            "order": getattr(s, "order", 0),
        })
    sections.sort(key=lambda x: x["order"])

    # Fallback: if no ReportSection nodes found, try Writer's node context output
    if not sections:
        from src.api.deps import get_scheduler
        scheduler = get_scheduler()
        dag = scheduler.get_task_dag(task_id)
        if dag:
            writer_nodes = [n for n in dag.nodes if n.agent_type == "Writer"]
            if writer_nodes:
                writer_node = writer_nodes[0]
                output_data = writer_node.context.get("_output_data", {})
                writer_state = writer_node.state
                # If Writer has report_markdown in its output, use it directly
                report_md = output_data.get("report_markdown", "") if isinstance(output_data, dict) else ""
                if not report_md:
                    report_md = str(output_data) if output_data else ""
                if report_md:
                    sections = [{"node_id": "writer_output", "section": "完整报告", "content": report_md, "order": 0}]
                elif writer_state == "failed":
                    error_msg = writer_node.context.get("error", "未知错误")
                    sections = [{"node_id": "error", "section": "报告生成失败", "content": f"Writer agent 执行失败: {error_msg}", "order": 0}]
                else:
                    sections = [{"node_id": "pending", "section": "报告生成中", "content": f"Writer agent 状态: {writer_state}", "order": 0}]

    # backward compat for mock data (no task_id filter matched, no scheduler)
    if not sections:
        for s in all_sections:
            sections.append({
                "node_id": getattr(s, "id", ""),
                "section": getattr(s, "section", ""),
                "content": getattr(s, "content", ""),
                "order": getattr(s, "order", 0),
            })
        sections.sort(key=lambda x: x["order"])

    if format == "json":
        return {"task_id": task_id, "format": "json", "sections": sections}
    md = "\n\n".join(f"## {s['section']}\n\n{s['content']}" for s in sections)
    return {"task_id": task_id, "format": "markdown", "content": md, "sections": sections}
