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
