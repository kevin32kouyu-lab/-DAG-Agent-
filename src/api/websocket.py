from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.api.deps import get_scheduler

router = APIRouter()

active_connections: dict[str, list[WebSocket]] = {}
_task_costs: dict[str, float] = {}
_callbacks_registered = False


async def _broadcast(task_id: str, event: dict):
    for conn in active_connections.get(task_id, []):
        try:
            await conn.send_json(event)
        except Exception:
            pass


def _ensure_callbacks_registered() -> None:
    """Register global callbacks once. Each callback broadcasts to ALL connections for the relevant task."""
    global _callbacks_registered
    if _callbacks_registered:
        return
    _callbacks_registered = True
    scheduler = get_scheduler()

    async def on_node_state_change(node):
        # node.context["task_id"] holds the dag's task_id
        task_id = node.context.get("task_id", "")
        if task_id:
            await _broadcast(task_id, {
                "event": "node_state_change",
                "task_id": task_id,
                "node_id": node.node_id,
                "agent_type": node.agent_type,
                "state": node.state,
                "depends_on": node.depends_on,
            })

    async def on_node_completed(node):
        task_id = node.context.get("task_id", "")
        if task_id:
            await _broadcast(task_id, {
                "event": "node_completed",
                "task_id": task_id,
                "node_id": node.node_id,
                "agent_type": node.agent_type,
                "state": node.state,
                "depends_on": node.depends_on,
            })

    async def on_node_failed(node):
        task_id = node.context.get("task_id", "")
        if task_id:
            await _broadcast(task_id, {
                "event": "node_failed",
                "task_id": task_id,
                "node_id": node.node_id,
                "agent_type": node.agent_type,
            })

    async def on_agent_log(task_id: str, node_id: str, agent_type: str, step: int,
                           phase: str, summary: str):
        await _broadcast(task_id, {
            "event": "agent_log",
            "task_id": task_id,
            "node_id": node_id,
            "agent_type": agent_type,
            "step": step,
            "phase": phase,
            "summary": summary,
        })

    async def on_cost_update(task_id: str, delta_cost: float, total_cost: float):
        _task_costs[task_id] = total_cost
        await _broadcast(task_id, {
            "event": "cost_update",
            "task_id": task_id,
            "delta_cost": delta_cost,
            "total_cost": total_cost,
        })

    async def on_qa_reject(task_id: str, qa_agent_type: str, failed_nodes: list[str],
                           reasons: list[str], affected_nodes: list[str], qa_round: int):
        await _broadcast(task_id, {
            "event": "qa_reject",
            "task_id": task_id,
            "qa_agent_type": qa_agent_type,
            "failed_nodes": failed_nodes,
            "reasons": reasons,
            "affected_nodes": affected_nodes,
            "qa_round": qa_round,
        })

    async def on_feedback_applied(data: dict):
        task_id = data.get("task_id", "")
        if task_id:
            await _broadcast(task_id, {
                "event": "feedback_applied",
                "task_id": task_id,
                "type": data.get("type", ""),
                "qa_node_id": data.get("qa_node_id", ""),
                "cr_node_id": data.get("cr_node_id", ""),
                "round": data.get("round", 0),
                "affected_nodes": data.get("affected_nodes", []),
            })

    async def on_checkpoint_reached(node, task_id: str):
        await _broadcast(task_id, {
            "event": "checkpoint_reached",
            "task_id": task_id,
            "node_id": node.node_id,
        })

    async def on_checkpoint_released(node, task_id: str):
        await _broadcast(task_id, {
            "event": "checkpoint_released",
            "task_id": task_id,
            "node_id": node.node_id,
        })

    scheduler.on("node_state_change", on_node_state_change)
    scheduler.on("node_completed", on_node_completed)
    scheduler.on("node_failed", on_node_failed)
    scheduler.on("agent_log", on_agent_log)
    scheduler.on("cost_update", on_cost_update)
    scheduler.on("qa_reject", on_qa_reject)
    scheduler.on("feedback_applied", on_feedback_applied)
    scheduler.on("checkpoint_reached", on_checkpoint_reached)
    scheduler.on("checkpoint_released", on_checkpoint_released)


async def _send_dag_state(ws: WebSocket, task_id: str) -> None:
    """Send full DAG state snapshot so reconnecting clients can restore UI."""
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        return
    nodes_state = []
    for node in dag.nodes:
        nodes_state.append({
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state,
            "depends_on": node.depends_on,
            "retries": node.retries,
            "error": node.context.get("error", ""),
        })
    await ws.send_json({
        "event": "dag_state",
        "task_id": task_id,
        "nodes": nodes_state,
        "total_cost": _task_costs.get(task_id, 0.0),
    })


@router.websocket("/ws/task/{task_id}")
async def task_websocket(ws: WebSocket, task_id: str):
    await ws.accept()
    _ensure_callbacks_registered()
    active_connections.setdefault(task_id, []).append(ws)
    # Send current state immediately so UI can restore on reconnect
    await _send_dag_state(ws, task_id)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        conns = active_connections.get(task_id, [])
        if ws in conns:
            conns.remove(ws)
