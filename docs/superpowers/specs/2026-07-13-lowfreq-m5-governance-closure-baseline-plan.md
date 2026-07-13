Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance closure baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Closure Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-closure-baseline-design.md`

## 1. Goal

This slice only closes the pending runtime chain for:

- `ValidationResult`
- `GovernanceDecisionRecord`

This slice must:

- allow pending `ValidationResult` envelopes without fabricating candidate run ids
- project pending validation and block decision objects into governance handoff bundles
- persist both object families through artifact and ledger payloads
- surface both count fields through CLI
- lock the new closure with focused tests

This slice explicitly does not:

- implement real candidate comparison
- implement promotion approval/reject execution
- add `AttentionItem`
- change runtime entrypoint or orchestrator contracts
- touch `M6`

## 2. Starting Point

Repository evidence before implementation:

- contracts for `ValidationResult` and `GovernanceDecisionRecord` already exist
- pure builders for both already exist
- current runtime closure still stops at `promotion_blockers`
- real comparison logic does not exist yet

So the correct narrow move is:

- represent pending validation truthfully
- represent blocker-based block decisions truthfully
- thread both through the existing `handoff -> artifact -> ledger -> CLI` chain

## 3. File Boundary

Production files:

- `neotrade3/governance/assembler.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `neotrade3/governance/__init__.py`

Focused test files:

- `tests/unit/test_m5_governance_contract_nucleus.py`
- `tests/unit/test_m5_governance_handoff_adapter.py`
- `tests/unit/test_m5_governance_run_ledger.py`
- `tests/unit/test_m5_governance_cli.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/orchestration/*`
- `neotrade3/benchmark/*`
- `M6`

## 4. Execution Steps

### M5CB-S1: Allow strictly-pending ValidationResult envelopes

Modify:

- `neotrade3/governance/assembler.py`

Implementation:

1. relax `build_validation_result(...)` so empty `candidate_run_id` is allowed only when:
   - `outcome == "awaiting_candidate_validation"`
2. keep non-empty `candidate_run_id` required for every other outcome
3. add one helper to build a pending validation result from:
   - `ExperimentRequest`
   - `source_run_id`

Implementation rule:

- do not weaken the builder more broadly
- do not invent synthetic candidate run ids

### M5CB-S2: Build blocker-based decision records

Modify:

- `neotrade3/governance/assembler.py`

Implementation:

1. add one helper that builds a decision record from an active `PromotionBlocker`
2. freeze:
   - `decision="block"`
   - `decision_scope="promotion"`
   - `approver="system_governance"`
   - `status="recorded"`

Implementation rule:

- decision remains a record of the active governance gate, not a human approval artifact

### M5CB-S3: Extend handoff bundle and projection chain

Modify:

- `neotrade3/governance/handoff.py`

Implementation:

1. add `validation_results` and `decision_records` to `GovernanceHandoffBundle`
2. include both in `to_payload()`
3. when a failing assessment produces:
   - `experiment_request`
   - `promotion_blocker`
   also produce:
   - pending `validation_result`
   - block `decision_record`
4. aggregate both in batch-run projection

Implementation rule:

- clean assessments still produce zero closure objects
- do not change projected issue counting semantics

### M5CB-S4: Persist and surface new counts

Modify:

- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`

Implementation:

1. add ledger counts:
   - `validation_result_count`
   - `decision_record_count`
2. round-trip those counts through:
   - `GovernanceRunLedgerRecord.from_dict()`
   - `to_payload()`
   - ledger write payload
3. expose the same counts in CLI JSON output

### M5CB-S5: Export new shared helpers if tests consume them

Modify:

- `neotrade3/governance/__init__.py`

Implementation:

1. export any new shared helper added in assembler only if directly used by focused tests

### M5CB-S6: Lock the closure with focused tests

Modify:

- `tests/unit/test_m5_governance_contract_nucleus.py`
- `tests/unit/test_m5_governance_handoff_adapter.py`
- `tests/unit/test_m5_governance_run_ledger.py`
- `tests/unit/test_m5_governance_cli.py`

Required coverage:

1. pending `ValidationResult` allows empty `candidate_run_id` only for the pending outcome
2. blocker-based `GovernanceDecisionRecord` fields are stable
3. failing handoff includes exactly one validation result and one decision record
4. clean handoff includes zero validation results and zero decision records
5. run ledger persists and reads back new counts
6. CLI output matches ledger counts

### M5CB-S7: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/assembler.py neotrade3/governance/handoff.py neotrade3/governance/run_ledger.py neotrade3/governance/cli.py neotrade3/governance/__init__.py tests/unit/test_m5_governance_contract_nucleus.py tests/unit/test_m5_governance_handoff_adapter.py tests/unit/test_m5_governance_run_ledger.py tests/unit/test_m5_governance_cli.py`
- `python3 -m pytest tests/unit/test_m5_governance_contract_nucleus.py tests/unit/test_m5_governance_handoff_adapter.py tests/unit/test_m5_governance_run_ledger.py tests/unit/test_m5_governance_cli.py`
- `git diff --check`

## 5. Risks And Guardrails

- **Risk: fabricate candidate comparison**
  - Guardrail: pending validation uses empty `candidate_run_id` and explicit pending outcome
- **Risk: over-broaden builder relaxation**
  - Guardrail: only pending outcome may omit `candidate_run_id`
- **Risk: overclaim approval authority**
  - Guardrail: decision record only records a `block` decision from `system_governance`

## 6. Done Criteria

This slice is done only when all of the following are true:

- governance handoff includes pending `validation_results`
- governance handoff includes blocker-based `decision_records`
- ledger and CLI surface new counts
- no fake candidate run id exists
- focused tests pass

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely within `M5` runtime closure and persistence
- `G1-G6` target mapping:
  - this is the minimum `G5` closure baseline after contract nucleus and runtime baseline already landed
- new contract introduced:
  - pending `awaiting_candidate_validation` outcome
  - blocker-based `block/promotion/recorded` decision record
- boundaries not touched:
  - no candidate comparison runtime
  - no promotion approval automation
  - no `M6`
