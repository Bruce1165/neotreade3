Status: active
Owner: lowfreq / governance / worker / api
Scope: Implementation plan for the narrow `M5 governance closure counts visibility baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Closure Counts Visibility Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-closure-counts-visibility-baseline-design.md`

## 1. Goal

This slice only surfaces two already-existing governance closure counts through the operational `worker -> orchestration API` chain.

This slice must:

- add `validation_result_count` to worker governance handoff details
- add `decision_record_count` to worker governance handoff details
- lock worker/orchestrator regressions for both fields
- lock one API wrapper regression proving wrapper persistence preserves both fields

This slice explicitly does not:

- add new governance contracts
- add new ledger or CLI fields
- add candidate validation or approval workflow
- modify `M6`

## 2. File Boundary

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-closure-counts-visibility-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-closure-counts-visibility-baseline-plan.md`

Production file:

- `apps/worker/main.py`

Focused test files:

- `tests/unit/test_m5_governance_orchestrator_fit.py`
- `tests/unit/test_bootstrap_skeleton.py`

Files intentionally not modified:

- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `apps/api/main.py`
- `neotrade3/governance/runtime.py`
- `M6`

## 3. Execution Steps

### M5CV-S1: Extend worker governance summary details

Modify:

- `apps/worker/main.py`

Implementation:

1. locate the governance handoff branch in `_create_governance_executor()`
2. preserve all existing `details` fields
3. add:
   - `validation_result_count`
   - `decision_record_count`
4. source both values from the returned `GovernanceRunLedgerRecord`

Implementation rule:

- do not touch the reject execution branch
- do not recompute counts from artifacts

### M5CV-S2: Lock worker/orchestrator regressions

Modify:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Implementation:

1. extend dry-run governance executor assertions with:
   - `validation_result_count`
   - `decision_record_count`
2. extend materialized governance executor assertions with the same two fields
3. keep existing assertions unchanged

Implementation rule:

- do not widen into candidate validation or reject runtime tests

### M5CV-S3: Lock API wrapper preservation

Modify:

- `tests/unit/test_bootstrap_skeleton.py`

Implementation:

1. extend `test_orchestration_run_view_uses_worker_runtime_and_writes_wrapper_files`
2. make the fake worker snapshot task detail carry:
   - `validation_result_count`
   - `decision_record_count`
3. assert the wrapper artifact preserves those fields in `tasks[0].details`

Implementation rule:

- do not change production API code
- keep this as a wrapper-preservation regression only

### M5CV-S4: Minimum verification

Run at minimum:

- `python3 -m py_compile apps/worker/main.py tests/unit/test_m5_governance_orchestrator_fit.py tests/unit/test_bootstrap_skeleton.py`
- `python3 -m pytest tests/unit/test_m5_governance_orchestrator_fit.py tests/unit/test_bootstrap_skeleton.py -k "governance_executor or orchestration_run_view_uses_worker_runtime_and_writes_wrapper_files"`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: widen into full closure workflow**
  - Guardrail: only surface two already-existing counts
- **Risk: introduce inconsistent sources**
  - Guardrail: always source from `GovernanceRunLedgerRecord`
- **Risk: change API behavior unnecessarily**
  - Guardrail: API layer stays untouched; only add regression coverage

## 5. Done Criteria

- worker governance handoff details include `validation_result_count`
- worker governance handoff details include `decision_record_count`
- worker/orchestrator tests lock both fields
- API wrapper regression proves the fields survive persistence
- no unrelated governance runtime or `M6` changes appear in the diff

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in `M5` worker/API summary visibility
- `G1-G6` target mapping:
  - this hardens `G2` by exposing closure counts on the operational path without inventing new workflow
- new runtime contract introduced:
  - governance worker details expose `validation_result_count`
  - governance worker details expose `decision_record_count`
- boundaries not touched:
  - no candidate comparison
  - no final validation materialization
  - no promotion/reject workflow expansion
  - no `M6`
