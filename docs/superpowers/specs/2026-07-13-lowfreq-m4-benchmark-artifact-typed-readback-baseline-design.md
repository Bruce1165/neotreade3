Status: active
Owner: lowfreq / benchmark
Scope: Narrow `M4 benchmark artifact typed readback baseline` slice after the benchmark mainline runner path and before governance switches upstream truth
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M4 Benchmark Artifact Typed Readback Baseline Design

Date: 2026-07-13

## 1. Goal

This slice advances `M4` one narrow step after the already-landed benchmark mainline runner path and the later `M5 governance orchestrator-fit` baseline.

Current repository evidence shows:

- `M4` already has canonical persisted storage for benchmark batch runs:
  - `neotrade3/benchmark/artifact_writer.py` writes `benchmark_batch_result.json`
  - `neotrade3/benchmark/run_ledger.py` writes and reads `BenchmarkRunLedgerRecord`
- the persisted benchmark artifact already contains the full serialized batch payload:
  - `write_benchmark_batch_run_artifact(...)` writes `batch_result.to_payload()` plus `written_at` and `sample_count`
- the current benchmark artifact readback remains untyped:
  - `read_benchmark_run_artifact(...)` returns `dict[str, Any] | None`
- the runtime object consumed by governance is still typed:
  - `build_governance_handoff_from_batch_run(...)` accepts `BenchmarkBatchRunResult`
- current `BenchmarkBatchRunResult` and nested `M4` contracts expose `to_payload()` only:
  - `BenchmarkBatchRunResult`
  - `BenchmarkAssessmentResult`
  - `AssessmentSummary`
  - `GapRecord`
  - `TraceBundle`
  - `InteractionGuardrailBreach`
- no current production helper reconstructs those typed objects from the persisted artifact payload

So the narrow problem is no longer:

- how to run a benchmark manifest
- how to persist artifact and ledger files
- how to list or read benchmark run ledger metadata

It is:

- how to reconstruct one truthful typed `BenchmarkBatchRunResult` from the already-persisted `M4` artifact
- how to do that without widening into governance runtime rewiring, orchestrator changes, or `M6` delivery

Project-phase note:

- domain: `M4 benchmark artifact typed readback`
- change type: `mainline persistence baseline -> typed reconstruction baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M4 / G5`, enabling the next truthful `M4 -> M5` handoff step

## 2. Scope

Included:

- add typed reconstruction for the persisted `M4` benchmark artifact payload
- add object-level `from_dict(...)` readback builders for the `M4` batch-result tree
- add one benchmark-level typed readback helper in the benchmark persistence surface
- keep the persisted artifact JSON shape unchanged
- add focused tests that lock round-trip reconstruction from live batch result to persisted artifact back to typed object

Excluded:

- no change to benchmark artifact file paths or file names
- no change to ledger file paths or file names
- no change to `write_benchmark_batch_run_artifact(...)`
- no change to benchmark scoring or fixture construction
- no change to governance runtime, CLI, worker, or orchestrator
- no direct change to `build_governance_handoff_from_batch_run(...)`
- no `M6` API, report, or UI work
- no generic repository-wide serialization framework

## 3. Existing Evidence

### 3.1 Persisted Artifact Already Contains The Full Batch Payload

Current repository evidence in `neotrade3/benchmark/artifact_writer.py` shows the benchmark artifact payload is built as:

- `batch_result.to_payload()`
- plus `written_at`
- plus `sample_count`

That means the missing capability is not missing data persistence.

The missing capability is typed reconstruction from already-persisted JSON.

This is the first hard boundary of the slice:

- do not redesign persistence
- do not invent another artifact format

### 3.2 Ledger Readback Exists, But It Stops At Metadata

Current repository evidence in `neotrade3/benchmark/run_ledger.py` shows:

- `BenchmarkRunLedgerRecord.from_dict(...)` exists
- `read_benchmark_run_ledger(...)` returns a typed ledger record
- `read_benchmark_run_artifact(...)` returns only a raw JSON dict

So the current benchmark readback surface is split:

- metadata is typed
- artifact content is not typed

This confirms the next narrow missing owner is artifact typed readback, not another ledger enhancement.

### 3.3 Governance Still Needs A Typed `BenchmarkBatchRunResult`

Current repository evidence in `neotrade3/governance/handoff.py` shows:

- `build_governance_handoff_from_batch_run(...)` accepts `BenchmarkBatchRunResult`
- it iterates over `batch_result.results`
- it reads `batch_result.run_id`

That means current `M5` consumption truth is still typed-object based.

So if governance is later switched from rerunning manifests to consuming persisted `M4` outputs, the missing bridge is exactly:

- persisted artifact
- to typed `BenchmarkBatchRunResult`

Not:

- a governance-specific dict parser
- a projection built directly from arbitrary JSON

### 3.4 The Current Contract Tree Is Write-Only

Current repository evidence in `neotrade3/benchmark/contracts.py` and `neotrade3/benchmark/batch_runner.py` shows:

- the batch result tree has `to_payload()` everywhere
- only a few unrelated registry/ledger models use `from_dict(...)`
- no `M4` result object currently has symmetric readback construction

So the real contract gap is asymmetry:

- write path exists
- read path does not

This is the second hard boundary of the slice:

- add only the minimum read symmetry needed for the batch-result tree
- do not widen into unrelated domain models

## 4. Approach Options

### Option A: Add One Governance-Specific Dict Adapter

- keep `M4` artifact readback raw
- add logic in governance to consume raw benchmark artifact dicts directly

Pros:

- smallest short-term change set for governance

Cons:

- duplicates serialization knowledge inside `M5`
- leaves `M4` persistence surface incomplete
- creates a one-off consumer path instead of a reusable typed owner
- makes future non-governance consumers repeat the same parsing

### Option B: Add Symmetric Typed Reconstruction In `M4` (Recommended)

- add `from_dict(...)` on the persisted `M4` batch-result object tree
- add one benchmark-level typed artifact readback helper
- keep governance unchanged in this slice

Pros:

- repairs the write/read symmetry where the data actually belongs
- creates one reusable upstream truth for any later `M4` consumer
- keeps `M5` free of `M4` serialization details
- preserves current persistence shape while enabling future upstream switching

Cons:

- touches several benchmark contract owners
- requires careful focused tests for nested object reconstruction

### Option C: Reconstruct Only The Minimal Governance Subset

- add a partial typed object or a special-purpose `M4ForGovernance` shape
- reconstruct only fields currently read by governance

Pros:

- less code than full object-tree symmetry

Cons:

- introduces a second near-duplicate truth beside `BenchmarkBatchRunResult`
- bakes current governance needs into `M4` storage design
- becomes misleading once other consumers need full batch details

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice should modify only the minimum `M4` owners required for typed readback:

- `neotrade3/benchmark/contracts.py`
  - add object-level `from_dict(...)` support for the persisted assessment tree
- `neotrade3/benchmark/batch_runner.py`
  - add `BenchmarkBatchRunResult.from_dict(...)`
- `neotrade3/benchmark/run_ledger.py`
  - add one typed artifact readback helper
- `neotrade3/benchmark/__init__.py`
  - export the new typed helper if it becomes part of the public benchmark package surface

Recommended new readback helper:

- `read_benchmark_batch_run_result(...)`

Recommended behavior:

1. locate the canonical artifact file by `run_id`
2. load the JSON payload
3. reconstruct `BenchmarkBatchRunResult` from the artifact payload
4. return the typed object
5. return `None` only when the artifact file does not exist

This helper must not:

- infer missing benchmark results from ledger metadata
- rerun a benchmark manifest
- invoke governance logic
- write any files

### 5.2 Contract Symmetry Freeze

The reconstruction baseline should be symmetric with the existing persisted shape, not with a new simplified shape.

Recommended object tree to reconstruct:

- `BenchmarkBatchRunResult`
- `BenchmarkAssessmentResult`
- `AssessmentSummary`
- `GapRecord`
- `TraceBundle`
- `InteractionGuardrailBreach`

Readback rule:

- `from_dict(...)` should accept the serialized payload shape already produced by each object's current `to_payload()`

Validation rule:

- root payload must be a JSON object
- missing required object payloads should surface a direct validation error
- optional fields should preserve the same defaults already implied by the dataclass definitions

Why full symmetry is preferred over a minimal subset:

- the artifact already stores the full object tree
- partial reconstruction would create an unnecessary second contract
- future consumers should not need to guess which fields are truly available

### 5.3 Artifact-Level Readback Contract

Current raw helper:

- `read_benchmark_run_artifact(...) -> dict[str, Any] | None`

Recommended new helper:

- `read_benchmark_batch_run_result(...) -> BenchmarkBatchRunResult | None`

Both helpers should coexist in this baseline.

Rationale:

- the raw helper is already used by current tests and may still be useful for low-level payload assertions
- the typed helper serves the new formal readback contract

Behavior rule:

- if the artifact file is missing, return `None`
- if the artifact file exists but contains an invalid shape, surface the parsing error instead of silently degrading

This preserves the repository's existing pattern:

- missing storage is a nullable read
- malformed stored content is a real failure

### 5.4 Extra Artifact Fields Must Stay Ignored By Reconstruction

The persisted artifact payload contains batch payload fields plus:

- `written_at`
- `sample_count`

Those fields are artifact-envelope metadata, not members of `BenchmarkBatchRunResult`.

So `BenchmarkBatchRunResult.from_dict(...)` should reconstruct only the batch-result contract:

- `run_id`
- `registry_path`
- `executed_sample_ids`
- `grade_summary`
- `bucket_summary`
- `results`

And it should ignore extra artifact-envelope keys that do not belong to the typed batch-result contract.

Reason:

- `BenchmarkBatchRunResult` should remain the runtime object that `run_benchmark_manifest(...)` returns
- adding persistence-only envelope metadata into it would blur runtime versus storage concerns

### 5.5 Builder Style And Validation Discipline

For consistency with nearby models, the new readback path should follow the repository's current contract style:

- use `@classmethod from_dict(...)`
- accept `Any` at the boundary
- fail fast when the root is not a JSON object

Recommended reconstruction style:

- object-level `from_dict(...)` should rebuild nested children by calling their own `from_dict(...)`
- use existing field names directly from persisted payloads
- coerce collections into tuples where runtime objects use tuples
- keep dict-backed summary fields as plain dicts with stable `str -> int` coercion where applicable

This slice should not introduce:

- generic schema validators
- version-migration registries
- multi-version artifact adapters beyond the current `object_version = 1` world

### 5.6 Public Surface Freeze

If the new typed helper is added, the benchmark package surface should export it alongside the existing raw helper.

Recommended package additions:

- export `read_benchmark_batch_run_result`

This keeps the benchmark persistence API explicit:

- raw artifact access remains available
- typed artifact access becomes first-class

### 5.7 File Boundary

Likely production files in scope:

- `neotrade3/benchmark/contracts.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/run_ledger.py`
- `neotrade3/benchmark/__init__.py`

Recommended focused test files:

- one new focused test file such as `tests/unit/test_m4_benchmark_typed_readback.py`

Files intentionally reused but not modified unless implementation evidence proves it necessary:

- `neotrade3/benchmark/artifact_writer.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/runtime.py`

Files explicitly not in scope:

- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `neotrade3/governance/cli.py`
- `neotrade3/governance/run_ledger.py`
- `docs/superpowers/specs/*m6*`

## 6. Testing Strategy

Add one focused test carrier for typed readback.

Tests should lock at least:

1. round-trip reconstruction
   - run a real benchmark manifest
   - materialize the artifact
   - typed readback reconstructs `BenchmarkBatchRunResult`
   - core summary fields match the original runtime object
2. nested object reconstruction
   - assessment summary fields survive
   - gap records survive
   - trace bundle survives when present
   - interaction guardrail breaches survive
3. extra envelope field tolerance
   - persisted artifact can include `written_at` and `sample_count`
   - typed readback still reconstructs the runtime object correctly
4. missing artifact behavior
   - typed helper returns `None` when the artifact file does not exist
5. public surface
   - the benchmark package exports the typed helper if this slice adds it

Testing rule:

- do not retest benchmark grading semantics
- do not retest governance projection semantics
- test only the new readback contract:
  - object reconstruction
  - typed helper behavior
  - persistence-envelope tolerance

Validation rule:

- keep minimum syntax validation with `py_compile`
- if `pytest` remains unavailable, use targeted inline assertions exactly against the new typed readback contract

## 7. Risks And Guardrails

Risk 1:

- widening into governance runtime rewiring because typed readback unblocks a later `M5` change

Guardrail:

- stop at `M4` typed readback helper and contract symmetry
- do not switch governance callers in this slice

Risk 2:

- leaking artifact-envelope metadata into `BenchmarkBatchRunResult`

Guardrail:

- keep runtime object fields unchanged
- ignore `written_at` and `sample_count` during typed reconstruction

Risk 3:

- adding a partial reconstruction that works only for today's governance usage

Guardrail:

- reconstruct the full persisted batch-result object tree
- keep the owner in `M4`, not in governance

Risk 4:

- turning readback into a silent best-effort parser

Guardrail:

- return `None` only for missing files
- surface malformed payload errors directly

Risk 5:

- widening into a generic serialization framework

Guardrail:

- add only direct `from_dict(...)` methods on the existing benchmark result tree
- follow the same minimal pattern already used by nearby registry and ledger models

## 8. Success Criteria

This slice is complete when:

- the persisted `M4` benchmark artifact can be reconstructed into a typed `BenchmarkBatchRunResult`
- nested benchmark assessment objects are reconstructed truthfully from persisted payloads
- raw artifact readback remains available
- the typed readback helper is part of the formal benchmark readback surface
- focused verification passes without widening into governance, orchestrator, or `M6`

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M4`
- future consumer enabled by this slice: `M5 governance`
- no ownership shift into `M5` or `M6`

Goal mapping:

- `G5`: strengthen the formal benchmark runtime/storage loop so persisted `M4` outputs become truthful typed upstream inputs
- not yet `G6`: no delivery, API, scheduler, or UI contract is added here

New contract introduced by this slice:

- persisted `M4` benchmark artifacts gain one formal typed readback path
- the benchmark result tree becomes serialization-symmetric at the object boundary

Not claimed in this slice:

- no claim that governance already consumes persisted `M4` artifacts
- no claim that benchmark artifacts support version migration beyond the current version
- no claim that benchmark ledger metadata alone can reconstruct full batch results
