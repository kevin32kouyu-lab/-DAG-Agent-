# Monitor 延迟优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 TaskPanel→Monitor 全链路的三段感知延迟，将 DAG 生成从同步等待改为异步 WebSocket 流式推送。

**Architecture:** POST /api/task 立即返回 task_id（0.1s），后台 asyncio 生成 DAG 后通过新 WS 事件 `dag_created` 推送完整结构。Monitor 新增 planning→executing 状态机，planning 阶段渲染 PipelineSkeleton 骨架动画。

**Tech Stack:** Python 3.12+ (FastAPI, asyncio), TypeScript (React 18, Tailwind CSS)

---

## File Map

| 文件 | 职责 | 改动 |
|------|------|------|
| `src/dag/scheduler.py` | 新增 `emit_dag_created`、`emit_dag_failed` 两个 emit 方法 | 修改 |
| `src/api/websocket.py` | 注册 dag_created/dag_failed 回调；`_send_dag_state` 空 DAG 时发送 planning 状态 | 修改 |
| `src/api/routes/task.py` | POST handler 改为立即返回 + `_plan_and_execute` 后台任务 | 修改 |
| `web/src/types.ts` | 新增 dag_created/dag_failed 事件类型；HistoryTask status 加 planning | 修改 |
| `web/src/index.css` | 新增 shimmer、fadeSlideUp、glow-green keyframes 和 utility classes | 修改 |
| `web/src/components/PipelineSkeleton.tsx` | 骨架占位组件，8 行 shimmer + 轮播文案 | **创建** |
| `web/src/pages/Monitor.tsx` | 四阶段状态机；处理 dag_created/dag_failed；planning 态渲染骨架 | 修改 |
| `web/src/components/DAGGraph.tsx` | 节点动画（running 呼吸、completed 辉光、入场 stagger） | 修改 |
| `web/src/pages/TaskPanel.tsx` | HistoryTask status 类型扩展 + StatusBadge 支持 planning | 修改 |

---

### Task 1: DAGScheduler 新增 emit 方法

**Files:**
- Modify: `src/dag/scheduler.py:85`

- [ ] **Step 1: 在 `_emit_cost_update` 之后添加 `emit_dag_created` 和 `emit_dag_failed`**

在 `_emit_cost_update` 方法之后（第 101 行 `pass` 行之后）添加：

```python
    async def emit_dag_created(self, task_id: str, dag) -> None:
        """Push full DAG structure to all WS clients when DAG generation completes."""
        self._dag_registry[task_id] = dag
        nodes_payload = []
        for node in dag.nodes:
            nodes_payload.append({
                "node_id": node.node_id,
                "agent_type": node.agent_type,
                "state": node.state if hasattr(node.state, 'value') else str(node.state),
                "depends_on": node.depends_on,
            })
        await self._emit("dag_created", task_id, nodes_payload)

    async def emit_dag_failed(self, task_id: str, error: str) -> None:
        """Notify WS clients that DAG generation failed."""
        await self._emit("dag_failed", task_id, error)
```

- [ ] **Step 2: 运行现有 scheduler 测试确认无回归**

```bash
python -m pytest tests/test_dag/ -v --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add src/dag/scheduler.py
git commit -m "feat: add emit_dag_created and emit_dag_failed to DAGScheduler"
```

---

### Task 2: WebSocket 注册新事件回调

**Files:**
- Modify: `src/api/websocket.py:37-163`
- Modify: `src/api/websocket.py:166-189` (`_send_dag_state`)

- [ ] **Step 1: 在 `_ensure_callbacks_registered` 末尾添加 dag_created/dag_failed 回调**

在 `scheduler.on("checkpoint_released", ...)` 之后（第 163 行）添加：

```python
    async def on_dag_created(task_id: str, nodes: list[dict]):
        await _broadcast(task_id, {
            "event": "dag_created",
            "task_id": task_id,
            "nodes": nodes,
            "total_cost": _task_costs.get(task_id, 0.0),
            "total_tokens": _task_tokens.get(task_id, 0),
            "pages_collected": _task_pages.get(task_id, 0),
        })

    async def on_dag_failed(task_id: str, error: str):
        await _broadcast(task_id, {
            "event": "dag_failed",
            "task_id": task_id,
            "error": error,
        })

    scheduler.on("dag_created", on_dag_created)
    scheduler.on("dag_failed", on_dag_failed)
```

- [ ] **Step 2: 修改 `_send_dag_state` 处理 DAG 不存在的情况**

将 `_send_dag_state` 函数（第 166-189 行）中的 `if dag is None: return` 改为发送 planning 状态：

```python
async def _send_dag_state(ws: WebSocket, task_id: str) -> None:
    """Send full DAG state snapshot so reconnecting clients can restore UI."""
    scheduler = get_scheduler()
    dag = scheduler.get_task_dag(task_id)
    if dag is None:
        await ws.send_json({
            "event": "dag_state",
            "task_id": task_id,
            "nodes": [],
            "status": "planning",
            "total_cost": _task_costs.get(task_id, 0.0),
            "total_tokens": _task_tokens.get(task_id, 0),
            "pages_collected": _task_pages.get(task_id, 0),
        })
        return
    nodes_state = []
    for node in dag.nodes:
        nodes_state.append({
            "node_id": node.node_id,
            "agent_type": node.agent_type,
            "state": node.state,
            "depends_on": node.depends_on,
            "retries": node.retries,
            "error": node.context.get("error", ""),
        })
    await ws.send_json({
        "event": "dag_state",
        "task_id": task_id,
        "nodes": nodes_state,
        "total_cost": _task_costs.get(task_id, 0.0),
        "total_tokens": _task_tokens.get(task_id, 0),
        "pages_collected": _task_pages.get(task_id, 0),
    })
```

- [ ] **Step 3: Commit**

```bash
git add src/api/websocket.py
git commit -m "feat: add dag_created/dag_failed WS callbacks and planning reconnect state"
```

---

### Task 3: task.py 异步 DAG 生成

**Files:**
- Modify: `src/api/routes/task.py:1-83`

- [ ] **Step 1: 重构 —— 提取 `_build_tools` 辅助函数，添加 `_plan_and_execute` 后台任务**

将 `create_task` 函数和整个文件替换为以下结构：

```python
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
    scheduler = get_scheduler()
    try:
        orch = OrchestratorAgent(gateway=gateway, store=store, tool_registry=tools)
        dag, _ = await orch.execute({
            "task_id": task_id,
            "targets": req.targets,
            "schema": req.model_dump(),
        })

        if dag is None:
            await scheduler.emit_dag_failed(task_id, "LLM 无法生成 DAG — 请重试")
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
```

- [ ] **Step 2: 运行 task route 相关测试**

```bash
python -m pytest tests/ -k "task" -v --tb=short
```

- [ ] **Step 3: Commit**

```bash
git add src/api/routes/task.py
git commit -m "feat: async DAG generation — POST /api/task returns immediately, WS streams dag_created"
```

---

### Task 4: types.ts 新增事件类型

**Files:**
- Modify: `web/src/types.ts:135-208`
- Modify: `web/src/types.ts:212-219`

- [ ] **Step 1: 扩展 WSEventType，新增 dag_created/dag_failed 接口，更新 WSEvent union**

在 `WSEventType`（第 135 行）中加入新事件类型：

```typescript
export type WSEventType =
  | 'node_state_change'
  | 'node_completed'
  | 'node_failed'
  | 'agent_log'
  | 'cost_update'
  | 'qa_reject'
  | 'dag_state'
  | 'dag_created'
  | 'dag_failed';
```

在 `WSDagState` 接口之后（第 199 行之后）添加新接口：

```typescript
export interface WSDagCreated extends WSBaseEvent {
  event: 'dag_created';
  nodes: Array<{
    node_id: string;
    agent_type: AgentType;
    state: NodeState;
    depends_on: string[];
  }>;
  total_cost: number;
  total_tokens: number;
  pages_collected: number;
}

export interface WSDagFailed extends WSBaseEvent {
  event: 'dag_failed';
  error: string;
}
```

更新 `WSEvent` union type（第 201-208 行）：

```typescript
export type WSEvent =
  | WSNodeStateChange
  | WSNodeCompleted
  | WSNodeFailed
  | WSAgentLog
  | WSCostUpdate
  | WSQAReject
  | WSDagState
  | WSDagCreated
  | WSDagFailed;
```

- [ ] **Step 2: 扩展 HistoryTask status 支持 planning**

修改 `HistoryTask` 接口（第 212 行）：

```typescript
export interface HistoryTask {
  id: string;
  time: string;
  targets: string;
  targetsArr?: string[];
  status: 'completed' | 'running' | 'failed' | 'planning';
  duration: string;
}
```

- [ ] **Step 3: 运行 TypeScript 类型检查**

```bash
cd web && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add web/src/types.ts
git commit -m "feat: add dag_created/dag_failed WS types and planning history status"
```

---

### Task 5: index.css 新增动画 keyframes

**Files:**
- Modify: `web/src/index.css:41-89`

- [ ] **Step 1: 在 keyframes 区域末尾（第 44 行之后）添加新 keyframes**

```css
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}

@keyframes glowGreen {
  0%, 100% { filter: drop-shadow(0 0 2px #22c55e); }
  50%      { filter: drop-shadow(0 0 6px #22c55e); }
}
```

- [ ] **Step 2: 在 utility classes 区域末尾（第 87 行之后）添加 utility classes**

```css
.animate-shimmer {
  background: linear-gradient(90deg, #1f2937 25%, #374151 50%, #1f2937 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

.animate-fadeSlideUp {
  animation: fadeSlideUp 0.4s ease-out both;
}

.animate-glowGreen {
  animation: glowGreen 0.5s ease-in-out 2;
}
```

- [ ] **Step 3: 扩展 stagger delays 到 17 个（覆盖完整 DAG 节点数）**

将 `web/src/index.css:79-88` 的 `.stagger-item:nth-child(...)` 从 10 条扩展到 17 条：

```css
.stagger-item:nth-child(1)  { animation-delay: 0ms; }
.stagger-item:nth-child(2)  { animation-delay: 30ms; }
.stagger-item:nth-child(3)  { animation-delay: 60ms; }
.stagger-item:nth-child(4)  { animation-delay: 90ms; }
.stagger-item:nth-child(5)  { animation-delay: 120ms; }
.stagger-item:nth-child(6)  { animation-delay: 150ms; }
.stagger-item:nth-child(7)  { animation-delay: 180ms; }
.stagger-item:nth-child(8)  { animation-delay: 210ms; }
.stagger-item:nth-child(9)  { animation-delay: 240ms; }
.stagger-item:nth-child(10) { animation-delay: 270ms; }
.stagger-item:nth-child(11) { animation-delay: 300ms; }
.stagger-item:nth-child(12) { animation-delay: 330ms; }
.stagger-item:nth-child(13) { animation-delay: 360ms; }
.stagger-item:nth-child(14) { animation-delay: 390ms; }
.stagger-item:nth-child(15) { animation-delay: 420ms; }
.stagger-item:nth-child(16) { animation-delay: 450ms; }
.stagger-item:nth-child(17) { animation-delay: 480ms; }
```

- [ ] **Step 4: Commit**

```bash
git add web/src/index.css
git commit -m "feat: add shimmer, fadeSlideUp, glowGreen keyframes and extend stagger to 17 items"
```

---

### Task 6: 创建 PipelineSkeleton 组件

**Files:**
- Create: `web/src/components/PipelineSkeleton.tsx`

- [ ] **Step 1: 创建组件**

```tsx
import { useState, useEffect } from 'react';

const ROWS = [
  { label: '编排', width: '60%' },
  { label: '源发现', width: '40%' },
  { label: '采集', width: '75%' },
  { label: '富化', width: '35%' },
  { label: '分析', width: '80%' },
  { label: '互审', width: '30%' },
  { label: '综合', width: '25%' },
  { label: '撰写 + QA', width: '50%' },
];

const MESSAGES = [
  '正在分析目标产品...',
  '正在规划 Agent 协作流程...',
  'DeepSeek 正在生成执行方案...',
];

export default function PipelineSkeleton() {
  const [msgIdx, setMsgIdx] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setMsgIdx(prev => (prev + 1) % MESSAGES.length);
    }, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 space-y-5">
      {/* header */}
      <div className="flex items-center gap-3">
        <div className="w-4 h-4 rounded-full border-2 border-cyan-500 border-t-transparent animate-spin" />
        <span className="text-gray-300 text-sm font-medium">正在规划分析流程...</span>
      </div>

      {/* skeleton rows */}
      <div className="space-y-2.5">
        {ROWS.map((row, i) => (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-gray-600 font-mono w-16 text-right shrink-0">
              {row.label}
            </span>
            <div
              className="h-5 rounded animate-shimmer"
              style={{ width: row.width }}
            />
          </div>
        ))}
      </div>

      {/* rotating status */}
      <p
        key={msgIdx}
        className="text-xs text-gray-500 font-mono text-center animate-fadeIn"
      >
        {MESSAGES[msgIdx]}
      </p>
    </div>
  );
}
```

- [ ] **Step 2: 确认 TypeScript 编译**

```bash
cd web && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/PipelineSkeleton.tsx
git commit -m "feat: add PipelineSkeleton component with shimmer animation and rotating status"
```

---

### Task 7: Monitor.tsx 状态机 + 新事件处理

**Files:**
- Modify: `web/src/pages/Monitor.tsx:1-267`

- [ ] **Step 1: 添加 phase 状态和新事件处理**

修改 Monitor 组件，在现有 state 变量后添加 phase 状态：

```tsx
// 在 dagNodes state 之后（第 44 行）添加：
const [phase, setPhase] = useState<'connecting' | 'planning' | 'executing' | 'done'>('connecting');
```

修改 `useEffect` 中的 WebSocket 连接状态同步逻辑（第 47-50 行），让 WS 连接成功后根据是否有 DAG 数据决定 phase：

```tsx
useEffect(() => {
  setWsConnected(connectionStatus === 'connected');
  if (connectionStatus === 'connected' && phase === 'connecting') {
    setPhase('planning');
  }
  return () => { setWsConnected(false); };
}, [connectionStatus, setWsConnected, phase]);
```

在事件处理 switch 中添加 `dag_created` 和 `dag_failed`（在 `dag_state` case 之后，约第 117 行）：

```tsx
case 'dag_created': {
  const nodes = (evt as { nodes?: Array<{ node_id: string; agent_type: string; state: NodeState; depends_on: string[] }> }).nodes ?? [];
  const agentMap = new Map<string, AgentState>();
  const dagList: DAGNode[] = [];
  for (const n of nodes) {
    agentMap.set(n.node_id, {
      node_id: n.node_id,
      agent_type: n.agent_type as AgentType,
      state: n.state,
      progress: 0,
    });
    dagList.push({
      node_id: n.node_id,
      agent_type: n.agent_type as AgentType,
      depends_on: n.depends_on,
      state: n.state,
    });
  }
  setAgents(agentMap);
  setDagNodes(dagList);
  setTotalCost((evt as { total_cost?: number }).total_cost ?? 0);
  setTotalTokens((evt as { total_tokens?: number }).total_tokens ?? 0);
  setPagesCollected((evt as { pages_collected?: number }).pages_collected ?? 0);
  setPhase('executing');
  break;
}

case 'dag_failed':
  setPhase('done');
  toast(`DAG 规划失败: ${(evt as { error?: string }).error || '未知错误'}`, 'error');
  break;
```

- [ ] **Step 2: 替换 Empty state 为 planning 骨架态**

将第 226-230 行的空状态：

```tsx
{agentList.length === 0 && (
  <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center text-gray-600 font-mono text-sm">
    等待 Agent 启动... (WebSocket {connectionStatus === 'connected' ? '已连接' : '等待连接'})
  </div>
)}
```

改为 planning / connecting 的二态 UI：

```tsx
{phase === 'planning' && agentList.length === 0 && (
  <PipelineSkeleton />
)}

{phase === 'connecting' && (
  <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center text-gray-600 font-mono text-sm">
    <span className="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse mr-2" />
    正在连接 WebSocket...
  </div>
)}
```

导入 PipelineSkeleton（文件顶部 import 区域）：

```tsx
import PipelineSkeleton from '../components/PipelineSkeleton';
```

- [ ] **Step 3: 确保 `dag_state` 在 re-connect 时能正确处理 planning 态**

在 `dag_state` case 中（第 91 行），当 nodes 为空数组时保持在 planning 阶段：

在 `dag_state` case 的 nodes 提取后添加：

```tsx
case 'dag_state':
  {
    const nodes = (evt as { nodes?: Array<...> }).nodes ?? [];
    if (nodes.length === 0) {
      setPhase('planning');
      break;
    }
    setPhase('executing');
    // ... 其余 dag_state 处理逻辑保持不变
  }
```

- [ ] **Step 4: 运行 TypeScript 类型检查**

```bash
cd web && npx tsc --noEmit
```

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/Monitor.tsx
git commit -m "feat: add planning→executing state machine and dag_created/dag_failed event handling to Monitor"
```

---

### Task 8: DAGGraph 节点动画

**Files:**
- Modify: `web/src/components/DAGGraph.tsx:113-171`

- [ ] **Step 1: 节点 rect 加动画 class，running/completed 加状态样式**

修改 SVG 节点渲染部分（第 142-157 行），给 `<g>` 加 `stagger-item animate-fadeSlideUp`，给 `<rect>` 加状态动画：

```tsx
{layout.map(ln => {
  const color = STATE_COLORS[ln.node.state] || '#6b7280';
  const short = AGENT_SHORT[ln.node.agent_type] || ln.node.agent_type.slice(0, 6);
  const isRunning = ln.node.state === 'running';
  const isCompleted = ln.node.state === 'completed';
  return (
    <g key={ln.node.node_id} className="stagger-item animate-fadeSlideUp">
      {isCompleted && (
        <rect
          x={ln.x - 38} y={ln.y - 12}
          width={76} height={24} rx={4}
          fill="none" stroke="#22c55e" strokeWidth={1.5}
          className="animate-glowGreen"
        />
      )}
      <rect
        x={ln.x - 36} y={ln.y - 10}
        width={72} height={20} rx={4}
        fill="#111827" stroke={color} strokeWidth={1}
        className={isRunning ? 'animate-pulse' : ''}
        style={{ transition: 'stroke 0.4s ease' }}
      />
      <circle
        cx={ln.x - 28} cy={ln.y} r={3}
        fill={color}
        style={{ transition: 'fill 0.3s ease' }}
      />
      <text x={ln.x - 20} y={ln.y + 4} fill="#d1d5db" fontSize={9} fontFamily="monospace">
        {short}
      </text>
    </g>
  );
})}
```

- [ ] **Step 2: 空态文案更新为更友好的提示**

将第 121 行 SVG 中的 `DAG 节点为空 — 请创建分析任务` 改为：

```tsx
<text x={width / 2} y={height / 2} textAnchor="middle" fill="#6b7280" fontSize={12} fontFamily="monospace">
  等待分析流程规划完成...
</text>
```

- [ ] **Step 3: 运行 TypeScript 类型检查**

```bash
cd web && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/DAGGraph.tsx
git commit -m "feat: add DAGGraph node animations — fadeSlideUp entry, running pulse, completed glow"
```

---

### Task 9: TaskPanel 支持 planning 历史状态

**Files:**
- Modify: `web/src/pages/TaskPanel.tsx:312-354`

- [ ] **Step 1: StatusBadge 已支持 planning 状态 —— 检查是否需要更新**

先检查 StatusBadge 组件：

```bash
grep -n "planning\|StatusBadge" web/src/components/StatusBadge.tsx
```

如果 StatusBadge 没有 planning case，执行 Step 2；否则跳过。

- [ ] **Step 2: 更新 StatusBadge 支持 planning**

修改 `web/src/components/StatusBadge.tsx:9-16`，在 `STATUS_CONFIG` 中添加 planning：

```tsx
const STATUS_CONFIG: Record<string, { label: string; classes: string }> = {
  completed: { label: '✓ 完成', classes: 'text-green-400 bg-green-400/10 border-green-400/30' },
  running:   { label: '◐ 运行中', classes: 'text-amber-400 bg-amber-400/10 border-amber-400/30' },
  failed:    { label: '✕ 失败', classes: 'text-red-400 bg-red-400/10 border-red-400/30' },
  pending:   { label: '○ 等待', classes: 'text-gray-500 bg-gray-500/10 border-gray-500/30' },
  ready:     { label: '◉ 就绪', classes: 'text-blue-400 bg-blue-400/10 border-blue-400/30' },
  degraded:  { label: '⚠ 降级', classes: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/30' },
  planning:  { label: '◌ 规划中', classes: 'text-cyan-400 bg-cyan-400/10 border-cyan-400/30' },
};
```

同时在 `StatusDot` 函数（第 30 行）的 colors 中加 planning：

```tsx
const colors: Record<string, string> = {
  completed: 'bg-green-500',
  running: 'bg-amber-500 animate-pulse',
  failed: 'bg-red-500',
  pending: 'bg-gray-600',
  ready: 'bg-blue-500',
  degraded: 'bg-yellow-600',
  planning: 'bg-cyan-500 animate-pulse',
};
```

- [ ] **Step 3: 确认前端编译**

```bash
cd web && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/TaskPanel.tsx web/src/components/StatusBadge.tsx
git commit -m "feat: add planning status to StatusBadge and TaskPanel history"
```

---

### Task 10: 端到端验证

- [ ] **Step 1: 启动后端并测试 DAG 异步生成**

```bash
# 启动服务器
python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000 &

# 创建任务
curl -s -X POST http://127.0.0.1:8000/api/task \
  -H "Content-Type: application/json" \
  -d '{"targets": ["Notion"], "industry": "saas"}'
# 预期：立即返回 {"task_id":"...","status":"planning","dag_nodes":[],"ws_endpoint":"..."}

# 等待 10s 后检查任务状态
sleep 10
TASK_ID=$(curl -s -X POST http://127.0.0.1:8000/api/task \
  -H "Content-Type: application/json" \
  -d '{"targets": ["Figma"], "industry": "saas"}' | python -c "import sys,json;print(json.load(sys.stdin)['task_id'])")

sleep 12
curl -s http://127.0.0.1:8000/api/task/$TASK_ID
# 预期：status 为 running 或 in_progress，nodes 非空
```

- [ ] **Step 2: 运行完整后端测试套件**

```bash
python -m pytest tests/ -v --tb=short --ignore=tests/test_agents/test_live_deepseek.py
```

- [ ] **Step 3: 运行前端类型检查**

```bash
cd web && npx tsc --noEmit
```

- [ ] **Step 4: 在浏览器中手动验证**

启动前端 `cd web && npm run dev`，打开浏览器：
1. 输入目标产品 → 点击"开始分析"
2. 确认几乎立即跳转到 Monitor 页面
3. 确认看到 PipelineSkeleton 骨架动画 + 轮播文案
4. 等待 `dag_created` 推送后，确认 DAG 图和 Agent 卡片带入场动画渲染
5. 确认节点状态动画正常运行

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: end-to-end verification complete — async DAG + streaming UI"
```
