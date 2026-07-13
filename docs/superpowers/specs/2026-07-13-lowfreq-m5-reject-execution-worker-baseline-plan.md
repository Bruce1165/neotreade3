Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 reject execution worker baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution Worker Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-worker-baseline-design.md`

## 1. Goal

This slice only lets the existing governance phase worker executor trigger reject execution.

This slice must:

- extend `_create_governance_executor()` with a reject branch
- keep the handoff branch unchanged
- add focused synthetic orchestrator-fit tests

This slice explicitly does not:

- modify production daily orchestrator config
- add automatic validation selection
- change CLI

## 2. File Boundary

Production file:

- `apps/worker/main.py`

Focused test file:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Files intentionally not modified:

- `config/orchestrator/daily_master_orchestrator.json`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `M6`

## 3. Execution Steps

### M5REJWORK-S1: Extend governance executor

Modify:

- `apps/worker/main.py`

Implementation:

1. inspect `task.args_template`
2. if `validation_id` is present and non-empty:
   - require `source_run_id`
   - call `run_governance_reject_execution(...)`
   - return reject execution task details
3. otherwise:
   - keep current handoff flow

### M5REJWORK-S2: Add synthetic orchestrator-fit tests

Modify:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Required coverage:

1. governance executor reject dry-run path
2. governance executor reject materialization path
3. reject branch failure for missing `validation_id` or missing `source_run_id`
4. handoff branch remains unchanged

### M5REJWORK-S3: Minimum verification

Run at minimum:

- `python3 -m py_compile apps/worker/main.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `python3 -m pytest tests/unit/test_m5_governance_orchestrator_fit.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: break existing handoff governance executor**
  - Guardrail: branch only when `validation_id` is explicitly present
- **Risk: accidentally imply production scheduling**
  - Guardrail: do not touch production orchestrator config
- **Risk: widen into CLI or runtime changes**
  - Guardrail: modify only worker main and orchestrator-fit tests

## 5. Done Criteria

- governance worker executor supports reject execution
- focused orchestrator-fit tests pass
- production config remains unchanged
- handoff branch remains unchanged

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` worker/executor adoption
- `G1-G6` target mapping:
  - this is the minimum `G2` worker/orchestrator compatibility step
- new runtime contract introduced:
  - governance phase executor reject branch keyed by explicit args
- boundaries not touched:
  - no production scheduled reject task
  - no auto validation selection
  - no promotion approval
  - no `M6`
