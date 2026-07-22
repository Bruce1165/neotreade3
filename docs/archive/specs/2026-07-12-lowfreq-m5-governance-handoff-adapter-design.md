Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance handoff adapter` slice for the six-layer back-half landing
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Handoff Adapter Design

Date: 2026-07-12

## 1. Goal

This slice advances `M5` one step beyond the already-landed contract nucleus, but keeps the boundary strictly inside pure in-memory projection.

Current repository evidence shows:

- `M4` already has a formal runnable path:
  - manifest/batch execution in [batch_runner.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py)
  - artifact + ledger materialization in [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/artifact_writer.py) and [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/run_ledger.py)
  - CLI entrypoint in [cli.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/cli.py)
- `M5` now has formal governance objects and a real `B4` diagnosis path:
  - contract objects in [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py)
  - `B4 -> DiagnosticChain / ChangeRequest / ExperimentRequest / PromotionBlocker` builders in [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py)
- there is still no production owner that turns `M4` benchmark outputs into a stable `M5` handoff surface

So the narrow problem is no longer:

- whether `M5` objects exist
- whether `M4` can run

It is:

- how to convert existing `M4` formal results into a formal `M5` governance bundle
- how to do that without widening into persistence, CLI, orchestrator, or `M6`

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `formal contract nucleus -> formal handoff adapter`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add one bounded owner for `M4 -> M5` pure projection
- accept existing `M4` formal inputs:
  - `BenchmarkAssessmentResult`
  - optionally `BenchmarkBatchRunResult`
- project only the already-proven `B4 local-global guardrail` path into:
  - `DiagnosticChain`
  - `ChangeRequest`
  - `ExperimentRequest`
  - `PromotionBlocker`
- add one stable handoff payload object or equivalent bundle owner that consumers can read without re-running builder logic
- add focused tests for:
  - single assessment projection
  - batch aggregation
  - zero-projection behavior when no matching `B4` breach exists

Excluded:

- no governance artifact writing
- no governance ledger or readback index
- no governance CLI
- no worker/orchestrator registration
- no API routes
- no `M6` delivery/UI projection
- no multi-path governance projection beyond the existing `B4` path
- no mutation of `M2/M3/M4` business logic

## 3. Existing Evidence

### 3.1 M4 Already Emits The Exact Inputs Needed

Current formal upstream objects already exist:

- `BenchmarkAssessmentResult` in [contracts.py:L243-L259](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L243-L259)
- `BenchmarkBatchRunResult` in [batch_runner.py:L58-L75](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py#L58-L75)

Those objects already carry:

- `gap_records`
- `trace_bundle`
- `interaction_guardrail_breaches`
- `benchmark_run_id`

This means the `M5` handoff slice does not need to invent new upstream extraction logic.

### 3.2 M5 Nucleus Already Freezes The First Real Governance Path

The previous slice already established:

- formal governance object family in [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py)
- the real `B4` diagnosis builder in [assembler.py:L238-L291](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L238-L291)
- diagnosis-derived governance action builders in [assembler.py:L294-L359](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L294-L359)

So the missing layer is not more builder semantics. The missing layer is a stable projection owner that packages those semantics for later consumption.

### 3.3 M6 Is Not The Next Safe Step

`M6` design expects formal `M1-M5` objects to be available as consumable delivery inputs. But current repository evidence shows:

- `M5` has no persistence
- no governance artifact/ledger exists
- no API or dashboard code consumes governance objects yet

So jumping directly to `M6` would force a delivery consumer before `M5` has even formed its first canonical handoff surface.

## 4. Approach Options

### Option A: Add A Pure `M4 -> M5` Handoff Adapter (Recommended)

- add one projection owner under `neotrade3/governance/`
- project assessment or batch results into one stable governance bundle
- keep everything pure and in-memory

Pros:

- smallest safe next step after the nucleus
- directly reuses the already-tested `B4` path
- creates a formal consumer surface for later persistence or `M6`
- avoids widening runtime semantics too early

Cons:

- still not runnable as a standalone governance pipeline

### Option B: Add Governance Materialization Now

Pros:

- closer to eventual `M6` consumption

Cons:

- immediately widens into artifact layout, ledger shape, and readback policy
- mixes handoff semantics with storage semantics in the first consumer slice

### Option C: Register Governance Into CLI/Orchestrator Now

Pros:

- closer to eventual automation

Cons:

- widens into runtime ownership before the handoff object shape is frozen
- entangles `M5` with incomplete scheduling and operational semantics

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice introduces one new bounded owner dedicated to projection only.

Recommended file shape:

- `neotrade3/governance/handoff.py`

Recommended responsibilities:

- accept one `BenchmarkAssessmentResult` and project it into a governance bundle
- accept one `BenchmarkBatchRunResult` and aggregate per-assessment projections into a batch-level governance bundle
- expose a stable `to_payload()` surface

This owner must not:

- read files
- write files
- call CLI
- know about orchestrator or worker execution

### 5.2 Handoff Contract Freeze

This slice should freeze one canonical handoff object, for example:

- `GovernanceHandoffBundle`

Minimum fields:

- `source_run_id`
- `source_layer`
- `diagnostics`
- `change_requests`
- `experiment_requests`
- `promotion_blockers`

Optional but still safe summary fields:

- `projected_assessment_count`
- `projected_issue_count`

Design rule:

- the bundle is a read model for downstream consumers
- it must only hold already-constructed `M5` formal objects or their stable payload equivalents
- it must not duplicate raw `M4` objects inside the bundle

### 5.3 Single-Assessment Projection

Recommended entrypoint:

- `build_governance_handoff_from_assessment(...)`

Input:

- `BenchmarkAssessmentResult`

Behavior:

1. require a non-null `trace_bundle`
2. inspect `interaction_guardrail_breaches`
3. select only the already-supported `C_GUARD_LOCAL_GLOBAL_END` path
4. build:
   - `DiagnosticChain`
   - `ChangeRequest`
   - `ExperimentRequest`
   - `PromotionBlocker`
5. return a stable handoff bundle

Zero-projection rule:

- if the assessment has no matching `B4 local-global` breach, return an empty bundle rather than raising

Reason:

- this owner is a projector, not a validator
- no-match is a valid business outcome for batch aggregation

### 5.4 Batch-Level Projection

Recommended entrypoint:

- `build_governance_handoff_from_batch_run(...)`

Input:

- `BenchmarkBatchRunResult`

Behavior:

1. iterate `results`
2. project each result through the single-assessment entrypoint
3. merge projected governance objects into one batch-level bundle
4. preserve `run_id` as the canonical `source_run_id`

Merge rule:

- this slice may concatenate stable objects in assessment order
- it does not need deduplication policy beyond deterministic ordering

Reason:

- current first path is single-breach-oriented and deterministic
- introducing deduplication policy now would be speculative

### 5.5 Supported Path Boundary

This slice supports only the already-proven path:

- sample bucket: `B4_interaction_guardrail`
- guardrail code: `C_GUARD_LOCAL_GLOBAL_END`
- gap label anchor: `L8 Local-Global-Misread`

It must not project:

- other benchmark buckets
- other gap groups
- other governance action types

Reason:

- repository evidence currently proves only this path end-to-end
- extending beyond it would be guesswork

### 5.6 Export Boundary

Expose the new handoff owner via:

- `neotrade3/governance/__init__.py`

Recommended exports:

- handoff bundle type
- assessment-level projection entrypoint
- batch-level projection entrypoint

No side effects at import time.

## 6. Testing Strategy

Add one focused unit test file:

- `tests/unit/test_m5_governance_handoff_adapter.py`

Tests should lock:

1. assessment-level `B4` failure projects into exactly one:
   - `DiagnosticChain`
   - `ChangeRequest`
   - `ExperimentRequest`
   - `PromotionBlocker`
2. assessment without matching `B4` breach yields zero-projection bundle
3. batch-level projection preserves deterministic ordering and summary counts
4. payload copies are defensive and do not leak internal mutable state

Test fixtures should reuse real `M4` assessment builders where practical, not fake dictionaries.

## 7. Risks And Guardrails

Risk 1:

- widening into storage because "handoff" sounds like artifact generation

Guardrail:

- forbid file IO in this slice
- keep all outputs in-memory only

Risk 2:

- overclaiming that `M5` runtime now exists

Guardrail:

- claim only that `M5` now has a formal consumer surface for `M4`
- do not claim persistence, governance queue, approval flow, or scheduling

Risk 3:

- making the handoff bundle a mirror of raw `M4` payloads

Guardrail:

- project only canonical `M5` objects
- keep raw benchmark evidence at the source layer

Risk 4:

- introducing unsupported governance paths under the name of “generic batch projection”

Guardrail:

- hard-freeze support to the existing `B4` local-global guardrail path only

## 8. Success Criteria

This slice is complete when:

- one formal `M4 -> M5` handoff owner exists in production code
- a real `BenchmarkAssessmentResult` can be projected into a stable governance bundle
- a real `BenchmarkBatchRunResult` can be projected into a stable aggregated governance bundle
- non-matching assessments yield zero projection without runtime failure
- focused tests lock the handoff contract

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M5`
- upstream dependency consumed but not modified: `M4`

Goal mapping:

- `G5`: convert formal benchmark deviation evidence into a formal governance handoff surface
- not yet `G6`: no delivery, UI, API, or persistence claim is made here

Not claimed in this slice:

- no governance artifact writer
- no governance ledger/readback
- no governance CLI
- no orchestrator/worker integration
- no `M6` delivery surface
