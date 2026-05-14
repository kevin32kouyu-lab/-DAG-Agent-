---
name: competitive-analysis-agents
description: 14-agent competitive analysis system — P1-P5 done, P6 in progress
metadata:
  type: project
---

Building "竞品分析 Agent 协作系统" — AI-driven competitive analysis with 14 agents collaborating through a knowledge graph.

**Status (updated 2026-05-15):** P1-P5 complete and committed. P6 (API + UI) in progress with uncommitted changes. P7 files beginning to appear.

**Architecture:** Knowledge Graph (SQLite, 3 layers: Raw→Analysis→Synthesis) → Agent execution layer (14 agents, each with independent ReAct loop) → DAG engine (scheduling + feedback loops) → FastAPI + WebSocket → React frontend.

**Key design decisions:**
- Knowledge graph is single source of truth; agents never communicate directly
- Cross-Review agent provides horizontal consistency checking between analysis agents
- QA agents provide vertical fact-checking and logic validation
- Two feedback loops: Cross-Review (1 round max) + QA (2 rounds max)
- Lazy imports for AgentExecutor to avoid forward-reference ImportError
- 3-tier data source degradation strategy in Collector

**Phase progress:**
- P1 ✓ Foundation: knowledge graph, LLM gateway, agent base + registry, ReAct loop
- P2 ✓ DAG: models, scheduler, executor with lazy imports
- P3 ✓ Collection: source discovery, collector, data enricher
- P4 ✓ Analysis: feature/sentiment/pricing/techstack/market position + cross-review + SWOT + writer
- P5 ✓ QA: fact-check + logic-check agents, feedback loop with downstream cascade
- P6 (in progress): FastAPI routes, WebSocket streaming, React frontend pages
- P7 (pending): infrastructure, audit, snapshot, task queue, health checks

**Key files:**
- Design: `docs/superpowers/specs/2026-05-14-competitive-analysis-agents-design.md`
- Master plan: `docs/superpowers/plans/2026-05-14-competitive-analysis-agents-plan.md`
- Phase plans: `docs/superpowers/plans/p1-foundation.md` through `p7-infrastructure.md`
