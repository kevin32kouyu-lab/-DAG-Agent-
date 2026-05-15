from fastapi import APIRouter, Query, HTTPException
from src.api.deps import get_store, get_audit_logger
from src.knowledge_graph.query import bfs_trace, find_contradictions, get_confidence_breakdown

router = APIRouter()


@router.get("/trace/{task_id}/{insight_id}")
async def trace_insight(task_id: str, insight_id: str, include_steps: bool = Query(False)):
    store = get_store()
    node = store.get_node(insight_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    chain = bfs_trace(store, insight_id)
    contradictions = find_contradictions(store, insight_id)
    breakdown = get_confidence_breakdown(store, insight_id)

    # Filter chain to only include nodes belonging to this task
    filtered_chain = []
    for entry in chain:
        node_meta = entry["node"].get("metadata", {}) if isinstance(entry["node"], dict) else {}
        if isinstance(node_meta, str):
            import json
            try:
                node_meta = json.loads(node_meta)
            except (json.JSONDecodeError, TypeError):
                node_meta = {}
        node_task_id = node_meta.get("task_id", "")
        if not node_task_id or node_task_id == task_id:
            filtered_chain.append(entry)
        # Also include the insight node itself
        elif entry["node"].get("id", "") == insight_id:
            filtered_chain.append(entry)

    result = {
        "insight": insight_id,
        "task_id": task_id,
        "confidence": getattr(node, "confidence", None),
        "chain": filtered_chain,
        "contradicting_evidence": contradictions,
        "confidence_breakdown": breakdown,
    }

    if include_steps:
        audit = get_audit_logger()
        step_traces: dict[str, list[dict]] = {}
        if audit is not None:
            for entry in chain:
                nid = entry["node"]["id"]
                traces = audit.get_step_traces(task_id, nid)
                if traces:
                    step_traces[nid] = traces
        result["step_traces"] = step_traces

    return result
