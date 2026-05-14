---
name: use-real-integration-tests
description: After MVP completion, all tests must use real LLM APIs, not mocks
metadata:
  type: feedback
---

All future tests must use real LLM APIs (DeepSeek/Anthropic), not mocked LLM gateways.

**Why:** Mock tests missed critical bugs — JSON parse fallback silently returning empty finalize, Writer producing no report content, WebSocket state loss. Mock tests always return perfect JSON so they never trigger real-world failure paths. User caught these issues in manual testing.

**How to apply:** When writing or running tests, use actual LLM calls via the real gateway. Unit tests for pure logic (config parsing, data structures) can still be lightweight. But any test that exercises agent execution, LLM calls, or the full DAG pipeline must hit real APIs. Accept the latency and cost as necessary for quality.

**Guidance:** Prefer focused integration tests (single agent with real LLM) over massive end-to-end runs. Keep API keys in .env (already in .gitignore). Use fast models (deepseek-chat, haiku) for tests where possible to minimize cost.
