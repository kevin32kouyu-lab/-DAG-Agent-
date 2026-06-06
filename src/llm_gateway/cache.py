"""这个模块提供 LLM 响应语义缓存，优先内存命中，再回落到 SQLite 持久缓存。"""

import hashlib
import json
import logging
import os
import sqlite3
import time

logger = logging.getLogger(__name__)


class SemanticCache:
    """管理 LLM 响应缓存，磁盘失败时降级为内存缓存。"""

    def __init__(self, ttl_seconds: int = 86400, db_path: str = "data/cache.db"):
        self._cache: dict[str, tuple[float, str]] = {}
        self.ttl = ttl_seconds
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化 SQLite 缓存表，失败时记录日志并保留内存缓存能力。"""
        try:
            cache_dir = os.path.dirname(self._db_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS cache "
                    "(key TEXT PRIMARY KEY, ts REAL, value TEXT)"
                )
                conn.commit()
        except Exception as exc:
            logger.warning("缓存初始化失败: db_path=%s, reason=%s", self._db_path, exc)

    def _make_key(self, prompt: str, system: str, messages: list[dict]) -> str:
        """根据 prompt、system 和消息列表生成稳定缓存键。"""
        data = json.dumps(
            {"prompt": prompt, "system": system, "messages": messages},
            sort_keys=True,
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, prompt: str, system: str, messages: list[dict]) -> str | None:
        """读取缓存内容，先查内存，再查 SQLite。"""
        key = self._make_key(prompt, system, messages)
        # 1) memory hit
        entry = self._cache.get(key)
        if entry is not None:
            ts, value = entry
            if time.time() - ts <= self.ttl:
                return value
            del self._cache[key]
        # 2) disk hit
        try:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    "SELECT ts, value FROM cache WHERE key = ?", (key,)
                ).fetchone()
            if row is not None:
                ts, value = row
                if time.time() - ts <= self.ttl:
                    self._cache[key] = (ts, value)
                    return value
        except Exception as exc:
            logger.warning("缓存读取失败: db_path=%s, reason=%s", self._db_path, exc)
        return None

    def set(self, prompt: str, system: str, messages: list[dict], response: str) -> None:
        """写入缓存内容，磁盘失败时仍保留内存缓存。"""
        key = self._make_key(prompt, system, messages)
        now = time.time()
        self._cache[key] = (now, response)
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, ts, value) VALUES (?, ?, ?)",
                    (key, now, response),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("缓存写入失败: db_path=%s, reason=%s", self._db_path, exc)
