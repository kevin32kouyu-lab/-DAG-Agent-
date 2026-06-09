from fastapi import APIRouter
from src.api.deps import get_scheduler
from src.api.routes.task import _node_view

router = APIRouter()


@router.get("/agent/{task_id}/status")
async def get_agent_status(task_id: str):
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        return {"task_id": task_id, "agents": []}
    return {"task_id": task_id, "agents": [_node_view(node) for node in dag.nodes]}
