import asyncio
import json
import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.api.deps import get_store, get_gateway, get_scheduler, get_audit_logger
from src.agents.orchestrator import OrchestratorAgent
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool
from src.agents.tools.web_tools import WebScrapeTool, WebSearchTool, BatchWebScrapeTool
from src.agents.tools.api_tools import ThirdPartyAPITool
from src.agents.tools.company_scope import CompanyScopeTool
from src.agents.tools.wayback_tool import WaybackTool
from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
from src.dag.executor import AgentExecutor
from src.dag.models import NodeState

router = APIRouter()
logger = logging.getLogger(__name__)


class CreateTaskRequest(BaseModel):
    targets: list[str]
    industry: str = "saas"
    planning_mode: str = "template"
    dimensions: list[dict] = Field(default_factory=list)
    exclude_dimensions: list[str] = Field(default_factory=list)
    focus_points: dict[str, list[str]] = Field(default_factory=dict)
    dimension_weights: dict[str, float] = Field(default_factory=dict)
    source_preferences: dict = Field(default_factory=dict)
    benchmark_product: str | None = None
    report_audience: str = "product_manager"
    report_sections: list[str] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=lambda: ["markdown"])
    execution_mode: str = "auto"
    collection_depth: str = "standard"
    model_preference: str = "auto"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    dag_nodes: list[dict] = Field(default_factory=list)
    ws_endpoint: str = ""


def _build_tools(store, req: CreateTaskRequest | None = None):
    """按任务场景注册工具，默认只启用稳定的核心工具。"""
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    tools.register(WebScrapeTool)
    tools.register(BatchWebScrapeTool)
    tools.register(WebSearchTool)
    from src.agents.tools.npm_tool import NpmTool
    from src.agents.tools.pypi_tool import PyPITool
    from src.agents.tools.yfinance_tool import YFinanceTool
    tools.register(NpmTool)
    tools.register(PyPITool)
    tools.register(YFinanceTool)
    from src.agents.tools.firecrawl_tool import FirecrawlTool
    from src.agents.tools.newsapi_tool import NewsAPITool
    from src.agents.tools.gitee_tool import GiteeTool
    from src.agents.tools.serper_tool import SerperSearchTool
    tools.register(FirecrawlTool)
    tools.register(NewsAPITool)
    tools.register(GiteeTool)
    tools.register(SerperSearchTool)
    tools.register(ThirdPartyAPITool)
    tools.register(CompanyScopeTool)
    tools.register(WaybackTool)

    if req and req.collection_depth == "deep":
        from src.agents.tools.github_tool import GitHubTool
        from src.agents.tools.google_trends_tool import GoogleTrendsTool
        from src.agents.tools.hackernews_tool import HackerNewsTool
        from src.agents.tools.news_tools import GoogleNewsTool
        from src.agents.tools.producthunt_tool import ProductHuntTool
        from src.agents.tools.reddit_tool import RedditTool
        from src.agents.tools.social_media_tool import SocialMediaTool
        from src.agents.tools.tianyancha_tool import TianyanchaTool

        tools.register(HackerNewsTool)
        tools.register(GitHubTool)
        tools.register(GoogleNewsTool)
        tools.register(RedditTool)
        tools.register(ProductHuntTool)
        tools.register(GoogleTrendsTool)
        tools.register(SocialMediaTool)
        tools.register(TianyanchaTool)

        if req.industry == "app":
            from src.agents.tools.app_store_tool import AppStoreTool
            tools.register(AppStoreTool)

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


def _persist_task_targets(task_id: str, targets: list[str], targets_file: str | Path = "data/task_targets.json") -> None:
    """保存任务目标产品，供服务重载后恢复图表产品名。"""
    path = Path(targets_file)
    existing_targets: dict = {}
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                existing_targets = existing
            else:
                logger.warning("任务目标缓存格式不是对象，已重建: %s", path)
        except Exception as exc:
            logger.warning("任务目标缓存读取失败，已重建: %s，原因: %s", path, exc)

    existing_targets[task_id] = targets
    try:
        path.write_text(json.dumps(existing_targets, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.warning("任务目标缓存写入失败: %s，原因: %s", path, exc)


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
    tools = _build_tools(store, req)

    _persist_task_targets(task_id, req.targets)

    asyncio.create_task(_plan_and_execute(task_id, req, store, gateway, tools))

    return TaskResponse(
        task_id=task_id,
        status="planning",
        ws_endpoint=f"/ws/task/{task_id}",
    )


def _task_status(dag) -> str:
    states = {n.state for n in dag.nodes}
    if all(s in {NodeState.COMPLETED, NodeState.DEGRADED} for s in states):
        return "completed"
    if any(s == NodeState.FAILED for s in states):
        return "failed"
    if any(s == NodeState.RUNNING for s in states):
        return "running"
    if any(s == NodeState.READY for s in states):
        return "in_progress"
    return "pending"


def _node_view(node) -> dict:
    return {
        "node_id": node.node_id,
        "agent_type": node.agent_type,
        "state": node.state.value if hasattr(node.state, "value") else str(node.state),
        "depends_on": node.depends_on,
        "stage": getattr(node, "stage", ""),
        "role_group": getattr(node, "role_group", ""),
        "display_name": getattr(node, "display_name", ""),
        "description": getattr(node, "description", ""),
        "retries": node.retries,
        "max_retries": node.max_retries,
    }


@router.get("/task/{task_id}")
async def get_task(task_id: str):
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        error = scheduler.get_task_error(task_id)
        if error is not None:
            return {"task_id": task_id, "status": "failed", "error": error}
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return {
        "task_id": task_id,
        "status": _task_status(dag),
        "workflow_template_id": getattr(dag, "workflow_template_id", ""),
        "scenario": getattr(dag, "scenario", ""),
        "targets": getattr(dag, "targets", []),
        "metadata": getattr(dag, "metadata", {}),
        "nodes": [_node_view(n) for n in dag.nodes],
    }


class SourceListResponse(BaseModel):
    task_id: str
    sources: list[str]


class ApproveSourcesRequest(BaseModel):
    urls: list[str]


@router.post("/task/{task_id}/release-checkpoint")
async def release_checkpoint(task_id: str):
    scheduler = get_scheduler()
    scheduler.release_checkpoint()
    return {"task_id": task_id, "checkpoint": "released"}


@router.get("/task/{task_id}/sources", response_model=SourceListResponse)
async def get_task_sources(task_id: str):
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    urls_set = set()
    import re
    
    # 1. Try to extract from Collector node's _output_data or context
    for node in dag.nodes:
        if node.agent_type == "Collector":
            output_data = node.context.get("_output_data", {})
            if output_data:
                # Helper function to recursively extract urls from any nested structures
                def extract_urls(val):
                    if isinstance(val, str):
                        for match in re.finditer(r'https?://[^\s,\)\}\]\'"]+', val):
                            urls_set.add(match.group(0))
                    elif isinstance(val, list):
                        for item in val:
                            extract_urls(item)
                    elif isinstance(val, dict):
                        for k, v in val.items():
                            if k == "url" and isinstance(v, str):
                                urls_set.add(v)
                            else:
                                extract_urls(v)
                extract_urls(output_data)
    
    # 2. Extract SourceInfo nodes from knowledge graph
    store = get_store()
    nodes = store.query_nodes(node_type="SourceInfo")
    for node in nodes:
        task_meta = node.metadata.get("task_id")
        if task_meta == task_id or not task_meta:
            if hasattr(node, "url") and node.url:
                urls_set.add(node.url)
            elif isinstance(node.properties, dict) and "url" in node.properties:
                urls_set.add(node.properties["url"])

    return SourceListResponse(
        task_id=task_id,
        sources=sorted(list(urls_set))
    )


@router.post("/task/{task_id}/sources/approve")
async def approve_sources(task_id: str, req: ApproveSourcesRequest):
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    
    # 1. Update the collector node's input_query with the approved URLs
    collector_node = None
    for node in dag.nodes:
        if node.node_id == "collector" or node.agent_type == "Collector":
            collector_node = node
            break
            
    if collector_node is None:
        raise HTTPException(status_code=404, detail="Collector node not found in DAG")
        
    collector_node.input_query["urls"] = req.urls
    if "targets" not in collector_node.input_query or not collector_node.input_query["targets"]:
        collector_node.input_query["targets"] = dag.targets
        
    # 2. Release checkpoint to resume scheduler
    scheduler.release_checkpoint()
    
    return {"task_id": task_id, "status": "approved", "urls_count": len(req.urls)}
