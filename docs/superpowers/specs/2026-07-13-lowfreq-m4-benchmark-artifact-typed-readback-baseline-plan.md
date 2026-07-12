Status: active
Owner: lowfreq / benchmark
Scope: Implementation plan for the narrow `M4 benchmark artifact typed readback baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M4 Benchmark Artifact Typed Readback Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m4-benchmark-artifact-typed-readback-baseline-design.md`

## 1. Goal

This plan implements only the next narrow `M4` slice after the benchmark mainline runner path and before any future `M5` upstream-switch work:

- add symmetric typed reconstruction for persisted `M4` benchmark batch artifacts
- expose one formal typed artifact readback helper beside the existing raw helper
- keep the persisted artifact JSON shape unchanged
- lock the new readback surface with one focused round-trip test carrier

This slice explicitly does not include:

- rewiring `M5 governance` to consume persisted `M4` artifacts
- changing benchmark artifact or ledger paths
- changing benchmark scoring, fixtures, or manifest execution
- adding a generic serialization framework
- changing worker, orchestrator, CLI, or `M6` delivery surfaces

## 2. Starting Point

Repository evidence before this slice:

- `neotrade3/benchmark/artifact_writer.py` already persists `batch_result.to_payload()` plus `written_at` and `sample_count`
- `neotrade3/benchmark/run_ledger.py` already exposes:
  - `read_benchmark_run_ledger(...)` as typed metadata readback
  - `read_benchmark_run_artifact(...)` as raw artifact readback
- `BenchmarkBatchRunResult` in `neotrade3/benchmark/batch_runner.py` has `to_payload()` only
- nested result contracts in `neotrade3/benchmark/contracts.py` also have `to_payload()` only
- `neotrade3/governance/handoff.py` still consumes typed `BenchmarkBatchRunResult`
- current tests verify materialization and raw artifact presence, but no test reconstructs the persisted artifact back into a typed batch result

So the correct narrow move is:

- add `from_dict(...)` symmetry to the persisted batch-result object tree
- add one typed helper in the benchmark readback surface
- verify round-trip reconstruction without changing any runtime caller yet

## 3. File Boundary

Production files:

- `neotrade3/benchmark/contracts.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/run_ledger.py`
- `neotrade3/benchmark/__init__.py`

Primary test file:

- `tests/unit/test_m4_benchmark_typed_readback.py`

Documentation files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m4-benchmark-artifact-typed-readback-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m4-benchmark-artifact-typed-readback-baseline-plan.md`

Files intentionally reused but not modified unless implementation evidence proves it necessary:

- `neotrade3/benchmark/artifact_writer.py`
- `tests/unit/test_m4_benchmark_run_ledger.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/runtime.py`

Files explicitly not in scope:

- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `neotrade3/governance/cli.py`
- `neotrade3/governance/run_ledger.py`
- `docs/superpowers/specs/*m6*`

Plan note:

- keep the existing raw helper `read_benchmark_run_artifact(...)` intact
- do not add persistence-envelope fields into `BenchmarkBatchRunResult`

## 4. Execution Steps

### M4READ-S1: Add object-level `from_dict(...)` symmetry for the persisted assessment tree

Modify:

- `neotrade3/benchmark/contracts.py`

Add typed reconstruction for:

- `AssessmentSummary`
- `GapRecord`
- `TraceBundle`
- `InteractionGuardrailBreach`
- `BenchmarkAssessmentResult`

Implementation rules:

- use `@classmethod from_dict(...)`
- accept `Any` at the boundary
- fail fast if the root payload is not a JSON object where a JSON object is required
- preserve current runtime dataclass field defaults for omitted optional fields
- reconstruct nested children through their own `from_dict(...)` methods

Completion check:

- the persisted `results[*]` payload tree can be reconstructed without introducing any new storage format

### M4READ-S2: Add `BenchmarkBatchRunResult.from_dict(...)`

Modify:

- `neotrade3/benchmark/batch_runner.py`

Implement:

- `BenchmarkBatchRunResult.from_dict(...)`

Reconstruction rules:

- rebuild:
  - `run_id`
  - `registry_path`
  - `executed_sample_ids`
  - `grade_summary`
  - `bucket_summary`
  - `results`
- coerce runtime tuple fields back to tuples
- rebuild nested `results` entries through `BenchmarkAssessmentResult.from_dict(...)`
- ignore extra artifact-envelope keys such as:
  - `written_at`
  - `sample_count`

Implementation rule:

- keep `BenchmarkBatchRunResult` as the runtime contract returned by `run_benchmark_manifest(...)`
- do not add storage-only metadata fields into the dataclass

Completion check:

- a persisted artifact root payload can be passed into `BenchmarkBatchRunResult.from_dict(...)` and reconstruct a valid runtime object

### M4READ-S3: Add a typed artifact readback helper

Modify:

- `neotrade3/benchmark/run_ledger.py`

Implement one new helper:

- `read_benchmark_batch_run_result(...)`

Recommended behavior:

1. resolve the canonical artifact file from `run_id`
2. return `None` if the file does not exist
3. load the artifact JSON payload
4. require the root payload to be a JSON object
5. return `BenchmarkBatchRunResult.from_dict(payload)`

Implementation rules:

- keep `read_benchmark_run_artifact(...)` unchanged
- do not reconstruct from ledger metadata alone
- surface malformed payload errors directly

Completion check:

- the benchmark persistence surface exposes both raw and typed artifact readback

### M4READ-S4: Export the typed helper

Modify:

- `neotrade3/benchmark/__init__.py`

Export:

- `read_benchmark_batch_run_result`

Implementation rule:

- keep existing exports stable
- add only the new typed helper needed for the formal public surface

Completion check:

- package-level imports can consume the typed helper directly

### M4READ-S5: Add focused typed-readback tests

Create:

- `tests/unit/test_m4_benchmark_typed_readback.py`

Test carrier pattern:

- run a real benchmark manifest through existing owners
- materialize under a temp project root
- read back through the new typed helper
- compare the reconstructed object to the original runtime object at the contract level

Test cases:

1. round-trip typed reconstruction
   - run the real default manifest
   - materialize the canonical artifact
   - read back via `read_benchmark_batch_run_result(...)`
   - assert key runtime fields align with the original `BenchmarkBatchRunResult`
2. nested reconstruction
   - assert first reconstructed assessment contains:
     - summary
     - gap records
     - optional trace bundle behavior
     - interaction guardrail breaches
3. envelope tolerance
   - assert persisted `written_at` and `sample_count` do not pollute the typed runtime object
4. missing artifact behavior
   - assert the typed helper returns `None` when the artifact file does not exist
5. package export
   - assert the benchmark package exposes `read_benchmark_batch_run_result`

Testing rule:

- do not re-test benchmark grading logic
- do not re-test governance projection logic
- test only the new readback contract:
  - object symmetry
  - typed helper behavior
  - envelope-key tolerance

Completion check:

- the typed readback surface is locked independently of governance, worker, and orchestrator work

### M4READ-S6: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/benchmark/contracts.py neotrade3/benchmark/batch_runner.py neotrade3/benchmark/run_ledger.py neotrade3/benchmark/__init__.py tests/unit/test_m4_benchmark_typed_readback.py`
- `.venv/bin/python -m pytest tests/unit/test_m4_benchmark_typed_readback.py tests/unit/test_m4_benchmark_run_ledger.py tests/unit/test_m4_benchmark_batch_runner.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - `BenchmarkBatchRunResult.from_dict(...)` with a persisted artifact payload
  - nested object reconstruction
  - `read_benchmark_batch_run_result(...)` missing-file behavior
  - package export availability

Completion check:

- syntax passes
- best-available focused verification passes

### M4READ-S7: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-13-lowfreq-m4-benchmark-artifact-typed-readback-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m4-benchmark-artifact-typed-readback-baseline-plan.md`
- `neotrade3/benchmark/contracts.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/run_ledger.py`
- `neotrade3/benchmark/__init__.py`
- `tests/unit/test_m4_benchmark_typed_readback.py`

Must exclude:

- `neotrade3/benchmark/artifact_writer.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/runtime.py`
- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`
- unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- widening into `M5` runtime rewiring because typed readback now exists

Guard:

- stop at the `M4` readback surface
- keep all governance callers untouched in this slice

Risk 2:

- letting storage-envelope metadata leak into the runtime dataclass

Guard:

- ignore `written_at` and `sample_count` in `BenchmarkBatchRunResult.from_dict(...)`
- keep runtime contract fields unchanged

Risk 3:

- adding only a governance-shaped partial reconstruction

Guard:

- reconstruct the full persisted result tree
- keep the owner in `M4`, not `M5`

Risk 4:

- breaking existing raw artifact consumers by replacing the old helper

Guard:

- preserve `read_benchmark_run_artifact(...)`
- add the new typed helper beside it

Risk 5:

- hiding malformed stored payloads behind nullable reads

Guard:

- return `None` only for missing files
- let malformed payloads fail directly during reconstruction

## 6. Success Criteria

This slice is complete when:

- persisted `M4` benchmark artifacts reconstruct into typed `BenchmarkBatchRunResult` objects
- nested assessment contracts reconstruct truthfully from the stored payload tree
- the benchmark package exports a formal typed artifact readback helper
- the raw helper remains intact
- focused verification passes
- syntax verification passes
