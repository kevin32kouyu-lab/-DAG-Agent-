from fastapi import APIRouter, Query, HTTPException
from src.api.deps import get_store, get_audit_logger
from src.knowledge_graph.query import bfs_trace, find_contradictions, get_confidence_breakdown

router = APIRouter()


@router.get("/trace/{task_id}/{insight_id}")
async def trace_insight(task_id: str, insight_id: str, include_steps: bool = Query(False)):
    store = get_store()
    node = store.get_node(insight_id)
    if node is None:
        raise HTTPException(404, "Insight not found")
    chain = bfs_trace(store, insight_id)
    contradictions = find_contradictions(store, insight_id)
    breakdown = get_confidence_breakdown(store, insight_id)

    result = {
        "insight": insight_id,
        "task_id": task_id,
        "confidence": getattr(node, "confidence", None),
        "chain": chain,
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
