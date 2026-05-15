import json
import os
from src.llm_gateway.gateway import LLMGateway, LLMResponse


class _NoOpCache:
    """Cache that never hits — forces all calls through to real LLM during recording."""
    def get(self, *args, **kwargs):
        return None
    def set(self, *args, **kwargs):
        pass


class ReplayLLMGateway:
    """Records or replays LLM chat() calls for deterministic integration testing.

    Record mode: delegates to real gateway, saves responses in call order.
    Replay mode: returns saved responses in call order, no network calls.

    Usage:
        # Record
        gw = ReplayLLMGateway(real_gateway, fixture_path, record_mode=True)
        # ... run pipeline ...

        # Replay
        gw = ReplayLLMGateway(real_gateway, fixture_path, record_mode=False)
        # ... run pipeline (same order, same inputs) ...
    """

    def __init__(self, real_gateway=None, fixture_path=None, record_mode=False):
        self._gateway = real_gateway
        self._fixture_path = fixture_path
        self._record_mode = record_mode
        self._responses: list[dict] = []
        self._replay_index = 0

        if fixture_path and os.path.exists(fixture_path) and not record_mode:
            with open(fixture_path, encoding="utf-8") as f:
                self._responses = json.load(f)

        # Disable cache on real gateway during recording so we get fresh responses
        if record_mode and real_gateway is not None:
            real_gateway.cache = _NoOpCache()

    async def chat(self, system, messages, model_tier="analysis", model=None,
                   agent_type=None, max_tokens=4096, temperature=0.3, response_format=None):

        if self._record_mode:
            response = await self._gateway.chat(
                system=system, messages=messages, model_tier=model_tier,
                model=model, agent_type=agent_type, max_tokens=max_tokens,
                temperature=temperature, response_format=response_format,
            )
            self._responses.append({
                "content": response.content,
                "model": response.model,
                "tokens_in": response.tokens_in,
                "tokens_out": response.tokens_out,
                "cost": response.cost,
            })
            self._save()
            return response

        if self._replay_index >= len(self._responses):
            raise RuntimeError(
                f"Replay exhausted: {self._replay_index} calls made, "
                f"only {len(self._responses)} recorded. "
                "Fixture may be stale — re-record with --record-fixtures."
            )

        data = self._responses[self._replay_index]
        self._replay_index += 1
        return LLMResponse(
            content=data["content"],
            model=data.get("model", ""),
            tokens_in=data.get("tokens_in", 0),
            tokens_out=data.get("tokens_out", 0),
            cost=data.get("cost", 0.0),
            cached=True,
        )

    @property
    def replay_count(self):
        return self._replay_index

    @property
    def recorded_count(self):
        return len(self._responses)

    def _save(self):
        if self._fixture_path:
            os.makedirs(os.path.dirname(self._fixture_path), exist_ok=True)
            with open(self._fixture_path, "w", encoding="utf-8") as f:
                json.dump(self._responses, f, indent=2, ensure_ascii=False)

    def __getattr__(self, name):
        if self._gateway is None:
            raise AttributeError(f"No real gateway to delegate '{name}' to")
        return getattr(self._gateway, name)
