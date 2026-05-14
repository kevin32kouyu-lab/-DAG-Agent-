from fastapi import APIRouter, HTTPException
from src.api.deps import get_store

router = APIRouter()


@router.get("/report/{task_id}")
async def get_report(task_id: str, format: str = "markdown"):
    store = get_store()
    all_sections = store.query_nodes(node_type="ReportSection", layer=3)
    sections = []
    for s in all_sections:
        sections.append({
            "section": getattr(s, "section", ""),
            "content": getattr(s, "content", ""),
            "order": getattr(s, "order", 0),
        })
    sections.sort(key=lambda x: x["order"])
    if format == "json":
        return {"task_id": task_id, "format": "json", "sections": sections}
    md = "\n\n".join(f"## {s['section']}\n\n{s['content']}" for s in sections)
    return {"task_id": task_id, "format": "markdown", "content": md, "sections": sections}
