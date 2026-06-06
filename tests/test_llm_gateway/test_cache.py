import pytest
import sqlite3
from src.llm_gateway.cache import SemanticCache


@pytest.fixture
def cache(tmp_path):
    return SemanticCache(ttl_seconds=3600, db_path=str(tmp_path / "cache.db"))


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


def test_cache_different_system_prompt():
    cache = SemanticCache(ttl_seconds=3600)
    cache.set("prompt", "system_a", [], "response_a")
    assert cache.get("prompt", "system_b", []) is None


def test_cache_different_messages():
    cache = SemanticCache(ttl_seconds=3600)
    cache.set("prompt", "system", [{"role": "user", "content": "msg_a"}], "response_a")
    assert cache.get("prompt", "system", [{"role": "user", "content": "msg_b"}]) is None


def test_cache_ttl_not_expired():
    cache = SemanticCache(ttl_seconds=3600)
    cache.set("p", "s", [], "r")
    assert cache.get("p", "s", []) == "r"


def test_cache_logs_init_failure(monkeypatch, caplog):
    def fail_makedirs(*_args, **_kwargs):
        raise OSError("directory unavailable")

    monkeypatch.setattr("src.llm_gateway.cache.os.makedirs", fail_makedirs)
    caplog.set_level("WARNING", logger="src.llm_gateway.cache")

    SemanticCache(ttl_seconds=3600, db_path="data/cache.db")

    assert "缓存初始化失败" in caplog.text
    assert "directory unavailable" in caplog.text


def test_cache_logs_disk_get_failure(cache, monkeypatch, caplog):
    def fail_connect(*_args, **_kwargs):
        raise sqlite3.OperationalError("disk unavailable")

    monkeypatch.setattr("src.llm_gateway.cache.sqlite3.connect", fail_connect)
    caplog.set_level("WARNING", logger="src.llm_gateway.cache")

    assert cache.get("missing", "system", []) is None

    assert "缓存读取失败" in caplog.text
    assert "disk unavailable" in caplog.text


def test_cache_logs_disk_set_failure(cache, monkeypatch, caplog):
    def fail_connect(*_args, **_kwargs):
        raise sqlite3.OperationalError("disk unavailable")

    monkeypatch.setattr("src.llm_gateway.cache.sqlite3.connect", fail_connect)
    caplog.set_level("WARNING", logger="src.llm_gateway.cache")

    cache.set("prompt", "system", [], "response")

    assert "缓存写入失败" in caplog.text
    assert "disk unavailable" in caplog.text
