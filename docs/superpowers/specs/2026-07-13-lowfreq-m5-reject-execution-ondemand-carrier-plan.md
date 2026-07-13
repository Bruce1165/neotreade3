Status: active
Owner: lowfreq / orchestration / governance
Scope: Implementation plan for the narrow `M5 reject execution on-demand carrier` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution On-Demand Carrier Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-ondemand-carrier-design.md`

## 1. Goal

This slice only formalizes explicit-task planning for reject execution and similar non-daily tasks.

This slice must:

- add `OnDemandTaskRequest`
- add `build_on_demand_plan(...)`
- add focused tests proving reject execution can run through it

This slice explicitly does not:

- modify daily config
- change governance runtime or worker executor semantics
- implement approval flows

## 2. File Boundary

Production files:

- `neotrade3/orchestration/models.py`
- `neotrade3/orchestration/daily_master_orchestrator.py`

Focused test file:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Files intentionally not modified:

- `config/orchestrator/daily_master_orchestrator.json`
- `apps/worker/main.py`
- `neotrade3/governance/*`

## 3. Execution Steps

### M5ONDEM-S1: Add on-demand task request contract

Modify:

- `neotrade3/orchestration/models.py`

Implementation:

1. add one task-item contract for explicit tasks
2. add `OnDemandTaskRequest`

### M5ONDEM-S2: Add on-demand plan builder

Modify:

- `neotrade3/orchestration/daily_master_orchestrator.py`

Implementation:

1. add `build_on_demand_plan(...)`
2. construct `PlannedTask` directly from explicit request tasks
3. preserve phases by first appearance

### M5ONDEM-S3: Lock focused tests

Modify:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Required coverage:

1. on-demand plan shape is correct
2. reject execution can run through on-demand plan
3. daily config path remains unchanged

### M5ONDEM-S4: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/orchestration/models.py neotrade3/orchestration/daily_master_orchestrator.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `python3 -m pytest tests/unit/test_m5_governance_orchestrator_fit.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: mutate daily planning semantics**
  - Guardrail: keep on-demand builder separate from `build_run_plan(...)`
- **Risk: over-generalize into a new scheduler**
  - Guardrail: only build `DailyRunPlan`, still reuse `execute_run_plan(...)`
- **Risk: widen beyond reject execution**
  - Guardrail: tests stay anchored to current reject path

## 5. Done Criteria

- on-demand request contract exists
- on-demand plan builder exists
- reject execution runs through the carrier in focused tests
- daily config stays unchanged

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in orchestration carrier support for `M5`
- `G1-G6` target mapping:
  - this is the minimum `G2` formal plan carrier step after worker executor compatibility
- new contract introduced:
  - `OnDemandTaskRequest`
  - `build_on_demand_plan(...)`
- boundaries not touched:
  - no daily config mutation
  - no auto validation selection
  - no promotion approval
  - no `M6`
