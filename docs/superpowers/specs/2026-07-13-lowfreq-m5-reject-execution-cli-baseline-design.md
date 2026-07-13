Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 reject execution CLI baseline` slice after reject execution persistence baseline
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution CLI Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- reject execution runtime and independent persistence now exist
- there is still no formal CLI surface for triggering that runtime
- worker/orchestrator fit is still absent

So the narrow next problem is:

- how to expose `run_governance_reject_execution(...)` through a stable CLI entrypoint

This slice is not:

- worker adoption
- orchestrator fit
- promotion approval
- blocker or attention status transitions

Project-phase note:

- domain: `M5 governance reject execution entrypoint`
- change type: `CLI baseline`
- NeoTrade2 remains reference only
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add a CLI subcommand for reject execution
- keep existing handoff CLI behavior unchanged
- add focused CLI tests for reject execution

Excluded:

- no worker/orchestrator changes
- no CLI for promotion approval
- no runtime/persistence contract changes
- no `M6`

## 3. Existing Evidence

- current CLI only supports handoff materialization: [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py)
- reject runtime exists: [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py)
- reject persistence exists: [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py)

This means the next narrow gap is pure entrypoint adoption.

## 4. Approach

Recommended option:

- convert governance CLI to subcommands:
  - `handoff`
  - `reject`

Reasons:

- keeps current handoff path stable
- gives reject execution its own required args without overloading the old parser
- leaves room for later approval entrypoints without breaking CLI shape again

## 5. Design

### 5.1 CLI Shape

Subcommands:

- `handoff`
  - `--project-root`
  - `--benchmark-run-id`
  - `--dry-run`
- `reject`
  - `--project-root`
  - `--source-run-id`
  - `--validation-id`
  - `--dry-run`

### 5.2 Output Freeze

`handoff` output stays unchanged.

`reject` output should emit:

- `validation_id`
- `source_run_id`
- `status`
- `baseline_run_id`
- `candidate_run_id`
- `decision_id`
- `decision`
- `artifact_path`
- `ledger_path`
- `dry_run`

### 5.3 Error Behavior

- missing `source_run_id` or `validation_id` should fail at parser level
- missing handoff bundle or invalid validation selection should propagate runtime `ValueError`

## 6. Testing Strategy

Focused tests should lock:

1. parser requires a subcommand
2. `handoff` parser still works
3. `reject` parser requires `source_run_id` and `validation_id`
4. `reject` dry-run returns JSON without writes
5. `reject` materialization writes independent artifact/ledger
6. missing validation path raises

## 7. Acceptance Criteria

- CLI subcommands exist
- handoff output remains stable
- reject output is stable
- focused CLI tests pass
- no worker/orchestrator changes

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` CLI entrypoint adoption
- `G1-G6` target mapping:
  - this is the minimum `G2` formal trigger surface for the already-landed reject runtime
- new contract introduced:
  - `governance cli reject` subcommand
- boundaries not touched:
  - no worker/orchestrator fit
  - no promotion approval
  - no `M6`
