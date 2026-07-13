Status: active
Owner: lowfreq / api / worker / governance
Scope: Implementation plan for the narrow `M5 reject execution API trigger baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution API Trigger Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-api-trigger-baseline-design.md`

## 1. Goal

This slice only exposes the existing worker governance reject trigger through the formal orchestration POST surface.

This slice must:

- extend `/api/orchestration/run` with an explicit `mode`
- dispatch `governance_reject` to `worker_app.run_governance_reject_on_demand(...)`
- add focused service and HTTP tests

This slice explicitly does not:

- add new route namespaces
- change governance runtime semantics
- add generic manual task APIs
- implement approval flows

## 2. File Boundary

Production files:

- `apps/api/main.py`
- `apps/api/router.py`

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-api-trigger-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-api-trigger-baseline-plan.md`

Focused test file:

- `tests/unit/test_bootstrap_skeleton.py`

Files intentionally not modified:

- `apps/worker/main.py`
- `neotrade3/governance/*`
- `config/orchestrator/daily_master_orchestrator.json`

## 3. Execution Steps

### M5API-S1: Extend API service branch

Modify:

- `apps/api/main.py`

Implementation:

1. extend `orchestration_run_view(...)` with `mode`, `source_run_id`, `validation_id`
2. keep `daily` behavior unchanged
3. add `governance_reject` branch delegating to `worker_app.run_governance_reject_on_demand(...)`
4. keep standard orchestration envelope persistence
5. avoid lab materialization for the reject branch

### M5API-S2: Extend router payload contract

Modify:

- `apps/api/router.py`

Implementation:

1. parse optional `mode`
2. validate `mode` against `daily|governance_reject`
3. validate `source_run_id` and `validation_id` for `governance_reject`
4. forward parsed fields to `service.orchestration_run_view(...)`

### M5API-S3: Lock focused tests

Modify:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. service `governance_reject` branch calls the worker owner and persists orchestration envelope
2. HTTP `POST /api/orchestration/run` accepts `mode="governance_reject"`
3. HTTP rejects missing `source_run_id`
4. HTTP rejects missing `validation_id`
5. legacy daily POST remains unchanged

### M5API-S4: Minimum verification

Run at minimum:

- `python3 -m py_compile apps/api/main.py apps/api/router.py tests/unit/test_bootstrap_skeleton.py`
- `python3 -m pytest tests/unit/test_bootstrap_skeleton.py -k "orchestration_run or governance_reject"`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: break existing daily orchestration POST clients**
  - Guardrail: `mode` defaults to `daily`
- **Risk: widen into a generic manual orchestration API**
  - Guardrail: only one new explicit branch is added
- **Risk: accidentally materialize unrelated lab outputs**
  - Guardrail: skip `_materialize_lab_runs_from_snapshot(...)` for reject mode

## 5. Done Criteria

- `/api/orchestration/run` supports `mode="governance_reject"`
- API service delegates to worker on-demand reject owner
- focused tests cover service and HTTP contract
- daily POST behavior remains intact

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in API/trigger exposure supporting `M5`
- `G1-G6` target mapping:
  - this is the minimum `G2` external trigger closure after worker trigger baseline
- new contract introduced:
  - `/api/orchestration/run` request field `mode`
  - `governance_reject` POST payload branch
- boundaries not touched:
  - no new route namespace
  - no governance runtime rewrite
  - no daily config mutation
  - no auto validation selection
  - no approval flow
  - no `M6`
