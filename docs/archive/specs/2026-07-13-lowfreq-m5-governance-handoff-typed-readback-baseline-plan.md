Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance handoff typed readback baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Handoff Typed Readback Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-handoff-typed-readback-baseline-design.md`

## 1. Goal

This slice only introduces symmetric typed reconstruction for persisted `M5 governance` handoff artifacts.

This slice must:

- add `from_dict(...)` for the persisted governance object tree
- add `GovernanceHandoffBundle.from_dict(...)`
- add `read_governance_handoff_bundle(...)`
- lock round-trip behavior with focused typed-readback tests

This slice explicitly does not:

- add reject execution runtime
- add promotion approval runtime
- change governance CLI or worker behavior
- change ledger schema
- touch `M6`

## 2. Starting Point

Repository evidence before implementation:

- governance persistence already exists through `artifact_writer.py` and `run_ledger.py`
- current governance artifact readback is raw-only
- current governance contracts do not reconstruct from persisted payloads
- the next audited mainline gap is reject execution, which should consume typed governance state rather than private raw dicts

So the correct narrow move is:

- repair write/read symmetry inside `M5`
- keep runtime execution work for the next slice

## 3. File Boundary

Production files:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`

Focused test file:

- `tests/unit/test_m5_governance_typed_readback.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `neotrade3/orchestration/*`
- `M6`

## 4. Execution Steps

### M5READ-S1: Add contract-level reconstruction

Modify:

- `neotrade3/governance/contracts.py`

Implementation:

1. add `from_dict(...)` to:
   - `DiagnosticChain`
   - `ChangeRequest`
   - `ExperimentRequest`
   - `ValidationResult`
   - `PromotionBlocker`
   - `AttentionItem`
   - `GovernanceDecisionRecord`
2. make each `from_dict(...)` consume the same payload shape already emitted by `to_payload()`
3. preserve current defaults for optional collections and metadata fields

Implementation rule:

- reject non-object payload roots with direct validation errors
- do not add new business fields

### M5READ-S2: Add typed handoff reconstruction

Modify:

- `neotrade3/governance/handoff.py`

Implementation:

1. add `GovernanceHandoffBundle.from_dict(...)`
2. reconstruct each nested object list through the new contract-level `from_dict(...)`
3. tolerate artifact envelope keys such as `written_at`

Implementation rule:

- reconstruct only the governance business payload
- do not infer missing objects

### M5READ-S3: Add typed artifact readback helper

Modify:

- `neotrade3/governance/run_ledger.py`

Implement one new helper:

- `read_governance_handoff_bundle(...)`

Recommended behavior:

1. resolve the canonical artifact file from `source_run_id`
2. return `None` if the file does not exist
3. load the artifact JSON payload
4. require the root payload to be a JSON object
5. return `GovernanceHandoffBundle.from_dict(payload)`

Implementation rules:

- keep `read_governance_handoff_artifact(...)` unchanged
- do not reconstruct from ledger metadata alone
- surface malformed payload errors directly

### M5READ-S4: Add focused typed-readback tests

Create:

- `tests/unit/test_m5_governance_typed_readback.py`

Test carrier pattern:

- run a real governance materialization under a temp project root
- read back through both the raw and typed helpers
- compare the reconstructed bundle to the original runtime bundle at the contract level

Test cases:

1. round-trip typed reconstruction
   - build a real governance bundle from the canonical B4 failing path
   - materialize it
   - read back via `read_governance_handoff_bundle(...)`
   - assert key runtime objects align with the original typed bundle
2. nested reconstruction
   - assert the reconstructed bundle contains:
     - diagnostics
     - validation results
     - attention items
     - decision records
3. envelope tolerance
   - assert persisted `written_at` does not pollute the typed runtime bundle
4. missing artifact behavior
   - assert the typed helper returns `None` when the artifact file does not exist
5. raw helper stability
   - assert `read_governance_handoff_artifact(...)` still returns the persisted raw dict payload

Testing rule:

- do not re-test benchmark grading logic
- do not re-test governance CLI/worker/orchestrator behavior
- test only the new readback contract:
  - object symmetry
  - typed helper behavior
  - envelope-key tolerance

### M5READ-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/contracts.py neotrade3/governance/handoff.py neotrade3/governance/run_ledger.py tests/unit/test_m5_governance_typed_readback.py`
- `python3 -m pytest tests/unit/test_m5_governance_typed_readback.py tests/unit/test_m5_governance_run_ledger.py tests/unit/test_m5_governance_handoff_adapter.py`
- `git diff --check`

## 5. Risks And Guardrails

- **Risk: create a reject-only adapter instead of a canonical readback owner**
  - Guardrail: reconstruct the full governance handoff bundle
- **Risk: leak artifact metadata into runtime objects**
  - Guardrail: ignore envelope-only keys such as `written_at`
- **Risk: widen into runtime execution**
  - Guardrail: no changes outside contracts/handoff/run_ledger/typed-readback test

## 6. Done Criteria

This slice is done only when all of the following are true:

- persisted governance artifacts can reconstruct into typed `GovernanceHandoffBundle` objects
- raw artifact readback remains unchanged
- nested governance objects reconstruct symmetrically
- focused typed-readback tests pass
- no reject/promotion runtime code is changed
- no `M6` file is modified

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely in the `M5` persisted readback symmetry layer
- `G1-G6` target mapping:
  - this is the minimum `G5` persisted-truth step before reject execution can consume typed governance state
- new readback contract introduced:
  - object-level `from_dict(...)` for the governance object tree
  - `GovernanceHandoffBundle.from_dict(...)`
  - `read_governance_handoff_bundle(...)`
- boundaries not touched:
  - no reject execution
  - no promotion approval
  - no `M6`
