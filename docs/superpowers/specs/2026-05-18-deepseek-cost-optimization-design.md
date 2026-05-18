# DeepSeek V4 成本与性能优化 — Phase 1

## 背景

项目全部使用 DeepSeek V4 (`deepseek-chat`)，通过 OpenAI 兼容接口调用。所有 Agent tier（reasoning/analysis/batch）映射到同一模型，无模型降级空间。DeepSeek 无 prompt caching。优化方向从"降单价"转为"堵浪费"。

当前状态：227 测试通过，14 skipped（需 API key 的集成测试）。Gateway 已是模块级单例（`deps.py` 中 `get_gateway()`），5 个分析 Agent 已在 DAG 层并行执行。

## 优化项

### 1. Token 预算系统 — 防泄漏

**问题：** Agent 在 ReAct 循环中卡住时无总 token 上限，持续消耗直到 max_steps 耗尽。

**方案：** BaseAgent 增加 `token_budget` 属性。在 `execute()` 开始时记录 cost_tracker 总 token 的快照，每步后计算增量，超预算立刻返回 degraded。无需改动 CostTracker。

**BaseAgent 新增属性（base.py）：**

```python
token_budget: int = 300_000  # 默认 300K tokens
```

**BaseAgent.execute() 改动（base.py）：** 在 `for step in range(self.max_steps):` 循环内，`_think()` 之后加入：

```python
agent_tokens = self.gateway.cost_tracker.total_tokens - start_tokens
if agent_tokens >= self.token_budget:
    degraded_result = {"summary": f"Token budget ({self.token_budget}) exceeded after {step+1} steps"}
    output = self._build_output(degraded_result)
    output.status = "degraded"
    return output, traces
```

**各 Agent 预算覆盖（各 Agent 文件）：**

| Agent | token_budget | 文件 |
|-------|-------------|------|
| SourceDiscovery, Collector | 100_000 | source_discovery.py, collector.py |
| DataEnricher | 150_000 | data_enricher.py |
| Feature/Sentiment/Pricing/TechStack/Market Analyzer | 300_000（默认） | 不改 |
| CrossReview, SWOT | 300_000（默认） | 不改 |
| ReportGenerator | 400_000 | writer.py |
| QA_FactCheck, QA_LogicCheck | 400_000 | qa_fact_check.py, qa_logic_check.py |

---

### 2. max_steps 收紧 — 防卡死浪费

**问题：** 大部分 Agent 默认 `max_steps=15`，但实际完成只需 3-5 步。正常 finalize 不受影响，仅在 Agent 卡住时触发。卡住时 15 步 vs 8 步差近一倍 token。

**方案：** 收紧到合理上限。

| Agent | 当前 | 改为 | 文件 |
|-------|------|------|------|
| BaseAgent 默认 | 15 | 10 | base.py |
| SourceDiscovery | 5 | 5（不变，加 token_budget） | source_discovery.py |
| Collector | 6 | 6（不变，加 token_budget） | collector.py |
| DataEnricher | 7 | 7（不变，加 token_budget） | data_enricher.py |
| Writer | 6 | 5 | writer.py |
| QA_FactCheck | 15 | 8 | qa_fact_check.py |
| QA_LogicCheck | 15 | 8 | qa_logic_check.py |

> SourceDiscovery/Collector/DataEnricher 的 max_steps 已经较紧，不必再收。分析 Agent/CrossReview/SWOT 通过 BaseAgent 默认值 10 生效。Orchestrator(5) 不变。

---

### 3. JSON 解析 Retry 轻量化 — 降低失败成本

**问题：** `_think()` 中 retry 重发完整 prompt（含 tools_desc + observation）+ 失败响应 + 纠正消息，cost ≈ 2.5x。DeepSeek 配合 `response_format={"type": "json_object"}` 失败率极低，但万一失败代价大。

**方案：** retry 时只发送纠正消息，不重复完整 prompt。依赖 DeepSeek 多轮上下文保持连贯。

**base.py `_think()` 改动：**

```python
# 修改前 (L218-228):
resp2 = await self.gateway.chat(
    system=self.system_prompt,
    messages=[
        {"role": "user", "content": prompt},           # 重复完整 prompt
        {"role": "assistant", "content": (resp.content or "")[:2000]},
        {"role": "user", "content": correction},
    ],
    ...
)

# 修改后:
correction_msg = (
    f"Your last response was NOT valid JSON. You MUST output ONLY a valid JSON object. "
    f"Wrap strings properly. Remember: {{\"reasoning\":\"...\",\"action\":\"...\",...}}. "
    f"Respond with json now."
)
resp2 = await self.gateway.chat(
    system=self.system_prompt,
    messages=[
        {"role": "user", "content": correction_msg},
    ],
    ...
)
```

> `response_format` 在 retry 时仍然生效（走 OpenAI 兼容路径时传入 kwargs），进一步降低二次失败概率。

---

### 4. SemanticCache 文件持久化 — 跨重启复用

**问题：** 当前缓存是内存字典，API 重启后丢失。相同产品多次分析时无法复用。

**方案：** 增加 SQLite 文件后端（`data/cache.db`），内存未命中时查文件，写入时双写。

**cache.py 改动：**

```python
class SemanticCache:
    def __init__(self, ttl_seconds: int = 86400, db_path: str = "data/cache.db"):
        self._cache: dict[str, tuple[float, str]] = {}
        self.ttl = ttl_seconds
        self._db_path = db_path
        self._init_db()

    def _init_db(self):
        import sqlite3, os
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, ts REAL, value TEXT)")
        conn.commit()
        conn.close()

    def get(self, prompt, system, messages):
        key = self._make_key(prompt, system, messages)
        # 1) memory hit
        entry = self._cache.get(key)
        if entry:
            ts, value = entry
            if time.time() - ts <= self.ttl:
                return value
            del self._cache[key]
        # 2) disk hit
        row = self._query_disk(key)
        if row:
            ts, value = row
            if time.time() - ts <= self.ttl:
                self._cache[key] = (ts, value)
                return value
        return None

    def set(self, prompt, system, messages, response):
        key = self._make_key(prompt, system, messages)
        self._cache[key] = (time.time(), response)
        self._write_disk(key, time.time(), response)
```

> 当前 `deps.py` 的 `get_gateway()` 创建 Gateway 时未传 cache 参数，SemanticCache 用默认 `data/cache.db` 路径即可。

---

### 5. SQLite WAL 模式 — 并发读写

**问题：** 默认 journal_mode=delete，写入阻塞读取。

**store.py 改动：**

```python
# _init_tables() 方法末尾加一行
self._conn.execute("PRAGMA journal_mode=WAL;")
```

---

### 6. DeepSeek 定价修正 — 成本追踪准确性

**问题：** `_estimate_cost_openai` 无 `deepseek-chat` 定价，fallback 到默认 $1/$2 per 1M。

**gateway.py 改动：**

```python
pricing = {
    "deepseek-chat": (0.27 / 1_000_000, 1.10 / 1_000_000),
    "kimi-k2": (0 / 1_000_000, 0 / 1_000_000),
    "qwen-plus": (2 / 1_000_000, 6 / 1_000_000),
    "glm-4": (1 / 1_000_000, 1 / 1_000_000),
}
```

---

## 改动清单

| 文件 | 改动量 | 内容 |
|------|-------|------|
| `src/llm_gateway/gateway.py` | ~5 行 | DeepSeek 定价修正 |
| `src/llm_gateway/cache.py` | ~40 行 | 文件持久化后端 |
| `src/agents/base.py` | ~20 行 | token_budget 属性 + per-agent 预算检查 + retry 轻量化 |
| `src/agents/writer.py` | 3 行 | max_steps: 6→4, token_budget: 400000 |
| `src/agents/source_discovery.py` | 3 行 | max_steps: 15→8, token_budget: 100000 |
| `src/agents/collector.py` | 3 行 | max_steps: 15→8, token_budget: 100000 |
| `src/agents/data_enricher.py` | 1 行 | token_budget: 150000 |
| `src/agents/qa_fact_check.py` | 3 行 | max_steps: 15→8, token_budget: 400000 |
| `src/agents/qa_logic_check.py` | 3 行 | max_steps: 15→8, token_budget: 400000 |
| `src/knowledge_graph/store.py` | 1 行 | WAL 模式 |

## 非目标

- 不改 Agent 行为逻辑（质量不变）
- 不改 DAG 调度逻辑
- 不改 API 接口
- 不改前端
- 不引入新依赖

## 验证

- 运行 `python -m pytest tests/ -v` 确保现有 227 测试通过
- 运行 `python -m pytest tests/test_agents/test_live_deepseek.py -v` 验证 DeepSeek 集成
- 手动检查 cost_tracker 输出确认定价修正生效
