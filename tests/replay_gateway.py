"""
ReplayLLMGateway: records real LLM responses to fixture files and replays them.

Plan A: Record once with real LLM → replay deterministically in CI/tests.
Fixtures capture real LLM behavior (malformed JSON, weird reasoning, etc.)
so tests exercise the actual robustness paths that mock tests never hit.
"""
import json
import hashlib
from pathlib import Path

from src.llm_gateway.gateway import LLMGateway, LLMResponse


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _make_cache_key(system: str, messages: list[dict]) -> str:
    """Deterministic key for matching LLM calls to fixture entries."""
    payload = json.dumps({"system": system, "messages": messages}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class RecordingGateway:
    """Wraps a real LLMGateway, records every chat() call to a fixture file."""

    def __init__(self, real_gateway: LLMGateway, fixture_path: Path):
        self._gateway = real_gateway
        self._path = Path(fixture_path)
        self._calls: list[dict] = []
        self._cache: dict[str, int] = {}  # cache_key → index in _calls

    @property
    def cost_tracker(self):
        return self._gateway.cost_tracker

    async def chat(self, **kwargs) -> LLMResponse:
        system = kwargs.get("system", "")
        messages = kwargs.get("messages", [])
        key = _make_cache_key(system, messages)

        # If same exact call was made before, replay from cache
        if key in self._cache:
            idx = self._cache[key]
            entry = self._calls[idx]
            return LLMResponse(
                content=entry["response"]["content"],
                model=entry["response"]["model"],
                tokens_in=entry["response"]["tokens_in"],
                tokens_out=entry["response"]["tokens_out"],
                cost=entry["response"]["cost"],
                cached=True,
            )

        # Call real LLM
        resp = await self._gateway.chat(**kwargs)

        # Record
        entry = {
            "key": key,
            "system": system,
            "messages": messages,
            "response": {
                "content": resp.content,
                "model": resp.model,
                "tokens_in": resp.tokens_in,
                "tokens_out": resp.tokens_out,
                "cost": resp.cost,
            },
        }
        self._calls.append(entry)
        self._cache[key] = len(self._calls) - 1
        return resp

    def save(self) -> None:
        """Write recorded calls to fixture file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._calls, f, ensure_ascii=False, indent=2)

    @property
    def call_count(self) -> int:
        return len(self._calls)


class ReplayGateway:
    """Reads responses from a fixture file, replays them in order.
    Raises RuntimeError if fixture is exhausted (calls > recorded).
    """

    def __init__(self, fixture_path: Path):
        self._path = Path(fixture_path)
        if not self._path.exists():
            raise FileNotFoundError(f"Fixture not found: {self._path}")
        with open(self._path, "r", encoding="utf-8") as f:
            self._calls: list[dict] = json.load(f)
        self._index = 0
        self._key_index: dict[str, int] = {}
        for i, entry in enumerate(self._calls):
            self._key_index[entry["key"]] = i

    @property
    def cost_tracker(self):
        # Return a no-op cost tracker for replay mode
        from src.llm_gateway.cost_tracker import CostTracker
        return CostTracker()

    async def chat(self, **kwargs) -> LLMResponse:
        system = kwargs.get("system", "")
        messages = kwargs.get("messages", [])
        key = _make_cache_key(system, messages)

        # Try key-based match first (tolerates reordering)
        if key in self._key_index:
            entry = self._calls[self._key_index[key]]
            return LLMResponse(
                content=entry["response"]["content"],
                model=entry["response"]["model"],
                tokens_in=entry["response"]["tokens_in"],
                tokens_out=entry["response"]["tokens_out"],
                cost=entry["response"]["cost"],
                cached=True,
            )

        # Fall back to sequential replay
        if self._index >= len(self._calls):
            raise RuntimeError(
                f"ReplayGateway exhausted: {len(self._calls)} calls recorded, "
                f"but agent requested more. Try re-recording fixtures."
            )
        entry = self._calls[self._index]
        self._index += 1
        return LLMResponse(
            content=entry["response"]["content"],
            model=entry["response"]["model"],
            tokens_in=entry["response"]["tokens_in"],
            tokens_out=entry["response"]["tokens_out"],
            cost=entry["response"]["cost"],
            cached=True,
        )


async def record_agent_fixture(
    agent_cls: type,
    agent_name: str,
    real_gateway: LLMGateway,
    store,
    tools,
    task: dict,
    fixture_path: Path | None = None,
) -> Path:
    """Run an agent with real LLM + recording, save fixture, return path."""
    rec = RecordingGateway(real_gateway, fixture_path or FIXTURE_DIR / f"{agent_name}.json")
    agent = agent_cls(gateway=rec, store=store, tool_registry=tools)
    try:
        await agent.execute(task)
    except Exception as e:
        # Still save partial fixture on failure — partial data is useful
        print(f"  [record] {agent_name} hit error (saving partial): {e}")
    rec.save()
    return rec._path
