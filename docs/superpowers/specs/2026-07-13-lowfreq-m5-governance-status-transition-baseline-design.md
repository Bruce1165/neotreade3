Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance status transition baseline` slice for reject-driven effective-state projection
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition Baseline Design

Date: 2026-07-13

## 1. Goal

This slice continues the current `M5 governance` closure mainline after:

- persisted governance handoff baseline
- typed handoff readback baseline
- reject execution persistence/runtime baseline
- closure counts visibility baseline

Current repository evidence shows:

- the persisted `governance_handoff` bundle is the current baseline truth for:
  - `attention_items`
  - `promotion_blockers`
  - `validation_results`
- reject execution already materializes an independent artifact and ledger keyed by `validation_id`
- current runtime still has no owner that projects the post-reject effective state of:
  - `AttentionItem.status`
  - `PromotionBlocker.active`

So the narrow problem is not:

- how to change the original handoff baseline
- how to redesign reject execution persistence
- how to add promotion approval
- how to introduce a full governance state machine

It is:

- how to derive one truthful reject-driven effective state from the already-persisted governance truth
- how to persist that derived state without mutating the baseline artifact
- how to keep downstream consumers out of ad-hoc status inference

Project-phase note:

- domain: `M5 governance`
- change type: `closure / reject-driven effective-state baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add a narrow runtime owner that materializes reject-driven status transition state
- persist one independent transition artifact keyed by `validation_id`
- persist one independent transition ledger keyed by `validation_id`
- project effective post-reject state for exactly:
  - one `AttentionItem`
  - one `PromotionBlocker`
- add focused tests for:
  - independent persistence
  - baseline immutability
  - semantic correctness
  - dry-run and error paths

Excluded:

- no mutation of `governance_handoff` artifact payloads
- no worker/orchestrator integration
- no CLI output changes
- no promotion approval path
- no generic multi-step governance workflow engine
- no automatic learning-loop writeback
- no `M6`

## 3. Boundary Decisions

User-confirmed boundary decisions for this slice are:

- persistence uses an independent namespace instead of patching the existing handoff baseline
- reject completion closes the effective `AttentionItem`
- reject completion does not deactivate the effective `PromotionBlocker`

Frozen semantic rule:

- reject means the candidate path is rejected
- reject does not mean the original governance risk is cleared

So the post-reject effective state is:

- `AttentionItem.status = "resolved"`
- `PromotionBlocker.active = true`

This slice intentionally models effective state only.

It does not claim that the original baseline object was rewritten.

## 4. Existing Evidence

### 4.1 Handoff Baseline Is The Immutable Initial Truth

Current repository evidence in:

- [handoff.py](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py)
- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py)

shows that:

- `GovernanceHandoffBundle` is materialized from persisted benchmark truth
- `AttentionItem.status` is initialized as `open`
- `PromotionBlocker` is persisted as the original blocker truth
- handoff storage is keyed by `source_run_id`

So the handoff artifact is the baseline projection owner, not the later transition owner.

### 4.2 Reject Execution Already Uses Independent Persistence

Current repository evidence in:

- [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L75-L121)
- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L237-L297)
- [test_m5_governance_reject_execution.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_reject_execution.py#L28-L95)

shows that:

- reject execution writes:
  - `var/artifacts/governance_rejections/<validation_id>/governance_reject_execution.json`
  - `var/ledgers/governance_rejections/<validation_id>/governance_reject_execution_run.json`
- reject execution does not overwrite the persisted handoff bundle

This is the already-established isolation rule for later governance actions.

### 4.3 Current Runtime Does Not Consume Or Update Status Fields

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L71-L117)

shows that current reject execution runtime:

- reads one persisted handoff bundle
- selects one `ValidationResult` by `validation_id`
- builds one reject decision record
- materializes one independent reject execution result

It does not:

- read `AttentionItem.status` as an execution input
- modify `PromotionBlocker.active`
- produce any effective-state projection

So there is no existing runtime owner for transition semantics.

### 4.4 The Existing ID Chain Is Sufficient

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py)
- [handoff.py](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py)

shows that the current object chain already supports deterministic backtracking:

- `validation_id`
- `experiment_id`
- `cr_id`
- `diagnostic_id`
- `blocker_id`
- `attention_id`

In practical terms:

- `validation_id -> experiment_id -> cr_id -> diagnostic_id -> blocker_id -> attention_id`

So this slice does not need:

- a manual mapping table
- a new join registry
- ad-hoc name matching

## 5. Approach Options

### Option A: Independent Effective-State Projection (Recommended)

- keep `governance_handoff` immutable
- keep reject execution immutable
- add a third independent transition projection keyed by `validation_id`

Pros:

- follows the already-established reject isolation pattern
- preserves historical baseline truth
- keeps effective-state logic explicit and auditable
- avoids hidden mutation side effects

Cons:

- adds one more persisted governance read-model
- requires a narrow new record shape

### Option B: Patch The Existing Handoff Artifact

- locate the persisted handoff bundle
- rewrite the matching attention and blocker objects in place

Pros:

- fewer files on disk

Cons:

- destroys the original baseline truth
- violates the already-established independent-persistence rule
- makes it unclear whether stored objects are initial state or post-action state

### Option C: Event-Only Transition Record

- record only that reject happened
- require future readers to derive status themselves every time

Pros:

- smallest payload

Cons:

- leaves effective-state inference duplicated across consumers
- does not actually close the visibility gap
- encourages private interpretation of status semantics

Decision:

- choose Option A

## 6. Design

### 6.1 Ownership Freeze

Production files:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/__init__.py`

Focused test file:

- `tests/unit/test_m5_governance_status_transition.py`

Files intentionally not modified:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `neotrade3/orchestration/*`
- `M6`

### 6.2 New Record Shape Freeze

This slice should introduce one narrow typed record for the derived transition result.

Recommended name:

- `GovernanceStatusTransitionRecord`

Recommended fields:

- `validation_id`
- `source_run_id`
- `decision_id`
- `status`
- `written_at`
- `artifact_path`
- `ledger_path`
- `baseline_run_id`
- `candidate_run_id`
- `effective_attention_id`
- `effective_attention_status`
- `effective_blocker_id`
- `effective_blocker_active`

Why this shape is sufficient:

- it anchors the record to the final validation subject
- it keeps the original source run visible
- it exposes the effective state without forcing all consumers to reopen the artifact payload
- it stays narrow and does not claim a broader workflow state machine

### 6.3 Independent Persistence Freeze

Execution key:

- `validation_id`

Artifact namespace:

- `var/artifacts/governance_status_transitions/<validation_id>/governance_status_transition.json`

Ledger namespace:

- `var/ledgers/governance_status_transitions/<validation_id>/governance_status_transition_run.json`

Why `validation_id` is the right key:

- the reject action is anchored to one final validation result
- the current reject execution namespace already uses `validation_id`
- it avoids collisions with the source-run keyed handoff baseline

### 6.4 Artifact Payload Freeze

The transition artifact should be a narrow JSON payload containing:

- `source_run_id`
- `validation_id`
- `decision_id`
- `baseline_run_id`
- `candidate_run_id`
- `trigger_artifact_path`
- `effective_attention_item`
- `effective_promotion_blocker`
- `written_at`

Design rules:

- `effective_attention_item` is a copied payload with effective `status="resolved"`
- `effective_promotion_blocker` is a copied payload with effective `active=true`
- the artifact must not claim that the original handoff objects were rewritten
- `trigger_artifact_path` points to the persisted reject execution artifact used as the transition trigger

### 6.5 Runtime Flow Freeze

Recommended runtime entrypoint:

- `run_governance_status_transition(...)`

Recommended parameters:

- `project_root`
- `source_run_id`
- `validation_id`
- `dry_run`

Runtime flow:

1. read the persisted handoff bundle by `source_run_id`
2. read the persisted reject execution ledger or artifact by `validation_id`
3. require that both inputs exist
4. locate the matching `ValidationResult` in the handoff bundle
5. backtrack:
   - `experiment_id`
   - `cr_id`
   - `diagnostic_id`
   - `blocker_id`
   - `attention_id`
6. locate exactly one matching blocker and attention item in the handoff bundle
7. build the effective attention payload with `status="resolved"`
8. build the effective blocker payload with `active=true`
9. persist the independent transition artifact and ledger

This runtime must not:

- patch the handoff artifact
- rerun reject execution
- infer transition semantics without a persisted reject execution proof
- materialize multi-object batch transitions in this slice

### 6.6 Error Rules

Error cases should fail deterministically:

- missing handoff bundle -> `ValueError`
- missing reject execution artifact or ledger -> `ValueError`
- missing validation result -> `ValueError`
- missing blocker backtracking target -> `ValueError`
- missing attention backtracking target -> `ValueError`
- ambiguous duplicate matches -> `ValueError`

Why strict failure is preferred:

- current transition semantics are narrow and evidence-driven
- silent fallback would hide broken ID-chain assumptions
- this slice should establish correctness before widening adoption

## 7. Testing Strategy

Focused tests should lock:

1. one persisted reject execution materializes one independent status transition artifact
2. one persisted reject execution materializes one independent status transition ledger
3. the original handoff artifact remains byte-for-byte unchanged after transition execution
4. the effective attention payload is persisted with `status="resolved"`
5. the effective blocker payload is persisted with `active=true`
6. dry-run writes nothing
7. missing reject execution proof fails deterministically
8. missing mapped blocker or attention object fails deterministically

Do not test in this slice:

- worker integration
- CLI output
- orchestration API
- promotion approval behavior

## 8. Verification

Minimum verification for this design slice:

- self-review the spec for placeholders, contradictions, and ambiguity
- `git diff --check`

Implementation verification is intentionally deferred to the later plan and execution slice.

## 9. Dual-Axis Audit

### 9.1 M-Axis

- `M5`: yes
  - this slice adds a governance-owned derived read-model for reject-driven effective state
- `M1-M4`: no
  - no upstream data, recognition, decision, or benchmark contract change
- `M6`: no
  - no delivery or observability integration yet

### 9.2 G-Axis

- `G5`: yes
  - improves governance auditability by making reject-driven effective state explicit and persisted
- `G1/G2/G3/G4/G6`: no direct expansion
  - no new candidate generation
  - no promotion approval automation
  - no learning-loop writeback

## 10. Non-Claims

This slice does not claim:

- a full governance lifecycle state machine already exists
- reject automatically clears the original governance concern
- downstream consumers have already switched to the transition artifact
- worker/CLI/API already expose transition results

It only defines the narrowest truthful next owner for reject-driven effective state.
