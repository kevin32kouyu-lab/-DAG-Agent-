# Phase 7: 基础设施增强（生产级稳定性）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** 将 Demo 级系统加固到生产可用——LLM 语义缓存、断点续传、审计日志、配置中心、健康检查、安全层。

**可验证产出:** 任务中断后可恢复、重复 LLM 调用被缓存命中、审计日志可追查每一步操作、配置可热加载。

**依赖:** P1-P6 完成

**Spec Reference:** 设计文档第 2.2 节企业基础设施层，第 2.2.1 节降级策略

---

### Task 7.1: LLM 语义缓存

**Files:**
- Create: `src/llm_gateway/cache.py`
- Create: `tests/test_llm_gateway/test_cache.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_llm_gateway/test_cache.py
import pytest
from src.llm_gateway.cache import SemanticCache


@pytest.fixture
def cache():
    return SemanticCache(ttl_seconds=3600)


def test_cache_hit_same_input(cache):
    cache.set("test_prompt", "test_system", [], "cached_response")
    result = cache.get("test_prompt", "test_system", [])
    assert result == "cached_response"


def test_cache_miss_different_input(cache):
    cache.set("prompt_a", "sys", [], "response_a")
    assert cache.get("prompt_b", "sys", []) is None


def test_cache_key_deterministic():
    cache = SemanticCache()
    key1 = cache._make_key("hello world", "system msg", [{"role": "user", "content": "hi"}])
    key2 = cache._make_key("hello world", "system msg", [{"role": "user", "content": "hi"}])
    key3 = cache._make_key("hello world!", "system msg", [{"role": "user", "content": "hi"}])
    assert key1 == key2
    assert key1 != key3


def test_cache_expiry():
    cache = SemanticCache(ttl_seconds=0)  # immediate expiry
    cache.set("p", "s", [], "response")
    assert cache.get("p", "s", []) is None
```

- [ ] **Step 2: 实现语义缓存**

```python
# src/llm_gateway/cache.py
import hashlib
import json
import time


class SemanticCache:
    def __init__(self, ttl_seconds: int = 86400):
        self._cache: dict[str, tuple[float, str]] = {}
        self.ttl = ttl_seconds

    def _make_key(self, prompt: str, system: str, messages: list[dict]) -> str:
        data = json.dumps({"prompt": prompt, "system": system, "messages": messages}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, prompt: str, system: str, messages: list[dict]) -> str | None:
        key = self._make_key(prompt, system, messages)
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts > self.ttl:
            del self._cache[key]
            return None
        return value

    def set(self, prompt: str, system: str, messages: list[dict], response: str) -> None:
        key = self._make_key(prompt, system, messages)
        self._cache[key] = (time.time(), response)
```

- [ ] **Step 3: 运行测试** — PASS

- [ ] **Step 4: Commit**

```bash
git add src/llm_gateway/cache.py tests/test_llm_gateway/test_cache.py
git commit -m "feat: add LLM semantic cache with SHA256-based content hashing"
```

---

### Task 7.2: LLM 成本追踪

**Files:**
- Create: `src/llm_gateway/cost_tracker.py`

- [ ] **Step 1: 实现 CostTracker**

```python
# src/llm_gateway/cost_tracker.py
from dataclasses import dataclass, field


@dataclass
class CostTracker:
    total_tokens: int = 0
    total_cost: float = 0.0
    llm_calls: int = 0
    per_agent: dict[str, dict] = field(default_factory=dict)

    def record(self, agent_type: str, tokens: int, cost: float) -> None:
        self.total_tokens += tokens
        self.total_cost += cost
        self.llm_calls += 1
        if agent_type not in self.per_agent:
            self.per_agent[agent_type] = {"tokens": 0, "cost": 0.0, "calls": 0}
        self.per_agent[agent_type]["tokens"] += tokens
        self.per_agent[agent_type]["cost"] += cost
        self.per_agent[agent_type]["calls"] += 1

    def summary(self) -> dict:
        return {
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 4),
            "total_calls": self.llm_calls,
            "per_agent": self.per_agent,
        }
```

- [ ] **Step 2: 集成到 LLMGateway.chat()** — 在返回前调用 `self.cost_tracker.record(model_tier, tokens, cost)`

- [ ] **Step 3: Commit**

```bash
git add src/llm_gateway/cost_tracker.py
git commit -m "feat: add LLM cost tracker per agent type"
```

---

### Task 7.3: 审计日志

**Files:**
- Create: `src/infrastructure/__init__.py`
- Create: `src/infrastructure/audit.py`

- [ ] **Step 1: 实现审计日志**

```python
# src/infrastructure/audit.py
import json
import sqlite3
from datetime import datetime
from typing import Any


class AuditLogger:
    def __init__(self, db_path: str = "data/audit.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS task_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL, node_id TEXT NOT NULL,
                agent_type TEXT NOT NULL, event TEXT NOT NULL,
                data TEXT DEFAULT '{}', timestamp TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS step_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL, node_id TEXT NOT NULL, agent_type TEXT NOT NULL,
                step_number INTEGER NOT NULL, phase TEXT NOT NULL,
                summary TEXT DEFAULT '', reasoning TEXT DEFAULT '',
                action TEXT DEFAULT '', params TEXT DEFAULT '{}',
                tokens INTEGER DEFAULT 0, cost REAL DEFAULT 0.0,
                nodes_created TEXT DEFAULT '[]', edges_created TEXT DEFAULT '[]',
                timestamp TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def log_event(self, task_id: str, node_id: str, agent_type: str,
                  event: str, data: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            "INSERT INTO task_audit_log (task_id, node_id, agent_type, event, data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, node_id, agent_type, event, json.dumps(data or {}), datetime.now().isoformat()),
        )
        self._conn.commit()

    def log_step_trace(self, trace) -> None:
        self._conn.execute(
            "INSERT INTO step_traces (task_id, node_id, agent_type, step_number, phase, summary, reasoning, action, params, tokens, cost, nodes_created, edges_created, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (trace.task_id, trace.node_id, trace.agent_type, trace.step_number,
             "act" if trace.action else "think",
             trace.observation_summary, trace.reasoning,
             trace.action, json.dumps(trace.action_params or {}),
             trace.llm_tokens, trace.llm_cost,
             json.dumps(trace.nodes_created), json.dumps(trace.edges_created),
             trace.timestamp.isoformat()),
        )
        self._conn.commit()

    def get_task_log(self, task_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM task_audit_log WHERE task_id = ? ORDER BY timestamp", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_step_traces(self, task_id: str, node_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM step_traces WHERE task_id = ? AND node_id = ? ORDER BY step_number",
            (task_id, node_id),
        ).fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 2: Commit**

```bash
git add src/infrastructure/audit.py
git commit -m "feat: add audit logger for task-level events and step-level traces"
```

---

### Task 7.4: 断点续传 + 任务队列

**Files:**
- Create: `src/infrastructure/snapshot.py`
- Create: `src/infrastructure/task_queue.py`

- [ ] **Step 1: 实现 SnapshotStore**

```python
# src/infrastructure/snapshot.py
import json
import sqlite3
from datetime import datetime
from src.dag.models import NodeSnapshot, NodeState


class SnapshotStore:
    def __init__(self, db_path: str = "data/snapshots.db"):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                task_id TEXT NOT NULL, node_id TEXT NOT NULL,
                state TEXT NOT NULL, kg_changeset TEXT DEFAULT '{}',
                checkpoint_time TEXT NOT NULL, llm_cost REAL DEFAULT 0.0,
                PRIMARY KEY (task_id, node_id)
            )
        """)
        self._conn.commit()

    def save(self, snapshot: NodeSnapshot) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (snapshot.task_id, snapshot.node_id, snapshot.state,
             json.dumps(snapshot.kg_changeset),
             snapshot.checkpoint_time.isoformat(), snapshot.llm_cost),
        )
        self._conn.commit()

    def load(self, task_id: str) -> dict[str, NodeSnapshot] | None:
        rows = self._conn.execute(
            "SELECT * FROM snapshots WHERE task_id = ?", (task_id,)
        ).fetchall()
        if not rows:
            return None
        return {
            r["node_id"]: NodeSnapshot(
                task_id=r["task_id"], node_id=r["node_id"],
                state=NodeState(r["state"]),
                kg_changeset=json.loads(r["kg_changeset"]),
                checkpoint_time=datetime.fromisoformat(r["checkpoint_time"]),
                llm_cost=r["llm_cost"],
            )
            for r in rows
        }
```

- [ ] **Step 2: 实现 TaskQueue**

```python
# src/infrastructure/task_queue.py
import asyncio
from dataclasses import dataclass, field
from src.dag.models import DAGNode


@dataclass
class TaskQueue:
    _queue: asyncio.PriorityQueue = field(default_factory=asyncio.PriorityQueue)

    async def enqueue(self, node: DAGNode) -> None:
        await self._queue.put((node.priority, node.node_id, node))

    async def dequeue(self) -> DAGNode:
        _, _, node = await self._queue.get()
        return node

    def size(self) -> int:
        return self._queue.qsize()
```

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/snapshot.py src/infrastructure/task_queue.py
git commit -m "feat: add snapshot store for checkpoint/resume and priority task queue"
```

---

### Task 7.5: 配置中心 + 降级策略

**Files:**
- Create: `src/infrastructure/config.py`
- Create: `src/schema/templates/saas.yaml`

- [ ] **Step 1: 实现配置中心**

```python
# src/infrastructure/config.py
import os
import yaml
from pathlib import Path


class Config:
    def __init__(self, config_dir: str = "config"):
        self._data: dict = {}
        self._config_dir = Path(config_dir)
        self.load()

    def load(self) -> None:
        self._data = {}
        for yf in self._config_dir.glob("*.yaml"):
            with open(yf) as f:
                self._data[yf.stem] = yaml.safe_load(f)
        self._data["env"] = dict(os.environ)

    def get(self, key: str, default=None):
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default

    def reload(self) -> None:
        self.load()


config = Config()
```

- [ ] **Step 2: 创建 SaaS 行业模板**

```yaml
# src/schema/templates/saas.yaml
industry: saas
default_dimensions:
  - name: 功能矩阵对比
    agent_type: FeatureAnalyzer
    weight: 20
  - name: 定价策略分析
    agent_type: PricingAnalyst
    weight: 20
  - name: 用户口碑分析
    agent_type: SentimentAnalyzer
    weight: 15
  - name: 技术栈推断
    agent_type: TechStackAnalyzer
    weight: 10
  - name: 市场定位分析
    agent_type: MarketPositionAnalyzer
    weight: 10

default_sources:
  priority: ["官网", "G2", "ProductHunt"]
  excluded: []
  min_credibility: 0.5

degradation_tiers:
  G2:
    primary: "网页采集（评分+评论摘要）"
    tier1: "仅提取公开评分（首页星级）"
    tier2: "搜索引擎缓存摘要"
    unavailable: "标记 G2 数据缺失"
  ProductHunt:
    primary: "网页采集公开页面"
    tier1: "ProductHunt RSS"
    tier2: "跳过"
  Reddit:
    primary: "搜索摘要"
    tier1: "搜索引擎 site:reddit.com 片段"
    tier2: "跳过"
  Official:
    primary: "httpx 直接请求"
    tier1: "Google 缓存 / Wayback Machine"
    tier2: "第三方页面产品描述替代"
```

- [ ] **Step 3: 实现降级策略处理器** — 在 Collector 中集成降级逻辑: 主路径失败→Tier 1→Tier 2→标记 DATA_DEGRADED

- [ ] **Step 4: 实现 Schema 模型** (设计文档第 4.4 节)

```python
# src/schema/__init__.py
# src/schema/models.py
from pydantic import BaseModel, Field


class FieldDef(BaseModel):
    name: str
    type: str  # str, int, float, enum, bool
    description: str = ""
    enum_values: list[str] | None = None
    range: tuple[float, float] | None = None


class Dimension(BaseModel):
    name: str
    description: str = ""
    focus_points: list[str] = Field(default_factory=list)
    node_types: list[str] = Field(default_factory=list)
    agent_type: str = ""
    prompt_override: str | None = None
    weight: float = 1.0


class SourcePrefs(BaseModel):
    priority_sources: list[str] = Field(default_factory=list)
    excluded_sources: list[str] = Field(default_factory=list)
    min_credibility: float = 0.5
    collection_depth: str = "standard"


class AnalysisSchema(BaseModel):
    industry: str = "saas"
    targets: list[str] = Field(default_factory=list)
    dimensions: list[Dimension] = Field(default_factory=list)
    exclude_dimensions: list[str] = Field(default_factory=list)
    custom_fields: dict[str, list[FieldDef]] = Field(default_factory=dict)
    dimension_weights: dict[str, float] = Field(default_factory=dict)
    source_preferences: SourcePrefs = SourcePrefs()
    benchmark_product: str | None = None
    report_audience: str = "product_manager"
    report_sections: list[str] = Field(default_factory=list)
    output_formats: list[str] = ["markdown"]
```

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/config.py src/schema/ src/infrastructure/
git commit -m "feat: add config center, SaaS template, degradation strategy, and schema models"
```

---

### Task 7.6: 安全层 + 健康检查

**Files:**
- Create: `src/infrastructure/health.py`

- [ ] **Step 1: 实现健康检查**

```python
# src/infrastructure/health.py
import time
from dataclasses import dataclass, field


@dataclass
class HealthCheck:
    agent_heartbeats: dict[str, float] = field(default_factory=dict)
    task_timeouts: dict[str, float] = field(default_factory=dict)
    heartbeat_timeout: float = 60.0
    task_timeout: float = 600.0

    def heartbeat(self, agent_id: str) -> None:
        self.agent_heartbeats[agent_id] = time.time()

    def get_unhealthy_agents(self) -> list[str]:
        now = time.time()
        return [aid for aid, ts in self.agent_heartbeats.items() if now - ts > self.heartbeat_timeout]

    def mark_task_start(self, task_id: str) -> None:
        self.task_timeouts[task_id] = time.time()

    def get_timed_out_tasks(self) -> list[str]:
        now = time.time()
        return [tid for tid, ts in self.task_timeouts.items() if now - ts > self.task_timeout]
```

- [ ] **Step 2: 安全层集成** — 确保: API Key 从环境变量读取（不进入代码仓库）、用户输入使用 Pydantic 校验消毒、CORS middleware 已配置。

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/health.py
git commit -m "feat: add health check with agent heartbeat and task timeout detection"
```

---

### Task 7.7: P7 集成验证

- [ ] **Step 1: 运行全部测试**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

- [ ] **Step 2: 验证缓存集成**

```python
# Quick manual test
from src.llm_gateway.cache import SemanticCache
cache = SemanticCache()
cache.set("test prompt", "system", [], "hello")
assert cache.get("test prompt", "system", []) == "hello"
print("Cache OK")
```

- [ ] **Step 3: 验证审计日志**

```bash
python -c "
from src.infrastructure.audit import AuditLogger
logger = AuditLogger(':memory:')
logger.log_event('t1', 'n1', 'Test', 'node_completed', {'detail': 'ok'})
print('Logs:', logger.get_task_log('t1'))
"
```

- [ ] **Step 4: 验证断点续传**

```bash
python -c "
from src.infrastructure.snapshot import SnapshotStore
from src.dag.models import NodeSnapshot, NodeState
store = SnapshotStore(':memory:')
snap = NodeSnapshot(task_id='t1', node_id='n1', state=NodeState.COMPLETED)
store.save(snap)
loaded = store.load('t1')
assert loaded and 'n1' in loaded
print('Snapshot OK')
"
```

- [ ] **Step 5: Final commit**

```bash
git commit -m "feat: P7 infrastructure verification - all systems operational"
```

---

## P7 完成检查清单

- [ ] 语义缓存：相同 prompt+system+messages 返回缓存结果
- [ ] 成本追踪：按 Agent 类型统计 tokens 和成本
- [ ] 审计日志：task_audit_log + step_traces 双表记录
- [ ] 断点续传：SnapshotStore 保存和恢复节点状态
- [ ] 任务队列：优先级调度，超时控制
- [ ] 配置中心：YAML + env 加载，支持热重载
- [ ] 降级策略：采集失败自动降级，记录 audit_log
- [ ] 健康检查：Agent 心跳 + 任务超时检测
- [ ] 安全层：.env 隔离 Key，Pydantic 校验输入
