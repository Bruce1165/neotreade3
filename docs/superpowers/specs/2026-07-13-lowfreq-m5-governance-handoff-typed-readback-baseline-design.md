Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance handoff typed readback baseline` slice after attention runtime baseline and before reject execution
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Handoff Typed Readback Baseline Design

Date: 2026-07-13

## 1. Goal

This slice advances `M5 governance` one narrow step beyond the already-landed attention runtime baseline.

Current repository evidence shows:

- `M5` already has:
  - formal governance contracts in `neotrade3/governance/contracts.py`
  - canonical persisted governance artifact and ledger readback in `neotrade3/governance/run_ledger.py`
  - runtime projection through `handoff -> artifact/ledger -> worker/CLI`
- `M5` still does not have:
  - typed reconstruction of a persisted `GovernanceHandoffBundle`
  - object-level `from_dict(...)` symmetry for the persisted governance object tree
- the next audited mainline gap is `reject execution baseline`
- reject execution would otherwise need to parse raw governance artifact dicts directly

So the narrow problem is no longer:

- how to build or persist governance handoff artifacts
- how to count attention items in the runtime mainline

It is:

- how to reconstruct one truthful typed `GovernanceHandoffBundle` from the already-persisted governance artifact
- how to keep future reject execution logic out of private raw-dict parsing
- how to repair write/read symmetry inside `M5` before execution semantics widen

Project-phase note:

- domain: `M5 governance typed persisted readback`
- change type: `runtime baseline -> typed reconstruction baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add `from_dict(...)` support for the persisted governance object tree
- add one typed governance artifact readback helper
- add focused tests that lock round-trip reconstruction from a live governance handoff artifact back into typed objects

Excluded:

- no reject execution runtime
- no promotion approval runtime
- no ledger schema changes
- no worker/orchestrator changes
- no CLI changes
- no `M6`

## 3. Existing Evidence

### 3.1 Governance Persistence Already Exists

Current repository evidence in:

- [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py)
- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py)

shows that governance already has:

- canonical persisted artifact writing
- canonical ledger writing
- raw artifact readback by `source_run_id`
- typed ledger readback by `source_run_id`

That means the missing capability is not persistence itself.

The missing capability is typed artifact reconstruction.

### 3.2 Current Artifact Readback Is Raw Only

Current repository evidence in:

- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L185-L201)

shows that:

- `read_governance_handoff_artifact(...)` returns `dict[str, Any] | None`
- there is no `read_governance_handoff_bundle(...)`
- there is no `GovernanceHandoffBundle.from_dict(...)`

So any future consumer of persisted governance artifacts would have to know private JSON details directly.

### 3.3 M4 Already Proved The Symmetric Typed Readback Pattern

Current repository evidence in:

- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/run_ledger.py#L164-L173)
- [test_m4_benchmark_typed_readback.py](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_typed_readback.py#L22-L94)

shows the already-proven pattern:

- keep the raw helper
- add a typed helper beside it
- reconstruct the full persisted object tree via `from_dict(...)`
- lock round-trip behavior with focused tests

The safest `M5` next step is to mirror this pattern narrowly for governance handoff artifacts.

### 3.4 Reject Execution Is The Next Consumer And Should Not Parse Raw Dicts

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py)
- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py)
- [test_m5_governance_contract_nucleus.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_contract_nucleus.py#L168-L284)

shows that:

- contracts already allow final `ValidationResult(outcome="rejected")`
- contracts already allow `GovernanceDecisionRecord(decision="reject")`
- current runtime still only materializes pending/block paths

So the next execution slice will need to consume persisted governance truth.

Doing that from raw dicts would duplicate serialization knowledge inside the execution runtime.

## 4. Approach Options

### Option A: Add One Reject-Specific Dict Adapter

- keep `M5` governance artifact readback raw
- add logic in reject runtime to consume raw artifact dicts directly

Pros:

- smallest short-term change set for reject execution

Cons:

- duplicates serialization knowledge inside `M5`
- creates a one-off consumer path instead of a reusable typed owner
- makes future non-reject consumers repeat the same parsing

### Option B: Add Symmetric Typed Reconstruction In `M5` (Recommended)

- add `from_dict(...)` on the persisted governance object tree
- add one governance-level typed artifact readback helper
- keep reject runtime unchanged in this slice

Pros:

- repairs the write/read symmetry where the data actually belongs
- creates one reusable upstream truth for any later `M5` consumer
- keeps reject execution free of raw serialization details
- preserves current persistence shape while enabling future execution switching

Cons:

- touches several governance contract owners
- requires careful focused tests for nested object reconstruction

### Option C: Reconstruct Only Validation/Decision Subsets

- add a partial typed object or a special-purpose `GovernanceForReject` shape
- reconstruct only the fields needed by reject execution

Pros:

- less code than full object-tree symmetry

Cons:

- introduces a second near-duplicate truth beside `GovernanceHandoffBundle`
- bakes current reject needs into storage design
- becomes misleading once other consumers need the full bundle

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice should modify only the minimum `M5` owners required for typed readback:

- `neotrade3/governance/contracts.py`
  - add object-level `from_dict(...)` support for the persisted governance object tree
- `neotrade3/governance/handoff.py`
  - add `GovernanceHandoffBundle.from_dict(...)`
- `neotrade3/governance/run_ledger.py`
  - add one typed artifact readback helper
- focused test owner:
  - `tests/unit/test_m5_governance_typed_readback.py`

Recommended new readback helper:

- `read_governance_handoff_bundle(...)`

Recommended behavior:

1. locate the canonical artifact file by `source_run_id`
2. return `None` if the file does not exist
3. load the artifact JSON payload
4. require the root payload to be a JSON object
5. return `GovernanceHandoffBundle.from_dict(payload)`

This helper must not:

- infer missing governance objects from ledger metadata
- rerun governance from benchmark artifacts
- invoke reject or promotion execution
- write any files

### 5.2 Contract Symmetry Freeze

The reconstruction baseline should be symmetric with the existing persisted shape, not with a new simplified shape.

Recommended object tree to reconstruct:

- `DiagnosticChain`
- `ChangeRequest`
- `ExperimentRequest`
- `ValidationResult`
- `PromotionBlocker`
- `AttentionItem`
- `GovernanceDecisionRecord`
- `GovernanceHandoffBundle`

Readback rule:

- `from_dict(...)` should accept the serialized payload shape already produced by each object's current `to_payload()`

Validation rule:

- root payload must be a JSON object
- malformed nested payloads should surface a direct validation error
- optional fields should preserve the same defaults already implied by the dataclass definitions

Why full symmetry is preferred over a minimal subset:

- the artifact already stores the full object tree
- partial reconstruction would create an unnecessary second contract
- future consumers should not need to guess which fields are truly available

### 5.3 Artifact-Level Readback Contract

Current raw helper:

- `read_governance_handoff_artifact(...)`

Should remain unchanged.

New typed helper:

- `read_governance_handoff_bundle(...)`

Contract:

- return `None` only when the artifact file does not exist
- raise direct validation errors for malformed artifact roots or malformed nested payloads
- ignore artifact envelope keys that are not part of `GovernanceHandoffBundle`, such as:
  - `written_at`

This matches the already-proven `M4` typed readback rule:

- metadata envelope keys are tolerated
- the canonical typed runtime object is reconstructed from the business payload only

### 5.4 No Runtime Widening

This slice must stop before reject execution.

So it should not:

- add new runtime entrypoints
- change existing governance CLI behavior
- change worker/orchestrator details
- mutate `decision_records`
- infer new final decisions from existing validation results

The acceptance standard is only:

- persisted governance artifacts reconstruct into typed `GovernanceHandoffBundle` objects

## 6. Testing Strategy

Focused tests should lock:

1. round-trip typed reconstruction from a real governance materialization
2. nested reconstruction of:
   - diagnostics
   - validation results
   - attention items
   - decision records
3. artifact-envelope tolerance
   - persisted `written_at` must not pollute the typed bundle
4. missing artifact behavior
   - typed helper returns `None`
5. raw helper remains unchanged

Testing rule:

- do not re-test benchmark grading logic
- do not re-test governance runtime orchestration
- test only the new readback contract:
  - object symmetry
  - typed helper behavior
  - envelope-key tolerance

## 7. Risks And Guardrails

### 7.1 Consumer-Specific Readback Drift

The main risk is building a reject-only adapter instead of a canonical typed owner.

Guardrail:

- reconstruct the full governance handoff bundle
- keep reject execution out of this slice

### 7.2 Envelope Leakage Risk

Another risk is letting artifact metadata pollute runtime objects.

Guardrail:

- `from_dict(...)` only reads business payload keys
- focused tests explicitly assert `written_at` does not become a runtime field

### 7.3 Scope Creep Risk

Another risk is widening into runtime execution while typed readback is being added.

Guardrail:

- no runtime entrypoint changes
- no CLI/worker/orchestrator changes

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- persisted governance artifacts can reconstruct into typed `GovernanceHandoffBundle` objects
- the raw artifact helper remains unchanged
- nested governance objects reconstruct symmetrically
- focused typed-readback tests pass
- no reject/promotion runtime code is changed
- no `M6` code is changed

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- `M5 reject execution baseline`
- `M5 promotion approval baseline`
- blocker/attention status transitions driven by final validation results
- governance execution CLI expansion
- `M6` decision delivery projection

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely inside `M5` persisted readback symmetry and does not cross into execution or delivery layers
- `G1-G6` target mapping:
  - this is the minimum `G5` persisted-truth step required before reject execution can consume typed governance state
- new readback contract introduced:
  - object-level `from_dict(...)` symmetry for the persisted governance tree
  - `read_governance_handoff_bundle(...)`
- boundaries not touched:
  - no reject execution
  - no promotion approval
  - no `M6`
