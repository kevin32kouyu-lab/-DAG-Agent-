import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.api.deps import get_store, get_gateway, get_scheduler, get_audit_logger
from src.agents.orchestrator import OrchestratorAgent
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool
from src.agents.tools.api_tools import ThirdPartyAPITool
from src.agents.tools.company_scope import CompanyScopeTool
from src.dag.executor import AgentExecutor
from src.dag.models import NodeState

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
    collection_depth: str = "standard"
    model_preference: str = "auto"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    dag_nodes: list[dict] = []
    ws_endpoint: str = ""


def _build_tools(store):
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebScrapeTool)
    tools.register(WebSearchTool)
    tools.register(ThirdPartyAPITool)
    tools.register(CompanyScopeTool)
    return tools


async def _plan_and_execute(task_id: str, req: CreateTaskRequest, store, gateway, tools):
    scheduler = None
    try:
        scheduler = get_scheduler()
        orch = OrchestratorAgent(gateway=gateway, store=store, tool_registry=tools)
        dag, _ = await orch.execute({
            "task_id": task_id,
            "targets": req.targets,
            "schema": req.model_dump(),
        })

        if dag is None:
            await scheduler.emit_dag_failed(task_id, "LLM failed to generate DAG — please retry")
            return

        for node in dag.nodes:
            node.context["task_id"] = task_id

        await scheduler.emit_dag_created(task_id, dag)

        scheduler.review_mode = (req.execution_mode == "review")
        from src.infrastructure.degradation import DegradationHandler
        from src.infrastructure.config import config
        degradation_handler = DegradationHandler(config=config, audit=get_audit_logger())
        executor = AgentExecutor(
            gateway=gateway, store=store, tool_registry=tools,
            audit_logger=get_audit_logger(),
            degradation_handler=degradation_handler,
        )
        await scheduler.run(dag, executor, gateway=gateway)

    except Exception as e:
        if scheduler is not None:
            await scheduler.emit_dag_failed(task_id, str(e))


@router.post("/task", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    task_id = f"task_{len(req.targets)}_{uuid4().hex[:8]}"
    store = get_store()
    gateway = get_gateway()
    tools = _build_tools(store)

    asyncio.create_task(_plan_and_execute(task_id, req, store, gateway, tools))

    return TaskResponse(
        task_id=task_id,
        status="planning",
        ws_endpoint=f"/ws/task/{task_id}",
    )


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        error = scheduler.get_task_error(task_id)
        if error is not None:
            return {"task_id": task_id, "status": "failed", "error": error}
        return {"task_id": task_id, "status": "planning"}
    states = {n.state for n in dag.nodes}
    if all(s in {NodeState.COMPLETED, NodeState.DEGRADED} for s in states):
        status = "completed"
    elif any(s == NodeState.FAILED for s in states):
        status = "failed"
    elif any(s == NodeState.RUNNING for s in states):
        status = "running"
    elif any(s == NodeState.READY for s in states):
        status = "in_progress"
    else:
        status = "pending"
    return {
        "task_id": task_id,
        "status": status,
        "nodes": [{"node_id": n.node_id, "agent_type": n.agent_type, "state": n.state} for n in dag.nodes],
    }


@router.post("/task/{task_id}/release-checkpoint")
async def release_checkpoint(task_id: str):
    scheduler = get_scheduler()
    scheduler.release_checkpoint()
    return {"task_id": task_id, "checkpoint": "released"}
