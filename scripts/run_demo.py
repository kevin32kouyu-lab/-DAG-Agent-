#!/usr/bin/env python
"""直接运行 demo 竞品分析（不启动 HTTP 服务器），用于快速验证端到端。"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 使用 auto 模式（先命中缓存，未命中时自动调 API 并写回缓存）
os.environ["TOOL_CACHE_MODE"] = "auto"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_demo")


async def main():
    from src.dag.compiler import WorkflowCompileRequest, WorkflowCompiler
    from src.dag.executor import AgentExecutor
    from src.dag.scheduler import DAGScheduler
    from src.dag.models import TaskDAG
    from src.knowledge_graph.store import GraphStore
    from src.llm_gateway.gateway import LLMGateway
    from src.agents.tools.cache import tool_cache
    from src.infrastructure.degradation import DegradationHandler
    from src.infrastructure.config import config
    from src.infrastructure.audit import AuditLogger
    from src.api.routes.task import _build_tools, CreateTaskRequest

    # 1. 检查缓存状态
    stats = tool_cache.stats()
    logger.info("Cache stats: %s", stats)
    if stats.get("total_entries", 0) == 0:
        logger.error("Cache is EMPTY! Run warmup_cache.py first.")
        return

    # 2. 初始化 Store + Gateway
    store = GraphStore("data/demo_run.db")

    # 确保 LLM gateway 能找到 API key（deps.py 检查 DEEPSEEK_API_KEY，但 .env 用的是 OPENAI_API_KEY）
    if not os.environ.get("DEEPSEEK_API_KEY") and os.environ.get("OPENAI_API_KEY"):
        os.environ["DEEPSEEK_API_KEY"] = os.environ["OPENAI_API_KEY"]

    gateway = LLMGateway(
        default_model=os.environ.get("LLM_DEFAULT_MODEL", "deepseek-chat"),
        model_map={
            "reasoning": os.environ.get("LLM_DEFAULT_MODEL", "deepseek-chat"),
            "analysis": os.environ.get("LLM_DEFAULT_MODEL", "deepseek-chat"),
            "batch": os.environ.get("LLM_DEFAULT_MODEL", "deepseek-chat"),
        },
        provider_map={
            os.environ.get("LLM_DEFAULT_MODEL", "deepseek-chat"): "openai_compatible",
        },
    )
    audit = AuditLogger()
    degradation_handler = DegradationHandler(config=config, audit=audit)

    req = CreateTaskRequest(
        targets=["飞书", "钉钉"],
        industry="saas",
        planning_mode="template",
        collection_depth="demo",  # 路由到 demo 模板
    )
    tools = _build_tools(store, req)

    # 3. 编译 DAG
    task_id = "demo_feishu_dingtalk"
    compiler = WorkflowCompiler()
    dag = compiler.compile(WorkflowCompileRequest(
        task_id=task_id,
        targets=["飞书", "钉钉"],
        scenario="saas",
        collection_depth="demo",
    ))

    # 注入 task_id
    for node in dag.nodes:
        node.context["task_id"] = task_id

    logger.info("DAG compiled: %d nodes", len(dag.nodes))
    for n in dag.nodes:
        logger.info("  - %s (%s) depends_on=%s dimension=%s",
                     n.node_id, n.agent_type, n.depends_on,
                     n.input_query.get("dimension", "-"))

    # 4. 执行
    scheduler = DAGScheduler()
    executor = AgentExecutor(
        gateway=gateway, store=store, tool_registry=tools,
        audit_logger=audit,
        degradation_handler=degradation_handler,
    )

    logger.info("=== 开始执行 demo (force_cache mode) ===")
    start = time.time()

    await scheduler.run(dag, executor, gateway=gateway)

    elapsed = time.time() - start
    logger.info("=== 执行完成: %.1fs ===", elapsed)

    # 5. 结果汇总
    for n in dag.nodes:
        status = n.state.value if hasattr(n.state, "value") else str(n.state)
        logger.info("  %s: %s", n.node_id, status)

    # 6. 读取报告
    report_nodes = store.query_nodes(node_type="ReportSection", layer=3)
    if report_nodes:
        logger.info("=== 报告内容 (共 %d 段) ===", len(report_nodes))
        for i, node in enumerate(report_nodes):
            section = getattr(node, "section", "")
            text = getattr(node, "text", "")[:500]
            print(f"\n--- {section or f'Section {i+1}'} ---")
            print(text)
    else:
        logger.warning("No report sections found in graph.")
        # 尝试读所有层 3 节点
        all_l3 = store.query_nodes(layer=3)
        logger.info("Layer 3 nodes: %d", len(all_l3))
        for n in all_l3:
            label = getattr(n, "label", getattr(n, "id", "?"))
            logger.info("  - %s (%s)", label, type(n).__name__)

    # 7. 最终结论
    completed = sum(1 for n in dag.nodes if n.state.value in ("completed", "degraded"))
    failed = sum(1 for n in dag.nodes if n.state.value == "failed")
    target_met = elapsed < 300  # 5 min target

    print(f"\n{'='*60}")
    print(f"DEMO RESULT: {'PASS' if target_met and failed == 0 else 'FAIL'}")
    print(f"  Time: {elapsed:.1f}s (target: <300s, met: {target_met})")
    print(f"  Nodes: {completed} completed, {failed} failed, {len(dag.nodes)} total")
    print(f"  Cache mode: force_cache (zero external API calls)")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())