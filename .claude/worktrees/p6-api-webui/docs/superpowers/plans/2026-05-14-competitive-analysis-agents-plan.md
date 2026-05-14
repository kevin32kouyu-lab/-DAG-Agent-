# 竞品分析 Agent 协作系统 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 AI 驱动的竞品分析 Agent 协作系统，14 个 Agent 通过知识图谱协作，自动完成从公开信息采集到结构化竞品报告输出。

**Architecture:** 分层架构 — 知识图谱为数据层唯一真相源，Agent 执行层通过 ReAct 循环独立决策，DAG 引擎负责任务编排和反馈闭环，FastAPI + WebSocket 驱动 React 前端。

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, SQLite, httpx, Anthropic SDK, OpenAI SDK, React 18, Tailwind CSS, Vite

**Spec Reference:** `docs/superpowers/specs/2026-05-14-competitive-analysis-agents-design.md`

---

## 分阶段计划索引

| Phase | 文档 | 内容 | 可验证产出 |
|-------|------|------|-----------|
| **P1** | [p1-foundation.md](p1-foundation.md) | 知识图谱 + LLM 网关 + Agent 框架 | 单 Agent 跑通 ReAct 循环 |
| **P2** | [p2-dag-engine.md](p2-dag-engine.md) | DAG 引擎 + Orchestrator | 多节点 DAG 调度，状态机完整 |
| **P3** | [p3-collection-pipeline.md](p3-collection-pipeline.md) | Source Discovery → Collector → Enricher | 端到端采集写入图谱 |
| **P4** | [p4-analysis-pipeline.md](p4-analysis-pipeline.md) | 5 分析 Agent + CrossReview + SWOT + Writer | 从采集到报告初稿全链路 |
| **P5** | [p5-qa-feedback.md](p5-qa-feedback.md) | QA 双审 + 反馈边闭环 | 完整反馈闭环跑通 |
| **P6** | [p6-api-webui.md](p6-api-webui.md) | FastAPI + WebSocket + React UI | 用户可操作的完整系统 |
| **P7** | [p7-infrastructure.md](p7-infrastructure.md) | 缓存/重试/审计/配置中心/安全 | 生产级稳定性 |

---

## 文件结构总览

```
e:/Agent_Project/
├── src/
│   ├── __init__.py
│   ├── knowledge_graph/
│   │   ├── __init__.py
│   │   ├── models.py           # Node/Edge Pydantic models
│   │   ├── store.py            # SQLite-backed graph CRUD
│   │   └── query.py            # BFS/query + trace utilities
│   ├── llm_gateway/
│   │   ├── __init__.py
│   │   ├── gateway.py          # Multi-model LLM router
│   │   ├── cache.py            # Semantic cache
│   │   └── cost_tracker.py     # Per-task token/cost accumulator
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseAgent + ReAct loop + StepTrace
│   │   ├── registry.py         # @agent_registry.register decorator
│   │   ├── context.py          # AgentContext
│   │   ├── contracts.py        # Pydantic output contracts
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Tool base + ToolRegistry
│   │   │   ├── graph_tools.py  # GraphQueryTool, GraphWriteTool
│   │   │   ├── web_tools.py    # WebSearchTool, WebScrapeTool
│   │   │   └── api_tools.py    # ThirdPartyAPITool
│   │   ├── orchestrator.py         #  1. Orchestrator
│   │   ├── source_discovery.py     #  2. Source Discovery
│   │   ├── collector.py            #  3. Collector (×N instances)
│   │   ├── data_enricher.py        #  4. Data Enricher
│   │   ├── feature_analyzer.py     #  5. Feature Analyzer
│   │   ├── sentiment_analyzer.py   #  6. Sentiment Analyzer
│   │   ├── pricing_analyst.py      #  7. Pricing Analyst
│   │   ├── techstack_analyzer.py   #  8. TechStack Analyzer
│   │   ├── market_position.py      #  9. Market Position
│   │   ├── cross_review.py         # 10. Cross-Review Agent
│   │   ├── swot_synthesizer.py     # 11. SWOT Synthesizer
│   │   ├── writer.py               # 12. Writer
│   │   ├── qa_fact_check.py        # 13. QA #1 Fact Check
│   │   └── qa_logic_check.py       # 14. QA #2 Logic Check
│   ├── dag/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── scheduler.py
│   │   ├── executor.py
│   │   └── feedback.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── deps.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── task.py
│   │   │   ├── report.py
│   │   │   ├── trace.py
│   │   │   └── agent.py
│   │   └── websocket.py
│   ├── infrastructure/
│   │   ├── __init__.py
│   │   ├── task_queue.py
│   │   ├── audit.py
│   │   ├── snapshot.py
│   │   ├── config.py
│   │   └── health.py
│   └── schema/
│       ├── __init__.py
│       ├── models.py
│       └── templates/
│           └── saas.yaml
├── tests/
│   ├── conftest.py
│   ├── test_knowledge_graph/
│   ├── test_llm_gateway/
│   ├── test_agents/
│   ├── test_dag/
│   └── test_api/
├── web/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── src/
│       ├── App.tsx
│       ├── hooks/
│       ├── pages/
│       └── components/
├── pyproject.toml
└── requirements.txt
```
