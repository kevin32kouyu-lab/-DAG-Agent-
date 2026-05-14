from fastapi import APIRouter

router = APIRouter()


@router.get("/agent/{task_id}/status")
async def get_agent_status(task_id: str):
    return {"task_id": task_id, "agents": []}
