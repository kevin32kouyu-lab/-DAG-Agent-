import json

from fastapi import APIRouter, HTTPException, Query
from src.api.deps import get_store, get_scheduler
from src.dag.models import NodeState

router = APIRouter()


def _extract_metadata(node) -> dict:
    metadata = getattr(node, "metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    return metadata or {}


def _layer1_report_sections(store, task_id: str) -> list[dict]:
    """Primary: read ReportSection nodes from the knowledge graph."""
    all_sections = store.query_nodes(node_type="ReportSection", layer=3)
    sections = []
    for s in all_sections:
        node_id = getattr(s, "id", "")
        metadata = _extract_metadata(s)
        if metadata and metadata.get("task_id") != task_id:
            continue
        sections.append({
            "node_id": node_id,
            "section": getattr(s, "section", ""),
            "content": getattr(s, "content", ""),
            "order": getattr(s, "order", 0),
        })
    sections.sort(key=lambda x: x["order"])
    return sections


def _layer2_report_generator_output(scheduler, task_id: str) -> list[dict] | None:
    """Fallback 1: ReportGenerator completed but didn't persist to graph."""
    dag = scheduler.get_task_dag(task_id)
    if not dag:
        return None
    rg_nodes = [n for n in dag.nodes if n.agent_type == "ReportGenerator"]
    if not rg_nodes:
        return None
    rg = rg_nodes[0]
    if rg.state == NodeState.FAILED:
        error_msg = rg.context.get("error", "")
        return [{"node_id": "error", "section": "报告生成失败",
                 "content": f"ReportGenerator agent 执行失败: {error_msg}", "order": 0}]
    output_data = rg.context.get("_output_data", {})
    if not isinstance(output_data, dict):
        return None
    report_md = output_data.get("report_markdown", "")
    sections_data = output_data.get("sections", [])
    if report_md:
        return [{"node_id": "rg_output", "section": "完整报告",
                 "content": report_md, "order": 0}]
    if sections_data:
        return sections_data
    return None


def _layer3_assembled_report(scheduler, task_id: str) -> list[dict]:
    """Fallback 2: assemble partial report from all completed agent outputs."""
    dag = scheduler.get_task_dag(task_id)
    if not dag:
        return None
    parts: list[dict] = []
    missing_dimensions: list[str] = []
    order = 0

    for node in sorted(dag.nodes, key=lambda n: n.node_id):
        if node.state != NodeState.COMPLETED:
            if node.agent_type not in ("ReportGenerator", "QA_FactCheck", "QA_LogicCheck",
                                        "Orchestrator", "SourceDiscovery", "Collector",
                                        "DataEnricher"):
                missing_dimensions.append(node.agent_type)
            continue
        output_data = node.context.get("_output_data", {})
        summary = ""
        if isinstance(output_data, dict):
            summary = output_data.get("summary", "") or json.dumps(output_data, default=str)
        elif output_data:
            summary = str(output_data)
        if summary and len(summary) > 20:
            parts.append({
                "node_id": node.node_id,
                "section": f"{node.agent_type} 分析结果",
                "content": summary,
                "order": order,
            })
            order += 1

    if not parts:
        return None

    header = "## 部分报告（自动拼接）\n\n"
    header += f"> 以下维度缺失或未完成: {', '.join(missing_dimensions) if missing_dimensions else '无'}\n\n"
    header += "---\n\n"
    parts.insert(0, {"node_id": "header", "section": "报告状态",
                      "content": header.strip(), "order": -1})
    return parts


def _layer4_error_state(scheduler, task_id: str) -> list[dict]:
    """Fallback 3: no data anywhere — return error with current task state."""
    dag = scheduler.get_task_dag(task_id)
    if not dag:
        return [{"node_id": "not_found", "section": "任务未找到",
                 "content": f"任务 {task_id} 不存在或尚未创建。", "order": 0}]
    states = {}
    for n in dag.nodes:
        states.setdefault(n.state.value, []).append(n.agent_type)
    state_desc = ", ".join(f"{st}: {', '.join(agents)}" for st, agents in states.items())
    has_rg = any(n.agent_type == "ReportGenerator" for n in dag.nodes)
    msg = f"报告尚未生成。当前 DAG 状态: {state_desc}。"
    if not has_rg:
        msg += " DAG 中缺少 ReportGenerator 节点，请联系管理员检查 Orchestrator 配置。"
    return [{"node_id": "error", "section": "报告未就绪", "content": msg, "order": 0}]


@router.get("/report/{task_id}")
async def get_report(task_id: str, format: str = Query("markdown")):
    store = get_store()
    scheduler = get_scheduler()

    # Layer 1: ReportSection nodes in graph
    sections = _layer1_report_sections(store, task_id)

    # Layer 2: ReportGenerator output data
    if not sections:
        sections = _layer2_report_generator_output(scheduler, task_id)

    # Layer 3: Assembled partial report
    if not sections:
        sections = _layer3_assembled_report(scheduler, task_id)

    # Layer 4: Error state
    if not sections:
        sections = _layer4_error_state(scheduler, task_id)

    if format == "json":
        return {"task_id": task_id, "format": "json", "sections": sections}
    md = "\n\n".join(f"## {s['section']}\n\n{s['content']}" for s in sections)
    return {"task_id": task_id, "format": "markdown", "content": md, "sections": sections}
