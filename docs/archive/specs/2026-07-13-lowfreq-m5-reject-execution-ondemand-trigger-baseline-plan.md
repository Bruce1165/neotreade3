Status: active
Owner: lowfreq / orchestration / governance / worker
Scope: Implementation plan for the narrow `M5 reject execution on-demand trigger baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution On-Demand Trigger Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-ondemand-trigger-baseline-design.md`

## 1. Goal

This slice only promotes the existing on-demand carrier into one formal worker trigger for governance reject execution.

This slice must:

- add one worker-owned on-demand reject runner
- add one explicit worker CLI mode that calls it
- add focused tests proving the worker trigger uses the existing carrier and executor path

This slice explicitly does not:

- modify daily config
- change governance runtime semantics
- add generic manual scheduling
- implement approval flows

## 2. File Boundary

Production files:

- `apps/worker/main.py`

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-ondemand-trigger-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-ondemand-trigger-baseline-plan.md`

Focused test file:

- `tests/unit/test_bootstrap_skeleton.py`

Files intentionally not modified:

- `config/orchestrator/daily_master_orchestrator.json`
- `neotrade3/governance/*`
- `neotrade3/orchestration/models.py`
- `neotrade3/orchestration/daily_master_orchestrator.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

## 3. Execution Steps

### M5TRIG-S1: Add worker-owned on-demand reject runner

Modify:

- `apps/worker/main.py`

Implementation:

1. import the existing on-demand orchestration contracts
2. add `run_governance_reject_on_demand(...)` on `BootstrapWorkerApp`
3. build one `OnDemandTaskRequest` containing the existing governance reject task
4. execute the plan through the existing governance executor and `execute_run_plan(...)`
5. return a narrow snapshot with orchestration payload and summary

### M5TRIG-S2: Add explicit worker CLI mode

Modify:

- `apps/worker/main.py`

Implementation:

1. add `--mode` with default `daily`
2. add `--source-run-id` and `--validation-id`
3. in `main()`, dispatch:
   - `daily` -> existing `run(...)`
   - `governance_reject` -> new `run_governance_reject_on_demand(...)`
4. preserve current JSON summary output and exit code semantics

### M5TRIG-S3: Lock focused worker tests

Modify:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. worker on-demand reject path materializes independent reject artifact and ledger
2. CLI returns `0` for `governance_reject` `ok`
3. CLI returns non-zero for `governance_reject` failure
4. existing daily-mode tests continue to pass unchanged

### M5TRIG-S4: Minimum verification

Run at minimum:

- `python3 -m py_compile apps/worker/main.py tests/unit/test_bootstrap_skeleton.py`
- `python3 -m pytest tests/unit/test_bootstrap_skeleton.py -k "governance_reject or worker_main"`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: accidentally break the existing daily worker CLI**
  - Guardrail: keep `daily` as the default mode and do not convert to required subcommands
- **Risk: widen into a generic on-demand launcher**
  - Guardrail: the new worker method stays specific to governance reject execution
- **Risk: bypass the orchestration carrier**
  - Guardrail: always build `OnDemandTaskRequest` and execute through `build_on_demand_plan(...)`

## 5. Done Criteria

- worker-owned on-demand reject runner exists
- worker CLI exposes explicit `governance_reject` mode
- reject execution materializes through the worker trigger in focused tests
- current daily worker behavior remains intact

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in worker/orchestration trigger ownership supporting `M5`
- `G1-G6` target mapping:
  - this is the minimum `G2` trigger closure after reject runtime, CLI, worker executor, and carrier baselines
- new contract introduced:
  - `BootstrapWorkerApp.run_governance_reject_on_demand(...)`
  - worker CLI `--mode governance_reject`
- boundaries not touched:
  - no daily config mutation
  - no governance runtime rewrite
  - no auto validation selection
  - no approval flow
  - no `M6`
