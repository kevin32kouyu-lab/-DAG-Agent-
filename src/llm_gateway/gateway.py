import os
from typing import Any
from dataclasses import dataclass

from src.llm_gateway.cache import SemanticCache
from src.llm_gateway.cost_tracker import CostTracker


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    cached: bool = False
    raw: Any = None


class LLMGateway:
    def __init__(
        self,
        default_model: str = "claude-sonnet-4-6",
        model_map: dict[str, str] | None = None,
        provider_map: dict[str, str] | None = None,
        cache: SemanticCache | None = None,
        cost_tracker: CostTracker | None = None,
    ):
        self.default_model = default_model
        self.model_map = model_map or {
            "reasoning": "claude-opus-4-8",
            "analysis": "claude-sonnet-4-6",
            "batch": "claude-haiku-4-5",
        }
        self.provider_map = provider_map or {}
        self.cache = cache or SemanticCache()
        self.cost_tracker = cost_tracker or CostTracker()
        self._anthropic_client = None
        self._openai_clients: dict[str, Any] = {}

    def resolve_model(self, tier: str) -> str:
        return self.model_map.get(tier, self.default_model)

    def _get_provider(self, model: str) -> str:
        return self.provider_map.get(model, "anthropic")

    def _get_anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
        return self._anthropic_client

    def _get_openai_client(self, model: str):
        if model not in self._openai_clients:
            from openai import AsyncOpenAI
            base_url = os.getenv(f"OPENAI_BASE_URL_{model.upper().replace('-', '_')}", "")
            api_key = os.getenv(f"OPENAI_API_KEY_{model.upper().replace('-', '_')}", os.getenv("OPENAI_API_KEY", ""))
            if not base_url:
                base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            self._openai_clients[model] = AsyncOpenAI(base_url=base_url, api_key=api_key)
        return self._openai_clients[model]

    async def chat(
        self,
        system: str,
        messages: list[dict[str, str]],
        model_tier: str = "analysis",
        model: str | None = None,
        agent_type: str | None = None,
        max_tokens: int = 4096,
        temperature: float | None = 0.3,
        top_p: float | None = None,
        top_k: int | None = None,
        thinking: dict[str, Any] | None = None,
        output_config: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        response_format: dict[str, str] | None = None,
        skip_cache: bool = False,
    ) -> LLMResponse:
        resolved = model or self.resolve_model(model_tier)

        # Check semantic cache (prompt = last user message), unless skipped
        if not skip_cache:
            prompt = messages[-1]["content"] if messages else ""
            cached = self.cache.get(prompt, system, messages)
            if cached is not None:
                return LLMResponse(content=cached, model=resolved, cached=True)
        else:
            prompt = ""

        provider = self._get_provider(resolved)

        if provider == "openai_compatible":
            resp = await self._chat_openai(resolved, system, messages, max_tokens, temperature, response_format)
        else:
            resp = await self._chat_anthropic(
                resolved,
                system,
                messages,
                max_tokens,
                temperature,
                top_p=top_p,
                top_k=top_k,
                thinking=thinking,
                output_config=output_config,
                output_schema=output_schema,
            )

        # Cache the response and track cost (skip caching when skip_cache=True)
        if not skip_cache:
            self.cache.set(prompt, system, messages, resp.content)
        ag = agent_type or model_tier
        self.cost_tracker.record(ag, resp.tokens_in + resp.tokens_out, resp.cost)
        return resp

    async def _chat_anthropic(
        self,
        model: str,
        system: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float | None,
        top_p: float | None = None,
        top_k: int | None = None,
        thinking: dict[str, Any] | None = None,
        output_config: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        client = self._get_anthropic()
        kwargs: dict[str, Any] = {
            "model": model,
            "system": system,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if not self._is_anthropic_opus_47_or_later(model):
            if temperature is not None:
                kwargs["temperature"] = temperature
            if top_p is not None:
                kwargs["top_p"] = top_p
            if top_k is not None:
                kwargs["top_k"] = top_k
        if thinking is not None:
            kwargs["thinking"] = self._normalize_anthropic_thinking(model, thinking)
        if output_config is not None and output_schema is not None:
            raise ValueError("output_config and output_schema are mutually exclusive")
        if output_schema is not None:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": output_schema}
            }
        elif output_config is not None:
            kwargs["output_config"] = output_config
        resp = await client.messages.create(**kwargs)
        # Handle both TextBlock and ThinkingBlock responses
        content_text = ""
        if resp.content:
            for block in resp.content:
                # Prefer TextBlock, but fallback to ThinkingBlock if no TextBlock found
                if hasattr(block, 'text'):
                    content_text = block.text
                    break
                elif hasattr(block, 'thinking'):
                    # ThinkingBlock - use thinking content as fallback
                    if not content_text:
                        content_text = block.thinking
        return LLMResponse(
            content=content_text,
            model=model,
            tokens_in=resp.usage.input_tokens if resp.usage else 0,
            tokens_out=resp.usage.output_tokens if resp.usage else 0,
            cost=self._estimate_cost(model, resp.usage),
            raw=resp,
        )

    async def _chat_openai(self, model: str, system: str, messages: list[dict],
                           max_tokens: int, temperature: float,
                           response_format: dict[str, str] | None = None) -> LLMResponse:
        client = self._get_openai_client(model)
        api_messages = [{"role": "system", "content": system}] + messages
        kwargs = dict(model=model, messages=api_messages, max_tokens=max_tokens, temperature=temperature)
        if response_format and self._supports_response_format(model):
            kwargs["response_format"] = response_format
        resp = await client.chat.completions.create(**kwargs)
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=model,
            tokens_in=resp.usage.prompt_tokens if resp.usage else 0,
            tokens_out=resp.usage.completion_tokens if resp.usage else 0,
            cost=self._estimate_cost_openai(model, resp.usage),
            raw=resp,
        )

    @staticmethod
    def _supports_response_format(model: str) -> bool:
        """判断 OpenAI-compatible 模型是否支持 response_format 参数。"""
        return not model.startswith("ep-")

    @staticmethod
    def _is_anthropic_opus_47_or_later(model: str) -> bool:
        normalized = model.removeprefix("anthropic.")
        return normalized in {"claude-opus-4-7", "claude-opus-4-8"}

    @staticmethod
    def _normalize_anthropic_thinking(model: str, thinking: dict[str, Any]) -> dict[str, Any]:
        if LLMGateway._is_anthropic_opus_47_or_later(model):
            if thinking.get("type") == "enabled":
                return {"type": "adaptive"}
        return thinking

    @staticmethod
    def _estimate_cost(model: str, usage: Any) -> float:
        if usage is None:
            return 0.0
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        pricing = {
            "claude-opus-4-8": (5 / 1_000_000, 25 / 1_000_000),
            "claude-opus-4-7": (5 / 1_000_000, 25 / 1_000_000),
            "claude-opus-4-6": (5 / 1_000_000, 25 / 1_000_000),
            "claude-sonnet-4-6": (3 / 1_000_000, 15 / 1_000_000),
            "claude-haiku-4-5": (1 / 1_000_000, 5 / 1_000_000),
        }
        in_price, out_price = pricing.get(model, (3 / 1_000_000, 15 / 1_000_000))
        return input_tokens * in_price + output_tokens * out_price

    @staticmethod
    def _estimate_cost_openai(model: str, usage: Any) -> float:
        if usage is None:
            return 0.0
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        pricing = {
            "deepseek-chat": (0.27 / 1_000_000, 1.10 / 1_000_000),
            "kimi-k2": (0 / 1_000_000, 0 / 1_000_000),
            "qwen-plus": (2 / 1_000_000, 6 / 1_000_000),
            "glm-4": (1 / 1_000_000, 1 / 1_000_000),
        }
        in_price, out_price = pricing.get(model, (1 / 1_000_000, 2 / 1_000_000))
        return input_tokens * in_price + output_tokens * out_price
