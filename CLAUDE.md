# CLAUDE.md

## Project: 竞品分析 Agent 协作系统

AI-driven competitive analysis with 14 agents collaborating through a knowledge graph.
Design + 7-phase plan complete. Starting P1 implementation.

## Memory

Project memory files in `.claude/memory/`. Check MEMORY.md before starting new work.

## Key Documents

- Design spec: `docs/superpowers/specs/2026-05-14-competitive-analysis-agents-design.md`
- Master plan: `docs/superpowers/plans/2026-05-14-competitive-analysis-agents-plan.md`
- Phase plans: `docs/superpowers/plans/p1-foundation.md` through `p7-infrastructure.md`

## Architecture

```
Knowledge Graph (SQLite, 3 layers) → 14 Agents (ReAct loops) → DAG Engine → FastAPI + WebSocket → React
```

- Knowledge graph is single source of truth — agents never communicate directly
- Each agent has independent ReAct loop, tool registry, output contract
- Cross-Review (horizontal) + QA (vertical) = two feedback loops
- Lazy imports in AgentExecutor (avoid forward-reference ImportError across phases)
- 3-tier data source degradation in Collector

## Development Rules

1. **Read the plan before writing code** — every task has exact file paths, code, and test commands
2. **Cross-document consistency audit** before starting each phase — check imports, file paths, class names against previous phases
3. **TDD**: write test → verify it fails → implement → verify it passes → commit
4. **One task at a time** — ~5 minute steps, commit after each task
5. **No forward references** — if code references a class/module from a later phase, use lazy imports or stubs

## Phase Order

P1 (foundation) → P2 (DAG) → P3 (collection) → P4 (analysis) → P5 (QA feedback) → P6 (API+UI) → P7 (infrastructure)

Each phase has verifiable output. P1 = single agent runs ReAct loop end-to-end.

## Tech Stack

Python 3.12+, FastAPI, Pydantic v2, SQLite, httpx, Anthropic SDK, OpenAI SDK, React 18, Tailwind CSS, Vite

## Commands

```bash
# Run tests for a specific module
python -m pytest tests/test_knowledge_graph/test_models.py -v

# Run all tests
python -m pytest tests/ -v

# Start API server (P6+)
python -m uvicorn src.api.app:app --reload --port 8000

# Start frontend dev server (P6+)
cd web && npm run dev
```

## File Structure (14 agents, one per file)

```
src/
├── knowledge_graph/   # models.py, store.py, query.py
├── llm_gateway/       # gateway.py, cache.py, cost_tracker.py
├── agents/
│   ├── base.py, registry.py, context.py, contracts.py
│   ├── tools/         # base.py, graph_tools.py, web_tools.py, api_tools.py
│   ├── orchestrator.py        #  1
│   ├── source_discovery.py    #  2
│   ├── collector.py           #  3
│   ├── data_enricher.py       #  4
│   ├── feature_analyzer.py    #  5
│   ├── sentiment_analyzer.py  #  6
│   ├── pricing_analyst.py     #  7
│   ├── techstack_analyzer.py  #  8
│   ├── market_position.py     #  9
│   ├── cross_review.py        # 10
│   ├── swot_synthesizer.py    # 11
│   ├── writer.py              # 12
│   ├── qa_fact_check.py       # 13
│   └── qa_logic_check.py      # 14
├── dag/               # models.py, scheduler.py, executor.py, feedback.py
├── api/               # app.py, deps.py, websocket.py, routes/
├── infrastructure/    # task_queue.py, audit.py, snapshot.py, config.py, health.py
└── schema/            # models.py, templates/saas.yaml
```
