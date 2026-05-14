# AI 驱动的竞品分析 Agent 协作系统 — 设计文档

**日期**: 2026-05-14
**状态**: Draft
**版本**: v1.0

---

## 1. 概述

### 1.1 目标

构建一个 AI 驱动的竞品分析 Agent 协作系统，通过多个专职 Agent 协同工作，自动完成从公开信息采集到结构化竞品报告输出的全链路。系统强调溯源能力（每条结论可追溯到原始数据）和可观测性（每个 Agent 的决策过程与中间产物完全透明）。

### 1.2 核心原则

- **知识图谱是唯一真相源（Single Source of Truth）**：Agent 不直接通信，一切通过图谱读写
- **Agent 是独立决策单元**：每个 Agent 拥有自己的工具集、上下文窗口和 ReAct 决策循环
- **DAG 编排只管调度，不管业务逻辑**：Agent 是纯函数式执行单元（输入=图谱查询，输出=图谱写入）
- **溯源 = 图谱遍历**：从结论节点沿 `derived_from` 边反向 BFS 还原推导链

### 1.3 Demo 范围

聚焦 SaaS 行业，以 Notion、Confluence、Linear 三款协作工具为目标进行竞品分析。架构预留行业扩展能力（通过 YAML 行业模板）。

---

## 2. 系统架构

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────┐
│                     Web UI (React)                       │
│  任务面板 │ 报告预览 │ 溯源钻取 │ Agent 状态监控          │
└──────────────────────┬──────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────┴──────────────────────────────────┐
│                   API Gateway (FastAPI)                   │
│              /task  /report  /trace  /agent              │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│               DAG Orchestrator (自研核心)                  │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐     │
│   │ 任务解析  │→│ 依赖分析  │→│ 并行调度 + 状态机 │     │
│   └──────────┘  └──────────┘  └──────────────────┘     │
│                     ↓ 反馈边                              │
│              质检触发上游局部重跑                           │
└──────────────────────┬──────────────────────────────────┘
                       │ 读写
┌──────────────────────┴──────────────────────────────────┐
│          Knowledge Graph (竞品知识图谱)                    │
│   ProductNode / FeatureNode / MetricNode / SourceNode   │
│                 ↑ 所有结论均关联 Source 边 ↑               │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│                   Agent 执行层                            │
│  14 个 Agent 实例（13 专职 + 1 编排），各自独立 ReAct 循环     │
│  ┌────────────────────────────────────────────────────┐ │
│  │              LLM Gateway (多模型)                   │ │
│  │    Claude  │  GPT  │  可扩展其他模型                 │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### 2.2 企业基础设施层

基础设施层位于 DAG Orchestrator 和 Agent 执行层之下，提供任务调度、容错、成本控制、安全隔离等横切能力。它不参与业务逻辑，但对系统能否在生产环境稳定运行起决定性作用。

```
┌──────────────────────────────────────────────────────────────┐
│                    企业基础设施层                              │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   任务队列     │  │   LLM 网关   │  │    审计日志       │  │
│  │              │  │              │  │                  │  │
│  │ • 多任务并行  │  │ • 多模型路由  │  │ • 每次 LLM 调用   │  │
│  │ • Agent级重试 │  │ • 速率限制    │  │ • 每次工具调用    │  │
│  │ • 优先级调度  │  │ • 语义缓存    │  │ • 每次图谱写入    │  │
│  │ • 超时控制    │  │ • 成本追踪    │  │ • 操作时间戳      │  │
│  │              │  │ • 降级策略    │  │ • 关联 task_id   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   断点续传    │  │ Agent Registry│  │    采集缓存       │  │
│  │              │  │              │  │                  │  │
│  │ • 节点级快照  │  │ • 装饰器注册  │  │ • URL 内容哈希   │  │
│  │ • 中断可恢复  │  │ • 依赖声明    │  │ • 24h 去重窗口   │  │
│  │ • 不重跑已完成│  │ • 输出契约    │  │ • robots.txt     │  │
│  │ • PG/SQLite  │  │ • 模型等级    │  │ • 速率控制       │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   配置中心    │  │   安全层     │  │   健康检查        │  │
│  │              │  │              │  │                  │  │
│  │ • 模型配置    │  │ • API Key    │  │ • Agent 心跳     │  │
│  │ • 行业模板    │  │   隔离存储   │  │ • 任务超时检测    │  │
│  │ • 动态开关    │  │ • 输入消毒    │  │ • 资源使用监控    │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**各组件说明与作用**：

| 组件 | 技术选型 | 解决的问题 | 实现要点 |
|------|---------|-----------|---------|
| 任务队列 | Redis + arq | 多用户同时提交分析任务时不能阻塞 | Agent 任务入队、优先级排序、超时自动重试 |
| LLM 网关 | litellm + 自定义 wrapper | 多模型切换、成本失控、重复调用浪费 | 统一 `/chat/completions` 接口，按 Agent 等级路由到不同模型；语义缓存避免相同输入重复调用 |
| 断点续传 | PostgreSQL / SQLite | 长时间分析任务中断后无需全部重跑 | 每个 DAG 节点 COMPLETED 时写入快照（task_id, node_id, state, kg_changeset），恢复时跳过已完成节点 |
| Agent Registry | Python 装饰器 | 新增 Agent 类型不应修改 DAG 引擎代码 | `@agent_registry.register()` 声明式注册，包含依赖、工具集、输出契约、模型等级 |
| 采集缓存 | Redis + 内容哈希 | 相同 URL 被多个 Agent 重复采集浪费时间和费用 | URL + 内容 SHA256 去重，24h 窗口，遵守 robots.txt |
| 审计日志 | PostgreSQL | 出问题时无法追溯是哪个 Agent 哪一步出错 | 两层日志：task_audit_log（DAG 节点级）+ step_traces（ReAct 步骤级），含完整 prompt/response 快照 |
| 配置中心 | YAML + env | 模型切换、行业模板、实验性功能需要动态控制 | 支持热加载，无需重启服务 |
| 安全层 | 环境变量 + 输入校验 | API Key 泄露、注入攻击 | Key 存储在 .env，不进入代码仓库；用户输入经过 Pydantic 校验和消毒 |

### 2.2.1 数据源获取与降级策略

公开数据源的可用性不稳定（G2 反爬、Reddit API 收紧、ProductHunt 限制）。系统为每类数据源定义三级降级路径，获取失败时自动降级，确保分析任务不会因单一数据源不可用而中断。

| 数据源 | 主路径 | 降级 Tier 1 | 降级 Tier 2 | 完全不可用时 |
|--------|--------|------------|------------|-------------|
| **G2** | 网页采集（评分 + 评论摘要） | 仅提取公开评分（首页星级，无需登录） | 使用搜索引擎缓存摘要 | 标记 G2 数据缺失，报告中注明"第三方评价数据不足"，依赖官网信息弥补 |
| **ProductHunt** | 网页采集公开页面 | 使用 ProductHunt RSS | 跳过 | 影响较小——PH 数据在 B2B 分析中权重较低 |
| **Reddit** | 搜索摘要（不调用完整 API） | 搜索引擎 `site:reddit.com` 结果片段 | 跳过 | 降权或排除 Reddit 信息源，增加 G2 / TrustRadius 权重补偿 |
| **官网** | httpx 直接请求 | Google 缓存 / Wayback Machine | 使用 Trustpilot/第三方页面中的产品描述替代 | 该产品标记为 `DATA_DEGRADED`，对比维度中缺失数据项标注"N/A" |
| **新闻/RSS** | RSS 订阅 + 网页采集 | 搜索引擎 `News` tab 结果 | 跳过 | 仅影响"行业动态"类分析，不影响核心功能/定价对比 |
| **第三方 API** (SimilarWeb/Crunchbase) | API 调用 | 公开数据替代（Alexa 排名/公开融资信息） | 跳过 | Data Enricher 输出节点数减少，综合层以其内部数据为准 |

**降级对分析质量的影响**：

```
数据源全部正常:
  置信度基线: 0.8–0.95
  溯源边密度: 高

1–2 个数据源进入 Tier 1 降级:
  置信度基线: 0.7–0.85
  溯源边密度: 中
  → 报告中标注使用了降级数据源

任意数据源进入 Tier 2 降级或完全不可用:
  置信度基线: 0.5–0.7
  溯源边密度: 低
  → 受影响的分析维度在报告中标注"⚠ 数据受限，建议人工补充"
  → QA Agent 对该维度的结论降低权重

所有降级事件记录于 audit_log:
  {event: "source_degraded", source: "G2", tier: 1, reason: "HTTP 403", fallback_used: "公开评分摘要"}
```

**说明**：降级策略确保系统不会因数据源不可用而崩溃。每个 Collector 执行时自动尝试主路径 → Tier 1 → Tier 2，最终失败则在图谱中创建 SourceInfo 节点并标记 `availability: "degraded"`。下游分析 Agent 和 QA Agent 根据数据可用性调整结论置信度。这符合真实竞品分析的工作方式——分析师在数据不完整时也会给出结论，但会标注不确定性。

---


## 3. Agent 体系

### 3.1 Agent 列表（1 个编排 Agent + 10 个专职 Agent + 1 个交叉审查 Agent + 2 个 QA Agent = 14 个 Agent 实例）

| # | Agent | 角色 | 核心职责 |
|---|-------|------|---------|
| 0 | **Orchestrator** | 任务指挥官 | 理解目标，拆分任务，生成初始 DAG，动态调整 |
| 1 | **Source Discovery** | 信息源侦察 | 搜索所有目标产品 + 评估信息源可信度，筛选高质量源（单实例处理所有产品，避免同源重复请求） |
| 2 | **Collector (×N)** | 并行采集兵 | 网页抓取、API 调用、结构化提取 |
| 3 | **Data Enricher** | 语境补充 | 关联第三方数据（SimilarWeb/Crunchbase），补充行业背景 |
| 4 | **Feature Analyzer** | 功能拆解 | 功能矩阵对比、迭代节奏分析 |
| 5 | **Sentiment Analyzer** | 市场感知 | 用户评价情感分析、口碑趋势 |
| 6 | **Pricing Analyst** | 定价分析 | 定价模型拆解、性价比评分、目标客群推断 |
| 7 | **TechStack Analyzer** | 技术栈推断 | 推断产品技术栈、架构特征 |
| 8 | **Market Position** | 定位分析 | 市场定位、GTM 策略分析 |
| 9 | **Cross-Review Agent** | 水平交叉审查 | 审查分析 Agent 之间的结论一致性，发现矛盾、遗漏和置信度异常 |
| 10 | **SWOT Synthesizer** | 战略综合 | 聚合所有分析 + 交叉审查结果，生成 SWOT 矩阵 |
| 11 | **Writer** | 报告撰写 | 从图谱生成结构化 Markdown 报告 |
| 12 | **QA #1** | 事实核查 | 核验每条结论的溯源链完整性、数据准确性 |
| 13 | **QA #2** | 逻辑一致性 | 核验报告内论点无矛盾、推理链无断裂 |

### 3.2 Agent 通用接口

每个 Agent 实现统一契约：

```python
class BaseAgent:
    agent_type: str           # Agent 类型标识
    tools: list[Tool]         # 可用工具集（爬虫、图谱读写、搜索等）
    context: AgentContext     # 短时记忆：当前任务的上下文

    async def execute(self, task: AgentTask) -> AgentOutput:
        """ReAct 循环：Observe → Think → Act → Observe → ..."""
        ...
```

### 3.3 Agent 内部架构

每个 Agent 是独立的决策单元，核心由五部分组成：

```
┌────────────────────── Agent 内部架构 ──────────────────────┐
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │                  ReAct Decision Loop                 │ │
│  │                                                     │ │
│  │   ┌──────────┐    ┌──────────┐    ┌──────────┐     │ │
│  │   │ Observe  │───→│  Think   │───→│   Act    │     │ │
│  │   │ 读取图谱  │    │ LLM推理  │    │ 调用工具  │     │ │
│  │   │ 读取上下文│    │ 选择行动  │    │ 写入图谱  │     │ │
│  │   └──────────┘    └──────────┘    └──────────┘     │ │
│  │        ↑                               │            │ │
│  │        └───────────────────────────────┘            │ │
│  │                 循环至任务完成或最大步数               │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                            │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Tool        │  │ Context     │  │ Output Contract  │  │
│  │ Registry    │  │ Window      │  │ (Pydantic Model) │  │
│  │             │  │             │  │                  │  │
│  │ • 图谱查询   │  │ • 当前任务   │  │ • 输出 Schema    │  │
│  │ • 图谱写入   │  │ • 历史对话   │  │ • 必填字段       │  │
│  │ • 网页采集   │  │ • 中间产物   │  │ • 验证规则       │  │
│  │ • 搜索 API  │  │ • Token预算  │  │                  │  │
│  │ • 第三方 API│  │             │  │                  │  │
│  └─────────────┘  └─────────────┘  └──────────────────┘  │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │                 审计与可观测性                         │ │
│  │  • 每次 LLM 调用记录: prompt / response / tokens / cost │
│  │  • 每次工具调用记录: tool_name / input / output / time  │
│  │  • 每次图谱写入记录: nodes_created / edges_created       │
│  └──────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────┘
```

**ReAct 循环伪代码（含 Step-level trace 记录）**：

```python
async def execute(self, task: AgentTask) -> AgentOutput:
    self.context.init(task)
    trace_writer = StepTraceWriter(task.task_id, self.node_id, self.agent_type)
    
    for step in range(self.max_steps):  # 默认最大 15 步
        # 1. Observe: 从图谱读取当前状态
        observation = await self.graph.query(task.input_query)
        await trace_writer.record_observe(
            step=step,
            summary=summarize(observation),
            nodes_read=observation.node_ids
        )
        
        # 2. Think: LLM 推理下一步行动
        thought = await self.llm.think(
            system=self.system_prompt,
            context=self.context.history,
            observation=observation,
            available_tools=self.tools.describe(),
            output_schema=self.output_contract.schema_json()
        )
        await trace_writer.record_think(
            step=step,
            reasoning=thought.reasoning,       # Agent 的思考过程
            confidence=thought.confidence,      # Agent 对当前判断的置信度
            prompt=thought.prompt,              # 完整的 LLM prompt
            response=thought.raw_response,      # 完整的 LLM response
            tokens=thought.tokens,
            cost=thought.cost
        )
        
        # 3. Act: 执行工具调用
        if thought.action == "finalize":
            # 验证输出是否符合 contract
            output = self.output_contract.validate(thought.result)
            await trace_writer.record_finalize(
                step=step,
                output_summary=summarize(output),
                nodes_created=output.node_ids,
                edges_created=output.edge_ids
            )
            return output
        else:
            result = await self.tools.execute(thought.action, thought.params)
            self.context.add(thought, result)
            await self.audit.log(thought, result)
            await trace_writer.record_act(
                step=step,
                action=thought.action,
                params=thought.params,
                result_summary=summarize(result)
            )
    
    raise MaxStepsExceeded(f"{self.agent_type} 超出最大步数")
```

**StepTrace 数据结构 —— 实现"中间产物完全透明"的核心**：

题目要求"每一个 Agent 的决策过程与中间产物都完全透明"。图谱节点只能展示 Agent 的最终产出（创建了哪些节点），但 Agent **为什么**做出这个决定、**经过了几步推理**、**中间考虑过但放弃的方案**——这些决策过程需要 StepTrace 来暴露。

```python
class StepTrace(BaseModel):
    """Agent 执行过程中每一步的完整记录"""
    task_id: str
    node_id: str                       # DAG 节点 ID
    agent_type: str
    step_number: int                   # 第几步（从 0 开始）
    timestamp: datetime
    
    # Observe 阶段：Agent 看到了什么
    observation_summary: str           # 观察摘要（图谱查询结果概述）
    data_nodes_read: list[str]         # 读取了哪些图谱节点 ID
    
    # Think 阶段：Agent 如何思考
    reasoning: str                     # LLM 的推理过程（why 这个决定）
    confidence: float | None           # Agent 对当前判断的置信度
    prompt_snapshot: str | None        # 完整 LLM prompt（可展开查看）
    response_snapshot: str | None      # 完整 LLM response（可展开查看）
    
    # Act 阶段：Agent 做了什么
    action: str                        # 调用的工具名（或 "finalize"）
    action_params: dict | None         # 工具参数
    action_result_summary: str | None  # 工具返回结果概述
    
    # 产出（仅 finalize 步骤有值）
    nodes_created: list[str]           # 创建的图谱节点 ID
    edges_created: list[str]           # 创建的图谱边 ID
    
    # 成本
    llm_tokens: int
    llm_cost: float
    
    # 存储于 PostgreSQL step_traces 表
    # 查询: SELECT * FROM step_traces WHERE task_id=$tid AND node_id=$nid ORDER BY step_number
```

**StepTrace 的三个透明层次**：

```
层次 1: "Agent 产出了什么"          → 图谱节点 + 边（已有）
层次 2: "Agent 经过了几步推理"      → StepTrace 列表（每个 step 的 observe→think→act）
层次 3: "Agent 为什么这样决定"      → StepTrace.reasoning（LLM 推理过程的完整记录）
层次 4: "Agent 看到了什么原始数据"   → StepTrace.prompt_snapshot + response_snapshot（完整可展开）
```

**说明**：StepTrace 让系统的"完全透明"从口号变为可审计的事实。用户可以逐步骤复盘任意 Agent 的决策过程——就像查看飞机的黑匣子。这在以下场景至关重要：(1) 分析结果出问题时定位是哪个推理步骤出错；(2) 合规审计要求证明 AI 决策过程可追溯；(3) 产品经理理解 Agent 的"思考逻辑"以改进分析质量。

**Agent Registry 插件机制**：

```python
# 新 Agent 通过装饰器注册，零侵入
@agent_registry.register(
    agent_type="FeatureAnalyzer",
    industry="saas",
    depends_on=["DataEnricher"],
    tools=[GraphQuery, GraphWrite, WebSearch],
    output_contract=FeatureMatrixOutput,
    model_tier="analysis"  # 决定使用哪个 LLM 等级
)
class FeatureAnalyzer(BaseAgent):
    system_prompt = "..."
    max_steps = 10
```

### 3.4 Agent 独立性

- 每个 Agent 独立运行在自己的 ReAct 循环中，有自己的 Tool Registry
- Agent 间不直接通信，仅通过知识图谱的读写间接协作
- 新 Agent 通过装饰器注册到 AgentRegistry，零侵入扩展
- 每个 Agent 的输出由 Pydantic Contract 强校验，不合规输出不会写入图谱

### 3.5 交叉审查机制 —— 从"最终 QA 把关"到"全程水平互审"

题目要求的"交叉审查反馈闭环"不应只是 QA 审查最终报告。真实的调研小组中，分析师之间会互相 challenge 对方的推理——定价分析师发现功能分析师遗漏了关键功能、情感分析师的数据与功能分析师的结论矛盾。系统需要在 DAG 中嵌入**水平交叉审查边**，而不只有垂直的 QA 审查。

**审查层次对比**：

```
                        垂直审查（已有）
                        ═══ QA #1 / QA #2 ═══
                               ↓ 审查
                        ┌─────────────┐
                        │   Writer     │
                        │   SWOT       │
                        └─────────────┘
                               ↑
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
  Feature Analyzer    Sentiment Analyzer    Pricing Analyst  ...
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
              ← ← ← 水平交叉审查（新增）→ → →
              Cross-Review Agent 在分析层与综合层之间
              检查分析 Agent 之间的结论一致性
```

**Cross-Review Agent 的工作机制**：

Cross-Review Agent 在所有分析 Agent 完成后、SWOT Synthesizer 之前运行。它读取图谱中所有 Layer 2 分析节点的输出，执行三类检查：

| 检查类型 | 检测内容 | 处理方式 |
|---------|---------|---------|
| **矛盾检测** | 两个分析 Agent 对同一产品/维度得出矛盾结论 | 标记冲突节点，创建 `contradicts` 边，由 Orchestrator 决定是否触发局部重分析 |
| **遗漏检测** | Agent A 基于的数据中包含了 Agent B 遗漏的关键信息 | 将遗漏信息转发给 Agent B，触发 Agent B 补充分析（增量，不重跑） |
| **置信度异常** | 某 Agent 的结论置信度很高但溯源边很少，或结论与用户关注点偏离 | 标记为"需人工复核"，降低该结论在最终报告中的权重 |

**交叉审查执行流程**：

```
1. 所有分析 Agent 完成 → Cross-Review Agent 被调度

2. Cross-Review Agent 遍历图谱:
   for each product in targets:
       for each dimension_pair in analysis_dimensions:
           # 检查矛盾
           conflicts = detect_conflicts(agent_a.output, agent_b.output)
           for conflict in conflicts:
               graph.create_edge(conflict, type="contradicts")
               graph.create_node(CrossReviewFlag, {
                   agents: [agent_a, agent_b],
                   conflict_description: "...",
                   severity: "high" | "medium" | "low"
               })

3. 如果 severity=high 的矛盾:
   → DAG 反馈边触发: 重置涉及的两个分析 Agent 为 PENDING
   → Agent 重跑时 context 中包含冲突说明: "你与 X Agent 在 Y 结论上存在矛盾，请重新审视"
   → 最多触发 1 轮交叉重跑（不同于 QA 的 2 轮）

4. 如果 severity=medium/low 的矛盾:
   → 创建 CrossReviewFlag 节点，但不触发重跑
   → SWOT Synthesizer 和 Writer 在综合时需考虑这些 flag
   → 报告中标注: "⚠ 分析 Agent 之间在此结论上存在分歧"
```

**DAG 中交叉审查的位置**：

```
FeatureAnalyzer  SentimentAnalyzer  PricingAnalyst  TechStack  MarketPosition
        │              │                  │              │           │
        └──────────────┼──────────────────┼──────────────┼───────────┘
                       │                  │              │
                       ↓                  ↓              ↓
                 ┌──────────────────────────────────────────┐
                 │        Cross-Review Agent                │
                 │                                         │
                 │  • 矛盾检测: Pricing vs Sentiment        │
                 │  • 遗漏检测: Feature 有新功能但 Pricing  │
                 │    未分析其定价影响                       │
                 │  • 置信度检查: TechStack 证据薄弱        │
                 └────────────┬─────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │ 发现 high 矛盾?    │
                    ├────────┬──────────┤
                    │ YES    │ NO       │
                    ↓        │          │
              局部重分析      │          │
              (max 1轮)      ↓          ↓
                         SWOT Synthesizer
                              │
                          Writer
                              │
                         QA #1 / QA #2
```

**与 QA 审查的关系**：

| 维度 | Cross-Review (水平) | QA (垂直) |
|------|-------------------|----------|
| 审查对象 | 分析 Agent 之间的结论一致性 | 最终报告的溯源完整性 + 逻辑正确性 |
| 审查时机 | 分析层完成，综合层之前 | 报告撰写完成之后 |
| 反馈方式 | 触发局部重分析（1 轮）或标记 flag | 触发局部重跑（2 轮）或标记 DEGRADED |
| 关注点 | "分析团队内部是否有分歧" | "最终报告是否可靠" |
| 用户可见 | 报告中标注分析分歧点 | 报告置信度评分 |

**说明**：交叉审查是"模拟真实数字调研小组"的关键机制——真实团队中分析师之间会互相阅读对方的产出并挑战不一致之处，而不是各自写完交给主编汇总。加入 Cross-Review Agent 后，反馈闭环从"QA → Writer"的单点审查，升级为"分析 Agent ↔ 分析 Agent → SWOT → Writer → QA"的网状审查。

---

## 4. 知识图谱 Schema（SaaS 行业）

知识图谱是所有 Agent 的唯一真相源（Single Source of Truth）。Agent 不直接通信，一切协作通过图谱的读写间接完成。Schema 按认知层级分为三层：原始数据层 → 分析层 → 综合层，高层节点通过 `derived_from` 边关联低层节点，形成完整的溯源链条。

### 4.1 三层节点体系

```
Layer 3: 综合层     ┌─────────┐  ┌─────────┐  ┌──────────┐
  (Synthesis)       │  SWOT   │  │ Scoring │  │  Report  │
                    │  Node   │  │  Node   │  │ Section  │
                    └────┬────┘  └────┬────┘  └────┬─────┘
                         │            │            │
                    ─────┼────────────┼────────────┼─────
Layer 2: 分析层         │            │            │
  (Analysis)    ┌───────┴──┐ ┌──────┴──────┐ ┌───┴───────┐
                │ Feature  │ │  Sentiment  │ │  Pricing  │
                │ Matrix   │ │  Analysis   │ │  Model    │
                └────┬─────┘ └──────┬──────┘ └─────┬──────┘
                     │              │               │
                ─────┼──────────────┼───────────────┼─────
Layer 1: 原始层      │              │               │
  (Raw Data)  ┌──────┴──────┐ ┌────┴─────┐ ┌───────┴──────┐
              │  Web Page   │ │  Review  │ │  Pricing     │
              │  (官网/博客) │ │  Entry   │ │  Data        │
              └──────┬──────┘ └────┬─────┘ └──────┬───────┘
                     │              │               │
                     └──────────────┼───────────────┘
                                    │
                           ┌────────┴────────┐
                           │   Source Info   │  ← 所有原始数据节点的元节点
                           │  URL / 可信度    │
                           │  采集时间戳      │
                           └─────────────────┘
```

**说明**：三层体系的核心设计理念是"认知分层，逐级溯源"。Layer 1 保留原始数据的完整语义（不做加工），Layer 2 由分析 Agent 生成结构化洞察（必须声明 derived_from），Layer 3 由综合 Agent 聚合为报告级别的结论。QA Agent 通过检查 derived_from 边的完整性来验证每一条结论的可信性——缺少溯源边的结论被视为"无据推断"，报告中将标记为低置信度。

### 4.2 节点类型定义

**原始层（Layer 1）— 由 Collector 和 Source Discovery 生成**：

| 节点类型 | 字段 |
|---------|------|
| `SourceInfo` | url, domain, credibility_score, crawl_time |
| `WebPage` | url, title, text, key_paragraphs[] |
| `ReviewEntry` | source, rating, text, date, verified |
| `PricingData` | plan_name, price, billing_cycle, features[] |
| `SocialPost` | platform, author, content, engagement, date（SaaS 模板默认不启用；适用 B2C 行业） |
| `NewsArticle` | source, title, summary, date |
| `MetricData` | source, metric_name, value, unit, date |

**分析层（Layer 2）— 由各分析 Agent 生成**：

| 节点类型 | 字段 |
|---------|------|
| `FeatureNode` | name, category, description, maturity, differentiation |
| `FeatureMatrix` | dimensions[], matrix: product→feature→status |
| `SentimentNode` | topic, sentiment_score, trend, key_quotes[] |
| `PricingModel` | strategy, target_segment, value_score, comparison |
| `TechStack` | languages, frameworks, infra, confidence |

**综合层（Layer 3）— 由 SWOT Synthesizer 和 Writer 生成**：

| 节点类型 | 字段 |
|---------|------|
| `SWOTNode` | strengths[], weaknesses[], opportunities[], threats[] |
| `ScoringNode` | dimension, score, weight, rationale |
| `InsightNode` | insight, importance, evidence_chain[] |
| `ReportSection` | section, content, order |

### 4.3 边类型（溯源链路核心）

| 边类型 | 方向 | 含义 |
|--------|------|------|
| `derived_from` | 分析→原始 | 核心溯源边，声明分析节点的数据来源 |
| `supports` | 证据→论点 | 正向支撑边，证据支持该结论 |
| `contradicts` | 证据→论点 | 负向矛盾边，证据削弱该结论（QA 重点检查） |
| `related_to` | 节点↔节点 | 节点间的语义关联 |
| `cites` | 报告→节点 | 报告对分析/原始节点的引用关系 |

### 4.4 Schema Builder — 用户自定义分析框架

题目要求"自定义竞品知识 Schema"，意味着分析维度不能由系统预设死。行业模板（saas.yaml）提供的是起点，用户应在创建任务时能够增删改分析维度、定义关注点、调整评分权重。Schema Builder 是这一能力的入口。

**设计原则**：行业模板 = 默认起点，用户自定义 = 运行时覆盖。用户不改则用默认，改了则以用户为准。

**Schema 自定义的范围**：

| 可自定义项 | 说明 | 示例 |
|-----------|------|------|
| 分析维度 | 从预设维度池中选择，或新建自定义维度 | 已启用（9 个）：功能矩阵、定价策略、用户口碑、技术栈、市场定位、AI 能力、API 生态、客户支持、产品迭代速度；后续扩展（6 个）：安全合规、Onboarding 体验、移动端体验、开源策略、国际化程度、团队规模 |
| 关注点 | 每个维度下的具体分析问题，决定分析的深度和角度 | 定价维度下：免费版限制条件、升级路径设计、隐藏成本、竞品价格锚定策略、大客户折扣 |
| 维度权重 | 调整各维度在综合评分中的权重 | 用户关心的核心是定价和 AI → 定价 40%、AI 30%、其他均分 30% |
| 信息源优先级 | 指定优先采集的信息源或排除特定源 | 优先 G2 + ProductHunt；排除 Reddit（噪音）；最低可信度阈值 0.6 |
| 对比基准 | 指定以哪个产品为基准进行对比 | "以 Notion 为基准，其他产品与其对比" |
| 采集深度 | 控制每个信息源的采集粒度 | 官网：仅产品页 / 含博客和文档；G2：仅最新 50 条 / 全部评论 |
| 报告语气与受众 | 报告的写作风格和目标读者 | 面向产品经理 / 面向投资人 / 面向工程师 |
| 报告结构 | 自定义报告章节顺序和内容 | 只关心定价和功能，跳过技术栈；或自定义章节标题 |
| 输出格式 | 报告的导出格式偏好 | Markdown / JSON |

**Schema 定义数据结构**：

```python
class AnalysisSchema(BaseModel):
    """用户自定义分析 Schema，创建任务时提交"""
    
    # 基础信息
    industry: str = "saas"                    # 行业模板（必选）
    targets: list[str]                        # 目标产品列表
    
    # 自定义维度（覆盖行业模板默认值）
    dimensions: list[Dimension] = []          # 用户自定义的分析维度
    exclude_dimensions: list[str] = []        # 要跳过的默认维度
    
    # 自定义字段（追加到现有节点类型）
    custom_fields: dict[str, list[FieldDef]] = {}  
    # 例: {"FeatureNode": [{"name": "ai_score", "type": "float", "range": [0,10]}]}
    
    # 权重调整
    dimension_weights: dict[str, float] = {}  # 维度权重覆盖
    
    # 信息源配置
    source_preferences: SourcePrefs = SourcePrefs()
    
    # 对比配置
    benchmark_product: str | None = None      # 以哪个产品为基准
    
    # 报告配置
    report_audience: str = "product_manager"  # 报告受众: product_manager / investor / engineer
    report_sections: list[str] = []           # 自定义报告章节（空=使用默认）
    output_formats: list[str] = ["markdown"]  # 输出格式: markdown / pdf / json


class Dimension(BaseModel):
    """用户自定义的分析维度"""
    name: str                                 # 维度名称
    description: str                          # 该维度分析什么
    focus_points: list[str] = []              # 关注点：该维度下要重点分析的具体问题
    node_types: list[str]                     # 关联的节点类型
    agent_type: str                           # 负责分析的 Agent
    prompt_override: str | None = None        # 自定义分析 Prompt
    weight: float = 1.0                       # 该维度的权重


class SourcePrefs(BaseModel):
    """信息源偏好"""
    priority_sources: list[str] = []          # 优先采集的域名/平台
    excluded_sources: list[str] = []          # 排除的域名/平台
    min_credibility: float = 0.5              # 最低可信度阈值
    collection_depth: str = "standard"        # 采集深度: shallow / standard / deep
    # shallow: 仅首页+定价页; standard: 含产品页+文档; deep: 含博客+所有子页面


class FieldDef(BaseModel):
    """自定义字段定义"""
    name: str
    type: str                                # "str" | "int" | "float" | "enum" | "bool"
    description: str
    enum_values: list[str] | None = None     # type=enum 时的可选值
    range: tuple[float, float] | None = None # type=float/int 时的值域
```

**Schema → Agent 的自适应机制**：

Schema 不是静态文档，它直接影响每个 Agent 的行为：

```
用户提交自定义 Schema
        │
        ↓
  Orchestrator Agent
    │  读取 dimensions[] → 决定启动哪些分析 Agent
    │  读取 dimensions[].focus_points[] → 注入到 Agent 的分析 Prompt 中
    │  读取 exclude_dimensions[] → 跳过对应 Agent
    │  读取 source_preferences → 约束 Source Discovery 的搜索范围
    │  读取 benchmark_product → 注入到所有分析 Agent 的 context
    │  读取 dimension_weights → 传递给 Scoring Agent 计算加权分
    │  读取 report_audience → 传递给 Writer Agent 调整写作风格
    │  输出: 定制化的 DAG 拓扑（维度越多节点越多，排除的维度不生成为对应 Agent）
        │
        ↓
  各分析 Agent 执行时:
    │  context.schema.dimensions → 知道自己要分析什么
    │  context.schema.focus_points → 在每个维度的 ReAct 循环中，把关注点作为分析清单逐条覆盖
    │  context.schema.custom_fields → 在创建节点时追加自定义字段
    │  context.schema.prompt_override → 使用自定义 Prompt 而非默认
    │  context.schema.benchmark_product → 以基准产品为参照进行分析
```

**示例：用户只关心定价和 AI 能力，且对定价有明确的关注点**

```json
// POST /api/task
{
  "targets": ["Notion", "Confluence", "Linear"],
  "schema": {
    "industry": "saas",
    "dimensions": [
      {
        "name": "定价策略深度分析",
        "description": "全面对比三家产品的定价模型、免费策略与隐藏成本",
        "focus_points": [
          "免费版的真实限制条件是什么？哪些关键功能被锁定？",
          "从免费到付费的升级路径如何设计？是否存在'鲶鱼定价'？",
          "企业版 / Team 版是否有隐藏成本（如超出用量后的计费方式）？",
          "三家产品各自的价格锚定策略是什么？谁在打价格战？",
          "大客户定制报价是否公开？销售周期多长？"
        ],
        "node_types": ["PricingData", "PricingModel"],
        "agent_type": "PricingAnalyst",
        "weight": 0.6
      },
      {
        "name": "AI 功能对比",
        "description": "对比三家产品的 AI 功能成熟度与实际可用性",
        "focus_points": [
          "AI 功能是自行研发还是接入第三方 API？对数据隐私有何影响？",
          "AI 文本生成 / 智能搜索 / 自动化工作流的实际效果如何？",
          "用户对 AI 功能的真实评价（是'眼前一亮'还是'鸡肋'）？"
        ],
        "node_types": ["FeatureNode", "FeatureMatrix"],
        "agent_type": "FeatureAnalyzer",
        "prompt_override": "重点分析 AI 相关功能，按成熟度（实验性/Beta/GA）分级，结合实际用户评价判断可用性",
        "weight": 0.4
      }
    ],
    "exclude_dimensions": ["技术栈推断", "市场定位", "API 生态"],
    "custom_fields": {
      "FeatureNode": [
        {"name": "ai_maturity", "type": "enum", "enum_values": ["experimental", "beta", "ga"], "description": "AI 功能成熟度"},
        {"name": "ai_self_developed", "type": "bool", "description": "是否自研 AI"}
      ]
    },
    "source_preferences": {
      "priority_sources": ["官网定价页", "G2", "ProductHunt"],
      "excluded_sources": ["Reddit"],
      "min_credibility": 0.6
    },
    "benchmark_product": "Notion",
    "report_audience": "product_manager"
  }
}
```

**说明**：Schema Builder 将"自定义"从口号变为可操作的能力。用户不写代码，通过结构化 JSON 声明关注什么、忽略什么、怎么加权，Orchestrator 据此生成定制 DAG，分析 Agent 据此调整分析重心。这从根本上改变了系统从"固定分析模板"到"用户驱动的自定义分析引擎"的定位。

---

## 5. DAG 引擎设计

### 5.1 节点状态机

```
PENDING → READY → RUNNING → COMPLETED
   ↑                    │
   └── RETRY ←── FAILED
                            │
QA_REJECTED → (上游受影响节点重置为 PENDING)
```

### 5.2 核心机制与伪代码

**DAG 调度器核心循环**：

```python
class DAGScheduler:
    """DAG 调度器：每轮检查依赖，并行调度就绪节点"""
    
    def __init__(self, task_queue, event_bus, snapshot_store):
        self.task_queue = task_queue      # Agent 任务队列
        self.event_bus = event_bus        # WebSocket 事件推送
        self.snapshot_store = snapshot_store  # 断点快照存储
    
    async def run(self, dag: TaskDAG) -> None:
        # 如果存在快照，从断点恢复
        if snapshot := await self.snapshot_store.load(dag.task_id):
            dag.restore(snapshot)
        
        while not dag.is_terminal():
            # 1. 依赖解析：找出所有依赖已满足的 PENDING 节点
            ready = [
                n for n in dag.nodes
                if n.state == NodeState.PENDING
                and all(dep.state == NodeState.COMPLETED 
                        for dep in n.depends_on)
            ]
            
            # 2. 标记为 READY 并并行分发到任务队列
            for node in ready:
                node.state = NodeState.READY
                await self.event_bus.emit(NodeReadyEvent(node))
            
            # 3. 并行提交到任务队列（Agent 异步执行）
            tasks = [
                self.task_queue.enqueue(node, priority=node.priority)
                for node in ready
            ]
            
            # 4. 等待任一任务完成或失败
            done, pending = await asyncio.wait(
                tasks, 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # 5. 处理完成的任务
            for task in done:
                node = task.result()
                if node.state == NodeState.COMPLETED:
                    await self.snapshot_store.save(node)   # 快照
                    await self.event_bus.emit(NodeCompletedEvent(node))
                elif node.state == NodeState.FAILED:
                    if node.retries < node.max_retries:
                        node.retries += 1
                        node.state = NodeState.PENDING    # 重试
                    else:
                        node.state = NodeState.FAILED      # 终态失败
                        await self.event_bus.emit(NodeFailedEvent(node))
```

**反馈边处理（QA 拒绝 → 局部重跑）**：

```python
async def handle_qa_rejection(self, qa_node, failed_nodes: list[NodeID], 
                                reasons: list[str]) -> None:
    """QA 拒绝时，仅重置受影响的子图，不重跑整个 DAG"""
    
    # 1. 反向 BFS：从失败节点沿 depends_on 反向追溯
    affected = set()
    for node_id in failed_nodes:
        affected.update(dag.trace_upstream(node_id))
    
    # 2. 检查重试轮次
    qa_node.qa_round += 1
    if qa_node.qa_round > 2:  # 最多 2 轮
        qa_node.state = NodeState.DEGRADED
        qa_node.qa_notes = f"2 轮重审未通过: {reasons}"
        await self.event_bus.emit(QADegradedEvent(qa_node, reasons))
        return
    
    # 3. 重置受影响节点为 PENDING（不碰无关节点）
    for node in affected:
        node.state = NodeState.PENDING
        node.retries = 0
    
    # 4. 记录 QA 反馈到审计日志
    await self.audit.log({
        "event": "qa_rejected",
        "qa_agent": qa_node.agent_type,
        "failed_nodes": [str(n) for n in failed_nodes],
        "affected_subgraph": [str(n) for n in affected],
        "reasons": reasons,
        "round": qa_node.qa_round
    })
    
    # 5. DAG 继续运行，受影响节点将被重新调度
```

**交叉审查反馈处理（Cross-Review 拒绝 → 局部重分析）**：

```python
async def handle_cross_review_rejection(self, cr_agent, flags: list[CrossReviewFlag]) -> None:
    """Cross-Review Agent 发现 high 矛盾时，触发局部重分析"""
    
    high_flags = [f for f in flags if f.severity == "high"]
    if not high_flags:
        # medium/low 仅标记，不触发重跑
        return
    
    # 1. 找出涉及的分析 Agent
    affected_agents = set()
    for flag in high_flags:
        affected_agents.update(flag.involved_agents)
    
    # 2. 反向 BFS 找到对应的 DAG 节点
    affected_nodes = set()
    for agent_type in affected_agents:
        affected_nodes.update(dag.find_nodes_by_agent(agent_type))
    
    # 3. 重置涉及节点为 PENDING（交叉重跑最多 1 轮）
    for node in affected_nodes:
        if node.cross_review_retries < 1:  # 只允许 1 轮
            node.state = NodeState.PENDING
            node.cross_review_retries += 1
            # 注入冲突上下文
            node.context["cross_review_flags"] = [
                f for f in high_flags if f.involves(node.agent_type)
            ]
    
    # 4. 记录审计日志
    await self.audit.log({
        "event": "cross_review_rejected",
        "flags": [f.dict() for f in high_flags],
        "affected_agents": list(affected_agents),
        "affected_nodes": [str(n) for n in affected_nodes]
    })
```

**断点快照数据结构**：

```python
@dataclass
class NodeSnapshot:
    task_id: str
    node_id: str
    state: NodeState
    kg_changeset: dict       # 该节点写入图谱的变更（用于回滚或审计）
    agent_log: list[dict]    # Agent 执行日志
    checkpoint_time: datetime
    llm_cost: float
    
# 恢复时
# SELECT * FROM snapshots WHERE task_id = $tid ORDER BY checkpoint_time
# → 跳过所有 state='COMPLETED' 的节点，重置 RUNNING 节点为 PENDING
```

### 5.3 SaaS 场景 DAG 拓扑（一次完整分析）

此拓扑展示一次分析 Notion、Confluence、Linear 三个目标产品的完整 DAG。流程包含两个反馈闭环：分析层之间的水平交叉审查（Cross-Review），以及最终报告的双 QA 垂直审查。

```
                             ┌─────────────────┐
                             │  Orchestrator    │
                             │  接收任务，生成DAG │
                             └────────┬────────┘
                                      │
                                      ↓
                            ┌──────────────────┐
                            │  Source Discovery │
                            │  (单实例)          │
                            │  搜索所有目标产品   │
                            │  → 可信 URL 列表   │
                            │  → 按产品+域名标记  │
                            └────────┬─────────┘
                                     │
                         ┌───────────┼───────────┐
                         ↓           ↓           ↓
              ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐
              │Coll. ││Coll. ││Coll. ││Coll. ││Coll. ││Coll. │
              │官网#1││官网#2││官网#3││ G2   ││Product││ News │
              │Notion││Conv. ││Linear││ 评价 ││ Hunt  ││ 新闻 │
              └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘
                 │      │      │      │      │      │
                 └──────┼──────┴──────┴──────┼──────┘
                        │                   │
                        └─────────┬─────────┘
                                  ↓
                        ┌──────────────────┐
                        │   Data Enricher  │
                        │  (单实例，按产品    │
                        │   分批富化数据)     │
                        └────────┬─────────┘
                                 │
         ┌─────────────┬─────────┼─────────┬──────────────┐
         ↓             ↓         ↓         ↓              ↓
   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Feature  │ │Sentiment │ │ Pricing  │ │TechStack │ │ Market   │
   │ Analyzer │ │ Analyzer │ │ Analyst  │ │ Analyzer │ │ Position │
   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
        │            │            │            │            │
        └────────────┼────────────┼────────────┼────────────┘
                     │            │            │
                     └────────────┼────────────┘
                                  ↓
                     ┌──────────────────────────┐
                     │   Cross-Review Agent     │  ← 水平交叉审查
                     │                          │
                     │  • 矛盾检测: Feature vs   │
                     │    Sentiment 是否矛盾?     │
                     │  • 遗漏检测: Pricing 是否 │
                     │    遗漏了关键功能?         │
                     │  • 置信度异常检查          │
                     └────────────┬─────────────┘
                                  │
                        ┌─────────┴─────────┐
                        │ 发现 high 矛盾?    │
                        ├────────┬──────────┤
                        │ YES    │ NO       │
                        ↓        │          │
                  局部重分析      │          │
                  (max 1轮)      ↓          ↓
                     ┌──────────────────────┐
                     │   SWOT Synthesizer   │
                     │ (含 CrossReview flag) │
                     └──────────┬───────────┘
                                ↓
                     ┌──────────────────────┐
                     │     Writer Agent     │
                     │  生成结构化 Markdown   │
                     │  标注分析分歧点        │
                     └──────────┬───────────┘
                                │
                    ┌───────────┼───────────┐
                    ↓                       ↓
          ┌──────────────────┐   ┌──────────────────┐
          │  QA Agent #1     │   │  QA Agent #2     │
          │  事实核查         │   │  逻辑一致性       │
          │  (溯源边完整性)    │   │  (论点无矛盾)     │
          └────────┬─────────┘   └────────┬─────────┘
                   │                      │
                   └──────────┬───────────┘
                              │
                        ┌─────┴─────┐
                        │ 双 QA 通过? │
                        ├─────┬─────┤
                        │ YES │ NO  │
                        ↓     │     │
                 ┌──────────┐ │     │ 反馈边：标记具体失败
                 │ COMPLETE │ │     │ 节点 + 原因，重置
                 │ 归档报告  │ │     │ 上游受影响子图
                 └──────────┘ ↓     ↓
                        ┌──────────────────┐
                        │  局部重跑         │
                        │  仅重跑 QA 标记   │
                        │  的受影响节点     │
                        │  (最多 2 轮)      │
                        └──────────────────┘
```

**关键设计决策**：
- Source Discovery 为单实例，同时搜索所有目标产品并按产品标记 URL，避免同一网站被多次请求
- Collector 实例数 = Source Discovery 发现的 URL 按域名分组后的批次数（示例中 6 个），按需动态创建
- Data Enricher 为单实例，在 Collector 全部完成后按产品分批富化
- **审核模式检查点**（可选）：Data Enricher COMPLETED 后，若用户选择了审核模式，DAG 暂停等待用户确认采集结果；用户可调整关注点或补充信息源，然后手动释放检查点继续
- 5 个分析 Agent 并行运行（相互无依赖），共同产出交给 Cross-Review Agent
- **Cross-Review Agent** 在所有分析 Agent 完成后运行，检测分析结论之间的矛盾、遗漏和置信度异常；发现 high 矛盾时触发局部重分析（最多 1 轮）
- SWOT Synthesizer 接收分析结果 + CrossReviewFlag，综合时需标注分析分歧点
- QA 反馈边只重置受影响子图（例如 QA#1 标记 FeatureMatrix 有问题 → 只重跑 Collector:官网 + FeatureAnalyzer，不动其他分析 Agent）
- **两个反馈闭环的分工**：Cross-Review 解决"分析团队内部是否一致"（水平），QA 解决"最终报告是否可靠"（垂直）

---

## 6. 数据流设计

系统有五个核心数据流：任务创建 → Agent 执行 → 水平交叉审查 → QA 垂直审查 → 用户溯源查询。以下逐一展开。

### 6.1 流程一：任务创建与 DAG 生成

```
用户 ──→ Web UI ──→ POST /api/task
                    {
                      targets: ["Notion","Confluence","Linear"],
                      schema: {                          ← 自定义分析 Schema
                        industry: "saas",
                        dimensions: [...],               ← 用户自定义维度
                        exclude_dimensions: [...],       ← 跳过的默认维度
                        custom_fields: {...},            ← 自定义节点字段
                        dimension_weights: {...},        ← 维度权重
                        source_preferences: {...},       ← 信息源偏好
                        benchmark_product: "Notion",     ← 对比基准
                        report_sections: [...]           ← 报告结构
                      },
                      depth: "standard"
                    }
                           │
                           ↓
                    API Gateway (FastAPI)
                      │  校验参数 (Pydantic: AnalysisSchema)
                      │  合并用户 schema + 行业默认模板
                      │  创建 task_id = uuid4()
                      ↓
                    Orchestrator Agent
                      │  输入: 用户需求 + 合并后的 Schema
                      │  LLM 推理: 
                      │    - 根据 dimensions[] 决定启动哪些分析 Agent
                      │    - 根据 exclude_dimensions[] 跳过对应 Agent
                      │    - 根据 source_preferences 定制采集策略
                      │    - 根据 benchmark_product 注入对比参照
                      │  输出: 定制化 DAG 任务图 JSON (节点数因维度而异)
                      │    - 节点列表 (每个节点含 agent_type, input_query, depends_on)
                      │    - 边列表 (依赖关系)
                      │    - 并行组标记
                      │    - schema 快照 (注入到每个 Agent 的 context)
                      ↓
                    写入 PostgreSQL:
                      • task 表: {task_id, status=CREATED, targets, schema_json, created_at}
                      • task_dag 表: {task_id, dag_json}
                      ↓
                    DAG Scheduler
                      │  解析 DAG，标记第一层节点为 READY
                      │  推入任务队列
                      ↓
                    返回: { task_id, ws_endpoint: "/ws/task/{task_id}" }
                           │
                           ↓
用户 ──→ 前端建立 WebSocket 连接，等待实时状态推送
```

**说明**：任务创建是同步返回的（~2s）。自定义 Schema 与行业默认模板在 API Gateway 层合并（用户值覆盖默认值，用户未指定的沿用默认）。Orchestrator 根据合并后的 Schema 生成定制 DAG——维度越多，DAG 节点越多；排除的维度对应的 Agent 不会被创建。Schema 快照随 DAG 一起持久化，确保后续溯源时能看到"当时是按什么标准分析的"。

**可选审核模式**：任务创建时支持选择 `execution_mode: "auto" | "review"`：
- **自动模式**（默认）：全流程无人干预，DAG 从头跑到尾
- **审核模式**：在采集层完成（Data Enricher COMPLETED）、分析层启动之前，DAG 设置一个检查点暂停，用户可在监控页查看已采集的原始数据并调整分析方向——追加关注点、调整权重、或补充特定信息源——然后手动释放检查点，分析 Agent 启动。这模拟了真实调研中"初步发现汇报 → 产品经理调整方向"的迭代过程。检查点超时（默认 30 分钟）后自动释放，避免任务永久阻塞。

### 6.2 流程二：Agent 执行循环（以 Feature Analyzer 为例）

```
┌─────────────── Agent 执行循环 (Feature Analyzer) ──────────┐
│                                                              │
│  1. 从任务队列获取任务                                        │
│     {                                                        │
│       "node_id": "feature_analyzer_1",                       │
│       "agent_type": "FeatureAnalyzer",                       │
│       "input_query": {"node_types": ["ProductNode", "WebPage"], │
│                        "filters": {"product": ["Notion",         │
│                                     "Confluence", "Linear"]}},   │
│       "context": "{task_id, depth, ...}"                     │
│     }                                                        │
│          ↓                                                   │
│  2. 图谱查询（读取输入数据）                                     │
│     graph.query(task.input_query)                            │
│     → 返回 Notion/Confluence/Linear 的产品信息和网页数据       │
│          ↓                                                   │
│  3. ReAct 决策循环（LLM 驱动）                                 │
│     Step 1:                                                  │
│       Thought: "需要对每个产品的功能进行分类对比，              │
│                 先提取 Notion 的功能模块"                       │
│       Action: extract_features(product="Notion",              │
│                                 web_content=...)              │
│       Observation: "提取到 47 个功能点，归为 8 个类别"          │
│     Step 2:                                                  │
│       Thought: "继续提取 Confluence..."                       │
│       Action: extract_features(product="Confluence", ...)     │
│       ... (循环至完成或最大步数)                                │
│          ↓                                                   │
│  4. 图谱写入（产生 Output）                                    │
│     for feature in extracted_features:                       │
│         graph.create_node(FeatureNode, data=feature)          │
│         graph.create_edge(                                    │
│             from=feature_node,                                │
│             to=source_webpage,                                │
│             type="derived_from"  ← 溯源边                     │
│         )                                                     │
│     graph.create_node(FeatureMatrix, data=matrix)             │
│          ↓                                                   │
│  5. 写审计日志 + 更新节点状态                                   │
│     audit_log.write({                                         │
│         "agent": "FeatureAnalyzer",                           │
│         "node_id": "feature_analyzer_1",                      │
│         "llm_calls": 4, "tokens_used": 12400, "cost": 0.18,  │
│         "nodes_created": 48, "edges_created": 141             │
│     })                                                        │
│     node.state = COMPLETED                                    │
│     await snapshot_store.save(node)  ← 断点快照                │
│          ↓                                                   │
│  6. WebSocket 推送                                             │
│     → 前端 DAG 图中该节点变绿 ✓                                │
│     → 下游依赖该节点的 PENDING 节点可能变为 READY                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**说明**：步骤 3 的 ReAct 循环是 Agent 自主性的核心——Agent 不是执行预设脚本，而是根据观察结果动态决定下一步行动。max_steps 默认 15（框架级），各 Agent 类型可按任务复杂度覆盖（如 FeatureAnalyzer 设为 10，Collector 设为 8）。步骤 4 中每条 derived_from 边都是后续溯源的基础。

### 6.3 流程三：水平交叉审查（Cross-Review 反馈闭环）

```
Cross-Review Agent 被调度（所有分析 Agent 完成后）:
  │
  │  从图谱读取所有 Layer 2 分析节点的输出:
  │    FeatureMatrix (Notion/Confluence/Linear)
  │    SentimentNode × N (各维度口碑)
  │    PricingModel × 3
  │    TechStack × 3
  │    MarketPosition × 3
  │
  ↓
执行三类检查:
  │
  │  检查 1: 矛盾检测
  │    例: FeatureMatrix 标记 "Linear 文档功能 ★★ (弱)"
  │        SentimentNode "文档体验" Linear +0.8 (正面)
  │        → 矛盾！功能分析说文档弱，但用户口碑很好
  │        → 可能原因: Feature Analyzer 采集的 Linear 官网未包含最新文档功能
  │        → 创建 CrossReviewFlag {type: "conflict", severity: "high",
  │            agents: ["FeatureAnalyzer", "SentimentAnalyzer"],
  │            detail: "文档功能评分与用户口碑矛盾"}
  │        → 创建 contradicts 边: FeatureMatrix ↔ SentimentNode
  │
  │  检查 2: 遗漏检测
  │    例: Sentiment Analyzer 从 G2 评论中发现 Linear 频繁提到 "API 集成"
  │        但 FeatureMatrix 中没有 "API 集成" 这个功能维度
  │        → Feature Analyzer 遗漏了重要功能维度
  │        → 创建 CrossReviewFlag {type: "omission", severity: "medium",
  │            source_agent: "SentimentAnalyzer",
  │            target_agent: "FeatureAnalyzer",
  │            detail: "G2 评论高频提及 API 集成，功能分析未覆盖"}
  │        → 转发遗漏信息给 Feature Analyzer，触发增量补充分析
  │
  │  检查 3: 置信度异常
  │    例: TechStack Analyzer 对 Linear 技术栈推断 confidence=0.9
  │        但 derived_from 边只有 1 条（仅来自 1 个 WebPage）
  │        → 高置信度但证据薄弱
  │        → 创建 CrossReviewFlag {type: "confidence_anomaly", severity: "low",
  │            agent: "TechStackAnalyzer",
  │            detail: "置信度 0.9 但仅 1 条溯源边"}
  │
  ↓
处理结果:
  │
  │  if severity == "high" 的矛盾:
  │    → DAG 反馈边触发
  │    → 涉及的两个 Agent 重置为 PENDING
  │    → Agent context 注入冲突说明
  │    → 重跑时 Agent 会特别审视矛盾点
  │    → 最多 1 轮交叉重跑
  │
  │  if severity == "medium" 的遗漏:
  │    → 目标 Agent 收到遗漏信息
  │    → Agent 增量补充分析（不重跑，仅追加）
  │    → 图谱追加新的 FeatureNode
  │
  │  if severity == "low":
  │    → 仅标记 flag，不触发重跑
  │    → SWOT 和 Writer 在综合时标注 "⚠ 需人工复核"
  │
  ↓
CrossReviewFlag 节点写入图谱
  → SWOT Synthesizer 读取 flag，在 SWOT 矩阵中标注分析分歧
  → Writer 在报告相关章节插入 "⚠ 分析分歧" 标注
  → 前端报告页显示分歧点和置信度
```

**说明**：交叉审查是系统"模拟真实调研小组"的核心机制。真实的分析团队中，分析师会互相阅读对方的发现并质疑不一致之处——"你说它的文档很弱，但用户评价很好，是不是你遗漏了它的新版文档？"Cross-Review Agent 将这种同行互审自动化，在分析层和综合层之间建立一道质量闸门。与 QA 的区别在于：QA 审查的是"报告是否忠实地引用了分析结果"，Cross-Review 审查的是"分析结果之间是否自洽"。

### 6.4 流程四：QA 反馈闭环（垂直审查）

```
QA Agent #1（事实核查）处理中：
  │
  │  遍历报告的每个断言，反向追溯溯源边：
  │  
  │  断言: "Linear 在项目管理能力上弱于 Notion"
  │     ↓ BFS 沿 derived_from 反向
  │     → SentimentNode("项目管理", score=-0.3)
  │        → ReviewEntry × 8 (G2, 4 条提到这点的)
  │           → SourceInfo(G2, credibility=0.85)  ✓ 溯源完整
  │     → FeatureMatrix(项目管理, Linear={...}, Notion={...})
  │        → FeatureNode("Linear:projects") → WebPage(Linear 官网 2024)
  │        → FeatureNode("Notion:projects")  → WebPage(Notion 官网 2025)
  │        → ❌ 问题！Linear 官网最近发布了 "Projects 2.0"
  │           但 Collector 抓的是缓存旧版本
  │  
  │  QA #1 标记: { node: "collector_linear_official",
  │                reason: "网页版本过旧，遗漏 Projects 2.0 信息",
  │                severity: "high" }
  │
  ↓
DAG Scheduler 收到 QA 拒绝事件：
  │
  │  affected = dag.trace_upstream(failed=["collector_linear_official"])
  │  → [Collector:Linear官网, FeatureAnalyzer, FeatureMatrix] ← 受影响子图
  │  
  │  qa_round = 1 (第 1 轮)
  │  
  │  仅这 3 个节点重置为 PENDING，重新入队
  │  ✓ SWOT Synthesizer 保持 COMPLETED (不受影响)
  │  ✓ SentimentAnalyzer 保持 COMPLETED (独立维度)
  │  ✓ PricingAnalyst 保持 COMPLETED (独立维度)
  │
  ↓
第二轮执行（仅受影响子图）：
  Collector:Linear官网 重新采集（获取 Projects 2.0 信息）
  → FeatureAnalyzer 重新分析
  → FeatureMatrix 更新
  → QA 重新审查 → Pass ✓
```

**说明**：这是系统"反馈闭环"的核心价值。传统的 ETL 管道出错需要全部重跑，而 DAG 引擎只重跑受影响的子图，大幅节省时间和 LLM 成本。2 轮上限防止无限循环。

### 6.5 流程五：用户溯源查询（含 Step-level trace）

溯源查询不仅追溯"数据从哪里来"，还追溯"Agent 如何从数据推导出结论"。

```
用户在 Web UI 报告页点击一句话：
  "Linear 的定价策略面向中大型团队"
         │
         ↓
GET /api/trace?insight_id=insight_42&task_id=task_001&include_steps=true
         │
         ↓
图谱 BFS 反向遍历（K 跳，最大深度 5）：
  InsightNode("定价面向中大型团队")
    ← derived_from ← PricingModel(Linear)           [Agent: PricingAnalyst]
      ← derived_from ← PricingData(Linear 官网: Business $12/seat) [Agent: Collector]
      ← derived_from ← ReviewEntry×23 (G2 "适合团队"评论) [Agent: Collector]
        ← has_source ← SourceInfo(G2, cred=0.85)
      ← derived_from ← PricingData(对比: Notion Plus $10, Confluence Std $6)
      ← supports     ← SentimentNode("性价比", score=+0.6)
         ← derived_from ← ReviewEntry×41 (正向评价)
      ← contradicts  ← ReviewEntry×3 ("对小团队太贵")
         │
         ↓
同时查询 step_traces 表：
  SELECT * FROM step_traces
  WHERE task_id='task_001'
    AND node_id IN ('pricing_analyst_1', 'collector_linear_pricing', ...)
  ORDER BY node_id, step_number
         │
         ↓
返回 JSON（含完整决策轨迹）:
{
  "insight": "Linear 的定价策略面向中大型团队",
  "confidence": 0.82,
  "chain": [
    { "level": 1, "type": "PricingModel", "summary": "...",
      "agent": "PricingAnalyst", "node_id": "pricing_analyst_1" },
    { "level": 2, "type": "PricingData", "url": "linear.app/pricing",
      "agent": "Collector", "node_id": "collector_linear_pricing" },
    ...
  ],
  "contradicting_evidence": [...],
  "step_traces": {                              ← 每个节点的完整决策步骤
    "pricing_analyst_1": [
      {
        "step": 0, "phase": "observe",
        "summary": "读取 3 个产品的 PricingData 节点",
        "nodes_read": ["pd_001", "pd_002", "pd_003"]
      },
      {
        "step": 0, "phase": "think",
        "reasoning": "Notion 的定价模型是典型的免费增值，Linear 是渗透定价...",
        "confidence": 0.7,
        "tokens": 2400, "cost": 0.03
      },
      {
        "step": 1, "phase": "observe",
        "summary": "读取 G2 用户评价中的定价相关评论"
      },
      {
        "step": 1, "phase": "think",
        "reasoning": "G2 评论中有 23 条提到 Linear 定价适合团队，3 条提到对小团队太贵...",
        "confidence": 0.85,
        "tokens": 1800, "cost": 0.02
      },
      {
        "step": 2, "phase": "act",
        "action": "finalize",
        "output_summary": "创建 PricingModel(Linear) + 3 条 derived_from 边",
        "nodes_created": ["pm_linear_001"],
        "edges_created": ["e_042", "e_043", "e_044"]
      }
    ],
    "collector_linear_pricing": [
      {
        "step": 0, "phase": "act",
        "action": "web_scrape",
        "params": {"url": "https://linear.app/pricing"},
        "result_summary": "成功抓取，提取 3 个定价计划"
      },
      {
        "step": 1, "phase": "think",
        "reasoning": "已提取完整定价信息，可以结构化输出",
        "confidence": 0.95
      },
      {
        "step": 2, "phase": "act",
        "action": "finalize",
        "nodes_created": ["pd_002"]
      }
    ]
  }
}
         │
         ↓
前端渲染溯源面板（可逐步骤展开 Agent 决策过程）：
  ✓ PricingModel → [展开查看 3 步推理过程]
      Step 0: 观察 → 读取 3 个产品的定价数据
      Step 0: 思考 → "Notion 免费增值，Linear 渗透定价..." [查看完整 Prompt]
      Step 1: 观察 → 读取 23 条 G2 定价评论
      Step 1: 思考 → "23 条正面 vs 3 条负面" confidence: 0.85
      Step 2: 行动 → finalize，创建 PricingModel
  ✓ 官网定价数据 → [展开查看 Collector 的抓取步骤]
  ⚠ 3 条矛盾证据（G2 用户评论）
  综合置信度: 82%
```

**说明**：溯源不是简单的"列出数据源"，而是展示完整推理链条 + 矛盾证据 + Agent 决策过程。用户看到的不只是结论，还有结论的"可信度全息图"——什么支撑它，什么反对它，哪个 Agent 在什么时候基于什么数据得出的。

---

## 7. Web UI 设计

四个核心页面，按用户使用路径排列：创建任务 → 监控执行 → 阅读报告（含溯源） → 深度探索。

### 7.1 页面一：任务面板 `/`

用户入口，用于创建新分析任务和查看历史。

```
┌──────────────────────────────────────────────────────────┐
│  竞品分析 Agent 协作系统                                   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 新建分析                                          │    │
│  │                                                   │    │
│  │ 目标产品: [Notion] [Confluence] [Linear]  + 添加  │    │
│  │ 行业模板: [SaaS ▾]                                │    │
│  │ 分析深度: ○ 快速  ● 标准  ○ 深度                  │    │
│  │ 执行模式: ● 自动  ○ 审核 (采集后暂停，调整方向再继续) │    │
│  │ 模型偏好: [Claude Opus ▾]  (可选，默认自动分配)     │    │
│  │                                                   │    │
│  │ ▶ 高级自定义（分析维度 / 关注点 / 权重 / 信息源）    │    │
│  │   ┌─────────────────────────────────────────┐     │    │
│  │   │ 分析维度 (勾选启用，拖拽调权重)           │     │    │
│  │   │                                         │     │    │
│  │   │ ☑ 功能矩阵对比    ▬▬▬▬▬▬○○ 20% [展开▾]  │     │    │
│  │   │ ☑ 定价策略分析    ▬▬▬▬▬▬▬▬ 40% [展开▾]  │     │    │
│  │   │   ┌─ 关注点 ─────────────────────────┐  │     │    │
│  │   │   │ • 免费版限制与升级路径            │  │     │    │
│  │   │   │ • 隐藏成本（超量计费、附加费）     │  │     │    │
│  │   │   │ • 竞品价格锚定策略               │  │     │    │
│  │   │   │ • 大客户折扣与销售周期           │  │     │    │
│  │   │   │ + 添加关注点                     │  │     │    │
│  │   │   └────────────────────────────────┘  │     │    │
│  │   │ ☑ 用户口碑分析    ▬▬▬▬○○○○ 15% [收起▶]│     │    │
│  │   │ ☑ AI 能力分析     ▬▬▬▬▬▬○○ 25% [展开▾]  │     │    │
│  │   │ ☑ 技术栈推断      ▬▬▬▬○○○○ 10%        │     │    │
│  │   │ ☑ 市场定位分析    ▬▬▬▬○○○○ 10%        │     │    │
│  │   │ ☑ API 与集成生态  ▬▬▬○○○○○ 5%         │     │    │
│  │   │ ☑ 客户支持质量    ▬▬○○○○○○ 3%         │     │    │
│  │   │ ☑ 产品迭代速度    ▬▬○○○○○○ 2%         │     │    │
│  │   │                                         │     │    │
│  │   │ ══════ 后续扩展（暂不可选） ══════      │     │    │
│  │   │ ☐ 安全合规        (开发中)              │     │    │
│  │   │ ☐ Onboarding 体验 (开发中)              │     │    │
│  │   │ ☐ 移动端体验      (开发中)              │     │    │
│  │   │ ☐ 开源策略        (开发中)              │     │    │
│  │   │ ☐ 国际化程度      (开发中)              │     │    │
│  │   │ ☐ 团队规模推断    (开发中)              │     │    │
│  │   │                                         │     │    │
│  │   │ + 新建自定义维度                          │     │    │
│  │   │                                         │     │    │
│  │   │ 信息源配置:                              │     │    │
│  │   │ 优先级:  [G2] [ProductHunt] [官网]       │     │    │
│  │   │          [TechCrunch] [36Kr]  + 添加     │     │    │
│  │   │ 排除源:  [Reddit]  + 添加                │     │    │
│  │   │ 最低可信度: ▬▬▬▬○ 0.6                    │     │    │
│  │   │                                         │     │    │
│  │   │ 对比基准: [Notion ▾]                     │     │    │
│  │   │ 报告受众: [产品经理 ▾]                    │     │    │
│  │   │ 输出格式: ☑ Markdown ☑ JSON            │     │    │
│  │   └─────────────────────────────────────────┘     │    │
│  │                                                   │    │
│  │ [开始分析]                                         │    │
│  └──────────────────────────────────────────────────┘    │
│                                                          │
│  历史任务                                                 │
│  ┌────────┬─────────────┬────────┬────────┬──────────┐  │
│  │ 时间   │ 目标产品     │ 状态   │ 耗时   │ 操作     │  │
│  ├────────┼─────────────┼────────┼────────┼──────────┤  │
│  │ 05-14  │ Notion /    │ ✓ 完成 │ 4m32s  │ 查看报告 │  │
│  │ 14:30  │ Confluence  │        │        │ 查看溯源 │  │
│  │        │ Linear      │        │        │          │  │
│  ├────────┼─────────────┼────────┼────────┼──────────┤  │
│  │ 05-14  │ Figma /     │ ◐ 运行 │ 2m15s  │ 实时监控 │  │
│  │ 15:02  │ Sketch      │  ████░░ │        │          │  │
│  ├────────┼─────────────┼────────┼────────┼──────────┤  │
│  │ 05-13  │ Slack /     │ ✕ 失败 │ -      │ 查看日志 │  │
│  │ 18:45  │ Teams       │        │        │ 重新运行 │  │
│  └────────┴─────────────┴────────┴────────┴──────────┘  │
└──────────────────────────────────────────────────────────┘
```

**说明**：分析深度选项控制采集广度和 Agent 数量——快速模式仅走官网 + G2 两条采集线，标准加入社媒和新闻，深度追加第三方 API。模型偏好可选，默认由 LLM 网关根据 Agent 等级自动分配。"高级自定义"是 Schema Builder 的 UI 入口——用户展开后可自定义分析维度、维度权重、信息源偏好和报告结构。用户不展开则使用 SaaS 行业默认 Schema。

### 7.2 页面二：实时监控 `/task/:id/monitor`

系统中最关键的可观测性页面。上半区展示 Agent 状态面板，下半区展示 DAG 拓扑图。通过 WebSocket 实时驱动更新。

**上半区 — Agent 状态面板**：

```
┌──────────────────────────────────────────────────────────────────┐
│  Agent 协作状态                          任务: Notion/Confluence… │
│                                                                  │
│  ┌─ Orchestrator ────────────────────────────────────────────┐  │
│  │  状态: ✓ COMPLETED  耗时: 12s  │ 输出: DAG 拓扑 (12 节点)  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Source Discovery ────────────────────────────────────────┐  │
│  │  实例: 1 个                                               │  │
│  │  状态: ✓ COMPLETED  耗时: 8s   │ 发现源: 34 个 URL         │  │
│  │  可信源 > 0.7: 28  排除低质: 6                            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Collector Group (×6 并行实例) ────────────────────────────┐  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │  │
│  │  │#1 Notion │ │#2 Conv.  │ │#3 Linear │ │#4 G2     │      │  │
│  │  │●●●●●●●●●●│ │●●●●●●●●●●│ │●●●●●●●○○○│ │●●●●●●●●●●│ ...  │  │
│  │  │✓ 完成    │ │✓ 完成    │ │◐ 采集中  │ │✓ 完成    │      │  │
│  │  │3 页 45KB│ │2 页 38KB │ │进度 70%  │ │15 条评论  │      │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │  │
│  │  ┌──────────┐ ┌──────────┐                                 │  │
│  │  │#5 ProdHunt│ │#6 News   │                                 │  │
│  │  │●●●●●●●●●●│ │○○○○○○○○○○│                                 │  │
│  │  │✓ 完成    │ │○ 等待上游│                                 │  │
│  │  │8 条帖子  │ │          │                                 │  │
│  │  └──────────┘ └──────────┘                                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 分析层 (5 Agent，等待上游) ───────────────────────────────┐  │
│  │  ◌ FeatureAnalyzer    ◌ SentimentAnalyzer                 │  │
│  │  ◌ PricingAnalyst     ◌ TechStackAnalyzer                 │  │
│  │  ◌ MarketPosition                                         │  │
│  │  状态: ○ PENDING — 等待 DataEnricher + Collectors 完成     │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ SWOT Synthesizer ────────────────────────────────────────┐  │
│  │  状态: ○ PENDING — 等待 5 个分析 Agent 全部完成            │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ QA Group (×2，等待 Writer) ──────────────────────────────┐  │
│  │  ○ QA #1 事实核查    ○ QA #2 逻辑一致性                    │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  资源消耗: Token 12.4k | 成本 $0.42 | 采集 23 个页面              │
└──────────────────────────────────────────────────────────────────┘
```

**下半区 — DAG 拓扑图**：

```
┌─── DAG 拓扑（自绘 SVG，基于节点间依赖关系渲染）────────────────┐
│                                                              │
│         Orchestrator ✓                                       │
│              │                                               │
│              ↓                                               │
│        Source Disc. ✓                                       │
│              │                                               │
│    ┌────┬────┼────┬────┬────┐                                │
│    ↓    ↓    ↓    ↓    ↓    ↓                                │
│   C#1✓ C#2✓ C#3◐ C#4✓ C#5✓ C#6○                             │
│    │   │     │      │     │     │                            │
│    └───┼─────┼──────┼─────┼─────┘                            │
│        └─────┼──────┘     │                                  │
│              ↓            ↓                                  │
│        Data Enricher ◐   Enricher ○                          │
│              │            │                                   │
│    ┌────┬────┼────┬────┬──┼──┬────┐                          │
│    ↓    ↓    ↓    ↓    ↓  ↓  ↓    ↓                          │
│   FA○  SA○  PA○  TA○  MP○    (全部 PENDING)                  │
│    │    │    │    │    │                                     │
│    └────┴────┼────┴────┘                                     │
│              ↓                                               │
│         SWOT ○                                               │
│              ↓                                               │
│          Writer ○                                            │
│           ┌──┴──┐                                            │
│           ↓     ↓                                            │
│         QA1○  QA2○                                           │
│           └──┬──┘                                            │
│              ↓                                               │
│          COMPLETE                                            │
│                                                              │
│  图例: ✓完成  ◐运行中  ○等待  ✕失败  ⟲重试中                │
└──────────────────────────────────────────────────────────────┘
```

**实时驱动机制**：

WebSocket 连接后，前端订阅以下事件类型：

| 事件 | 触发时机 | 前端响应 |
|------|---------|---------|
| `node_state_change` | 节点状态变更 | 更新对应 Agent 卡片和 DAG 节点颜色 |
| `node_completed` | 节点执行完成 | 节点变绿，下游解锁节点变 READY |
| `agent_log` | Agent 输出日志 | 追加到实时日志流区域 |
| `cost_update` | 累计成本更新 | 刷新资源消耗栏数字 |
| `qa_reject` | QA 拒绝 | 受影响节点变黄，显示拒绝原因 |

**说明**：这是系统的可观测性中枢。用户在此页面可以理解：(1) 每个 Agent 当前在做什么；(2) 谁在等谁——阻塞关系一目了然；(3) 成本实时累积；(4) QA 审查状态。DAG 图按依赖关系自顶向下渲染，节点颜色反映状态。

### 7.3 页面三：报告页 `/task/:id/report`

用户阅读结构化报告，并通过溯源侧边栏验证每条结论。

```
┌──────────────────────────────────────────────────────────────┐
│  竞品分析报告: Notion vs Confluence vs Linear                 │
│  生成: 2026-05-14 15:08 | [导出 Markdown] [导出 JSON]       │
│                                                              │
│  ┌─────────── 报告正文（Markdown 渲染） ─────────────────┐   │
│  │                                                       │   │
│  │  ## 一、概述                                          │   │
│  │  Notion 以 all-in-one 工作区定位占据...                 │   │
│  │  [📎 溯源]                                            │   │
│  │  ...                                                  │   │
│  │                                                       │   │
│  │  ## 二、功能对比矩阵                                   │   │
│  │  | 功能    | Notion | Confluence | Linear |            │   │
│  │  |---------|--------|------------|--------|            │   │
│  │  | 文档    | ★★★★★  | ★★★★       | ★★     |            │   │
│  │  | 数据库  | ★★★★★  | ★★         | ★      |            │   │
│  │  | 项目管… | ★★★    | ★★         | ★★★★★  |            │   │
│  │  [📎 溯源] ← 每个结论可点击                           │   │
│  │                                                       │   │
│  │  ## 三、定价分析                                       │   │
│  │  [📎 溯源] Linear 的定价策略面向中大型团队...           │   │
│  │                                                       │   │
│  │  ## 四、SWOT 分析                                      │   │
│  │  ...                                                  │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─── 溯源侧边栏（点击 [📎 溯源] 展开） ───────────────┐    │
│  │  ▼ "Linear 定价面向中大型团队"                       │    │
│  │  ├─ ✓ PricingModel(Linear) [PricingAnalyst]        │    │
│  │  │   耗时 18s, LLM×2, $0.03                        │    │
│  │  ├─ ✓ PricingData 官网 $12/seat [Collector]        │    │
│  │  ├─ ✓ ReviewEntry×23 G2 [Collector]               │    │
│  │  ├─ ✓ PricingData 竞品对比 [PricingAnalyst]       │    │
│  │  └─ ⚠ 矛盾证据×3 (点击展开)                        │    │
│  │  置信度: 82%                                        │    │
│  │  [查看完整溯源图 →]                                  │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

**导出格式**：
- **Markdown**：适合阅读、分发或导入 Notion/Confluence
- **JSON**：包含完整图谱数据 + Agent 决策轨迹，适合下游系统消费或二次分析

### 7.4 页面四：溯源探索器 `/task/:id/trace`

以可展开的树形列表呈现溯源链，用户逐层展开查看推导路径。实现成本远低于力导向图，且在小规模溯源链（Demo 场景下 5–30 个节点）中可读性更好。

```
┌──────────────────────────────────────────────────────────────┐
│  溯源链: "Linear 定价面向中大型团队"    置信度: 82%            │
│                                                              │
│  ◉ InsightNode: "Linear 的定价策略面向中大型团队"             │
│  ├─ ▶ PricingModel (Linear) [PricingAnalyst] 耗时 18s       │
│  │  ├─ ▶ PricingData 官网 $12/seat [Collector]              │
│  │  │  └─ ▶ SourceInfo: linear.app/pricing (cred: 0.9)      │
│  │  ├─ ▶ PricingData 对比数据 [PricingAnalyst]              │
│  │  │  ├─ ▶ PricingData Notion Plus $10                     │
│  │  │  └─ ▶ PricingData Confluence Std $6                   │
│  │  └─ ▶ SentimentNode "性价比" +0.6 [SentimentAnalyzer]    │
│  │     ├─ ▶ ReviewEntry×23 "适合团队" (G2)                  │
│  │     └─ ⚠ ReviewEntry×3 "对小团队太贵" (矛盾证据)         │
│  │                                                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 节点详情（点击 ▶ 展开）                                │   │
│  │                                                       │   │
│  │ 选中节点: PricingModel (Linear)                       │   │
│  │ Agent: PricingAnalyst  |  耗时: 18s  |  成本: $0.03   │   │
│  │ 输入: PricingData×3 + ReviewEntry×26                  │   │
│  │ 输出: pricing_strategy="渗透定价", target="中大型团队" │   │
│  │                                                       │   │
│  │ Agent 决策轨迹 (StepTrace) ▾                           │   │
│  │  ├─ Step 0: Observe → 读取 3 个产品的定价数据          │   │
│  │  ├─ Step 0: Think → "Notion 免费增值，Linear 渗透..." │   │
│  │  ├─ Step 1: Act → sentiment_analyze(Linear)           │   │
│  │  └─ Step 2: Finalize → 创建 PricingModel              │   │
│  │  [查看完整 Prompt/Response]                             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  筛选: [按 Agent 类型 ▾] [按层级 ▾]  搜索: [_________]       │
└──────────────────────────────────────────────────────────────┘
```

**交互方式**：
- **点击 ▶**：展开/折叠节点的下游溯源边
- **点击节点**：右侧/下方显示节点详情 + Agent 决策轨迹
- **搜索框**：输入关键词过滤相关节点
- **筛选器**：按 Agent 类型 / 节点层级过滤显示
- **导出**：将当前溯源链导出为 JSON（用于下游分析）

**点击节点后的 StepTrace 决策轨迹面板**（节点详情下方）：

```
  ┌──────────────────────────────────────────────────────┐
  │ Agent 决策轨迹: SentimentAnalyzer                     │
  │ 节点: SentimentNode #42         总步数: 4 步          │
  │                                                       │
  │  Step 0 ── Observe ──────────────────────────────    │
  │  │  读取 ReviewEntry×41 (G2 + Reddit)                 │
  │  │  数据覆盖 3 个产品，时间范围 2024-2025             │
  │  │                                                    │
  │  ├── Think ───────────────────────────────────────    │
  │  │  推理: "评论中频繁出现 pricing 和 team size 关键    │
  │  │   词，需要按产品分别统计情感倾向..."                │
  │  │  置信度: 0.65                                     │
  │  │  考虑过: "直接按评分排序 → 放弃，信息损失太大"      │
  │  │  [查看完整 Prompt] [查看完整 Response]             │
  │  │                                                    │
  │  Step 1 ── Act ──────────────────────────────────    │
  │  │  工具: sentiment_analyze                           │
  │  │  参数: {product: "Linear", reviews: [...]}         │
  │  │  结果: 23 条正面, 8 条中性, 3 条负面               │
  │  │                                                    │
  │  ├── Think ───────────────────────────────────────    │
  │  │  推理: "Linear 的性价比维度得分 +0.6，正面评论      │
  │  │   集中在'适合团队''定价合理'..."                    │
  │  │  置信度: 0.85                                     │
  │  │  [查看完整 Prompt] [查看完整 Response]             │
  │  │                                                    │
  │  Step 2 ── Act ──────────────────────────────────    │
  │  │  工具: sentiment_analyze                           │
  │  │  参数: {product: "Notion", reviews: [...]}         │
  │  │  ...                                              │
  │  │                                                    │
  │  Step 3 ── Finalize ──────────────────────────────   │
  │  │  产出: SentimentNode #42                          │
  │  │  创建 3 条 derived_from 边 (→ ReviewEntry×41)     │
  │  │                                                    │
  │  ───────────────────────────────────────────────      │
  │  总成本: Token 4.2k | $0.06 | 耗时 22s               │
  └──────────────────────────────────────────────────────┘
```

**说明**：StepTrace 面板是系统"完全透明"承诺的最终体现。每个 Agent 的每一步推理——它看到了什么数据（Observe）、它如何思考（Think）、它做了什么操作（Act）——全部以时间线形式呈现。用户可以逐步骤复盘 Agent 的"思考过程"，就像检视一位人类分析师的工作笔记。这在以下场景中具有决定性价值：(1) 分析结论出问题时，定位是哪一个推理步骤引入了偏差；(2) 合规审计时，证明 AI 辅助分析的决策过程完全可追溯；(3) 调试 Agent Prompt 时，观察实际推理路径与预期的偏差。

---

## 8. 技术栈

### 8.1 LLM 网关与多模型支持

LLM 网关支持 OpenAI 兼容协议，可接入国内外主流模型。通过统一配置切换，不同 Agent 可使用不同模型以平衡质量与成本。

```python
MODELS = {
    "claude-opus-4-7": {
        "provider": "anthropic",
        "model": "claude-opus-4-7",
    },
    "kimi-k2": {
        "provider": "openai_compatible",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-auto",
    },
    "qwen-plus": {
        "provider": "openai_compatible",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "glm-4": {
        "provider": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4",
    },
}
```

**模型分配策略**：
- 关键推理 Agent（Orchestrator、QA × 2）：强模型（Claude Opus / DeepSeek-V4）
- 批量处理 Agent（Collector、Sentiment、Data Enricher）：性价比模型（Qwen-Plus、GLM-4）
- 分析 Agent（Feature、Pricing、SWOT 等）：中等模型，可灵活切换

### 8.2 通用技术栈

| 层 | Demo 阶段 | 生产阶段 |
|---|-----------|----------|
| LLM 接入 | Anthropic SDK + OpenAI SDK + 国内模型兼容 | + litellm 统一网关 |
| Agent 框架 | 自研 ReAct 循环 (~200行) | 同左 |
| DAG 引擎 | 自研 (~600行) | 同左 |
| 知识图谱 | SQLite + JSON（nodes + edges 表） | Neo4j |
| 图查询层 | Python dict-based API（封装 BFS/CRUD） | Neo4j Cypher |
| 后端 | FastAPI + WebSocket + Pydantic v2 | 同左 |
| 任务队列 | asyncio.Queue + Redis | Redis + Celery/arq |
| 采集 | httpx + BeautifulSoup | + Playwright (SPA) |
| 数据库 | SQLite + Redis | PostgreSQL + Redis |
| 前端 | React + Tailwind CSS | 同左 |
| 部署 | 单进程 FastAPI | Docker Compose |

---

## 9. 行业扩展机制

Schema 通过 YAML 配置文件驱动。以 `saas.yaml` 起步，后续可添加 `automotive.yaml`、`consumer_electronics.yaml` 等。每个行业模板定义：
- 行业专用节点类型及字段
- 行业专用分析 Agent 列表
- 通用 Agent（SentimentAnalyzer、SWOT、QA 等）跨行业复用

---

## 10. 非功能需求

| 维度 | 目标 |
|------|------|
| 溯源完整性 | 每条分析结论可追溯到至少一条原始数据 |
| 可观测性 | 每个 Agent 的 LLM 调用、图谱写入、工具调用全量审计 |
| 容错性 | 单 Agent 失败影响限于子图，支持断点续传 |
| 成本可控 | LLM 网关限流 + 缓存 + 成本追踪面板 |
| 响应时间 | 快速（仅官网+G2）< 2min，标准（+社媒+新闻）< 5min，深度（+第三方API数据）< 10min |
| 反馈重试上限 | QA 拒绝后最多重跑 2 轮，超限标记 DEGRADED，报告中标注低置信度 |
