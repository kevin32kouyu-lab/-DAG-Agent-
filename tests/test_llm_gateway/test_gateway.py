import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from src.llm_gateway.gateway import LLMGateway


def anthropic_message(content: str = "{}"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=content)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


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


@pytest.mark.asyncio
async def test_anthropic_opus_47_omits_sampling_parameters():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client

    await gw._chat_anthropic(
        "claude-opus-4-7",
        "system",
        [{"role": "user", "content": "hello"}],
        max_tokens=128,
        temperature=0.1,
        top_p=0.9,
        top_k=40,
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-7"
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert "top_k" not in kwargs


@pytest.mark.asyncio
async def test_anthropic_opus_48_omits_sampling_parameters():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client

    await gw._chat_anthropic(
        "claude-opus-4-8",
        "system",
        [{"role": "user", "content": "hello"}],
        max_tokens=128,
        temperature=0.1,
        top_p=0.9,
        top_k=40,
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-opus-4-8"
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert "top_k" not in kwargs


@pytest.mark.asyncio
async def test_anthropic_sonnet_46_keeps_temperature():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client

    await gw._chat_anthropic(
        "claude-sonnet-4-6",
        "system",
        [{"role": "user", "content": "hello"}],
        max_tokens=128,
        temperature=0.2,
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["temperature"] == 0.2


@pytest.mark.asyncio
async def test_anthropic_opus_48_converts_budget_thinking_to_adaptive():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client

    await gw._chat_anthropic(
        "claude-opus-4-8",
        "system",
        [{"role": "user", "content": "hello"}],
        max_tokens=128,
        temperature=0.1,
        thinking={"type": "enabled", "budget_tokens": 4096},
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["thinking"] == {"type": "adaptive"}


@pytest.mark.asyncio
async def test_anthropic_opus_48_preserves_adaptive_thinking_display():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client

    await gw._chat_anthropic(
        "claude-opus-4-8",
        "system",
        [{"role": "user", "content": "hello"}],
        max_tokens=128,
        temperature=0.1,
        thinking={"type": "adaptive", "display": "summarized"},
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["thinking"] == {"type": "adaptive", "display": "summarized"}


@pytest.mark.asyncio
async def test_anthropic_output_schema_becomes_output_config_format():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    await gw._chat_anthropic(
        "claude-opus-4-8",
        "system",
        [{"role": "user", "content": "hello"}],
        max_tokens=128,
        temperature=0.1,
        output_schema=schema,
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["output_config"] == {
        "format": {"type": "json_schema", "schema": schema}
    }


@pytest.mark.asyncio
async def test_anthropic_output_config_passes_through():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client
    output_config = {"effort": "high"}

    await gw._chat_anthropic(
        "claude-opus-4-8",
        "system",
        [{"role": "user", "content": "hello"}],
        max_tokens=128,
        temperature=0.1,
        output_config=output_config,
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["output_config"] == output_config


@pytest.mark.asyncio
async def test_chat_does_not_send_response_format_to_anthropic():
    gw = LLMGateway()
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=anthropic_message())
    gw._anthropic_client = mock_client

    await gw.chat(
        "system",
        [{"role": "user", "content": "return json"}],
        model="claude-opus-4-8",
        temperature=0.1,
        response_format={"type": "json_object"},
        skip_cache=True,
    )

    kwargs = mock_client.messages.create.call_args.kwargs
    assert "response_format" not in kwargs


@pytest.mark.asyncio
async def test_openai_compatible_keeps_supported_response_format():
    gw = LLMGateway(provider_map={"qwen-plus": "openai_compatible"})
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )
    )
    gw._openai_clients["qwen-plus"] = mock_client

    await gw.chat(
        "system",
        [{"role": "user", "content": "return json"}],
        model="qwen-plus",
        temperature=0.1,
        response_format={"type": "json_object"},
        skip_cache=True,
    )

    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}


def test_gateway_default_reasoning_model_is_opus_48():
    gw = LLMGateway()
    assert gw.resolve_model("reasoning") == "claude-opus-4-8"
