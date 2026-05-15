# Monitor 延迟优化设计

## 问题

用户在 TaskPanel 点击"开始分析"后感知到三段明显等待：

1. **延迟 ①（5-15s）**：POST /api/task 同步等待 LLM 生成 DAG，按钮一直转圈
2. **延迟 ②（1-3s）**：跳转到 Monitor 后等待 WebSocket 首个事件，页面空白
3. **延迟 ③（10-30s/节点）**：Agent 串行执行，节点逐个更新，间隔长

根因：DAG 生成是同步 LLM 调用，且 POST 响应中已有的 dag_nodes 数据未被 Monitor 利用。

## 方案：异步 DAG 生成 + WebSocket 流式推送

### 架构变更

```
现状:  TaskPanel → POST(等LLM 5-15s) → 返回dag_nodes → navigate → Monitor → WS连接 → dag_state → 渲染
目标:  TaskPanel → POST(0.1s立即返回) → navigate → Monitor → WS连接 → planning骨架 → dag_created → 渲染DAG → 执行
```

核心：把 LLM 生成 DAG 从同步请求-响应改为后台异步 + WebSocket 推送。

---

## 后端改动

### 1. `src/api/routes/task.py`

POST /api/task 不再同步等待 LLM：

- 立即返回 `{task_id, status: "planning", ws_endpoint}`（~0.1s）
- `asyncio.create_task(_plan_and_execute(...))` 后台执行
- 新增 `_plan_and_execute` 函数：生成 DAG → 推送 dag_created → 启动 scheduler.run()

提取 `_build_tools` 辅助函数避免重复。

### 2. `src/dag/scheduler.py`

新增两个方法：

- `emit_dag_created(task_id, dag)` — 推送完整 DAG 结构给所有 WS 客户端
- `emit_dag_failed(task_id, error)` — DAG 生成失败时通知

### 3. `src/api/websocket.py`

新增两个回调注册：

- `on_dag_created(task_id, nodes)` — 广播 dag_created 事件
- `on_dag_failed(task_id, error)` — 广播 dag_failed 事件

`_send_dag_state` 保持不变（断线重连恢复用）。

---

## 前端改动

### 1. `TaskPanel.tsx`

- POST 不再阻塞 5-15s，自然受益，无需大改
- 新增历史状态"规划中"（status: "planning"）

### 2. `Monitor.tsx` — 核心改动

新增四阶段状态机：

| 阶段 | 触发条件 | UI |
|------|----------|-----|
| `connecting` | 初始 / WS 断开 | 状态栏红色脉冲 |
| `planning` | WS 已连接，等待 dag_created | PipelineSkeleton 骨架 + 文案 |
| `executing` | 收到 dag_created | DAG 图 + Agent 卡片 + 日志 |
| `done` | 全部完成或失败 | toast 通知 |

新增事件处理：
- `dag_created` → 从 nodes 数组构建 agents Map + dagNodes → setPhase('executing')
- `dag_failed` → toast 错误 + setPhase('done')

planning 态的 PipelineSkeleton：显示 8 行 Agent 分组骨架，逐行渐亮动画，底部文案轮播。

### 3. `PipelineSkeleton.tsx`（新文件）

骨架组件：
- 8 行分组模拟（编排 → 源发现 → 采集 → 富化 → 分析 → 互审 → 撰写 → QA）
- CSS shimmer 动画逐行扫描
- 底部文案：3s 轮播一次（"正在分析目标产品..." / "正在规划协作流程..." / "即将完成..."）

### 4. `DAGGraph.tsx`

- running 节点：CSS 呼吸动画（`animate-pulse`）
- completed 节点：500ms 绿色辉光（`filter: drop-shadow`）
- DAG 图初次渲染：节点带 stagger 的 fadeSlideUp 入场动画

### 5. `types.ts`

新增事件类型：
- `dag_created`：`{event, task_id, nodes: DAGNode[]}`
- `dag_failed`：`{event, task_id, error: string}`

### 6. `index.css`

新增 keyframes：
- `shimmer` — 骨架扫描光
- `fadeSlideUp` — 节点入场
- `glow-green` — 完成辉光

---

## 边缘情况

- **planning 阶段 WS 断开**：重连后 `_send_dag_state` 恢复。若 DAG 仍未生成（dag=None），前端保持 planning 态
- **dag_failed**：停止骨架动画，显示错误 + "返回重试"按钮
- **planning 阶段刷新页面**：`_send_dag_state` 逻辑不变，dag 为 None 时返回空 → 前端保持 planning
- **DAG 生成超时（>30s）**：骨架文案轮播暗示系统仍在工作，无超时中断

---

## 涉及文件

| 层级 | 文件 | 改动类型 |
|------|------|----------|
| 后端 | `src/api/routes/task.py` | 重构 POST handler，新增 `_plan_and_execute` |
| 后端 | `src/dag/scheduler.py` | 新增 `emit_dag_created`、`emit_dag_failed` |
| 后端 | `src/api/websocket.py` | 新增 dag_created/dag_failed 回调 |
| 前端 | `web/src/pages/TaskPanel.tsx` | 新增 planning 历史状态 |
| 前端 | `web/src/pages/Monitor.tsx` | 四阶段状态机 + 新事件处理 |
| 前端 | `web/src/components/PipelineSkeleton.tsx` | **新文件** |
| 前端 | `web/src/components/DAGGraph.tsx` | 节点动画 |
| 前端 | `web/src/types.ts` | 新事件类型 |
| 前端 | `web/src/index.css` | 新 keyframes |

## 不改动

- Agent 执行逻辑
- DAG 模型 / scheduler 核心循环
- WebSocket 重连机制
- 后端其他 route（report / trace / agent）
