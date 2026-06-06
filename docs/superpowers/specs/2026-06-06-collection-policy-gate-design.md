# Collection Policy Gate 设计方案

## 背景

当前系统已经支持 14 个 Agent 通过 DAG 协作完成竞品分析。近期从 DeepSeek 切换到豆包 Ark EP 后，Demo 出现明显变慢：Collector 对同一批 URL 重复搜索和抓取，且包含 G2、ProductHunt 等高风险页面，导致 Tavily / Wayback 兜底失败和多轮重试。

这不是 API key 无效，也不是单纯模型响应慢。根因是当前采集策略主要写在 prompt 里，模型仍然可以决定搜什么、抓什么、抓几轮、何时收手。DeepSeek 对这些 prompt 约束遵守较好，豆包 lite 模型更容易继续搜索和扩大证据范围，因此换模型后采集行为漂移。

## 目标

1. 让换模型不再改变采集策略。
2. 降低 Demo 和标准分析模式的成本、耗时和失败率。
3. 保留多 Agent 分工：Agent 继续负责判断和分析，策略层负责成本、风险和执行边界。
4. 支持 `standard`、`deep`、`debug` 三种采集策略，避免把策略写死在单一路径里。
5. 让“部分成功”被明确标记为降级完成，而不是反复失败重试。

## 非目标

1. 不取消多 Agent 架构。
2. 不把所有采集逻辑改成完全固定脚本。
3. 不在本设计中新增付费第三方 API。
4. 不改变报告生成、图表生成和知识图谱的核心数据模型。
5. 不追求一次性解决所有 Agent 的 prompt 稳定性问题。

## 核心设计

新增一个 **Collection Policy Gate**。它位于 Agent 和工具之间，负责决定模型提出的工具调用是否允许执行。

```text
Agent 提议工具调用
        ↓
Policy Gate 检查策略、预算、重复调用、来源风险
        ↓
允许：调用真实工具
拒绝：返回明确的策略拒绝结果
裁剪：截断 URL 列表后再调用工具
        ↓
Agent 基于结果继续整理或 finalize
```

这层不是替代 Agent，而是给 Agent 加边界。Agent 仍然判断“需要什么信息”和“如何整理结论”，但不能无限搜索、不能重复抓同一批 URL、不能在低成本模式下抓高风险页面。

## 策略模式

### standard

用于 Demo 和日常低成本分析。

- 每个 Collector 最多 1 次搜索。
- 每个 Collector 最多 1 次批量抓取。
- 每次批量抓取最多 5 个 URL。
- 优先允许：官网、价格页、文档页、GitHub、可信文章。
- 默认不直接抓取：G2、ProductHunt、Reddit、社交媒体、论坛页面。
- 高风险来源可以保留搜索摘要，供后续 Agent 参考。
- 同一个 Agent 不能重复执行同样参数的搜索或抓取。
- Collector 有任意有效页面或搜索摘要时，允许标记为 `degraded` 完成。
- Collector 默认不做多轮失败重试。

### deep

用于更完整、成本更高的分析。

- 每个 Collector 最多 3 次搜索。
- 每个 Collector 最多 2 次批量抓取。
- 每次批量抓取最多 10-15 个 URL。
- 允许 G2、ProductHunt、Reddit、新闻和社区来源。
- 允许更多兜底和重试。
- 失败后仍要记录风险和来源可信度。

### debug

用于排查模型行为和策略问题。

- 策略上限可与 `standard` 或 `deep` 一致。
- 额外记录每次工具调用是否被允许、裁剪或拒绝。
- 记录 URL 被过滤的原因。
- 记录重复调用被拒绝的 key。
- 方便判断是模型策略漂移，还是 Policy Gate 过紧。

## 模块设计

### CollectionPolicy

新增策略对象，负责描述当前任务的采集边界。

建议位置：`src/infrastructure/collection_policy.py`

主要字段：

```text
mode: standard | deep | debug
max_search_calls
max_scrape_calls
max_urls_per_batch
allow_high_risk_domains
high_risk_domains
preferred_domains
dedupe_tool_calls
collector_retry_limit
partial_success_as_degraded
```

策略来源：

- 读取 `CreateTaskRequest.collection_depth`
- `standard` 对应低成本默认策略
- `deep` 对应深度采集策略
- `debug` 可通过后续配置开关启用

### ToolCallGuard

新增工具调用闸门，负责在工具真正执行前检查调用。

建议位置：`src/agents/tools/policy_guard.py`

职责：

1. 统计每个任务、节点、工具的调用次数。
2. 对工具参数生成稳定 key，识别重复调用。
3. 对 `batch_web_scrape` 的 URL 做去重、过滤和截断。
4. 对高风险域名返回策略拒绝或摘要保留说明。
5. 返回结构化结果，告诉 Agent 这次调用被允许、裁剪还是拒绝。

返回结果示例：

```json
{
  "policy_status": "trimmed",
  "reason": "standard mode allows at most 5 scrape URLs",
  "allowed_params": {
    "urls": ["https://cursor.sh", "https://github.com/features/copilot"]
  },
  "filtered": [
    {"url": "https://www.g2.com/products/cursor/reviews", "reason": "high_risk_domain"}
  ]
}
```

### ToolRegistry 集成

Policy Gate 应尽量接近工具执行入口，避免每个 Agent 单独实现一遍。

推荐改法：

- `ToolRegistry` 保持注册工具职责。
- `BaseAgent._act()` 在调用工具前先调用 `ToolCallGuard`。
- `ToolCallGuard` 根据 `task_id`、`node_id`、`agent_type`、`collection_depth` 判断是否放行。
- 如果拒绝，`_act()` 直接返回策略拒绝结果，不调用真实工具。
- 如果裁剪，`_act()` 用裁剪后的参数调用真实工具，并把过滤信息附加到结果里。

这样所有 Agent 的工具调用都能被统一管住。

### DAG 和失败降级

当前调度器允许上游永久失败后下游继续执行，但任务状态会因为任意节点 `failed` 而显示整体失败，用户会误以为系统卡住。

建议调整：

1. Collector 部分成功时返回 `degraded`，不返回 `failed`。
2. Scheduler 将 `degraded` 视为可继续执行的正常终态。
3. `GET /api/task/{task_id}` 如果只有降级节点，不应返回 `failed`。
4. 如果 Collector 完全没有任何有效信息，再返回 `failed`。
5. WebSocket 和前端显示“降级完成”，而不是“失败”或“运行中”。

## 数据流

```text
用户创建任务
        ↓
CreateTaskRequest.collection_depth
        ↓
CollectionPolicy.from_request()
        ↓
DAG 节点 context 携带 policy mode
        ↓
Agent 调用工具
        ↓
ToolCallGuard 检查调用
        ↓
工具执行或策略拒绝
        ↓
StepTrace 记录策略结果
        ↓
DAG 根据 completed / degraded / failed 更新状态
```

## 状态语义

- `completed`：节点按预期完成。
- `degraded`：节点部分完成，信息质量或覆盖范围不足，但后续可以继续。
- `failed`：节点没有可用结果，或者发生不可恢复错误。

Collector 的判断建议：

```text
有成功抓取页面 → completed
没有成功抓取页面，但有搜索摘要 → degraded
没有抓取页面，也没有搜索摘要 → failed
```

## 前端展示

前端不需要大改，只需要更准确展示状态：

- `degraded` 显示为“降级完成”。
- 鼠标悬浮或详情区显示原因，例如“部分页面无法抓取，已使用搜索摘要继续”。
- 任务总状态中，只有 `failed` 才显示失败；`degraded` 不应让整条任务变失败。
- 监控页可以显示被过滤 URL 数量和原因，方便 Demo 时解释系统不是卡住。

## 测试方案

### 单元测试

1. `CollectionPolicy` 根据 `standard`、`deep` 返回不同限制。
2. `ToolCallGuard` 能过滤高风险域名。
3. `ToolCallGuard` 能截断批量抓取 URL。
4. `ToolCallGuard` 能拒绝重复工具调用。
5. `BaseAgent._act()` 在策略拒绝时不调用真实工具。
6. Collector 部分成功时返回 `degraded`。
7. 任务状态中只有 `degraded` 节点时不返回整体失败。

### 集成测试

1. 使用豆包或 mock gateway 跑 standard 模式，确认 Collector 不会重复抓同一批 URL。
2. standard 模式下 G2 / ProductHunt 不被直接抓取。
3. deep 模式下高风险来源可被放行。
4. 有部分采集结果时，后续 DataEnricher 和分析 Agent 可以继续执行。

### 回归检查

1. 默认后端测试通过。
2. 不运行真实 LLM 测试，除非显式开启。
3. Demo 任务的 Collector 步数、抓取 URL 数、重复调用数可从审计记录中验证。

## 落地步骤

1. 新增 `CollectionPolicy`，先覆盖 `standard` 和 `deep`。
2. 新增 `ToolCallGuard`，先管住 `tavily_search`、`web_search`、`web_scrape`、`batch_web_scrape`。
3. 在 `BaseAgent._act()` 接入 guard。
4. Collector 部分成功时返回 `degraded`。
5. 调整任务状态接口和 WebSocket 状态展示。
6. 补充单元测试和一个 mock 集成测试。
7. 用豆包跑一次 standard Demo，确认策略不再漂移。

## 风险和取舍

1. standard 模式信息覆盖会变少，但 Demo 成本和稳定性会明显改善。
2. 高风险来源不直接抓取，可能减少用户评论类证据；可以通过搜索摘要弥补。
3. deep 模式仍可能较慢，但这是用户主动选择的高成本模式。
4. Policy Gate 太紧时可能过滤掉有价值页面，因此 debug 模式需要保留过滤原因。

## 成功标准

1. 豆包 standard 模式下 Collector 不重复抓同一批 URL。
2. standard 模式下单个 Collector 抓取 URL 不超过 5 个。
3. G2 / ProductHunt 默认不进入直接抓取。
4. Collector 部分成功时任务继续执行，并显示“降级完成”。
5. 换模型后，采集次数、抓取上限和高风险来源策略保持一致。

