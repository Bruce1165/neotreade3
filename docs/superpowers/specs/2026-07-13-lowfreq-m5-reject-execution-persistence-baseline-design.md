Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 reject execution persistence baseline` slice using an independent execution artifact
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution Persistence Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence plus the just-confirmed boundary decision now freeze:

- `governance_handoff` artifacts remain the immutable pending/mainline baseline
- reject execution must persist to an independent execution artifact
- reject execution should consume typed governance truth, not raw dicts

Current repository evidence shows:

- typed governance handoff readback now exists
- reject decision builder nucleus now exists
- runtime still has no way to materialize a final reject execution result independently of the handoff artifact

So the narrow problem is:

- how to read one persisted governance handoff bundle
- how to select one final rejected validation result by `validation_id`
- how to materialize one independent reject execution artifact and ledger

This slice is not yet:

- promotion approval runtime
- blocker/attention status transitions
- worker/orchestrator/CLI expansion
- generic governance execution workflow

Project-phase note:

- domain: `M5 governance reject execution runtime`
- change type: `independent execution artifact/ledger baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add a narrow reject execution runtime owner
- persist reject execution into an independent artifact namespace
- persist reject execution into an independent ledger namespace
- add focused runtime/persistence tests

Excluded:

- no overwrite of `governance_handoff` artifacts
- no promotion approval runtime
- no blocker or attention status transitions
- no CLI or orchestrator changes
- no `M6`

## 3. Boundary Decision

User-confirmed execution persistence rule:

- reject execution must use an independent execution artifact instead of overwriting the existing `governance_handoff` artifact

Why this matters:

- current `governance_handoff` artifact is the pending baseline keyed by `source_run_id`
- overwriting it would erase the historical pending baseline
- reject execution is a later governance act and should therefore be stored separately

## 4. Existing Evidence

### 4.1 Handoff Persistence Is Already Keyed By `source_run_id`

Current repository evidence in:

- [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py)
- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py)

shows that:

- current governance persistence is strictly one artifact and one ledger per `source_run_id`
- the stored object is `governance_handoff_bundle`

That storage is the wrong place for final reject execution if we want to preserve the baseline truth.

### 4.2 Typed Input Truth Now Exists

Current repository evidence in:

- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L204-L214)

shows that:

- `read_governance_handoff_bundle(...)` now exists

So reject execution no longer needs private JSON parsing.

### 4.3 Canonical Reject Decision Mapping Now Exists

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L318-L335)

shows that:

- `build_reject_decision_record_from_validation_result(...)` now exists

So reject runtime can stay thin and should only:

- select the target validation result
- validate that it is rejected
- materialize the independent execution artifact

## 5. Design

### 5.1 Ownership Freeze

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

### 5.2 Input Contract Freeze

Input parameters:

- `project_root`
- `source_run_id`
- `validation_id`
- `dry_run`

Runtime flow:

1. read typed governance handoff bundle by `source_run_id`
2. find exactly one validation result whose `validation_id` matches the input
3. require `validation_result.outcome == "rejected"`
4. build the canonical reject decision record from that validation result
5. persist the execution artifact and execution ledger in an independent namespace

Error rules:

- missing handoff bundle -> `ValueError`
- missing validation result -> `ValueError`
- non-rejected validation result -> `ValueError`

### 5.3 Independent Persistence Freeze

Execution key:

- `validation_id`

Artifact namespace:

- `var/artifacts/governance_rejections/<validation_id>/governance_reject_execution.json`

Ledger namespace:

- `var/ledgers/governance_rejections/<validation_id>/governance_reject_execution_run.json`

Why `validation_id` is the right key:

- the reject decision is anchored to a final validation result
- it avoids colliding with the existing `source_run_id`-keyed handoff artifact
- it keeps execution storage aligned to the actual subject of the decision

### 5.4 Execution Artifact Shape Freeze

The reject execution artifact should be a narrow JSON payload containing:

- `source_run_id`
- `validation_id`
- `baseline_run_id`
- `candidate_run_id`
- `decision_record`
- `validation_result`
- `written_at`

Why include both `validation_result` and `decision_record`:

- `validation_result` is the final proof object
- `decision_record` is the final governance action
- both are needed for future readback/audit without reopening the original handoff bundle

### 5.5 Execution Ledger Shape Freeze

Add one independent ledger record:

- `validation_id`
- `source_run_id`
- `status`
- `written_at`
- `artifact_path`
- `ledger_path`
- `baseline_run_id`
- `candidate_run_id`
- `decision_id`
- `decision`

This is enough for:

- stable readback
- audit visibility
- later CLI/orchestrator adoption

without widening into a broader workflow engine.

## 6. Testing Strategy

Focused tests should lock:

1. rejected validation result materializes one independent reject execution artifact
2. original governance handoff artifact remains unchanged
3. ledger and artifact paths use the new independent namespace
4. missing validation id fails deterministically
5. non-rejected validation result fails deterministically
6. dry-run writes nothing

Do not test:

- CLI output
- worker/orchestrator behavior
- promotion approval

## 7. Acceptance Criteria

- reject runtime owner exists
- independent reject execution artifact is written by `validation_id`
- independent reject execution ledger is written by `validation_id`
- original `governance_handoff` artifact remains unchanged
- focused tests pass
- no CLI/orchestrator/`M6` files change

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` runtime execution and persistence
- `G1-G6` target mapping:
  - this is the minimum `G2` reject runtime adoption step after typed readback and reject decision nucleus landed
- new runtime contract introduced:
  - independent reject execution artifact keyed by `validation_id`
  - independent reject execution ledger keyed by `validation_id`
- boundaries not touched:
  - no handoff overwrite
  - no promotion approval
  - no CLI/orchestrator adoption
  - no `M6`
