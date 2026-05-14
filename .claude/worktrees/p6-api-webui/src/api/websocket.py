from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.api.deps import get_scheduler

router = APIRouter()

active_connections: dict[str, list[WebSocket]] = {}

# Cumulative cost tracking per task
_task_costs: dict[str, float] = {}


async def _broadcast(task_id: str, event: dict):
    for conn in active_connections.get(task_id, []):
        await conn.send_json(event)


@router.websocket("/ws/task/{task_id}")
async def task_websocket(ws: WebSocket, task_id: str):
    await ws.accept()
    active_connections.setdefault(task_id, []).append(ws)
    scheduler = get_scheduler()

    async def on_node_state_change(node):
        await _broadcast(task_id, {
            "event": "node_state_change",
            "task_id": task_id,
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state,
        })

    async def on_node_completed(node):
        await _broadcast(task_id, {
            "event": "node_completed",
            "task_id": task_id,
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state,
        })

    async def on_node_failed(node):
        await _broadcast(task_id, {
            "event": "node_failed",
            "task_id": task_id,
            "node_id": node.node_id,
            "agent_type": node.agent_type,
        })

    async def on_agent_log(task_id_log: str, node_id: str, agent_type: str, step: int,
                           phase: str, summary: str):
        await _broadcast(task_id, {
            "event": "agent_log",
            "task_id": task_id_log,
            "node_id": node_id,
            "agent_type": agent_type,
            "step": step,
            "phase": phase,
            "summary": summary,
        })

    async def on_cost_update(task_id_cost: str, delta_cost: float, total_cost: float):
        _task_costs[task_id] = total_cost
        await _broadcast(task_id, {
            "event": "cost_update",
            "task_id": task_id_cost,
            "delta_cost": delta_cost,
            "total_cost": total_cost,
        })

    async def on_qa_reject(task_id_qa: str, qa_agent_type: str, failed_nodes: list[str],
                           reasons: list[str], affected_nodes: list[str], qa_round: int):
        await _broadcast(task_id, {
            "event": "qa_reject",
            "task_id": task_id_qa,
            "qa_agent_type": qa_agent_type,
            "failed_nodes": failed_nodes,
            "reasons": reasons,
            "affected_nodes": affected_nodes,
            "qa_round": qa_round,
        })

    scheduler.on("node_state_change", on_node_state_change)
    scheduler.on("node_completed", on_node_completed)
    scheduler.on("node_failed", on_node_failed)
    scheduler.on("agent_log", on_agent_log)
    scheduler.on("cost_update", on_cost_update)
    scheduler.on("qa_reject", on_qa_reject)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        active_connections.get(task_id, []).remove(ws)
