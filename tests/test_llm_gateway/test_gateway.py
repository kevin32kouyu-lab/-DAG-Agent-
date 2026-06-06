import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from src.llm_gateway.gateway import LLMGateway


@pytest.fixture
def gateway():
    return LLMGateway(default_model="test-model")


@pytest.mark.asyncio
async def test_chat_resolves_model_from_tier():
    gw = LLMGateway(
        default_model="claude-haiku-4-5",
        model_map={"reasoning": "claude-opus-4-7"},
    )
    assert gw.resolve_model("reasoning") == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_chat_uses_default_model_for_unknown_tier():
    gw = LLMGateway(default_model="claude-haiku-4-5")
    assert gw.resolve_model("batch") == "claude-haiku-4-5"
    assert gw.resolve_model("unknown") == "claude-haiku-4-5"


def test_gateway_resolve_model_by_tier():
    gw = LLMGateway(
        default_model="claude-haiku-4-5",
        model_map={
            "reasoning": "claude-opus-4-7",
            "analysis": "claude-sonnet-4-6",
            "batch": "claude-haiku-4-5",
        },
    )
    assert gw.resolve_model("reasoning") == "claude-opus-4-7"
    assert gw.resolve_model("batch") == "claude-haiku-4-5"
    assert gw.resolve_model("unknown_tier") == "claude-haiku-4-5"


def test_gateway_returns_completion():
    gw = LLMGateway(model_map={"test": "test-model"})
    assert gw.resolve_model("test") == "test-model"


def test_gateway_openai_compatible_provider():
    gw = LLMGateway(
        provider_map={
            "qwen-plus": "openai_compatible",
            "kimi-k2": "openai_compatible",
        },
    )
    assert gw._get_provider("qwen-plus") == "openai_compatible"
    assert gw._get_provider("claude-sonnet-4-6") == "anthropic"


def test_resolve_model_with_openai():
    gw = LLMGateway(
        model_map={
            "reasoning": "deepseek-v4",
            "batch": "qwen-plus",
        },
        provider_map={
            "deepseek-v4": "openai_compatible",
            "qwen-plus": "openai_compatible",
        },
    )
    assert gw.resolve_model("reasoning") == "deepseek-v4"
    assert gw._get_provider("deepseek-v4") == "openai_compatible"


@pytest.mark.asyncio
async def test_doubao_ep_omits_unsupported_response_format():
    """豆包 EP 不支持 json_object 参数，网关应自动去掉。"""
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )
    )
    gw._openai_clients["ep-test"] = mock_client

    await gw._chat_openai(
        "ep-test",
        "system",
        [{"role": "user", "content": "return json"}],
        max_tokens=128,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "ep-test"
    assert "response_format" not in kwargs
