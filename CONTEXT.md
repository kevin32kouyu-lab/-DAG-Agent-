# CONTEXT.md

## 当前正在做什么
自研 Agent DAG 平台引擎第一阶段改造已完成：工作流模板、DAG 编译器、调度器元数据、任务 API 模板化路由全部实现并通过测试。

## 上次停在哪个位置
Phase 1 所有 7 个 Task 已完成并提交：
- Task 1: DAG 模型扩展（REJECTED/RERUNNING 状态 + platform metadata 字段）
- Task 2: 工作流模板注册表（SaaS + App 两个模板）
- Task 3: DAG 编译器（确定性转换，不依赖 LLM）
- Task 4: 调度器事件元数据 + WebSocket 向后兼容
- Task 5: 任务 API 默认 template 模式，保留 orchestrator 为显式 legacy
- Task 6: 集成测试 + 回放测试验证
- Task 7: 全量验证通过

## 近期关键决定和原因
- 一键报告默认使用确定性模板编译 DAG（`planning_mode="template"`），保留 Orchestrator 为显式 legacy 选项
- WebSocket `dag_created` 协议保持向后兼容，旧字段不丢失
- output_contract 名称已对齐 contracts.py 实际类名
- MockExecutor 使用强类型 stub 而非依赖静默异常
- QA 节点在模板中串行化（fact_check → logic_check），比 Orchestrator 的并行模式更合理
