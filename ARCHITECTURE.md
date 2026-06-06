# ARCHITECTURE.md

## 文件/模块职责
- `src/knowledge_graph/`：保存采集、分析和报告节点，是报告与仪表盘的数据来源。
- `src/agents/`：按职责运行采集、分析、写作、复核等 Agent。
- `src/agents/orchestrator.py`：把用户任务规划成 DAG，LLM 输出无法解析或坏节点被跳过时记录日志，并在补齐强制节点前过滤坏节点。
- `src/agents/base.py`：提供所有 Agent 的基础执行循环和步骤轨迹写入；默认观察内容不预加载全库节点，也不把随机任务 ID 发给 LLM。
- `src/agents/writer.py`：生成最终报告；图谱读取失败时记录日志并使用本地兜底报告，避免报告任务二次失败。
- `src/agents/tools/graph_tools.py`：给 Agent 查询和写入知识图谱，默认按当前 `_task_id` 隔离数据。
- `src/agents/tools/web_tools.py`：提供网页搜索、单页抓取和批量抓取；直接抓取失败时依次尝试 Tavily 和 Wayback 兜底。
- `src/llm_gateway/cache.py`：缓存 LLM 响应，默认保留 30 天；SQLite 不可用时记录日志并降级为内存缓存。
- `src/api/deps.py`：集中创建后端共享依赖；默认 LLM 模型可通过 `LLM_DEFAULT_MODEL` 切换，并按 OpenAI-compatible 方式调用。
- `src/dag/`：编排任务节点执行顺序，记录每个任务的目标产品和运行状态；快照、成本更新、事件回调和检查点超时都会记录日志。
- `src/dag/executor.py`：把 DAG 节点映射到具体 Agent；未知 Agent、模块导入失败和类名缺失都会返回可读错误，方便排查 DAG 配置。
- `src/dag/feedback.py`：处理 QA 和 Cross-Review 反馈，审计写入失败时记录日志但不阻塞节点重置或降级。
- `src/api/routes/report.py`：提供报告正文和仪表盘接口入口。
- `src/api/report_pdf.py`：把报告章节转换成 PDF 文件，中文字体注册失败时记录日志并回退到 Helvetica。
- `src/api/analytics_builder.py`：从当前任务的知识图谱节点构建仪表盘数据，缺少结构化节点时从当前任务报告正文做低可信度兜底推断；任务目标缓存读取失败时记录日志。
- `src/api/routes/task.py`：创建和推进分析任务。
- `web/src/components/charts/AnalyticsDashboard.tsx`：展示仪表盘图表，并提示数据来源。
- `web/src/demoContent.ts`：集中保存预设 Demo、四阶段流程和可信度说明文案。
- `web/src/components/DemoStageStrip.tsx`：展示对外演示的四个固定阶段。
- `web/src/pages/TaskPanel.tsx`：首页入口，优先展示预设案例和自定义分析。
- `web/src/pages/Report.tsx`：报告阅读页，优先展示报告、图表和证据链。
- `web/src/components/Toast.tsx`：只负责渲染全局提示，提示上下文和 hook 拆分到独立文件。
- `web/src/context/TaskContext.tsx`：只负责提供任务上下文状态，读取 hook 拆分到 `web/src/hooks/useTaskContext.ts`。
- `web/src/hooks/useToast.ts`、`web/src/hooks/useTaskContext.ts`：提供前端共享状态的读取入口，避免组件文件混合导出。
- `web/src/utils/export.ts`：处理 Markdown、JSON 和 PDF 下载，其中 PDF 从后端接口获取。
- `web/src/utils/markdown.ts`：把报告正文 Markdown 渲染成 HTML，包含表格渲染。
- `web/src/types.ts`：定义前端接口数据类型。

## 调用关系
- 前端报告页调用 `/api/report/{task_id}` 获取正文，调用 `/api/report/{task_id}/analytics` 获取图表数据，导出 PDF 时调用 `/api/report/{task_id}?format=pdf`。
- 前端首页读取 `demoContent.ts` 中的预设案例，点击后按现有 `/api/task` 接口创建任务。
- `/api/report/{task_id}/analytics` 只负责路由转发，具体数据组装交给 `src/api/analytics_builder.py`。
- `analytics_builder.py` 优先读取当前任务的结构化知识图谱节点；如果没有可用结构化图表数据，再读取当前任务的 `ReportSection` 正文解析兜底。
- Agent 通过 `GraphQueryTool` 查询知识图谱时默认只看到当前 `_task_id` 的节点，避免报告生成和 QA 阶段读取历史任务残留。
- Agent 默认观察阶段只提供稳定任务输入，不再读取整个知识图谱；需要图谱数据时由 `GraphQueryTool` 按当前任务隔离读取。

## 关键设计决定
- 历史数据不删除，问题通过任务隔离修复，避免影响已有记录。
- 图表数据优先级固定为：当前任务结构化节点 → 当前任务报告正文推断 → 空数据和 warning。
- 报告正文兜底只用于展示，不写回知识图谱，避免把推断内容当成证据。
- Writer 图谱读取失败时必须返回本地兜底报告并记录日志，避免报告生成兜底路径再次失败。
- PDF 中文字体注册失败不阻塞导出，但必须切回 Helvetica 并记录日志，避免页脚继续使用失败字体。
- 图表任务目标缓存读取失败不阻塞仪表盘返回，但必须记录日志，方便解释产品名缺失。
- Agent 步骤轨迹写入失败不阻塞分析流程，但必须记录日志，避免溯源缺失时无从排查。
- QA / Cross-Review 反馈审计失败不阻塞节点重跑和降级，但必须记录日志，避免反馈链路无记录。
- DAG 快照系统只负责恢复能力，不决定主流程成败；读取失败时从头执行，保存失败时保留已完成节点状态，并记录日志。
- DAG 成本和采集页数更新只服务监控展示；更新失败不影响任务完成，但必须记录日志，避免监控页缺数据时无从排查。
- DAG 事件回调用于 WebSocket 和监控展示；单个回调失败不影响节点状态推进，但必须记录日志。
- 人工检查点超时会自动放行任务，必须记录日志，方便解释 review mode 下任务为什么继续执行。
- DAG 执行器遇到未知 Agent、模块导入失败或类名缺失时必须给出清晰错误，避免只暴露内部映射表或懒加载异常。
- 网页抓取兜底失败不阻塞最终错误返回，但 Tavily 和 Wayback 异常必须记录日志，方便判断采集失败原因。
- Orchestrator 的 LLM 规划失败或节点字段不完整不改变原有兜底流程，但必须记录日志；强制节点补齐前先过滤坏节点，避免部分坏节点打断完整 DAG 生成。
- LLM 缓存失败不阻塞主流程，但初始化、读取和写入失败都要记录日志，避免静默失效。
- LLM 缓存默认保留 30 天，可用 `LLM_CACHE_TTL_SECONDS` 调整，避免跨天 Demo 重跑时重新消耗模型额度。
- LLM 缓存 key 不应包含随机任务 ID；BaseAgent 发给 LLM 的观察内容会隐藏 `task_id`、`node_id` 等易变字段，提高重复任务命中率。
- 默认 LLM 不再写死 DeepSeek；`.env` 中的 `LLM_DEFAULT_MODEL`、`OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 决定实际接入的 OpenAI-compatible 服务。
- `include_all=True` 只作为调试入口保留，正常 Agent 查询不使用全库数据。
- 对外展示优先讲报告结果，DAG、Trace 和 Agent 细节保留为次级入口。
- PDF 导出统一放在后端生成，前端不再携带大体积 PDF 渲染库。
- 第三方付费 API 未接入时只返回低可信 Demo 降级数据，并明确标记为 mock。
