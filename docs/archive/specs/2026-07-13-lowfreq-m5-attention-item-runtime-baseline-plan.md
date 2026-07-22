Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance AttentionItem runtime baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 AttentionItem Runtime Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-attention-item-runtime-baseline-design.md`

## 1. Goal

This slice only introduces the minimal `AttentionItem` runtime projection through the existing `M5` governance mainline.

This slice must:

- add `attention_items` to `GovernanceHandoffBundle`
- project one `AttentionItem` from each active `PromotionBlocker`
- persist `attention_items` in governance handoff artifacts
- add `attention_item_count` to ledger, worker task details, and CLI output
- lock the mainline with focused tests

This slice explicitly does not:

- redesign the `AttentionItem` contract
- add approval or reject execution logic
- freeze taxonomy enums
- add `M6` delivery output

## 2. Starting Point

Repository evidence before implementation:

- `AttentionItem` nucleus already exists in `governance.contracts`, `governance.assembler`, and `governance.__init__`
- `GovernanceHandoffBundle` currently stops at `decision_records`
- ledger, worker task details, and CLI output currently stop at `decision_record_count`
- current runtime mainline already materializes the handoff bundle, so the missing owner is projection, not runtime orchestration

So the correct narrow move is:

- extend the existing `M5` handoff chain with `AttentionItem`
- keep the source mapping minimal and deterministic
- avoid introducing a new workflow surface

## 3. File Boundary

Production files:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`

Focused test files:

- `tests/unit/test_m5_governance_handoff_adapter.py`
- `tests/unit/test_m5_governance_run_ledger.py`
- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Files intentionally not modified:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/runtime.py`
- `neotrade3/orchestration/models.py`
- `M6`

Optional thin-helper file only if strictly needed:

- `neotrade3/governance/assembler.py`

## 4. Execution Steps

### M5AIR-S1: Extend handoff bundle

Modify:

- `neotrade3/governance/handoff.py`

Implementation:

1. add `attention_items` to `GovernanceHandoffBundle`
2. include `attention_items` in `to_payload()`
3. preserve existing object order and defensive payload copying

Implementation rule:

- do not change existing diagnostic/change/experiment/validation/blocker/decision semantics

### M5AIR-S2: Add minimal blocker projection

Modify:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/assembler.py` only if a thin projection helper improves clarity

Implementation:

1. build one `AttentionItem` from each active `PromotionBlocker`
2. keep the projection deterministic and local to the current governance chain
3. aggregate projected `attention_items` in batch order

Implementation rule:

- do not add a generalized routing matrix from diagnostics or change requests

### M5AIR-S3: Persist attention counts

Modify:

- `neotrade3/governance/run_ledger.py`

Implementation:

1. add `attention_item_count` to `GovernanceRunLedgerRecord`
2. persist that field when writing ledger payloads
3. hydrate it in `from_dict()`

Implementation rule:

- artifact payload should stay a thin reflection of `GovernanceHandoffBundle.to_payload()`

### M5AIR-S4: Expose runtime summaries

Modify:

- `neotrade3/governance/cli.py`
- `apps/worker/main.py`

Implementation:

1. add `attention_item_count` to CLI JSON output
2. add `attention_item_count` to governance worker task `details`

Implementation rule:

- do not emit full `attention_items` arrays through worker or CLI in this slice

### M5AIR-S5: Lock focused runtime-chain tests

Modify:

- `tests/unit/test_m5_governance_handoff_adapter.py`
- `tests/unit/test_m5_governance_run_ledger.py`
- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Required coverage:

1. failing B4 handoff path produces one `attention_item`
2. clean assessment produces zero `attention_items`
3. batch handoff preserves deterministic `attention_items` order
4. ledger persists `attention_item_count`
5. CLI output includes `attention_item_count`
6. worker executor details include `attention_item_count`

Testing rule:

- do not widen into approval execution tests
- do not widen into `M6` tests

### M5AIR-S6: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/handoff.py neotrade3/governance/run_ledger.py neotrade3/governance/cli.py apps/worker/main.py tests/unit/test_m5_governance_handoff_adapter.py tests/unit/test_m5_governance_run_ledger.py tests/unit/test_m5_governance_cli.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `python3 -m pytest tests/unit/test_m5_governance_handoff_adapter.py tests/unit/test_m5_governance_run_ledger.py tests/unit/test_m5_governance_cli.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `git diff --check`

## 5. Risks And Guardrails

- **Risk: widen into full attention runtime**
  - Guardrail: only project from existing promotion blockers and only surface counts downstream
- **Risk: mutate governance semantics while adding attention**
  - Guardrail: existing blocker and decision records remain unchanged
- **Risk: leak a larger external surface**
  - Guardrail: worker and CLI expose only `attention_item_count`

## 6. Done Criteria

This slice is done only when all of the following are true:

- `GovernanceHandoffBundle` carries `attention_items`
- failing governance handoff paths project one attention item per blocker
- ledger, worker details, and CLI output include `attention_item_count`
- focused runtime-chain tests pass
- no approval/reject logic is added
- no `M6` file is modified

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely in the `M5` runtime projection and persistence layer
- `G1-G6` target mapping:
  - this is the minimum `G2` runtime-adoption step after the `AttentionItem` nucleus landed
- new runtime contract introduced:
  - `GovernanceHandoffBundle.attention_items`
  - `GovernanceRunLedgerRecord.attention_item_count`
  - worker/CLI `attention_item_count`
- boundaries not touched:
  - no approval execution
  - no taxonomy freeze
  - no `M6`
