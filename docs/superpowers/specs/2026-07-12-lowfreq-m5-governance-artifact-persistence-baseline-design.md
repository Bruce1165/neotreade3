Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance artifact persistence baseline` slice for the six-layer back-half landing
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Artifact Persistence Baseline Design

Date: 2026-07-12

## 1. Goal

This slice advances `M5` one step beyond the already-landed governance handoff surface, but keeps the boundary strictly inside canonical artifact materialization.

Current repository evidence shows:

- `M5` already has the minimum formal object and handoff layers:
  - formal governance objects in [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py)
  - `B4` governance builders in [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py)
  - formal `M4 -> M5` projection in [handoff.py](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py)
- `M4` already follows the next storage pattern that `M5` should mirror narrowly:
  - benchmark artifact writing in [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/artifact_writer.py)
- `M5` still has no persisted artifact surface at all:
  - no governance artifact writer exists
  - no governance artifact path exists under `var/artifacts/`
  - no persisted read model exists for later ledger, readback, or delivery consumption

So the narrow problem is no longer:

- whether `M5` can build governance objects
- whether `M4 -> M5` handoff can be projected in memory

It is:

- how to persist one canonical `GovernanceHandoffBundle` artifact
- how to do that before widening into ledger, CLI, API, orchestrator, or `M6`

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `formal handoff adapter -> artifact persistence baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add one bounded persistence owner under `neotrade3/governance/`
- accept one `GovernanceHandoffBundle` as the only input contract
- write one canonical JSON artifact to:
  - `var/artifacts/governance_handoffs/<source_run_id>/governance_handoff_bundle.json`
- return one stable write record, for example:
  - `GovernanceArtifactRecord`
- support:
  - `dry_run=True` path computation without file creation
  - real write path with deterministic JSON formatting
- add focused tests for:
  - dry-run record shape
  - real write path and payload shape
  - deterministic artifact path derivation
  - defensive handling of empty `source_run_id`

Excluded:

- no governance ledger or readback index
- no governance CLI
- no worker/orchestrator registration
- no API routes
- no `M6` delivery/UI projection
- no mutation of `GovernanceHandoffBundle`
- no re-building governance semantics from raw `M4` inputs
- no multi-artifact layout beyond the single canonical bundle artifact

## 3. Existing Evidence

### 3.1 M5 Already Has The Right Persistable Input

Current formal upstream object already exists:

- `GovernanceHandoffBundle` in [handoff.py:L34-L59](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py#L34-L59)

That object already provides:

- stable `source_run_id`
- stable `source_layer`
- stable projected governance collections
- stable `to_payload()` output

This means the persistence slice does not need to know any `M4` builder details.

### 3.2 M4 Already Freezes The Storage Baseline Pattern

Current storage precedent already exists:

- `BenchmarkArtifactRecord` in [artifact_writer.py:L17-L23](file:///Users/mac/NeoTrade3/neotrade3/benchmark/artifact_writer.py#L17-L23)
- `write_benchmark_batch_run_artifact(...)` in [artifact_writer.py:L25-L54](file:///Users/mac/NeoTrade3/neotrade3/benchmark/artifact_writer.py#L25-L54)

Important proven choices in that owner:

- project-root-relative artifact paths
- `var/artifacts/.../<run_id>/...json` layout
- `dry_run` support
- JSON formatting with `indent=2` and `sort_keys=True`
- returned write record separated from the persisted payload

So the safest `M5` next step is to mirror that pattern narrowly rather than invent a new storage convention.

### 3.3 Ledger Or Delivery Before Artifact Would Be Premature

Current repository evidence shows:

- no governance artifact exists to index
- no governance ledger exists to point at an artifact path
- no delivery consumer exists that reads governance persistence

So doing ledger, readback, CLI, or `M6` first would require storage semantics that are not frozen yet.

## 4. Approach Options

### Option A: Add Artifact-Only Persistence Baseline (Recommended)

- add one writer owner under `neotrade3/governance/`
- persist exactly one canonical handoff bundle artifact
- return a write record only

Pros:

- smallest safe next step after handoff projection
- mirrors the already-proven `M4` storage pattern
- gives later ledger/readback work a stable `artifact_path`
- keeps runtime semantics deferred

Cons:

- still does not provide listing, readback, or CLI entrypoints

### Option B: Add Artifact And Ledger Together

Pros:

- closer to a runnable governance persistence chain

Cons:

- widens immediately into index shape and lifecycle policy
- mixes artifact contract freeze with lookup policy in one slice

### Option C: Add Artifact And CLI Together

Pros:

- closer to operator visibility

Cons:

- exposes incomplete storage semantics through a runtime surface
- forces output wording and CLI behavior before persistence contract is frozen

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice introduces one new bounded owner dedicated to persistence only.

Recommended file shape:

- `neotrade3/governance/artifact_writer.py`

Recommended responsibilities:

- accept one `GovernanceHandoffBundle`
- derive the canonical artifact path from `bundle.source_run_id`
- serialize one JSON artifact deterministically
- return one stable write record for downstream callers

This owner must not:

- build governance objects
- read ledger indexes
- provide CLI output
- know about orchestrator, worker, or delivery consumers

### 5.2 Persistence Contract Freeze

This slice should freeze one canonical write record, for example:

- `GovernanceArtifactRecord`

Minimum fields:

- `source_run_id`
- `written_at`
- `artifact_path`
- `projected_assessment_count`
- `projected_issue_count`

Design rule:

- the write record is a side-effect summary, not the canonical business payload
- the canonical business payload remains `bundle.to_payload()`
- `artifact_path` should be stored relative to `project_root`, matching the existing `M4` pattern

### 5.3 Canonical File Layout

Recommended artifact location:

- `var/artifacts/governance_handoffs/<source_run_id>/governance_handoff_bundle.json`

Layout rule:

- there is exactly one artifact file in this slice
- the directory key must come from `bundle.source_run_id`
- no timestamped filename, suffix rotation, or multi-file fan-out is introduced here

Reason:

- later ledger/readback can safely point to one stable path
- introducing versions or multi-file layout now would be speculative

### 5.4 Writer Entrypoint

Recommended entrypoint:

- `write_governance_handoff_artifact(...)`

Input:

- `project_root`
- `bundle: GovernanceHandoffBundle`
- `dry_run: bool = False`

Behavior:

1. normalize `project_root` to `Path`
2. require non-empty `bundle.source_run_id`
3. compute canonical artifact directory and file path
4. compute `written_at`
5. build persisted payload from:
   - `bundle.to_payload()`
   - one extra metadata field:
     - `written_at`
6. if `dry_run` is false:
   - create parent directory
   - write the JSON file
7. return `GovernanceArtifactRecord`

Validation rule:

- empty or whitespace-only `source_run_id` must raise rather than silently falling back to an invented directory name

Reason:

- this slice freezes storage identity and must not fabricate artifact ownership keys

### 5.5 JSON Formatting Rule

Use the same formatting baseline already proven by `M4`:

- `indent=2`
- `sort_keys=True`
- newline-terminated file

Compatibility note:

- the writer may keep `ensure_ascii=False` for parity with the existing benchmark artifact writer
- no custom encoder, compression, or binary format is introduced

### 5.6 Dry-Run Rule

`dry_run=True` must:

- compute the exact same `artifact_path`
- compute the exact same record shape
- not create directories
- not create files

Reason:

- later orchestration or CLI slices need a stable preview mode before real write side effects

### 5.7 Export Boundary

This slice does not require package-root re-export yet.

Reason:

- there is no current production caller outside the immediate governance package
- adding `__init__` surface now would widen public API before the persistence line has a consumer

If implementation evidence later shows an immediate call site needs package-root import ergonomics, that decision should be taken in the plan, not assumed here.

## 6. Testing Strategy

Add one focused unit test file:

- `tests/unit/test_m5_governance_artifact_writer.py`

Tests should lock:

1. dry-run returns a stable `GovernanceArtifactRecord` without creating files
2. real write creates:
   - the canonical directory
   - the canonical file
3. persisted JSON equals:
   - `bundle.to_payload()`
   - plus `written_at`
4. returned `artifact_path` is project-root-relative
5. empty `source_run_id` raises a deterministic validation error

Fixture rule:

- build the bundle through the real `build_governance_handoff_from_assessment(...)` or `build_governance_handoff_from_batch_run(...)` path where practical
- avoid fake dict payloads as primary fixtures

## 7. Risks And Guardrails

Risk 1:

- widening into ledger semantics because storage now exists

Guardrail:

- return only one write record
- do not add index files, listing APIs, or readback helpers

Risk 2:

- mutating bundle semantics during persistence

Guardrail:

- persist `bundle.to_payload()` directly
- allow only minimal write metadata addition

Risk 3:

- inventing fallback directory names for missing run ids

Guardrail:

- reject empty `source_run_id` at write time

Risk 4:

- overclaiming that governance runtime now exists

Guardrail:

- claim only that `M5` now has a canonical persisted artifact baseline
- do not claim governance queue, approval workflow, ledger, or delivery read-model

## 8. Success Criteria

This slice is complete when:

- one formal `M5` artifact writer exists in production code
- one `GovernanceHandoffBundle` can be materialized into the canonical JSON path
- `dry_run` and real write share the same path contract
- persisted JSON shape is stable and deterministic
- focused tests lock the write record and path contract

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M5`
- upstream dependency consumed but not modified: `M5 handoff surface`
- pattern reference only, not dependency: `M4 artifact writer`

Goal mapping:

- `G5`: convert formal governance handoff into the first persisted governance artifact surface
- not yet `G6`: no delivery, UI, API, or readback claim is made here

Not claimed in this slice:

- no governance ledger/readback
- no governance CLI
- no orchestrator/worker integration
- no automated validation or promotion runtime
- no `M6` delivery surface
