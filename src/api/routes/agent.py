from fastapi import APIRouter
from src.api.deps import get_scheduler

router = APIRouter()


@router.get("/agent/{task_id}/status")
async def get_agent_status(task_id: str):
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        return {"task_id": task_id, "agents": []}
    agents = []
    for node in dag.nodes:
        agents.append({
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state.value if hasattr(node.state, 'value') else str(node.state),
            "depends_on": node.depends_on,
        })
    return {"task_id": task_id, "agents": agents}
