from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.api.deps import get_store, get_gateway, get_scheduler
from src.agents.orchestrator import OrchestratorAgent
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool

router = APIRouter()


class CreateTaskRequest(BaseModel):
    targets: list[str]
    industry: str = "saas"
    dimensions: list[dict] = []
    exclude_dimensions: list[str] = []
    focus_points: dict[str, list[str]] = {}
    dimension_weights: dict[str, float] = {}
    source_preferences: dict = {}
    benchmark_product: str | None = None
    report_audience: str = "product_manager"
    report_sections: list[str] = []
    output_formats: list[str] = ["markdown"]
    execution_mode: str = "auto"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    dag_nodes: list[dict] = []
    ws_endpoint: str = ""


@router.post("/task", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    task_id = f"task_{len(req.targets)}_{uuid4().hex[:8]}"
    store = get_store()
    gateway = get_gateway()
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    orch = OrchestratorAgent(gateway=gateway, store=store, tool_registry=tools)
    try:
        dag, _ = await orch.execute({"task_id": task_id, "targets": req.targets, "schema": req.model_dump()})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate DAG: {e}")
    if dag is None:
        raise HTTPException(status_code=500, detail="Failed to generate DAG")
    return TaskResponse(
        task_id=task_id, status="created",
        dag_nodes=[{"node_id": n.node_id, "agent_type": n.agent_type, "depends_on": n.depends_on, "state": n.state} for n in dag.nodes],
        ws_endpoint=f"/ws/task/{task_id}",
    )


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    return {"task_id": task_id, "status": "completed"}


@router.post("/task/{task_id}/release-checkpoint")
async def release_checkpoint(task_id: str):
    scheduler = get_scheduler()
    scheduler.release_checkpoint()
    return {"task_id": task_id, "checkpoint": "released"}
