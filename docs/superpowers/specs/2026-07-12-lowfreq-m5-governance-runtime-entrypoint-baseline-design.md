Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance runtime/entrypoint baseline` slice after ledger/readback baseline
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Runtime Entrypoint Baseline Design

Date: 2026-07-12

## 1. Goal

This slice advances `M5 governance` one narrow step beyond the already-landed ledger/readback baseline.

Current repository evidence shows:

- `M5` already has:
  - formal governance contracts in `neotrade3/governance/contracts.py`
  - formal `M4 -> M5` projection in `neotrade3/governance/handoff.py`
  - canonical artifact persistence in `neotrade3/governance/artifact_writer.py`
  - canonical ledger/readback helpers in `neotrade3/governance/run_ledger.py`
- `M4` already has the exact production-entry pattern that turns internal owners into a runnable path:
  - `neotrade3/benchmark/cli.py`
- `M5` still does not have:
  - a formal production caller that executes the governance handoff path from a configured upstream input
  - a stable operator-facing JSON summary for one governance materialization run
  - a package-level runtime entrypoint that can be invoked without reconstructing the call chain manually

So the narrow problem is no longer how to project or persist one governance bundle.

It is:

- how to expose one formal `M5` entrypoint
- how to run the already-frozen `M4 -> M5` handoff path from a benchmark manifest
- how to materialize the result into the already-existing governance artifact and ledger paths
- how to do that without widening into orchestrator registration, API routes, or `M6` delivery surfaces

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `ledger/readback baseline -> runtime/entrypoint baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add one formal package CLI entrypoint under `neotrade3/governance/`
- let that entrypoint run:
  - benchmark manifest load
  - benchmark batch execution
  - `M4 -> M5` handoff projection
  - governance artifact + ledger materialization
- support explicit `--manifest`, `--project-root`, and `--dry-run`
- print a stable JSON summary for human/manual invocation and later automation
- add focused tests for parser behavior and end-to-end CLI materialization

Excluded:

- no new governance API route
- no worker/orchestrator registration
- no scheduler integration
- no `M6` delivery/UI projection
- no mutation of `GovernanceHandoffBundle`
- no mutation of `BenchmarkBatchRunResult`
- no governance read-model redesign
- no new aggregate index file
- no approval workflow runtime
- no validation/promotion execution runtime

## 3. Existing Evidence

### 3.1 M5 Already Has The Internal Projection And Persistence Chain

The full internal owner set already exists:

- `build_governance_handoff_from_batch_run(...)` in `neotrade3/governance/handoff.py`
- `materialize_governance_handoff(...)` in `neotrade3/governance/run_ledger.py`

That means this slice should not add another persistence owner or another projection owner.

It should only add the missing caller that composes the already-landed chain.

### 3.2 M4 Already Freezes The Exact Runtime Shape

Current production precedent already exists in `neotrade3/benchmark/cli.py`:

- `build_parser()`
- `main(argv: Sequence[str] | None = None) -> int`
- runtime flow:
  - resolve `project_root`
  - resolve manifest path
  - `load_benchmark_run_manifest(...)`
  - `run_benchmark_manifest(...)`
  - `materialize_benchmark_batch_run(...)`
  - print JSON summary

Important proven choices:

- keep parser contract minimal
- default manifest is config-backed
- `dry_run` still returns an in-memory summary
- surface errors directly instead of inventing a new CLI error taxonomy

The safest `M5` next step is to mirror this pattern narrowly with governance-specific composition.

### 3.3 The M5 Handoff Builder Already Accepts Batch-Run Input

`build_governance_handoff_from_batch_run(...)` already consumes:

- `BenchmarkBatchRunResult`

Current repository evidence does not show any typed `M4` readback path that reconstructs a full `BenchmarkBatchRunResult` from a persisted artifact.

So the narrow runnable path with the strongest repository evidence is:

1. load benchmark manifest
2. run benchmark batch
3. project batch result into `GovernanceHandoffBundle`
4. materialize governance outputs

This avoids inventing an unproven readback-to-runtime reconstruction layer.

## 4. Approach Options

### Option A: Add One Pure Runtime Function Only

- add `neotrade3/governance/runtime.py`
- expose only one helper callable from Python code
- postpone CLI

Pros:

- smaller public surface
- keeps the package free from another executable module

Cons:

- still leaves `M5` without one formal runnable entrypoint
- weaker parity with the already-landed `M4` mainline pattern
- tests and operators still need to build their own invocation shell

### Option B: Add `neotrade3/governance/cli.py` As The Canonical M5 Entrypoint (Recommended)

- keep existing governance owners unchanged
- add one package CLI with parser + `main()`
- reuse existing benchmark manifest execution and governance materialization owners
- print a compact JSON result

Pros:

- smallest production diff that creates a real runnable `M5` path
- mirrors the already-proven `M4` package CLI pattern exactly where evidence exists
- keeps all orchestration and API concerns outside this slice
- makes current governance materialization callable without manual glue code

Cons:

- `M5` runtime still depends on re-running upstream `M4` benchmark execution
- still manual/CLI-driven, not yet orchestrator-driven

### Option C: Register Governance Directly Into Orchestrator Now

Pros:

- closer to eventual automation

Cons:

- widens into phase semantics, task registration, and executor plumbing
- current repository evidence does not show a reserved orchestrator path for `M5 governance`
- mixes two unfinished themes:
  - `M5` entrypoint exposure
  - orchestrator runtime completion

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice introduces one new bounded owner:

- `neotrade3/governance/cli.py`

Recommended entrypoints:

- `build_parser()`
- `main(argv: Sequence[str] | None = None) -> int`

This owner is responsible only for runtime composition:

- resolve runtime arguments
- run the already-existing upstream benchmark path
- project one batch result into a governance handoff bundle
- materialize governance artifact + ledger outputs
- print a stable JSON summary

This owner must not:

- build new governance business objects
- redesign persistence format
- add HTTP behavior
- register orchestrator tasks
- implement approval or promotion runtime

### 5.2 CLI Contract Freeze

The CLI should support:

- `--project-root`
  - optional repo root override
  - defaults to repository root derived from file location
- `--manifest`
  - path to a benchmark run manifest JSON
  - defaults to `config/benchmark/validation_seed_manifest.json`
- `--dry-run`
  - execute and summarize without writing governance artifact/ledger files

Recommended runtime flow:

1. resolve `project_root`
2. resolve `manifest_path`
3. load manifest via `load_benchmark_run_manifest(...)`
4. run benchmark via `run_benchmark_manifest(...)`
5. project batch result via `build_governance_handoff_from_batch_run(...)`
6. materialize via `materialize_governance_handoff(...)`
7. print a JSON summary

### 5.3 Output Summary Freeze

The CLI output should be a stable JSON payload containing at least:

- `source_run_id`
- `status`
- `source_layer`
- `projected_assessment_count`
- `projected_issue_count`
- `diagnostic_count`
- `change_request_count`
- `experiment_request_count`
- `promotion_blocker_count`
- `artifact_path`
- `ledger_path`
- `dry_run`

Status semantics:

- successful run returns `status = "completed"`
- `dry_run` still returns the in-memory materialization payload, but no files are written

Why keep it this small:

- current need is a runnable formal path
- not a verbose governance reporting layer
- not an approval dashboard payload
- not a replacement for the persisted artifact itself

### 5.4 Error Handling

This CLI should not introduce a custom governance runtime error taxonomy in this slice.

Rules:

- invalid manifest path should raise the underlying file/read error
- invalid manifest payload should raise the existing validation error
- benchmark execution errors should surface directly
- governance handoff/materialization errors should surface directly

Rationale:

- this is still a bootstrap-stage formal entrypoint
- direct failure is better than inventing an unproven operator contract

### 5.5 File Boundary

Production file:

- `neotrade3/governance/cli.py`

Focused test file:

- `tests/unit/test_m5_governance_cli.py`

Files intentionally reused but not modified unless evidence proves necessary:

- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`

Files explicitly not in scope:

- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/__init__.py`

Default recommendation:

- do not widen package-root exports in this slice

Reason:

- tests can import `neotrade3.governance.cli` directly
- the main value here is executable entrypoint behavior, not another package-root symbol

### 5.6 Why Not Read From Persisted M4 Artifacts Yet

A tempting alternative is:

- read an existing persisted `M4` artifact
- reconstruct a batch-run object
- build governance outputs without rerunning benchmark execution

Current repository evidence does not support that path yet because:

- `read_benchmark_run_artifact(...)` returns raw JSON payload
- no existing typed readback builder reconstructs `BenchmarkBatchRunResult`
- adding one now would create a second theme:
  - persisted read-model reconstruction
  - governance runtime entrypoint

That would violate the narrow-slice rule.

So this slice deliberately chooses runtime composition from the manifest-backed upstream path.

## 6. Testing Strategy

Add one focused unit test file:

- `tests/unit/test_m5_governance_cli.py`

Tests should lock:

1. parser defaults
   - `project_root is None`
   - `manifest == "config/benchmark/validation_seed_manifest.json"`
   - `dry_run is False`
2. parser explicit arguments
   - accepts custom `--project-root`
   - accepts custom `--manifest`
   - accepts `--dry-run`
3. CLI dry-run
   - runs successfully
   - prints stable JSON summary
   - does not write artifact or ledger files
4. CLI materialize
   - runs successfully on a prepared temp project root
   - writes governance artifact and ledger outputs
   - printed summary matches persisted run identity and counts

Fixture rule:

- mirror the `M4 benchmark CLI` test carrier style where evidence already exists
- prepare a temp project root with benchmark config files copied into `config/benchmark/`
- do not re-test benchmark scoring semantics
- test only the new `M5` CLI contract and its composition boundary

## 7. Risks And Guardrails

Risk 1:

- widening into orchestrator ownership because the new CLI is runnable

Guardrail:

- keep the slice package-local to `neotrade3/governance/cli.py`
- add no task registration and no config changes under `config/orchestrator/`

Risk 2:

- widening into a second runtime source that bypasses the existing `M4` formal path

Guardrail:

- load only benchmark manifests already consumed by `M4`
- call `run_benchmark_manifest(...)` directly instead of inventing a new execution stack

Risk 3:

- over-designing a governance report payload inside the CLI summary

Guardrail:

- keep the summary to stable identity, counts, paths, and `dry_run`
- leave detailed evidence inspection to persisted artifact readback

Risk 4:

- claiming governance approval/runtime closure too early

Guardrail:

- claim only `runtime/entrypoint baseline`
- do not claim approval workflow, promotion automation, API querying, or `M6` delivery

## 8. Success Criteria

This slice is complete when:

- `neotrade3/governance/cli.py` exists as a formal runnable owner
- one benchmark manifest can drive:
  - benchmark batch execution
  - governance handoff projection
  - governance artifact + ledger materialization
- CLI `dry_run` returns a stable summary without writing files
- non-dry-run CLI writes the canonical governance artifact and ledger files
- focused tests lock parser behavior and end-to-end CLI materialization independently of API/orchestrator concerns

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M5`
- upstream runtime dependency consumed but not modified: `M4 benchmark mainline path`
- persistence surface reused but not modified: `M5 governance run_ledger`

Goal mapping:

- `G5`: convert the already-queryable governance persistence baseline into a runnable formal governance entrypoint
- not yet `G6`: no delivery, UI, API, or orchestrator exposure is added here

Not claimed in this slice:

- no governance API
- no worker/orchestrator integration
- no scheduler registration
- no approval workflow runtime
- no promotion execution runtime
- no `M6` delivery surface
