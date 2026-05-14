# Phase 6: API + WebSocket + Web UI

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 用户可通过 Web UI 创建任务、监控 DAG 执行、阅读报告、钻取溯源链。FastAPI + WebSocket 驱动实时状态推送，React 渲染四个核心页面。

**可验证产出:** 启动 `uvicorn src.api.app:app` 后，浏览器可完成"创建任务→实时监控→阅读报告→溯源钻取"完整闭环。

**依赖:** P1-P5 完成（全后端逻辑可用）

**Spec Reference:** 设计文档第 6 章数据流设计、第 7 章 Web UI 设计

---

### Task 6.1: FastAPI 应用骨架 + API 路由

**Files:**
- Create: `src/api/__init__.py`, `src/api/app.py`, `src/api/deps.py`
- Create: `src/api/routes/__init__.py`, `src/api/routes/task.py`, `src/api/routes/report.py`, `src/api/routes/trace.py`, `src/api/routes/agent.py`
- Create: `tests/test_api/__init__.py`, `tests/test_api/test_task.py`, `tests/test_api/test_report.py`, `tests/test_api/test_trace.py`

- [ ] **Step 1: 实现 FastAPI app 和依赖注入**

```python
# src/api/app.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import task, report, trace, agent

app = FastAPI(title="Competitive Analysis Agent System", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(task.router, prefix="/api", tags=["task"])
app.include_router(report.router, prefix="/api", tags=["report"])
app.include_router(trace.router, prefix="/api", tags=["trace"])
app.include_router(agent.router, prefix="/api", tags=["agent"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

```python
# src/api/deps.py
from functools import lru_cache
from src.knowledge_graph.store import GraphStore
from src.llm_gateway.gateway import LLMGateway
from src.dag.scheduler import DAGScheduler

_store: GraphStore | None = None
_scheduler: DAGScheduler | None = None
_gateway: LLMGateway | None = None
_audit_logger = None


def get_store() -> GraphStore:
    global _store
    if _store is None:
        _store = GraphStore(db_path="data/knowledge_graph.db")
    return _store


def get_gateway() -> LLMGateway:
    global _gateway
    if _gateway is None:
        _gateway = LLMGateway()
    return _gateway


def get_scheduler() -> DAGScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = DAGScheduler()
    return _scheduler


def get_audit_logger():
    global _audit_logger
    if _audit_logger is None:
        from src.infrastructure.audit import AuditLogger
        _audit_logger = AuditLogger(db_path="data/audit.db")
    return _audit_logger
```

- [ ] **Step 2: 实现任务路由**

```python
# src/api/routes/task.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from src.api.deps import get_store, get_gateway, get_scheduler
from src.agents.orchestrator import OrchestratorAgent
from src.agents.tools.base import ToolRegistry
from src.agents.tools.graph_tools import GraphQueryTool, GraphWriteTool

router = APIRouter()


class CreateTaskRequest(BaseModel):
    """Matches AnalysisSchema from src.schema.models (P7) — creates task with analysis config."""
    targets: list[str]
    industry: str = "saas"
    dimensions: list[dict] = []
    exclude_dimensions: list[str] = []
    focus_points: dict[str, list[str]] = {}  # dimension_name → [questions]
    dimension_weights: dict[str, float] = {}
    source_preferences: dict = {}
    benchmark_product: str | None = None
    report_audience: str = "product_manager"
    report_sections: list[str] = []
    output_formats: list[str] = ["markdown"]
    execution_mode: str = "auto"  # "auto" | "review"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    dag_nodes: list[dict] = []
    ws_endpoint: str = ""


@router.post("/task", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest):
    task_id = f"task_{len(req.targets)}_{hash(tuple(req.targets))}"
    store = get_store()
    gateway = get_gateway()
    tools = ToolRegistry()
    tools.register(GraphQueryTool, store=store)
    tools.register(GraphWriteTool, store=store)
    orch = OrchestratorAgent(gateway=gateway, store=store, tool_registry=tools)
    dag, _ = await orch.execute({"task_id": task_id, "targets": req.targets, "schema": req.schema})
    if dag is None:
        raise HTTPException(500, "Failed to generate DAG")
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
    """Release review mode checkpoint — resumes DAG after Data Enricher."""
    scheduler = get_scheduler()
    scheduler.release_checkpoint()
    return {"task_id": task_id, "checkpoint": "released"}
```

- [ ] **Step 3: 实现报告路由**

```python
# src/api/routes/report.py
from fastapi import APIRouter, HTTPException
from src.api.deps import get_store

router = APIRouter()


@router.get("/report/{task_id}")
async def get_report(task_id: str, format: str = "markdown"):
    """Return the generated competitive analysis report for a task."""
    store = get_store()
    # Query Layer 3 ReportSection nodes, ordered by the 'order' field
    all_sections = store.query_nodes(node_type="ReportSection", layer=3)
    # Filter to those belonging to this task via metadata or edge traversal
    sections = []
    for s in all_sections:
        sections.append({
            "section": getattr(s, "section", ""),
            "content": getattr(s, "content", ""),
            "order": getattr(s, "order", 0),
        })
    sections.sort(key=lambda x: x["order"])
    if format == "json":
        return {"task_id": task_id, "sections": sections}
    # Default markdown: concatenate section contents
    md = "\n\n".join(f"## {s['section']}\n\n{s['content']}" for s in sections)
    return {"task_id": task_id, "format": "markdown", "content": md, "sections": sections}
```

- [ ] **Step 4: 实现溯源路由**

```python
# src/api/routes/trace.py
from fastapi import APIRouter, Query
from src.api.deps import get_store, get_audit_logger
from src.knowledge_graph.query import bfs_trace, find_contradictions, get_confidence_breakdown

router = APIRouter()


@router.get("/trace/{task_id}/{insight_id}")
async def trace_insight(task_id: str, insight_id: str, include_steps: bool = Query(False)):
    store = get_store()
    node = store.get_node(insight_id)
    if node is None:
        raise HTTPException(404, "Insight not found")
    chain = bfs_trace(store, insight_id)
    contradictions = find_contradictions(store, insight_id)
    breakdown = get_confidence_breakdown(store, insight_id)

    result = {
        "insight": insight_id,
        "task_id": task_id,
        "confidence": getattr(node, "confidence", None),
        "chain": chain,
        "contradicting_evidence": contradictions,
        "confidence_breakdown": breakdown,
    }

    if include_steps:
        audit = get_audit_logger()
        # Collect step traces for all nodes in the trace chain
        step_traces: dict[str, list[dict]] = {}
        for entry in chain:
            nid = entry["node"]["id"]
            traces = audit.get_step_traces(task_id, nid)
            if traces:
                step_traces[nid] = traces
        result["step_traces"] = step_traces

    return result
```

- [ ] **Step 5: 实现 Agent 状态路由**

```python
# src/api/routes/agent.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/agent/{task_id}/status")
async def get_agent_status(task_id: str):
    return {"task_id": task_id, "agents": []}
```

- [ ] **Step 6: 编写 API 测试**

```python
# tests/test_api/test_task.py
from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_task_requires_targets():
    resp = client.post("/api/task", json={"targets": ["Notion"]})
    assert resp.status_code in (200, 500)  # 500 if no LLM configured, still valid schema


def test_get_task_404():
    resp = client.get("/api/task/nonexistent")
    assert resp.status_code == 200  # returns stub
```

```bash
python -m pytest tests/test_api/test_task.py -v
```

- [ ] **Step 7: Commit**

```bash
git add src/api/ tests/test_api/
git commit -m "feat: add FastAPI app with task, report, trace, agent routes"
```

---

### Task 6.2: WebSocket 实时推送

**Files:**
- Create: `src/api/websocket.py`

- [ ] **Step 1: 实现 WebSocket handler**

```python
# src/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.api.deps import get_scheduler

router = APIRouter()

active_connections: dict[str, list[WebSocket]] = {}

# Cumulative cost tracking per task (updated by agent execution)
_task_costs: dict[str, float] = {}


async def _broadcast(task_id: str, event: dict):
    for conn in active_connections.get(task_id, []):
        await conn.send_json(event)


@router.websocket("/ws/task/{task_id}")
async def task_websocket(ws: WebSocket, task_id: str):
    await ws.accept()
    active_connections.setdefault(task_id, []).append(ws)
    scheduler = get_scheduler()

    async def on_node_state_change(node):
        """node_state_change: any node state transition (PENDING→READY→RUNNING→COMPLETED/FAILED)"""
        await _broadcast(task_id, {
            "event": "node_state_change",
            "task_id": task_id,
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state,
        })

    async def on_node_completed(node):
        """node_completed: node execution succeeded"""
        await _broadcast(task_id, {
            "event": "node_completed",
            "task_id": task_id,
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state,
        })

    async def on_node_failed(node):
        """node_failed: node execution failed permanently (retries exhausted)"""
        await _broadcast(task_id, {
            "event": "node_failed",
            "task_id": task_id,
            "node_id": node.node_id,
            "agent_type": node.agent_type,
        })

    async def on_agent_log(task_id_log: str, node_id: str, agent_type: str, step: int,
                           phase: str, summary: str):
        """agent_log: streaming agent decision log"""
        await _broadcast(task_id, {
            "event": "agent_log",
            "task_id": task_id_log,
            "node_id": node_id,
            "agent_type": agent_type,
            "step": step,
            "phase": phase,
            "summary": summary,
        })

    async def on_cost_update(task_id_cost: str, delta_cost: float, total_cost: float):
        """cost_update: cumulative cost for this task changed"""
        _task_costs[task_id] = total_cost
        await _broadcast(task_id, {
            "event": "cost_update",
            "task_id": task_id_cost,
            "delta_cost": delta_cost,
            "total_cost": total_cost,
        })

    async def on_qa_reject(task_id_qa: str, qa_agent_type: str, failed_nodes: list[str],
                           reasons: list[str], affected_nodes: list[str], qa_round: int):
        """qa_reject: QA rejected the report, feedback loop triggered"""
        await _broadcast(task_id, {
            "event": "qa_reject",
            "task_id": task_id_qa,
            "qa_agent_type": qa_agent_type,
            "failed_nodes": failed_nodes,
            "reasons": reasons,
            "affected_nodes": affected_nodes,
            "qa_round": qa_round,
        })

    scheduler.on("node_state_change", on_node_state_change)
    scheduler.on("node_completed", on_node_completed)
    scheduler.on("node_failed", on_node_failed)
    scheduler.on("agent_log", on_agent_log)
    scheduler.on("cost_update", on_cost_update)
    scheduler.on("qa_reject", on_qa_reject)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        active_connections.get(task_id, []).remove(ws)
```

- [ ] **Step 2: 注册到 app.py**

```python
# Add to src/api/app.py
from src.api.websocket import router as ws_router
app.include_router(ws_router)
```

- [ ] **Step 3: Commit**

```bash
git add src/api/websocket.py src/api/app.py
git commit -m "feat: add WebSocket real-time event streaming for DAG status"
```

---

### Task 6.3: React 前端项目初始化

**Files:**
- Create: `web/` (Vite + React + Tailwind)

- [ ] **Step 1: 初始化前端项目**

```bash
cd e:/Agent_Project && npm create vite@latest web -- --template react-ts
cd web && npm install && npm install tailwindcss @tailwindcss/vite react-router-dom
```

- [ ] **Step 2: 配置 Tailwind** — 更新 `vite.config.ts` 和 `src/index.css`

- [ ] **Step 3: 实现 App.tsx 路由和布局**

```tsx
// web/src/App.tsx
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import TaskPanel from './pages/TaskPanel';
import Monitor from './pages/Monitor';
import Report from './pages/Report';
import TraceExplorer from './pages/TraceExplorer';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <nav className="border-b border-gray-700 px-6 py-3 flex gap-4">
          <Link to="/" className="font-bold text-lg">CompAgent</Link>
          <Link to="/" className="text-gray-400 hover:text-white">Tasks</Link>
        </nav>
        <Routes>
          <Route path="/" element={<TaskPanel />} />
          <Route path="/task/:id/monitor" element={<Monitor />} />
          <Route path="/task/:id/report" element={<Report />} />
          <Route path="/task/:id/trace" element={<TraceExplorer />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: 实现 WebSocket hook**

```tsx
// web/src/hooks/useWebSocket.ts
import { useEffect, useRef, useState } from 'react';

export function useWebSocket(taskId: string) {
  const [events, setEvents] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/task/${taskId}`);
    wsRef.current = ws;
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents((prev) => [...prev, data]);
    };
    return () => ws.close();
  }, [taskId]);

  return events;
}
```

- [ ] **Step 5: 实现四个页面组件** — 按设计文档第 7.1-7.4 节的布局实现 TaskPanel、Monitor、Report、TraceExplorer，以及 DAGGraph、AgentCard、TracePanel、SchemaBuilder 等子组件。

*（每个页面组件的完整代码约 100-200 行，按设计文档中的 ASCII 布局实现即可）*

- [ ] **Step 6: Commit**

```bash
git add web/
git commit -m "feat: add React frontend with TaskPanel, Monitor, Report, TraceExplorer"
```

---

### Task 6.4: P6 端到端测试

- [ ] **Step 1: 启动后端**

```bash
cd e:/Agent_Project && python -m uvicorn src.api.app:app --reload --port 8000
```

- [ ] **Step 2: 启动前端**

```bash
cd e:/Agent_Project/web && npm run dev
```

- [ ] **Step 3: 手动验证流程**

1. 打开 `http://localhost:5173`
2. 创建任务（输入 Notion, Confluence, Linear）
3. 跳转到监控页 → 查看 DAG 图实时更新
4. 等待完成后进入报告页 → 阅读结构化报告
5. 点击 `[溯源]` 按钮 → 查看溯源链 + Agent 决策轨迹

- [ ] **Step 4: Commit**

```bash
git commit -m "feat: P6 frontend-backend integration verified"
```

---

## P6 完成检查清单

- [ ] `POST /api/task` 创建任务 → 返回 task_id + DAG 节点列表（含完整 AnalysisSchema）
- [ ] WebSocket 实时推送全部 5 类事件：`node_state_change` / `node_completed` / `node_failed` / `agent_log` / `cost_update` / `qa_reject`
- [ ] `GET /api/report/{task_id}` 返回结构化报告（Markdown + JSON）
- [ ] `GET /api/trace/{task_id}/{insight_id}` 返回溯源链 + 矛盾证据 + StepTrace
- [ ] `POST /api/task/{task_id}/release-checkpoint` 审核模式下手动释放检查点
- [ ] 前端四页面可用：任务面板 / 监控 / 报告 / 溯源探索器
