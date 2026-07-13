Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 reject decision nucleus` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Decision Nucleus Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-decision-nucleus-design.md`

## 1. Goal

This slice only freezes the canonical builder from rejected validation result to reject decision record.

This slice must:

- add `build_reject_decision_record_from_validation_result(...)`
- export it from `neotrade3.governance`
- lock the mapping with focused tests

This slice explicitly does not:

- add reject runtime execution
- materialize artifacts
- update blocker or attention statuses
- add promotion approval

## 2. File Boundary

Production files:

- `neotrade3/governance/assembler.py`
- `neotrade3/governance/__init__.py`

Focused test file:

- `tests/unit/test_m5_governance_contract_nucleus.py`

Files intentionally not modified:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`

## 3. Execution Steps

### M5REJ-S1: Add reject decision builder

Modify:

- `neotrade3/governance/assembler.py`

Implementation:

1. add `build_reject_decision_record_from_validation_result(...)`
2. require `validation_result.outcome == "rejected"`
3. return `GovernanceDecisionRecord` through `build_governance_decision_record(...)`

Canonical mapping:

- `decision_id = f"{validation_id}:decision"`
- `subject_type = "validation_result"`
- `subject_id = validation_id`
- `decision = "reject"`
- `decision_scope = "promotion"`
- `rationale = "validation outcome rejected"`
- `approver = "system_governance"`
- `status = "recorded"`
- `evidence_refs = validation_result.evidence_refs`

### M5REJ-S2: Export the builder

Modify:

- `neotrade3/governance/__init__.py`

Implementation:

1. export `build_reject_decision_record_from_validation_result`
2. keep package ordering and style consistent with current governance exports

### M5REJ-S3: Lock focused tests

Modify:

- `tests/unit/test_m5_governance_contract_nucleus.py`

Required coverage:

1. rejected validation result produces one reject decision record
2. the resulting record fields match the canonical mapping
3. non-rejected outcomes raise `ValueError`

### M5REJ-S4: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/assembler.py neotrade3/governance/__init__.py tests/unit/test_m5_governance_contract_nucleus.py`
- `python3 -m pytest tests/unit/test_m5_governance_contract_nucleus.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: let runtime invent reject decision fields later**
  - Guardrail: freeze the canonical builder now
- **Risk: widen into runtime/materialization**
  - Guardrail: modify only assembler/export/test
- **Risk: accept non-final validation outcomes**
  - Guardrail: raise on any outcome other than `rejected`

## 5. Done Criteria

- reject decision builder exists
- package export exists
- focused tests pass
- no runtime/materialization files change

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` builder ownership
- `G1-G6` target mapping:
  - this is the minimum `G2` reject owner freeze before runtime adoption
- new contract introduced:
  - canonical rejected-validation to reject-decision builder
- boundaries not touched:
  - no runtime execution
  - no artifact mutation
  - no promotion approval
  - no `M6`
