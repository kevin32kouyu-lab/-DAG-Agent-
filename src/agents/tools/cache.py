"""工具响应缓存层 — SQLite 单文件 + 内存 LRU，支持 auto/force_cache/bypass 三种模式。

与 `src/llm_gateway/cache.py` 的 LLM 响应缓存不同，本模块缓存的是**工具调用结果**
（如 Serper 搜索、Firecrawl 抓取、NewsAPI 新闻等），key 由 tool_name + params 决定。
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)

DEFAULT_TTL = 3600  # 1 hour default

# 按工具类型分级的 TTL（秒）
TTL_CONFIG: dict[str, int] = {
    "firecrawl": 30 * 86400,  # 网页内容变化慢
    "web_scrape": 30 * 86400,
    "batch_web_scrape": 30 * 86400,
    "social_media": 7 * 86400,  # 社交舆情 demo 友好
    "producthunt": 7 * 86400,
    "google_trends": 7 * 86400,
    "serper_search": 3 * 86400,
    "tavily": 3 * 86400,
    "reddit": 3 * 86400,
    "hackernews": 3 * 86400,
    "newsapi": 1 * 86400,  # 新闻时效高
    "gitee": 1 * 86400,
    "github": 1 * 86400,
    "npm": 1 * 86400,
    "pypi": 1 * 86400,
    "yfinance": 1 * 86400,
    "tianyancha": 1 * 86400,
    "app_store": 1 * 86400,
    "wayback_machine": 30 * 86400,
    "company_scope": 7 * 86400,
    "google_news": 3 * 86400,
}

# 永远不走缓存的工具（本地操作或太不稳定）
NEVER_CACHE = {"graph_query", "graph_write", "web_search"}


class ToolCache:
    """工具响应缓存，优先内存 LRU，再回落到 SQLite。

    三种模式（通过环境变量 ``TOOL_CACHE_MODE`` 控制）：
    - ``auto``（默认）：命中返回缓存；未命中调 API；写回缓存。
    - ``force_cache``：**只读缓存**；未命中返回 error，强制 LLM 改用其他工具。
    - ``bypass``：跳过缓存直接调 API（预灌缓存时使用）。
    """

    def __init__(self, db_path: str = "data/tool_cache.db"):
        self._memory: dict[str, tuple[float, dict]] = {}
        self._db_path = db_path
        self._mode = os.environ.get("TOOL_CACHE_MODE", "auto").lower()
        self._init_db()
        logger.info("ToolCache 初始化: mode=%s, db=%s", self._mode, self._db_path)

    @property
    def mode(self) -> str:
        return self._mode

    def _init_db(self) -> None:
        """初始化 SQLite 缓存表。磁盘失败时仅保留内存缓存能力。"""
        try:
            cache_dir = os.path.dirname(self._db_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS cache "
                    "(key TEXT PRIMARY KEY, ts REAL, value TEXT, tool_name TEXT)"
                )
                # 索引加速按工具名的查询（用于 warmup 统计）
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tool_name ON cache(tool_name)"
                )
                conn.commit()
        except Exception as exc:
            logger.warning("ToolCache 初始化失败: db_path=%s, reason=%s", self._db_path, exc)

    @staticmethod
    def _make_key(tool_name: str, params: dict) -> str:
        """生成稳定的缓存键。

        过滤掉以 ``_`` 开头的参数（如 ``_task_id``、``_agent_type``），
        避免不同任务因元数据差异导致永远 cache miss。
        """
        filtered = {
            k: v for k, v in sorted(params.items())
            if not k.startswith("_") and v is not None
        }
        data = json.dumps({"tool": tool_name, "params": filtered}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    async def get_or_call(
        self,
        tool_name: str,
        params: dict,
        call_fn: Callable[..., Any],
        call_kwargs: dict | None = None,
    ) -> dict:
        """缓存获取或调用工具（async）。

        :param tool_name: 工具名称（tool.name）
        :param params: 用于生成 cache key 的业务参数
        :param call_fn: 实际调用的 async 函数（如 tool.execute）
        :param call_kwargs: 实际传给 call_fn 的参数（通常含 ``_task_id`` 等内部字段，
            可能与 ``params`` 不同）。默认与 ``params`` 一致。
        :returns: 工具响应（命中时带 ``_cache_hit`` 标记）
        """
        if call_kwargs is None:
            call_kwargs = params

        # bypass 模式：跳过缓存，调 API 但不写回
        if self._mode == "bypass":
            return await call_fn(**call_kwargs)

        # Never-cache 工具：直接调 API
        if tool_name in NEVER_CACHE:
            return await call_fn(**call_kwargs)

        key = self._make_key(tool_name, params)
        ttl = TTL_CONFIG.get(tool_name, DEFAULT_TTL)

        # 1) 内存 hit
        entry = self._memory.get(key)
        if entry is not None:
            ts, value = entry
            if time.time() - ts <= ttl:
                hit = dict(value)
                hit["_cache_hit"] = True
                return hit
            del self._memory[key]

        # 2) 磁盘 hit
        try:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT ts, value FROM cache WHERE key = ?", (key,)
                ).fetchone()
            if row is not None:
                ts, value_raw = row
                if time.time() - ts <= ttl:
                    value = json.loads(value_raw)
                    self._memory[key] = (ts, value)
                    hit = dict(value)
                    hit["_cache_hit"] = True
                    return hit
        except Exception as exc:
            logger.warning("ToolCache 磁盘读取失败: key=%s, reason=%s", key, exc)

        # 3) force_cache 模式下未命中 → 返回 error，让 LLM 换工具
        if self._mode == "force_cache":
            return {
                "error": f"cache_miss: {tool_name} has no cached data for these params",
                "_cache_required": True,
                "results": [],
            }

        # 4) auto 模式：调 API 并缓存
        result = await call_fn(**call_kwargs)
        if isinstance(result, dict) and "error" not in result:
            self._store(key, tool_name, result)
        return result

    def _store(self, key: str, tool_name: str, value: dict) -> None:
        """写入缓存内容。磁盘失败时仍保留内存缓存。"""
        now = time.time()
        # 去掉 _cache_hit 标记再存，避免下次读取时带旧标记
        clean = {k: v for k, v in value.items() if k != "_cache_hit"}
        self._memory[key] = (now, clean)
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, ts, value, tool_name) VALUES (?, ?, ?, ?)",
                    (key, now, json.dumps(clean), tool_name),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("ToolCache 写入失败: key=%s, reason=%s", key, exc)

    def clear(self, tool_name: str | None = None) -> int:
        """清空缓存。指定 tool_name 时只清空该工具的缓存。"""
        count = 0
        try:
            with sqlite3.connect(self._db_path) as conn:
                if tool_name:
                    cursor = conn.execute("DELETE FROM cache WHERE tool_name = ?", (tool_name,))
                else:
                    cursor = conn.execute("DELETE FROM cache")
                count = cursor.rowcount
                conn.commit()
        except Exception as exc:
            logger.warning("ToolCache 清空失败: %s", exc)
        # 也清空内存
        if tool_name:
            # 内存里没法按 tool_name 精确清空，整表清
            pass
        self._memory.clear()
        return count

    def stats(self) -> dict:
        """返回缓存统计信息。"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
                by_tool = conn.execute(
                    "SELECT tool_name, COUNT(*) FROM cache GROUP BY tool_name ORDER BY COUNT(*) DESC"
                ).fetchall()
            return {
                "total_entries": total,
                "by_tool": {row[0]: row[1] for row in by_tool},
                "memory_entries": len(self._memory),
                "mode": self._mode,
            }
        except Exception as exc:
            return {"error": str(exc), "memory_entries": len(self._memory), "mode": self._mode}


# 全局单例
tool_cache = ToolCache()