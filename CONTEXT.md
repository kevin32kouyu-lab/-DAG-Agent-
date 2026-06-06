# CONTEXT.md

## 当前正在做什么
已定位并修复 LLM 缓存大量未命中的主要原因：Agent 默认观察阶段不再把全库节点和随机任务 ID 发给 LLM，缓存默认有效期延长到 30 天。

## 上次停在哪个位置
本次验证已完成：Agent / Writer / 缓存相关测试 60 个通过；后端全量本地测试 293 个通过、24 个跳过，剩余 1 个外部依赖警告；用当前知识图谱模拟观察内容，节点数从全库 1353 个降为 0 个，观察文本约 178 字符，且不同 task_id 的观察内容一致。

## 近期关键决定和原因
- `src/agents/base.py` 未指定 `node_type` 或 `layer` 时不再调用 `store.query_nodes()` 读取全库，避免把历史报告节点塞进每次 LLM prompt。
- `src/agents/base.py` 发给 LLM 的 `task` 会隐藏 `task_id`、`node_id`、`context.task_id` 等随机字段，提高同类任务缓存命中率；工具执行仍保留真实 task_id。
- `src/llm_gateway/cache.py` 默认缓存有效期从 24 小时改为 30 天，并支持 `LLM_CACHE_TTL_SECONDS` 环境变量，避免跨天 Demo 重跑时重新消耗模型额度。
- 本次排查证据：当前知识图谱有 1353 个节点，其中 1228 个是历史 `ReportSection`；刚才任务 `task_3_40421cb4` 的 ReportGenerator / QA 两个节点每次约 36.7 万 token。
- `src/agents/writer.py` 图谱读取失败时会记录日志并生成本地兜底报告，避免报告兜底路径再次失败。
- `tests/test_agents/test_writer.py` 已覆盖 Writer 图谱读取失败时仍能返回兜底报告。
- `src/api/report_pdf.py` 中文字体注册失败时会记录日志并回退到 Helvetica，避免页脚继续使用失败字体导致 PDF 导出中断。
- `tests/test_api/test_report_pdf.py` 已覆盖 PDF 字体注册失败后的回退导出。
- `src/api/analytics_builder.py` 读取任务目标缓存失败时会记录日志并返回空列表，方便排查图表产品名缺失。
- `tests/test_api/test_analytics_modules.py` 已覆盖任务目标缓存损坏时的日志。
- `src/dag/executor.py` 遇到 Agent 模块导入失败或类名缺失时会返回清晰错误，保留原始异常链，方便排查懒加载配置问题。
- `tests/test_dag/test_executor.py` 已覆盖 Agent 模块导入失败和类名缺失两类错误提示。
- `src/dag/executor.py` 遇到未知 Agent 类型时会返回清晰错误，并列出可用 Agent 类型，方便排查 DAG 配置或 Orchestrator 输出问题。
- `tests/test_dag/test_executor.py` 和 `tests/test_agents/test_component.py` 已覆盖未知 Agent 类型错误提示。
- `src/dag/scheduler.py` 的人工检查点等待超时会记录日志，任务仍自动继续，方便排查 review mode 下无人确认但任务继续执行的原因。
- `tests/test_dag/test_scheduler.py` 新增检查点超时测试，覆盖 SourceDiscovery 检查点自动放行链路。
- `src/dag/scheduler.py` 的事件回调失败会记录日志，任务主流程继续执行，避免 WebSocket 或监控监听器异常拖垮 DAG。
- `tests/test_dag/test_scheduler.py` 新增事件回调失败测试，覆盖节点状态通知失败时任务仍能完成。
- `src/dag/scheduler.py` 的成本和采集页数更新失败会记录日志，任务主流程继续执行，方便排查监控页缺少成本数据的问题。
- `tests/test_dag/test_scheduler.py` 新增成本更新失败测试，覆盖监控统计依赖缺失时任务仍能完成。
- `src/dag/scheduler.py` 将快照读取拆成非阻塞步骤；读取失败时记录日志并从头执行任务，避免恢复点存储异常直接中断分析。
- `tests/test_dag/test_scheduler.py` 新增快照读取失败测试，覆盖“恢复点不可用但任务仍应执行”的链路。
- `src/dag/scheduler.py` 将节点完成后的快照写入拆成非阻塞步骤；保存失败只记录日志，不回滚节点完成状态。
- `tests/test_dag/test_scheduler.py` 新增快照保存失败测试，覆盖“执行成功但恢复点写入失败”的真实链路。
- `src/agents/orchestrator.py` 在补齐 ReportGenerator 和 QA 节点前会先过滤 LLM 返回的坏节点，避免部分坏节点让真实执行链路提前报错。
- `tests/test_agents/test_orchestrator.py` 新增真实执行链路测试，覆盖坏节点过滤后仍能补齐强制节点。
- `src/agents/orchestrator.py` 的 LLM DAG 输出无法解析时会记录日志，并继续按原流程返回空结果，方便定位任务为什么没有生成 DAG。
- `src/agents/orchestrator.py` 遇到字段不完整或类型错误的 DAG 节点时会记录跳过原因，不改变原有节点过滤逻辑。
- `tests/test_agents/test_orchestrator.py` 新增 Orchestrator 解析失败和坏节点跳过日志测试，覆盖 legacy DAG 规划入口。
- `src/agents/tools/web_tools.py` 的 Tavily 和 Wayback 兜底异常会记录日志，最终错误中也会带上兜底失败摘要，方便定位采集失败原因。
- `tests/test_agents/test_resilient_scrape.py` 新增 Tavily / Wayback 兜底异常日志测试，覆盖三层采集降级链路。
- `src/dag/feedback.py` 的反馈审计写入失败会记录日志，不再静默吞掉审计异常；节点重置、重跑和降级逻辑仍继续执行。
- `tests/test_dag/test_feedback.py` 新增反馈审计失败日志测试，覆盖 QA / Cross-Review 反馈链路的可观测性。
- `src/agents/base.py` 的步骤轨迹写入失败会记录日志，不再静默吞掉审计异常；Agent 主流程仍继续运行。
- `tests/test_agents/test_base.py` 新增审计写入失败日志测试，覆盖 Agent 溯源链路的可观测性。
- `src/llm_gateway/cache.py` 增加日志和连接上下文管理，SQLite 初始化、读取、写入失败时记录原因，主流程继续使用内存缓存。
- `tests/test_llm_gateway/test_cache.py` 改用临时缓存数据库，并覆盖缓存初始化、读取、写入失败日志。
- `tests/test_agents/test_base.py` 的测试辅助类从 `TestAgent` 改为 `DummyAgent`，避免 pytest 误收集产生警告。
- `web/src/components/Toast.tsx` 只保留提示渲染，`useToast` 拆到 `web/src/hooks/useToast.ts`，避免组件文件混合导出。
- `web/src/context/TaskContext.tsx` 只保留上下文 Provider，`useTaskContext` 拆到 `web/src/hooks/useTaskContext.ts`。
- `web/src/components/LoadingSkeleton.tsx` 使用固定宽度序列，不再在渲染时调用随机函数。
- `web/src/pages/TraceExplorer.tsx` 的溯源请求和状态更新拆开，去掉 `any` 和副作用表达式。
- `web/src/pages/Monitor.tsx` 的连接阶段改为派生显示状态，不再用额外 effect 同步改 phase。
- `web/src/App.tsx` 的页面路由改为懒加载，首屏不再一次性加载所有页面。
- `web/src/pages/Report.tsx` 中图表仪表盘改为懒加载，报告页正文和图表分开加载。
- `web/src/utils/export.ts` 的 PDF 导出改为请求后端 `/api/report/{task_id}?format=pdf`，前端删除 `html2pdf.js`，避免携带大体积 PDF 渲染库。
- `README.md` 和 `ARCHITECTURE.md` 已同步记录后端 PDF 生成、前端下载和图表按需加载。
- `src/api/routes/task.py` 中任务目标缓存读写已抽为 `_persist_task_targets`，缓存读取/写入失败会记录日志，不再静默吞掉异常。
- `src/api/routes/report.py` 中证据链读取已抽为 `_collect_evidence_sources`，读取失败会记录日志并返回空证据链。
- `src/api/websocket.py` 的广播失败会记录日志，并从连接池移除失效连接，避免监控页长期保留坏连接。
- `.gitignore` 明确忽略 `data/*.db`、`data/*.db-wal`、`data/*.db-shm` 和 `data/task_targets.json`，不删除现有运行数据。
- 新增 `tests/README.md`，说明默认后端测试、真实 LLM 测试和前端测试命令。
- 新增 `docs/README.md`，把日常文档入口和历史设计/计划文档分开。
- 当前仍超过 300 行的文件主要是页面组件、测试聚合和外部工具实现；本轮不为行数强拆，避免制造更多碎片文件。
- `src/api/routes/report.py` 从 513 行收缩到 266 行，PDF 生成逻辑迁移到 `src/api/report_pdf.py`。
- `src/api/analytics_builder.py` 从 518 行收缩到 128 行，只负责组织图表接口响应；结构化节点转换迁移到 `src/api/analytics_structured.py`，报告正文兜底解析迁移到 `src/api/analytics_fallback.py`。
- `tests/conftest.py` 统一跳过真实 LLM / smoke 测试，避免默认本地全量测试卡住或产生费用。
- `src/api/routes/report.py` 不再保留重复的图表数据构建函数，图表接口统一委托 `src/api/analytics_builder.py`。
- 前端行业选择只保留后端真实支持的 `saas` 和 `app`，避免用户选择后端不支持的行业。
- 高级配置只保留当前主流程实际对应的 5 个分析维度，移除“开发中”和自定义维度入口。
- 任务工具注册改为核心工具默认注册，深度分析时再加载新闻、Reddit、ProductHunt、趋势、社交媒体、天眼查等外部工具。
- 当前“复杂感”的主要来源不是单个 bug，而是生产级能力、真实 LLM 测试、演示兜底和前端展示改造同时存在。
- 优先可收缩方向：删除 `report.py` 中已迁移到 `analytics_builder.py` 的重复图表逻辑；前端只展示后端支持的行业；收起或删除未真实支撑的高级配置；外部数据源工具按场景注册；真实 LLM/诊断测试移出默认测试路径。
- 当前项目总体符合最早的核心预期：14 个 Agent、知识图谱、DAG、API/WebSocket、报告页、溯源和基础设施模块均已落地。
- 当前更接近“本地演示和功能验证”状态，不等同于完整生产部署；真实第三方 API、线上部署、监控和负载测试仍未覆盖。
- 展示型改造继续采用“作品集 Demo 化”：先讲报告结果，再展示技术细节。
- 默认演示固定为 3 个预设案例：AI 编程助手、项目管理工具、浏览器插件，降低首次体验的不确定性。
- 首页公开流程压成 4 阶段：资料收集、结构化分析、报告撰写、质量检查。
- 前端主体验改为专业咨询感：浅灰白背景、深色正文、深蓝/青绿强调色、小圆角和低阴影。
- 报告页优先展示报告、图表和“查看证据链”，DAG 和 Trace 保留为次级入口。
- 技术细节页只改展示层，不改 API、WebSocket、DAG、Trace 或报告生成逻辑；普通中文使用系统字体，ID、JSON、Token、成本等技术字段保留等宽字体。
- 不接入新的付费第三方 API；`ThirdPartyAPITool` 明确返回 `is_mock=true`、`data_source=mock` 和低可信说明，避免把 Demo 数据误认为真实来源。
- 依赖以 `pyproject.toml` 为主，补齐 `fpdf2`；`requirements.txt` 同步测试依赖，降低新环境缺包风险。
- 本次仍不包含生产部署、监控、负载测试和线上环境配置。
