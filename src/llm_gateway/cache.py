import hashlib
import json
import os
import sqlite3
import time


class SemanticCache:
    def __init__(self, ttl_seconds: int = 86400, db_path: str = "data/cache.db"):
        self._cache: dict[str, tuple[float, str]] = {}
        self.ttl = ttl_seconds
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache "
                "(key TEXT PRIMARY KEY, ts REAL, value TEXT)"
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _make_key(self, prompt: str, system: str, messages: list[dict]) -> str:
        data = json.dumps(
            {"prompt": prompt, "system": system, "messages": messages},
            sort_keys=True,
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, prompt: str, system: str, messages: list[dict]) -> str | None:
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
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT ts, value FROM cache WHERE key = ?", (key,)
            ).fetchone()
            conn.close()
            if row is not None:
                ts, value = row
                if time.time() - ts <= self.ttl:
                    self._cache[key] = (ts, value)
                    return value
        except Exception:
            pass
        return None

    def set(self, prompt: str, system: str, messages: list[dict], response: str) -> None:
        key = self._make_key(prompt, system, messages)
        now = time.time()
        self._cache[key] = (now, response)
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, ts, value) VALUES (?, ?, ?)",
                (key, now, response),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass
