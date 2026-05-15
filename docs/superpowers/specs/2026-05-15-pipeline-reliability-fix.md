# Pipeline Reliability Fix Design Spec

## Problem
Orchestrator LLM generates incomplete DAGs (missing Writer, SWOT, QA agents), so the
entire pipeline runs but produces zero report output. Error propagation is silent, and
the Report API has no fallback for missing data.

## Root Cause
1. Orchestrator system prompt lists agent types but doesn't enforce mandatory ones
2. No post-validation after LLM DAG generation — bad DAGs pass silently
3. Downstream agents fail without fallback when upstream data is missing
4. Report API returns empty when Writer didn't run

## Solution: Prompt + Hard-Rule Guard + Adaptive Degradation

### 1. Orchestrator post-validation & auto-inject (`src/agents/orchestrator.py`)

Add `_ensure_mandatory_nodes(dag_json, schema)` after `_parse_dag_json`:
- Writer always required — if missing, auto-create node depending on SWOTAnalyzer
  (or last analysis agent if SWOT is excluded)
- QA_FactCheck / QA_LogicCheck always required — if missing, auto-create depending on Writer
- SWOTAnalyzer required unless "swot" in exclude_dimensions
- Auto-generated nodes marked with `auto_generated: true`
- Deduplicate node_ids; ensure no circular deps

### 2. Agent adaptive degradation (`src/agents/base.py`)

- BaseAgent `_think` prompt updated: when data is sparse, instruct LLM to infer from
  general knowledge and set `confidence: 0.1-0.3`
- Each analysis agent already has "CRITICAL: if no data, infer and set low confidence"
  in its system prompt (done in prior commits)

### 3. Error propagation (`src/api/routes/task.py`)

- `_plan_and_execute` exception handler already calls `emit_dag_failed`
- Ensure ALL exception paths hit the handler
- `GET /api/task/{task_id}` response already includes `error` field when task not found
- Add structured error in the task status response

### 4. Report API multi-layer fallback (`src/api/routes/report.py`)

Layer priority:
1. ReportSection nodes in GraphStore (normal path)
2. Writer node's `_output_data.report_markdown` (Writer completed but didn't persist)
3. Auto-assemble "partial report" from all completed agent outputs, listing missing dimensions
4. Clear error: "Writer not in DAG, current task state: {node_states}"

### 5. Semantic cache fix (`src/llm_gateway/gateway.py`)

- Skip cache for orchestrator DAG generation (different prompts should yield different DAGs)
- Add cache-busting parameter per task_id

## Verification (all must pass)

- `test_smoke_orchestrator_generates_valid_dag` — full-dimension DAG has all required agents
- `test_smoke_single_product_full_pipeline` — report > 200 chars, product name present
- NEW: `test_minimal_dag_all_dimensions_excluded` — Writer + QA still present
- NEW: `test_upstream_failure_graceful_degradation` — partial report when analysis fails
- All 172 existing tests continue to pass

## Files Changed

| File | Change |
|------|--------|
| `src/agents/orchestrator.py` | +`_ensure_mandatory_nodes`, +`_validate_dag` |
| `src/api/routes/report.py` | Multi-layer fallback |
| `src/api/routes/task.py` | Error propagation hardening |
| `src/llm_gateway/gateway.py` | Cache skip for DAG generation |
| `tests/test_integration/test_pipeline_smoke.py` | Fix existing + add new tests |
