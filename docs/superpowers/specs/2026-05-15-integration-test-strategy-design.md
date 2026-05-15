# 全链路集成测试策略设计

## 问题

167 个测试中 166 个通过，但用户每次在前端试用都会发现大量 bug。根因是**测试策略缺陷**，而非架构问题：

- **API 测试极度浅薄**：`GET /api/task/nonexistent` 期望返回 200（[test_task.py:21-25](../../tests/test_api/test_task.py)），不测错误路径
- **Agent 测试全量 mock**：gateway、store、tools 全部 MagicMock，等于没测真实行为
- **WebSocket 测试只检查路由注册**：从未建立真实连接
- **无全链路测试**：POST task → DAG 调度 → Agent 执行 → report 生成，这条用户真正使用的路径零覆盖
- **前端仅 1 个组件测试**：StatusBadge，其余组件无测试

核心矛盾：测试在隔离环境下验证「Python 类能否实例化」，而非验证「用户能不能完成一次完整分析」。

## 方案：双层集成测试（A+B）

### 架构

```
┌─────────────────────────────────────────────────────────┐
│                    方案 A：真实 LLM 烟雾测试              │
│  慢（2-3min）、花钱、测真东西                            │
│  触发：PR 合并前 / 每日 CI                               │
│  标记：@pytest.mark.smoke                                │
├─────────────────────────────────────────────────────────┤
│                    方案 B：回放模式集成测试               │
│  快（秒级）、免费、确定性的                               │
│  触发：每次 commit                                       │
│  标记：@pytest.mark.integration                          │
└─────────────────────────────────────────────────────────┘

共用：ReplayLLMGateway（记录/回放 LLM 响应）
```

### ReplayLLMGateway（`src/llm_gateway/replay.py`）

所有 LLM 调用都经过 `LLMGateway.chat()`。在此层面做 recording/replay，上游代码完全无感知。

```
记录模式:  Agent → Gateway.chat() → ReplayLLMGateway → 真实 LLM API → 保存响应到 JSON
回放模式:  Agent → Gateway.chat() → ReplayLLMGateway → 从 JSON 读取响应（无网络）
```

- **请求指纹**：`SHA256(system_prompt + json(messages) + model)`
- **Fixture 格式**：`{fingerprint: {content, model, tokens_in, tokens_out, cost}}`
- **回放 miss**：清晰报错 `"Replay miss for fingerprint abc123. Fixture may be stale — re-record with --record-fixtures"`
- **CLI 参数**：`--record-fixtures` 切换为记录模式

### 方案 B 测试（回放模式）

文件中每个测试函数自己创建 replay gateway、注入 scheduler、用 TestClient 走完整 HTTP 路径。

| 测试 | 验证内容 |
|------|----------|
| `test_full_pipeline_single_target` | POST task(1 target) → 轮询 GET /task 直到 completed → GET /report → 验证 sections 非空、内容包含产品名 |
| `test_task_status_progression` | task 状态按 planning → in_progress → completed 推进 |
| `test_websocket_receives_dag_created` | `websocket.connect()` 后收到 `dag_created` 事件 |
| `test_websocket_receives_node_completed` | agent 完成时收到 `node_completed` 事件 |
| `test_nonexistent_task_returns_404` | GET /task/nonexistent → 404（修复当前返回 200 的 bug） |
| `test_report_json_format` | GET /report/{id}?format=json → 结构正确 |

### 方案 A 测试（真实 LLM）

| 测试 | 验证内容 |
|------|----------|
| `test_smoke_single_product` | POST task(["Notion"], depth="shallow") → 等待完成 → 验证报告存在且包含 Notion |
| `test_smoke_task_creation` | POST task → 立即返回 task_id + ws_endpoint + status=planning |

### 实施顺序

1. 创建 `ReplayLLMGateway`
2. 录制第一份 fixture（用真实 LLM 跑一次最小任务）
3. 写方案 B 的 6 个回放测试，全部通过
4. 写方案 A 的 2 个烟雾测试，全部通过
5. 修复 `test_get_task_returns_stub` — 不存在 task 应返回 404

### 文件变更

```
新增:
  src/llm_gateway/replay.py              ← ReplayLLMGateway
  tests/test_integration/fixtures/
    pipeline_smoke.json                  ← 录制的 LLM 响应
  tests/test_integration/test_pipeline_replay.py  ← 方案 B
  tests/test_integration/test_pipeline_smoke.py   ← 方案 A

修改:
  tests/test_integration/conftest.py     ← 新增 replay_gateway fixture
  tests/test_api/test_task.py            ← 修复 GET nonexistent 应返回 404
  tests/conftest.py                      ← 新增 --record-fixtures CLI 参数
```

### 不做什么

- 不修改任何 Agent/Executor/Scheduler 代码（仅新增测试基础设施）
- 不涉及前端测试（另开独立设计）
- 不回填已有单元测试的 mock（不在本次范围）
