Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 reject execution persistence baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution Persistence Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-persistence-baseline-design.md`

## 1. Goal

This slice only introduces the minimum independent reject execution runtime and persistence path.

This slice must:

- read one typed governance handoff bundle by `source_run_id`
- select one final rejected validation result by `validation_id`
- build one canonical reject decision record
- persist one independent reject execution artifact and ledger under `validation_id`

This slice explicitly does not:

- overwrite `governance_handoff` artifacts
- implement promotion approval
- change blocker or attention state
- change CLI or orchestrator behavior

## 2. File Boundary

Production files:

- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/runtime.py`

Focused test file:

- `tests/unit/test_m5_governance_reject_execution.py`

Files intentionally not modified:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `neotrade3/orchestration/*`
- `M6`

## 3. Execution Steps

### M5REX-S1: Add independent reject artifact writer

Modify:

- `neotrade3/governance/artifact_writer.py`

Implementation:

1. add a narrow record for reject execution artifact metadata
2. add one writer for:
   - `var/artifacts/governance_rejections/<validation_id>/governance_reject_execution.json`
3. artifact payload must include:
   - `source_run_id`
   - `validation_id`
   - `baseline_run_id`
   - `candidate_run_id`
   - `validation_result`
   - `decision_record`
   - `written_at`

### M5REX-S2: Add independent reject ledger helpers

Modify:

- `neotrade3/governance/run_ledger.py`

Implementation:

1. add one reject execution ledger record
2. add read/materialize helpers for:
   - `var/ledgers/governance_rejections/<validation_id>/governance_reject_execution_run.json`
3. keep all existing handoff ledger/readback helpers unchanged

### M5REX-S3: Add reject runtime owner

Modify:

- `neotrade3/governance/runtime.py`

Implementation:

1. add a runtime entrypoint:
   - read typed handoff bundle by `source_run_id`
   - locate one validation result by `validation_id`
   - require rejected outcome
   - build reject decision record
   - materialize the independent execution artifact/ledger
2. keep the existing benchmark-to-handoff runtime unchanged

### M5REX-S4: Lock focused tests

Create:

- `tests/unit/test_m5_governance_reject_execution.py`

Required coverage:

1. rejected validation result materializes one independent execution artifact and ledger
2. original handoff artifact remains unchanged
3. missing validation id fails deterministically
4. non-rejected validation result fails deterministically
5. dry-run writes nothing

### M5REX-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/artifact_writer.py neotrade3/governance/run_ledger.py neotrade3/governance/runtime.py tests/unit/test_m5_governance_reject_execution.py`
- `python3 -m pytest tests/unit/test_m5_governance_reject_execution.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: accidentally overwrite the handoff baseline**
  - Guardrail: use a separate `governance_rejections/<validation_id>` namespace
- **Risk: runtime reads raw dicts again**
  - Guardrail: always start from `read_governance_handoff_bundle(...)`
- **Risk: widen into CLI/orchestrator**
  - Guardrail: keep changes inside artifact_writer/run_ledger/runtime/test

## 5. Done Criteria

- independent reject execution artifact exists
- independent reject execution ledger exists
- runtime owner exists
- original handoff artifact remains unchanged
- focused tests pass
- no CLI/orchestrator/`M6` file changes

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` reject runtime and persistence
- `G1-G6` target mapping:
  - this is the minimum `G2` reject runtime adoption step
- new runtime contract introduced:
  - independent reject execution artifact and ledger keyed by `validation_id`
- boundaries not touched:
  - no handoff overwrite
  - no promotion approval
  - no CLI/orchestrator adoption
  - no `M6`
