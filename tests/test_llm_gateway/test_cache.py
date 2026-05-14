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
