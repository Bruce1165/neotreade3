Status: active
Owner: lowfreq / governance / worker
Scope: Implementation plan for the narrow `M5 governance status transition worker/on-demand trigger baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition Worker On-Demand Trigger Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-worker-ondemand-trigger-baseline-design.md`

## 1. Goal

This slice only promotes the existing status-transition runtime into one formal worker-owned on-demand trigger.

This slice must:

- add one worker-owned on-demand status-transition runner
- add one explicit worker CLI mode that calls it
- add focused tests proving the worker trigger uses the existing governance executor path
- keep API and orchestrator surfaces unchanged

This slice explicitly does not:

- change governance runtime semantics
- change transition artifact or ledger schemas
- change governance CLI behavior
- add API mode adoption
- add scheduled orchestrator adoption
- touch `M6`

## 2. File Boundary

Production file:

- `apps/worker/main.py`

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-worker-ondemand-trigger-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-worker-ondemand-trigger-baseline-plan.md`

Focused test files:

- `tests/unit/test_bootstrap_skeleton.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Files intentionally not modified:

- `apps/api/main.py`
- `apps/api/router.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `tests/integration/test_http_smoke.py`

## 3. Execution Steps

### M5TWORK-S1: Add worker-owned on-demand status-transition runner

Modify:

- `apps/worker/main.py`

Implementation:

1. import the existing status-transition runtime owner
2. add `run_governance_status_transition_on_demand(...)` on `BootstrapWorkerApp`
3. build one `OnDemandTaskRequest` containing a governance-only planned task for status transition
4. execute the task through the existing governance executor path
5. return the same narrow orchestration snapshot envelope already used by reject on-demand

Implementation rules:

- task id stays distinct:
  - `governance.status_transition`
- entrypoint stays:
  - `neotrade3.governance.runtime:run_governance_status_transition`
- argument payload stays minimal:
  - `source_run_id`
  - `validation_id`

### M5TWORK-S2: Add explicit worker CLI mode

Modify:

- `apps/worker/main.py`

Implementation:

1. extend `--mode` choices with:
   - `governance_status_transition`
2. reuse existing CLI arguments:
   - `--source-run-id`
   - `--validation-id`
3. in `main()`, dispatch:
   - `daily` -> existing `run(...)`
   - `governance_reject` -> existing `run_governance_reject_on_demand(...)`
   - `governance_status_transition` -> new `run_governance_status_transition_on_demand(...)`
4. preserve the current JSON summary and exit-code behavior

Implementation rules:

- keep `daily` as default mode
- require both `source_run_id` and `validation_id` for `governance_status_transition`
- do not change the bootstrap worker output envelope

### M5TWORK-S3: Lock focused worker tests

Modify:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. worker on-demand status-transition path materializes independent transition artifact and ledger
2. CLI returns `0` for `governance_status_transition` ok snapshot
3. CLI returns non-zero for `governance_status_transition` failure
4. existing daily-mode and reject-mode tests continue to pass unchanged

Testing rules:

- reuse the existing governance preparation helpers already used by reject on-demand tests
- keep assertions focused on worker trigger behavior and resulting snapshot shape
- avoid duplicating runtime-internal transition assertions already covered elsewhere

### M5TWORK-S4: Lock focused governance-executor tests

Modify:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Required coverage:

1. dry-run governance status transition through `execute_run_plan(...)`
2. persisted-write governance status transition through `execute_run_plan(...)`
3. failure path for missing reject proof or missing validation

Testing rules:

- mirror the existing governance reject executor coverage pattern
- keep the planned-task contract narrow and explicit

### M5TWORK-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile apps/worker/main.py tests/unit/test_bootstrap_skeleton.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `python3 -m pytest tests/unit/test_bootstrap_skeleton.py tests/unit/test_m5_governance_orchestrator_fit.py -k "governance_status_transition or worker_main"`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: accidentally break existing daily worker behavior**
  - Guardrail: keep `daily` as default mode and preserve current dispatch/output semantics
- **Risk: widen into API adoption**
  - Guardrail: limit production edits to `apps/worker/main.py`
- **Risk: blur reject and transition task identities**
  - Guardrail: use a distinct task id `governance.status_transition`
- **Risk: bypass the orchestration carrier**
  - Guardrail: always build `OnDemandTaskRequest` and execute through the existing governance executor path

## 5. Done Criteria

- worker-owned on-demand status-transition runner exists
- worker CLI exposes explicit `governance_status_transition` mode
- status-transition materializes through the worker trigger in focused tests
- current daily and reject worker behavior remains intact
- no API/orchestrator diff appears in this slice

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in worker/orchestration trigger ownership supporting `M5`
- `G1-G6` target mapping:
  - this is the next minimum `G5` trigger closure after status-transition runtime and CLI baselines
- new contract introduced:
  - `BootstrapWorkerApp.run_governance_status_transition_on_demand(...)`
  - worker CLI `--mode governance_status_transition`
- boundaries not touched:
  - no governance runtime rewrite
  - no API adoption
  - no scheduled orchestrator adoption
  - no `M6`
