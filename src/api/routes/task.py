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
from src.agents.tools.hackernews_tool import HackerNewsTool
from src.agents.tools.github_tool import GitHubTool
from src.agents.tools.news_tools import GoogleNewsTool
from src.agents.tools.reddit_tool import RedditTool
from src.agents.tools.tianyancha_tool import TianyanchaTool
from src.agents.tools.tavily_tool import TavilySearchTool
from src.agents.tools.app_store_tool import AppStoreTool
from src.agents.tools.producthunt_tool import ProductHuntTool
from src.agents.tools.wayback_tool import WaybackTool
from src.agents.tools.google_trends_tool import GoogleTrendsTool
from src.agents.tools.social_media_tool import SocialMediaTool
from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
from src.dag.executor import AgentExecutor
from src.dag.models import NodeState

router = APIRouter()


class CreateTaskRequest(BaseModel):
    targets: list[str]
    industry: str = "saas"
    planning_mode: str = "template"
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
    tools.register(TavilySearchTool)
    tools.register(ThirdPartyAPITool)
    tools.register(CompanyScopeTool)
    tools.register(HackerNewsTool)
    tools.register(GitHubTool)
    tools.register(GoogleNewsTool)
    tools.register(RedditTool)
    tools.register(TianyanchaTool)
    tools.register(AppStoreTool)
    tools.register(ProductHuntTool)
    tools.register(WaybackTool)
    tools.register(GoogleTrendsTool)
    tools.register(SocialMediaTool)
    return tools


def _compile_template_dag(task_id: str, req: CreateTaskRequest):
    compiler = WorkflowCompiler()
    return compiler.compile(WorkflowCompileRequest(
        task_id=task_id,
        targets=req.targets,
        scenario=req.industry,
        collection_depth=req.collection_depth,
        schema=req.model_dump(),
    ))


async def _plan_and_execute(task_id: str, req: CreateTaskRequest, store, gateway, tools):
    scheduler = None
    try:
        scheduler = get_scheduler()

        if req.planning_mode == "template":
            dag = _compile_template_dag(task_id, req)
        elif req.planning_mode == "orchestrator":
            orch = OrchestratorAgent(gateway=gateway, store=store, tool_registry=tools)
            dag, _ = await orch.execute({
                "task_id": task_id,
                "targets": req.targets,
                "schema": req.model_dump(),
            })
        else:
            await scheduler.emit_dag_failed(task_id, f"不支持的规划模式: {req.planning_mode}")
            return

        if dag is None:
            error_msg = "Orchestrator LLM 未能生成 DAG，请重试。提示：确认 API 密钥有效、产品名称正确。"
            await scheduler.emit_dag_failed(task_id, error_msg)
            return

        # Validate DAG has mandatory nodes — template mode guarantees this,
        # but orchestrator (LLM-generated) needs a belt-and-suspenders check.
        if req.planning_mode == "orchestrator":
            agent_types = {n.agent_type for n in dag.nodes}
            missing_mandatory = [a for a in OrchestratorAgent.MANDATORY_AGENTS
                                if a not in agent_types]
            if missing_mandatory:
                error_msg = f"DAG 缺少强制 Agent: {', '.join(missing_mandatory)}。Orchestrator 后验证失败。"
                await scheduler.emit_dag_failed(task_id, error_msg)
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
        import logging
        logging.getLogger(__name__).error(f"Pipeline failed for {task_id}: {e}", exc_info=True)
        if scheduler is not None:
            await scheduler.emit_dag_failed(task_id, f"Pipeline 执行异常: {e}")


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
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
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
