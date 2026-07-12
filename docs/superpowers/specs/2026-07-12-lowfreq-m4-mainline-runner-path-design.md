Status: active
Owner: lowfreq / benchmark
Scope: Narrow `M4 benchmark mainline runner path` slice for the six-layer back-half landing
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M4 Mainline Runner Path Design

Date: 2026-07-12

## 1. Goal

This design covers the next six-layer back-half acceleration slice after the `M2 shadow minimal contract` recovery.

The current repository evidence shows:

- `M4` already has formal internal owners for:
  - manifest loading in [batch_runner.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py)
  - artifact persistence in [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/artifact_writer.py)
  - ledger materialization and readback in [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/run_ledger.py)
- `config/benchmark/` already carries formal seed manifests and registry:
  - [validation_seed_manifest.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_manifest.json)
  - [validation_seed_v2_manifest.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_v2_manifest.json)
  - [validation_seed_samples.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_samples.json)
- the public package surface already exports the run/materialize helpers:
  - [__init__.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/__init__.py)
- those manifests are currently referenced by tests and spec docs, but not by any production caller:
  - [test_m4_benchmark_batch_runner.py](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_batch_runner.py)
  - [test_m4_benchmark_artifact_writer.py](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_artifact_writer.py)
  - [test_m4_benchmark_run_ledger.py](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_run_ledger.py)

So the narrow problem is no longer "how to execute a benchmark batch" but:

- how to expose one formal production entrypoint that can run a configured manifest
- how to materialize the result into the already-existing artifact and ledger path
- how to do that without widening into orchestrator registration or `M5/M6` consumers

This design is not:

- a rewrite of `M4` scoring rules
- a rewrite of fixture construction
- an orchestrator phase expansion
- an `M5` governance integration
- an `M6` delivery/UI implementation

Project-phase note:

- domain: `lowfreq M4 benchmark mainline runner path`
- change type: `skeleton -> minimal formal runtime entry`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M4 / G5-G6`

## 2. Scope

Included:

- add one formal CLI entrypoint under `neotrade3/benchmark/`
- let that entrypoint run:
  - manifest load
  - batch execution
  - artifact + ledger materialization
- support explicit `--manifest`, `--project-root`, and `--dry-run`
- print a stable JSON summary for human/manual invocation and later automation
- add focused tests for parser behavior and end-to-end CLI materialization

Excluded:

- changing benchmark manifests or registry shape
- adding new sample buckets
- changing `build_benchmark_fixture_bundle(...)`
- registering benchmark tasks in `config/orchestrator/daily_master_orchestrator.json`
- changing worker phase execution
- adding `M5` governance object consumption
- adding `M6` display endpoints

## 3. Existing Context

Current repository evidence:

- internal benchmark run path already exists:
  - [batch_runner.py:L78-L145](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py#L78-L145)
  - [artifact_writer.py:L17-L54](file:///Users/mac/NeoTrade3/neotrade3/benchmark/artifact_writer.py#L17-L54)
  - [run_ledger.py:L87-L181](file:///Users/mac/NeoTrade3/neotrade3/benchmark/run_ledger.py#L87-L181)
- config-backed manifests already exist and are readable:
  - [validation_seed_manifest.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_manifest.json)
  - [validation_seed_v2_manifest.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_v2_manifest.json)
- no script or package CLI currently consumes:
  - `load_benchmark_run_manifest(...)`
  - `run_benchmark_manifest(...)`
  - `materialize_benchmark_batch_run(...)`
  in production code
- a nearby proven pattern already exists for "formal owner + CLI + storage":
  - [screeners/cli.py](file:///Users/mac/NeoTrade3/neotrade3/screeners/cli.py)

So the missing piece is not another storage owner. The missing piece is a stable caller that turns `M4` from "testable library capability" into "runnable formal path."

## 4. Approach Options

### Option A: Add `neotrade3/benchmark/cli.py` as the canonical M4 runner entrypoint (Recommended)

- keep existing owners unchanged
- add one package CLI with parser + `main()`
- call existing manifest/batch/materialize helpers
- print a compact JSON result

Pros:

- smallest production diff that creates a real runnable path
- consistent with the existing `screeners.cli` pattern
- does not entangle `M4` with unfinished orchestrator execution semantics
- makes current config manifests actually executable outside tests

Cons:

- still manual/CLI-driven, not yet orchestrator-driven

### Option B: Add a top-level script under `scripts/` only

Pros:

- very direct manual usability

Cons:

- duplicates runtime-entry logic outside the package
- weaker reuse surface for tests and future automation
- less consistent with the package CLI pattern already used by screeners

### Option C: Register benchmark directly into daily orchestrator now

Pros:

- closer to eventual full automation

Cons:

- widens into orchestrator phase semantics, task registration, and executor plumbing
- current orchestrator still has large `pending_implementation` surface
- too much scope for the next atomic slice

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice introduces one new bounded owner:

1. add `neotrade3/benchmark/cli.py`
   - `build_parser()`
   - `main()`

No new benchmark storage or assessment owner is needed because those contracts already exist.

### 5.2 CLI Contract Freeze

The CLI should support:

- `--manifest`:
  - path to a benchmark run manifest JSON
  - defaults to `config/benchmark/validation_seed_manifest.json`
- `--project-root`:
  - optional repo root override
  - defaults to repository root derived from file location
- `--dry-run`:
  - execute and summarize without writing artifact/ledger files

Recommended runtime flow:

1. resolve `project_root`
2. resolve manifest path
3. load manifest
4. run batch via `run_benchmark_manifest(...)`
5. materialize via `materialize_benchmark_batch_run(...)`
6. print a JSON summary

### 5.3 Output Summary Freeze

The CLI output should be a stable JSON payload containing at least:

- `run_id`
- `status`
- `sample_count`
- `executed_sample_ids`
- `grade_summary`
- `bucket_summary`
- `artifact_path`
- `ledger_path`
- `dry_run`

Status semantics:

- successful run returns `status = "completed"`
- `dry_run` still returns the in-memory materialization payload, but no files are written

Why keep it this small:

- current need is a runnable formal path
- not a verbose reporting layer
- not a governance handoff layer

### 5.4 Error Handling

This CLI should not hide errors behind custom wrappers.

Rules:

- invalid manifest path should raise the underlying file/read error
- invalid manifest payload should raise the existing validation error
- execution/materialization errors should surface directly

Rationale:

- this is still a bootstrap-stage formal entrypoint
- direct failure is better than inventing an unproven error taxonomy

### 5.5 Export Boundary

This slice does not need to expand `neotrade3/benchmark/__init__.py`.

Reason:

- tests can import `neotrade3.benchmark.cli` directly
- the main value is executable entrypoint behavior, not another package-root symbol

### 5.6 Why Not Orchestrator Yet

Current orchestrator evidence shows:

- task configs live in [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json)
- execution plumbing is phase-driven and still partial in [daily_master_orchestrator.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/daily_master_orchestrator.py)
- no current task or executor path is reserved for `M4 benchmark`

So forcing benchmark into orchestrator now would mix two unfinished themes:

- `M4` mainline exposure
- orchestrator execution completion

That would violate the narrow-slice rule. The CLI entrypoint is therefore the correct minimal bridge from internal owner set to actual production caller.

## 6. Risks and Guardrails

Risk 1:

- widening into a new script plus package CLI duplicate path

Guardrail:

- choose one canonical package CLI only
- do not add a parallel `scripts/*` wrapper in this slice

Risk 2:

- widening into orchestrator registration because "production path" sounds like scheduling

Guardrail:

- keep this slice at the manual/formal entrypoint layer only
- explicitly exclude `config/orchestrator/*` and worker execution changes

Risk 3:

- accidentally changing benchmark result semantics while only trying to expose a caller

Guardrail:

- reuse `load_benchmark_run_manifest(...)`, `run_benchmark_manifest(...)`, and `materialize_benchmark_batch_run(...)` unchanged
- keep business logic out of the CLI

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/benchmark/cli.py`
2. implement parser + runtime flow around existing owners
3. add focused tests for parser defaults and end-to-end materialization
4. run syntax checks and focused verification

## 8. Success Criteria

This slice is complete when:

- the repository has one formal `M4` CLI entrypoint
- `config/benchmark/*.json` manifests become runnable without test-only scaffolding
- a manual invocation can produce the existing benchmark artifact and ledger outputs
- `dry_run` can execute without writing files
- focused tests lock parser and materialization behavior

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M4`
- no new direct consumer layer is claimed in this slice

Goal mapping:

- `G5`: expose repeatable benchmark execution as a real caller path rather than test-only library behavior
- `G6`: make benchmark artifact/ledger outputs manually deliverable for the later `M5/M6` chain

Not claimed in this slice:

- no claim that orchestrator has absorbed benchmark execution
- no claim that `M5` now consumes benchmark outputs
- no claim that `M6` now visualizes benchmark outputs
