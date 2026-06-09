"""ToolCache 单元测试 — 验证 auto/force_cache/bypass 三种模式、TTL、key 过滤。"""

import json
import os
import sqlite3
import time
import tempfile

import pytest

from src.agents.tools.cache import ToolCache, TTL_CONFIG, NEVER_CACHE


# ── helpers ──

class _FakeTool:
    """模拟一个可调用工具，记录调用次数。"""
    def __init__(self, name="test_tool"):
        self.name = name
        self.call_count = 0

    async def execute(self, **kwargs):
        self.call_count += 1
        return {"result": f"call_{self.call_count}", "params": kwargs}


class _FakeNeverCacheTool:
    """模拟不可缓存工具。"""
    name = "graph_query"

    async def execute(self, **kwargs):
        return {"nodes": []}


@pytest.fixture
def cache_db(tmp_path):
    """创建临时数据库路径。"""
    return str(tmp_path / "test_tool_cache.db")


@pytest.fixture
def cache(cache_db, monkeypatch):
    """创建一个 auto 模式的 ToolCache 实例。"""
    monkeypatch.setenv("TOOL_CACHE_MODE", "auto")
    return ToolCache(db_path=cache_db)


# ── auto 模式 ──

class TestAutoMode:
    @pytest.mark.asyncio
    async def test_cache_miss_calls_tool(self, cache):
        tool = _FakeTool()
        result = await cache.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert result["result"] == "call_1"
        assert tool.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self, cache):
        tool = _FakeTool()
        # First call: miss → call tool
        r1 = await cache.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert r1["result"] == "call_1"
        # Second call: hit → return cached
        r2 = await cache.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert r2["result"] == "call_1"  # same as first call, not call_2
        assert r2["_cache_hit"] is True
        assert tool.call_count == 1  # tool not called again

    @pytest.mark.asyncio
    async def test_different_params_different_key(self, cache):
        tool = _FakeTool()
        r1 = await cache.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        r2 = await cache.get_or_call("test_tool", {"query": "钉钉"}, tool.execute)
        assert r1["result"] == "call_1"
        assert r2["result"] == "call_2"  # different params → different key → call again
        assert tool.call_count == 2

    @pytest.mark.asyncio
    async def test_underscore_params_excluded_from_key(self, cache):
        tool = _FakeTool()
        # Same business params, different _task_id → should hit cache
        r1 = await cache.get_or_call(
            "test_tool", {"query": "飞书"},
            tool.execute, call_kwargs={"query": "飞书", "_task_id": "task_1"},
        )
        r2 = await cache.get_or_call(
            "test_tool", {"query": "飞书"},
            tool.execute, call_kwargs={"query": "飞书", "_task_id": "task_2"},
        )
        assert r2["_cache_hit"] is True
        assert tool.call_count == 1

    @pytest.mark.asyncio
    async def test_error_response_not_cached(self, cache):
        call_count = 0

        async def flaky_tool(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"error": "timeout", "results": []}
            return {"result": "success"}

        r1 = await cache.get_or_call("test_tool", {"query": "x"}, flaky_tool)
        assert "error" in r1
        r2 = await cache.get_or_call("test_tool", {"query": "x"}, flaky_tool)
        assert r2["result"] == "success"
        assert call_count == 2  # error was not cached → retried

    @pytest.mark.asyncio
    async def test_never_cache_tools_always_call(self, cache):
        tool = _FakeNeverCacheTool()
        r1 = await cache.get_or_call("graph_query", {"node_type": "FeatureNode"}, tool.execute)
        r2 = await cache.get_or_call("graph_query", {"node_type": "FeatureNode"}, tool.execute)
        assert "_cache_hit" not in r1
        assert "_cache_hit" not in r2  # never cached


# ── force_cache 模式 ──

class TestForceCacheMode:
    @pytest.mark.asyncio
    async def test_hit_returns_cached(self, cache_db, monkeypatch):
        monkeypatch.setenv("TOOL_CACHE_MODE", "auto")
        c = ToolCache(db_path=cache_db)
        tool = _FakeTool()
        # Warm up cache in auto mode
        await c.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert tool.call_count == 1

        # Switch to force_cache
        monkeypatch.setenv("TOOL_CACHE_MODE", "force_cache")
        c2 = ToolCache(db_path=cache_db)
        r = await c2.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert r["_cache_hit"] is True
        assert r["result"] == "call_1"
        assert tool.call_count == 1  # not called again

    @pytest.mark.asyncio
    async def test_miss_returns_error(self, cache_db, monkeypatch):
        monkeypatch.setenv("TOOL_CACHE_MODE", "force_cache")
        c = ToolCache(db_path=cache_db)
        tool = _FakeTool()
        r = await c.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert "error" in r
        assert "cache_miss" in r["error"]
        assert r.get("_cache_required") is True
        assert tool.call_count == 0  # tool NOT called in force_cache mode


# ── bypass 模式 ──

class TestBypassMode:
    @pytest.mark.asyncio
    async def test_always_calls_tool(self, cache_db, monkeypatch):
        monkeypatch.setenv("TOOL_CACHE_MODE", "bypass")
        c = ToolCache(db_path=cache_db)
        tool = _FakeTool()
        r1 = await c.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        r2 = await c.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert tool.call_count == 2  # called every time
        assert "_cache_hit" not in r1
        assert "_cache_hit" not in r2


# ── TTL 过期 ──

class TestTTLExpiry:
    @pytest.mark.asyncio
    async def test_expired_entry_calls_tool_again(self, cache_db, monkeypatch):
        monkeypatch.setenv("TOOL_CACHE_MODE", "auto")
        c = ToolCache(db_path=cache_db)
        tool = _FakeTool()

        # Manually set a very short TTL for test_tool by injecting an old timestamp
        r1 = await c.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert tool.call_count == 1

        # Backdoor: age the memory entry to make it expired
        key = c._make_key("test_tool", {"query": "飞书"})
        ts, value = c._memory[key]
        c._memory[key] = (ts - 999999, value)  # set ts far in the past

        # Also age the SQLite entry
        with sqlite3.connect(cache_db) as conn:
            conn.execute("UPDATE cache SET ts = ? WHERE key = ?", (ts - 999999, key))
            conn.commit()

        r2 = await c.get_or_call("test_tool", {"query": "飞书"}, tool.execute)
        assert tool.call_count == 2  # expired → re-called
        assert "_cache_hit" not in r2


# ── Key 生成 ──

class TestKeyGeneration:
    def test_key_stability(self):
        """Same params → same key."""
        k1 = ToolCache._make_key("serper_search", {"query": "飞书", "gl": "cn"})
        k2 = ToolCache._make_key("serper_search", {"query": "飞书", "gl": "cn"})
        assert k1 == k2

    def test_key_ignores_underscore_params(self):
        k1 = ToolCache._make_key("serper_search", {"query": "飞书", "_task_id": "t1"})
        k2 = ToolCache._make_key("serper_search", {"query": "飞书", "_task_id": "t2"})
        assert k1 == k2

    def test_key_ignores_none_values(self):
        k1 = ToolCache._make_key("serper_search", {"query": "飞书", "hl": None})
        k2 = ToolCache._make_key("serper_search", {"query": "飞书"})
        assert k1 == k2

    def test_different_tools_different_keys(self):
        k1 = ToolCache._make_key("serper_search", {"query": "飞书"})
        k2 = ToolCache._make_key("tavily", {"query": "飞书"})
        assert k1 != k2


# ── Stats / Clear ──

class TestStatsAndClear:
    @pytest.mark.asyncio
    async def test_stats(self, cache):
        tool = _FakeTool()
        await cache.get_or_call("test_tool", {"query": "a"}, tool.execute)
        await cache.get_or_call("test_tool", {"query": "b"}, tool.execute)
        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert "test_tool" in stats["by_tool"]
        assert stats["by_tool"]["test_tool"] == 2

    @pytest.mark.asyncio
    async def test_clear_by_tool(self, cache):
        tool = _FakeTool()
        await cache.get_or_call("test_tool", {"query": "a"}, tool.execute)
        count = cache.clear("test_tool")
        assert count == 1
        stats = cache.stats()
        assert stats["total_entries"] == 0

    @pytest.mark.asyncio
    async def test_clear_all(self, cache):
        tool = _FakeTool()
        await cache.get_or_call("test_tool", {"query": "a"}, tool.execute)
        count = cache.clear()
        assert count >= 1
        stats = cache.stats()
        assert stats["total_entries"] == 0


# ── TTL Config ──

class TestTTLConfig:
    def test_known_tools_have_custom_ttl(self):
        """关键工具应该有自定义 TTL，不是默认 1h。"""
        assert TTL_CONFIG["firecrawl"] > 86400  # 至少 1 天
        assert TTL_CONFIG["serper_search"] >= 3 * 86400
        assert TTL_CONFIG["social_media"] >= 7 * 86400
        assert TTL_CONFIG["newsapi"] <= 2 * 86400  # 新闻时效高

    def test_never_cache_set(self):
        assert "graph_query" in NEVER_CACHE
        assert "graph_write" in NEVER_CACHE
