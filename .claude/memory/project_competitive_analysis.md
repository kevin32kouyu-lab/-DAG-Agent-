---
name: competitive-analysis-agents
description: 14-agent competitive analysis system — design complete, plans done, ready for P1 implementation
metadata:
  type: project
---

Building "竞品分析 Agent 协作系统" — AI-driven competitive analysis with 14 agents collaborating through a knowledge graph.

**Status:** Design and 7-phase planning complete (2026-05-14). All cross-document consistency issues fixed. Ready to start P1 implementation.

**Architecture:** Knowledge Graph (SQLite, 3 layers: Raw→Analysis→Synthesis) → Agent execution layer (14 agents, each with independent ReAct loop) → DAG engine (scheduling + feedback loops) → FastAPI + WebSocket → React frontend.

**Key design decisions:**
- Knowledge graph is single source of truth; agents never communicate directly
- Cross-Review agent provides horizontal consistency checking between analysis agents
- QA agents provide vertical fact-checking and logic validation
- Two feedback loops: Cross-Review (1 round max) + QA (2 rounds max)
- Lazy imports for AgentExecutor to avoid forward-reference ImportError
- 3-tier data source degradation strategy in Collector

**Phase plan:** P1 (foundation)→P2 (DAG)→P3 (collection)→P4 (analysis)→P5 (QA feedback)→P6 (API+UI)→P7 (infrastructure). Each phase has verifiable output.

**Key files:**
- Design: `docs/superpowers/specs/2026-05-14-competitive-analysis-agents-design.md`
- Master plan: `docs/superpowers/plans/2026-05-14-competitive-analysis-agents-plan.md`
- Phase plans: `docs/superpowers/plans/p1-foundation.md` through `p7-infrastructure.md`
