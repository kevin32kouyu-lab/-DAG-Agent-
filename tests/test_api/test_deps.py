"""测试 API 依赖配置，避免模型接入被写死到某个供应商。"""

from src.api import deps
from src.llm_gateway.gateway import LLMGateway


def test_get_gateway_uses_env_openai_compatible_model(monkeypatch):
    """没有 Anthropic key 时，默认 LLM 可通过环境变量切换。"""
    monkeypatch.setattr(deps, "_gateway", None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_DEFAULT_MODEL", "ep-test")

    gateway = deps.get_gateway()

    assert gateway.default_model == "ep-test"
    assert gateway.model_map == {
        "reasoning": "ep-test",
        "analysis": "ep-test",
        "batch": "ep-test",
    }
    assert gateway.provider_map == {"ep-test": "openai_compatible"}


def test_get_gateway_uses_anthropic_default_model(monkeypatch):
    """有 Anthropic key 时应回到 Anthropic 默认网关配置。"""
    monkeypatch.setattr(deps, "_gateway", None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("LLM_DEFAULT_MODEL", raising=False)

    gateway = deps.get_gateway()

    assert isinstance(gateway, LLMGateway)
    assert gateway.resolve_model("reasoning") == "claude-opus-4-8"
    assert gateway.resolve_model("analysis") == "claude-sonnet-4-6"
    assert gateway.resolve_model("batch") == "claude-haiku-4-5"
