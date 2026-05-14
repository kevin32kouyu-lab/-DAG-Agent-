---
name: competitive-analysis-agents
description: 14-agent competitive analysis system — all P1-P7 complete
metadata:
  type: project
---

Building "竞品分析 Agent 协作系统" — AI-driven competitive analysis with 14 agents collaborating through a knowledge graph.

**Status (updated 2026-05-15):** All 7 phases complete and committed. 156 tests passing. Project is production-ready.

**Architecture:** Knowledge Graph (SQLite, 3 layers: Raw→Analysis→Synthesis) → Agent execution layer (14 agents, each with independent ReAct loop) → DAG engine (scheduling + feedback loops) → FastAPI + WebSocket → React frontend.

**Key design decisions:**
- Knowledge graph is single source of truth; agents never communicate directly
- Cross-Review agent provides horizontal consistency checking between analysis agents
- QA agents provide vertical fact-checking and logic validation
- Two feedback loops: Cross-Review (1 round max) + QA (2 rounds max)
- Lazy imports for AgentExecutor to avoid forward-reference ImportError
- 3-tier data source degradation strategy in Collector (primary → tier1 → tier2 → DATA_DEGRADED)

**Phase progress:**
- P1 ✓ Foundation: knowledge graph, LLM gateway, agent base + registry, ReAct loop
- P2 ✓ DAG: models, scheduler, executor with lazy imports
- P3 ✓ Collection: source discovery, collector, data enricher
- P4 ✓ Analysis: feature/sentiment/pricing/techstack/market position + cross-review + SWOT + writer
- P5 ✓ QA: fact-check + logic-check agents, feedback loop with downstream cascade
- P6 ✓ API + UI: FastAPI routes, WebSocket streaming, React frontend
- P7 ✓ Infrastructure: semantic cache, cost tracker, audit logger, snapshot/resume, task queue, config center, degradation handler, health check, schema models, SaaS template, security layer

**Key files:**
- Design: `docs/superpowers/specs/2026-05-14-competitive-analysis-agents-design.md`
- Master plan: `docs/superpowers/plans/2026-05-14-competitive-analysis-agents-plan.md`
- Phase plans: `docs/superpowers/plans/p1-foundation.md` through `p7-infrastructure.md`
