Status: active
Owner: lowfreq / governance / api
Scope: Implementation plan for the narrow `M5 governance status transition API adoption baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition API Adoption Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-api-adoption-baseline-design.md`

## 1. Goal

This slice only promotes the existing governance status-transition worker trigger into the API-visible orchestration surface.

This slice must:

- add one API-visible mode:
  - `governance_status_transition`
- route that mode to the existing worker-owned trigger
- add focused unit and HTTP smoke tests proving the API contract works end to end
- keep runtime, worker, and schema surfaces unchanged

This slice explicitly does not:

- change governance runtime semantics
- change transition artifact or ledger schemas
- change worker trigger behavior
- change governance CLI behavior
- add scheduled orchestrator adoption
- touch `M6`

## 2. File Boundary

Production files:

- `apps/api/main.py`
- `apps/api/router.py`

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-api-adoption-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-api-adoption-baseline-plan.md`

Focused test files:

- `tests/unit/test_bootstrap_skeleton.py`
- `tests/integration/test_http_smoke.py`

Files intentionally not modified:

- `apps/worker/main.py`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

## 3. Execution Steps

### M5TAPI-S1: Add API service dispatch for status transition

Modify:

- `apps/api/main.py`

Implementation:

1. keep `daily` on the existing trading-day and lab-materialization path
2. keep `governance_reject` on the existing reject worker path
3. add an explicit `governance_status_transition` branch that calls:
   - `self.worker_app.run_governance_status_transition_on_demand(...)`
4. preserve existing orchestration run ledger/artifact writing behavior
5. preserve the existing API response envelope

Implementation rules:

- do not use a generic non-daily else-branch
- do not materialize lab runs for governance status transition
- do not require trading-day gating for governance status transition

### M5TAPI-S2: Extend router mode validation

Modify:

- `apps/api/router.py`

Implementation:

1. extend valid `mode` values with:
   - `governance_status_transition`
2. keep `daily` validation unchanged
3. require both:
   - `source_run_id`
   - `validation_id`
   for `governance_status_transition`
4. keep reject validation unchanged
5. preserve the current parameter normalization passed into `orchestration_run_view(...)`

Implementation rules:

- keep validation logic centralized in the router
- reuse the existing error codes:
  - `invalid_mode`
  - `invalid_source_run_id`
  - `invalid_validation_id`
- do not add aliases or inferred ids

### M5TAPI-S3: Lock focused API unit tests

Modify:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. `orchestration_run_view(...)` uses `run_governance_status_transition_on_demand(...)`
2. governance status-transition mode does not require trading day
3. governance status-transition mode does not materialize lab runs
4. persisted orchestration ledger/artifact record:
   - `mode == "governance_status_transition"`
   - `task_id == "governance.status_transition"`
5. router accepts orchestration run with:
   - `mode="governance_status_transition"`
6. router rejects missing `source_run_id`
7. router rejects missing `validation_id`

Testing rules:

- mirror the existing reject API coverage pattern
- keep assertions focused on API ownership and orchestration payload shape
- avoid duplicating worker-internal status-transition assertions already covered elsewhere

### M5TAPI-S4: Lock focused HTTP smoke

Modify:

- `tests/integration/test_http_smoke.py`

Required coverage:

1. POST `/api/orchestration/run` with:
   - `mode="governance_status_transition"`
2. GET orchestration detail returns the stored run payload
3. GET orchestration download returns the stored artifact payload
4. stored ledger and artifact persist:
   - `mode == "governance_status_transition"`
   - `task_id == "governance.status_transition"`

Testing rules:

- reuse the existing `_serve(...)`, `_post_json(...)`, `_read_json(...)`, and `_read_bytes(...)` harness
- monkeypatch the worker-owned status-transition trigger only
- keep the smoke path symmetric with the existing reject round trip

### M5TAPI-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile apps/api/main.py apps/api/router.py tests/unit/test_bootstrap_skeleton.py tests/integration/test_http_smoke.py`
- `python3 -m pytest tests/unit/test_bootstrap_skeleton.py tests/integration/test_http_smoke.py -k "governance_status_transition or governance_reject"`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: status transition accidentally falls into reject dispatch**
  - Guardrail: add an explicit branch in `orchestration_run_view(...)`
- **Risk: widen the slice into worker/runtime changes**
  - Guardrail: limit production edits to `apps/api/main.py` and `apps/api/router.py`
- **Risk: break existing reject API behavior**
  - Guardrail: mirror the current reject validation and dispatch path without refactoring unrelated logic
- **Risk: add daily-only side effects to governance modes**
  - Guardrail: keep trading-day checks and lab materialization confined to the `daily` branch

## 5. Done Criteria

- router accepts `governance_status_transition`
- API dispatch reaches `run_governance_status_transition_on_demand(...)`
- unit tests lock service dispatch and router validation
- HTTP smoke proves post/detail/download parity for the new mode
- no worker/runtime/schema diff appears in this slice

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in API/orchestration trigger ownership supporting `M5`
- `G1-G6` target mapping:
  - this is the next minimum `G5` operability closure after worker trigger support
- new contract introduced:
  - API mode `governance_status_transition` for `/api/orchestration/run`
- boundaries not touched:
  - no governance runtime rewrite
  - no worker trigger rewrite
  - no scheduled orchestrator adoption
  - no `M6`
