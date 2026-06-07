# 比赛项目优化任务清单

> 本文档将严格评估报告中的优化项拆分为可执行任务。每个任务包含目标、问题、建议改动、优先级和验收标准。

---

## 任务 1：修复 LLM Gateway 的 Claude 参数兼容问题

**优先级：P0**  
**对应评分维度：技术深度与工程完整度、多 Agent 协作稳定性**

### 当前问题

当前 LLM Gateway 对 Anthropic 调用统一传入 `temperature`。如果实际模型是 `claude-opus-4-7` 或 `claude-opus-4-8`，根据当前 Claude API 规则，该参数会导致请求 400。

同时 Anthropic 和 OpenAI-compatible 的结构化输出参数也应分开处理：

- OpenAI-compatible：`response_format`
- Anthropic：`output_config.format`

### 建议优化

1. 为 Anthropic 和 OpenAI-compatible 拆分参数适配逻辑。
2. 对 Opus 4.7 / 4.8 不传 `temperature/top_p/top_k`。
3. 默认 reasoning 模型建议改为 `claude-opus-4-8`。
4. 对复杂 reasoning 请求增加：
   - `thinking={"type": "adaptive"}`
   - `output_config={"effort": "high"}` 或按任务配置
5. 增加模型能力/模型前缀判断函数。
6. 增加单元测试覆盖：
   - Anthropic Opus 4.7/4.8 不传 temperature
   - Sonnet/OpenAI-compatible 参数保持可用
   - OpenAI-compatible 的 `ep-` 模型继续跳过 `response_format`

### 涉及文件

- [src/llm_gateway/gateway.py](../src/llm_gateway/gateway.py)
- [src/api/deps.py](../src/api/deps.py)
- [tests/test_llm_gateway/test_gateway.py](../tests/test_llm_gateway/test_gateway.py)

### 验收标准

- 使用 `claude-opus-4-7` / `claude-opus-4-8` 时不会传 `temperature`。
- Anthropic 结构化输出不再误用 OpenAI `response_format`。
- 相关测试通过。
- 真实 LLM smoke 测试不会因为参数不兼容失败。

---

## 任务 2：增加稳定 Demo / Replay 模式

**优先级：P0**  
**对应评分维度：业务价值与产品体验、技术完整度、交付答辩**

### 当前问题

比赛现场不能依赖真实网络、真实爬虫、第三方 API 或 LLM 长时间运行。当前项目虽然有 replay/integration 相关测试，但产品级一键 Demo 模式还不够显式。

### 建议优化

1. 增加 Demo 模式开关，例如：
   - `DEMO_MODE=1`
   - `planning_mode=demo`
   - 或任务创建页的 “演示模式” 按钮
2. 准备固定 Demo 数据集：
   - Figma vs Miro
   - Notion vs Coda
   - 飞书 vs 钉钉
3. Demo 模式下：
   - 使用固定来源数据
   - 固定 DAG
   - 固定 Agent 输出或 replay fixture
   - 固定报告和证据链
4. 保证 3 ~ 5 分钟内跑完整流程。
5. 前端明确标记 Demo 数据和真实数据区别。

### 涉及文件

- [src/api/routes/task.py](../src/api/routes/task.py)
- [src/dag/replay.py](../src/dag/replay.py)
- [tests/test_integration/fixtures/](../tests/test_integration/fixtures/)
- [web/src/pages/TaskPanel.tsx](../web/src/pages/TaskPanel.tsx)
- [web/src/pages/Monitor.tsx](../web/src/pages/Monitor.tsx)

### 验收标准

- 无需真实第三方 API 也能跑完整演示。
- Demo 从创建任务到报告生成不超过 5 分钟。
- 前端能展示 DAG、Agent 进度、报告和证据链。
- README 中包含 Demo 模式启动说明。

---

## 任务 3：报告增加证据链与可信度展示

**优先级：P0**  
**对应评分维度：多 Agent 协作与输出可信度、业务价值**

### 当前问题

比赛要求每条分析结论可追溯到原始数据源。当前项目有知识图谱和 trace_upstream 能力，但报告层展示还不够强。

### 建议优化

1. 报告每个核心结论增加：
   - 可信度分数
   - 数据来源 URL
   - 来源类型
   - 证据节点 ID
   - 是否经过 QA 校验
2. 报告结构建议：

```text
结论：Figma 在多人协同设计方面领先
可信度：0.86，高
证据来源：
- 官网功能页
- 用户评论
- ProductHunt 页面
```

3. 对无来源结论标记：
   - `低可信`
   - `无公开来源验证`
   - `需人工确认`
4. 前端报告页支持点击证据查看原始来源。

### 涉及文件

- [src/agents/writer.py](../src/agents/writer.py)
- [src/api/routes/report.py](../src/api/routes/report.py)
- [src/api/analytics_builder.py](../src/api/analytics_builder.py)
- [web/src/pages/Report.tsx](../web/src/pages/Report.tsx)
- [web/src/components/charts/](../web/src/components/charts/)

### 验收标准

- 报告中的关键结论至少 80% 带来源或低可信标记。
- 前端可点击查看来源。
- 无证据结论不会被包装成高可信事实。
- QA Agent 可检查证据覆盖率。

---

## 任务 4：实现可演示的 QA 打回重跑闭环

**优先级：P0**  
**对应评分维度：多 Agent 协作与输出可信度**

### 当前问题

项目已有 QA 和 CrossReview 反馈逻辑，但需要一个稳定可演示的场景证明反馈闭环真实可触发。

### 建议优化

1. 设计一个固定失败场景：
   - PricingAnalyst 生成无来源定价结论
   - QA_FactCheck 识别缺少来源
   - Scheduler 标记相关节点 rejected/rerunning
   - 重新执行分析或标记低可信
2. 前端 Monitor 页面展示：
   - QA 发现的问题
   - 被打回节点
   - 重跑轮次
   - 重跑前后结果差异
3. 报告页展示 QA 修正记录。

### 涉及文件

- [src/dag/scheduler.py](../src/dag/scheduler.py)
- [src/dag/feedback.py](../src/dag/feedback.py)
- [src/agents/qa_fact_check.py](../src/agents/qa_fact_check.py)
- [src/agents/qa_logic_check.py](../src/agents/qa_logic_check.py)
- [web/src/pages/Monitor.tsx](../web/src/pages/Monitor.tsx)
- [web/src/components/TracePanel.tsx](../web/src/components/TracePanel.tsx)

### 验收标准

- Demo 中可以稳定触发一次 QA reject。
- 前端能看到问题、打回、重跑、改善。
- 答辩时能解释反馈闭环不是写死流程。

---

## 任务 5：增加 Agent 决策回放页面

**优先级：P1**  
**对应评分维度：技术深度、可观测性、多 Agent 协作可信度**

### 当前问题

BaseAgent 已记录 StepTrace，但前端对每个 Agent 的观察、思考、动作、结果展示还不够比赛化。

### 建议优化

1. 在 Trace 页面增加 Agent Step Timeline：

```text
Step 1 Observe：读取哪些图谱节点
Step 2 Think：关键推理摘要
Step 3 Act：调用了哪个工具
Step 4 Result：工具返回摘要
Step 5 Finalize：输出结论
```

2. 展示：
   - prompt snapshot
   - response snapshot
   - tokens
   - cost
   - confidence
   - nodes_created
   - edges_created
3. 支持按 Agent、节点、任务阶段过滤。

### 涉及文件

- [src/agents/base.py](../src/agents/base.py)
- [src/infrastructure/audit.py](../src/infrastructure/audit.py)
- [src/api/routes/trace.py](../src/api/routes/trace.py)
- [web/src/pages/TraceExplorer.tsx](../web/src/pages/TraceExplorer.tsx)
- [web/src/components/TracePanel.tsx](../web/src/components/TracePanel.tsx)

### 验收标准

- 用户可查看每个 Agent 的执行步骤。
- 每步可看到输入、动作、输出和消耗。
- 可作为答辩中的可观测性亮点展示。

---

## 任务 6：增加知识图谱 Schema 可视化

**优先级：P1**  
**对应评分维度：技术深度、多 Agent 输出可信度**

### 当前问题

项目有三层知识图谱模型，但前端和文档中没有足够清晰地展示“竞品知识 Schema”。

### 建议优化

1. 增加知识图谱三层展示：

```text
Layer 1：原始来源
Layer 2：结构化分析
Layer 3：洞察与报告
```

2. 展示节点类型关系：

```text
SourceInfo → WebPage → FeatureNode → FeatureMatrix → Insight → ReportSection
```

3. 在报告页显示每条结论关联的图谱路径。
4. 在文档中补知识图谱 Schema 图。

### 涉及文件

- [src/knowledge_graph/models.py](../src/knowledge_graph/models.py)
- [src/knowledge_graph/query.py](../src/knowledge_graph/query.py)
- [src/api/routes/trace.py](../src/api/routes/trace.py)
- [web/src/pages/TraceExplorer.tsx](../web/src/pages/TraceExplorer.tsx)

### 验收标准

- 前端或文档中能清楚解释三层图谱。
- 每类节点职责明确。
- 证据链能以图谱路径展示。

---

## 任务 7：强化任务创建和人工介入体验

**优先级：P1**  
**对应评分维度：业务价值与产品体验**

### 当前问题

当前产品体验偏工程演示。比赛要求报告查看、溯源跳转、人工介入修正、Agent 决策回放等动作直观。

### 建议优化

1. 任务创建页支持：
   - 目标产品
   - 对比竞品
   - 行业类型
   - 分析维度选择
   - 采集深度
   - 报告受众
   - 是否开启人工审核
2. 来源审核页支持：
   - 查看候选来源
   - 删除不可信来源
   - 添加自定义 URL
   - 批准后继续执行
3. 报告页支持：
   - 人工修正结论
   - 重新生成报告
   - 导出 Markdown / JSON / PDF

### 涉及文件

- [web/src/pages/TaskPanel.tsx](../web/src/pages/TaskPanel.tsx)
- [web/src/pages/Monitor.tsx](../web/src/pages/Monitor.tsx)
- [web/src/pages/Report.tsx](../web/src/pages/Report.tsx)
- [src/api/routes/task.py](../src/api/routes/task.py)
- [src/api/routes/report.py](../src/api/routes/report.py)

### 验收标准

- 用户可以配置分析任务。
- 用户可以审核来源。
- 用户可以导出最终报告。
- 产品体验不像纯技术后台。

---

## 任务 8：补齐 `.env.example`、Docker 和部署说明

**优先级：P1**  
**对应评分维度：工程完整度、代码质量与文档、交付要求**

### 当前问题

项目缺少 `.env.example` 和完整部署说明。评委或其他用户难以快速复现。

### 建议优化

1. 增加 `.env.example`：

```text
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OPENAI_BASE_URL=
LLM_DEFAULT_MODEL=deepseek-chat
LLM_CACHE_TTL_SECONDS=2592000
TAVILY_API_KEY=
TIANYANCHA_TOKEN=
RUN_REAL_LLM_TESTS=0
```

2. 增加 Dockerfile。
3. 增加 docker-compose.yml。
4. README 中补：
   - 本地启动
   - 前端启动
   - 后端启动
   - Demo 模式
   - API key 配置
   - 常见问题

### 涉及文件

- [.env.example](../.env.example)
- [Dockerfile](../Dockerfile)
- [docker-compose.yml](../docker-compose.yml)
- [README.md](../README.md)
- [web/package.json](../web/package.json)

### 验收标准

- 新用户可按 README 在 10 分钟内启动项目。
- 配置项说明清楚。
- Demo 模式不依赖昂贵 API。

---

## 任务 9：补齐比赛交付文档和架构图

**优先级：P1**  
**对应评分维度：代码质量与文档、材料与答辩**

### 当前问题

现有文档偏开发计划和架构记录，缺少面向比赛评委的交付材料。

### 建议优化

新增 `docs/contest_submission.md`，包含：

1. 项目名称
2. 团队成员与分工
3. 核心功能清单
4. 端到端流程
5. 在线 Demo 链接
6. 演示视频链接
7. 源码仓库链接
8. README/运行说明
9. 系统架构图
10. Agent 协作图
11. 知识图谱 Schema 图
12. 大模型使用说明
13. 工程难点与解决方案
14. 项目完成度
15. 创新点
16. 合规说明

### 涉及文件

- [docs/contest_submission.md](contest_submission.md)
- [README.md](../README.md)
- [docs/](./)

### 验收标准

- 评委无需阅读代码即可理解系统亮点。
- 所有比赛提交字段都有对应内容。
- 架构图、流程图、Agent 协作图齐全。

---

## 任务 10：补充数据采集合规和 AI 风险控制说明

**优先级：P1**  
**对应评分维度：合规、材料与答辩**

### 当前问题

项目使用公开网页和第三方数据源，但合规说明不够显式。Writer fallback 也可能带来无来源结论风险。

### 建议优化

1. 新增合规说明文档：
   - 只采集公开网页
   - 尊重 robots.txt
   - 不绕过登录/付费/反爬
   - 不采集敏感个人信息
   - 第三方 API 按 ToS 使用
   - 用户评论只做匿名聚合
2. AI 风险控制说明：
   - 无证据结论标低可信
   - QA FactCheck 检查来源覆盖
   - CrossReview 检查冲突
   - 人工可审核和修正
3. 修改报告 fallback 策略：
   - 不将模型常识包装为高可信事实
   - 明确标注“未找到公开证据”

### 涉及文件

- [docs/compliance_and_ai_risk.md](compliance_and_ai_risk.md)
- [src/agents/writer.py](../src/agents/writer.py)
- [src/agents/qa_fact_check.py](../src/agents/qa_fact_check.py)
- [web/src/pages/Report.tsx](../web/src/pages/Report.tsx)

### 验收标准

- 文档中有明确合规声明。
- 报告中无来源内容不会被标记为高可信。
- 答辩时可以解释数据来源和隐私保护策略。

---

## 任务 11：强化报告业务价值和可操作建议

**优先级：P2**  
**对应评分维度：业务价值与产品体验**

### 当前问题

报告如果只是 Markdown 总结，业务价值不够。竞品分析需要给产品经理明确行动建议。

### 建议优化

1. 报告增加：
   - 功能差距矩阵
   - 定价对比表
   - 用户痛点 Top N
   - 市场机会点
   - 风险列表
   - 推荐路线图
2. 每条建议包含：
   - 建议内容
   - 证据
   - 影响
   - 优先级
   - 可信度

### 涉及文件

- [src/agents/writer.py](../src/agents/writer.py)
- [src/api/routes/report.py](../src/api/routes/report.py)
- [web/src/pages/Report.tsx](../web/src/pages/Report.tsx)
- [web/src/components/charts/](../web/src/components/charts/)

### 验收标准

- 报告不仅总结事实，还提供可执行建议。
- 建议带优先级和证据。
- 更贴近真实产品团队工作流。

---

## 任务 12：更新成本统计和模型配置说明

**优先级：P2**  
**对应评分维度：技术完整度、答辩可信度**

### 当前问题

成本价格表硬编码，可能与当前模型价格不一致。答辩时如果强调成本数值，容易被质疑。

### 建议优化

1. 将模型价格表移到配置文件。
2. 标注成本为估算值。
3. 支持按 provider 配置模型价格。
4. 文档中说明：
   - 当前默认模型
   - reasoning/analysis/batch tier
   - OpenAI-compatible fallback
   - 真实 LLM 测试开关

### 涉及文件

- [src/llm_gateway/gateway.py](../src/llm_gateway/gateway.py)
- [src/llm_gateway/cost_tracker.py](../src/llm_gateway/cost_tracker.py)
- [config/](../config/)
- [README.md](../README.md)

### 验收标准

- 成本统计不会误导为绝对精确。
- 模型配置对评委和使用者清晰。

---

## 总体优先级建议

### 立即做（P0）

1. 修 LLM Gateway 参数兼容
2. 增加稳定 Demo / Replay 模式
3. 报告增加证据链和可信度
4. 实现 QA 打回重跑可演示闭环

### 比赛前强烈建议做（P1）

5. Agent 决策回放页面
6. 知识图谱 Schema 可视化
7. 任务创建和人工介入体验
8. `.env.example`、Docker、部署说明
9. 比赛交付文档和架构图
10. 合规与 AI 风险控制说明

### 有时间再做（P2）

11. 强化报告业务价值和可操作建议
12. 更新成本统计和模型配置说明
