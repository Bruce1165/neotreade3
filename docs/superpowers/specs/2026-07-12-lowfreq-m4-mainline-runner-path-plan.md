Status: active
Owner: lowfreq / benchmark
Scope: Implementation plan for the narrow `M4 benchmark mainline runner path` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M4 Mainline Runner Path Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m4-mainline-runner-path-design.md`

## 1. Goal

This plan covers only the next six-layer back-half acceleration slice after the `M2 shadow minimal contract` recovery.

This slice only handles:

- one formal `M4` CLI entrypoint
- manifest-driven batch execution through the existing benchmark owners
- artifact/ledger materialization through the existing benchmark owners

The goal is to:

- stop `M4` from being runnable only inside tests
- make `config/benchmark/*.json` a real executable contract surface
- expose the smallest formal mainline path without widening into orchestrator work

This slice does not:

- change benchmark samples, manifests, or fixture semantics
- change assessment rules, trace bundles, or gap objects
- register new orchestrator tasks
- touch `M5` governance or `M6` delivery code

## 2. Starting Point

Current repository evidence shows:

- `neotrade3/benchmark/batch_runner.py` already loads manifests and executes formal batches
- `neotrade3/benchmark/artifact_writer.py` already writes JSON artifacts
- `neotrade3/benchmark/run_ledger.py` already writes/readbacks benchmark ledger entries
- `config/benchmark/validation_seed_manifest.json` and `config/benchmark/validation_seed_v2_manifest.json` already exist
- those manifests are only consumed by tests and docs, not by a production caller
- `neotrade3/screeners/cli.py` already demonstrates the preferred package CLI pattern

So the correct narrow move is:

- add one package CLI for benchmark
- reuse all existing `M4` runtime owners
- keep the new code as a thin facade

## 3. Implementation Strategy

Production boundary:

- `neotrade3/benchmark/cli.py`

Test boundary:

- `tests/unit/test_m4_benchmark_cli.py`
- optionally `tests/unit/test_bootstrap_skeleton.py` only if a tiny parser regression anchor is materially useful

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-m4-mainline-runner-path-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m4-mainline-runner-path-plan.md`

## 4. Execution Steps

### M4CLI-S1: Add the CLI module

Create:

- `neotrade3/benchmark/cli.py`

Implement:

- `build_parser()`
- `main()`

Parser contract:

- `--manifest`
- `--project-root`
- `--dry-run`

Defaults:

- project root defaults to repository root derived from module location
- manifest defaults to `config/benchmark/validation_seed_manifest.json`

Completion check:

- parser can be imported and used independently from command execution

### M4CLI-S2: Wire the mainline runtime flow

In `main()`:

1. parse args
2. resolve `project_root`
3. resolve manifest path
4. call `load_benchmark_run_manifest(...)`
5. call `run_benchmark_manifest(...)`
6. call `materialize_benchmark_batch_run(...)`
7. print one JSON summary
8. return `0`

Output payload should include at least:

- `run_id`
- `status`
- `sample_count`
- `executed_sample_ids`
- `grade_summary`
- `bucket_summary`
- `artifact_path`
- `ledger_path`
- `dry_run`

Completion check:

- the CLI is only a thin caller over existing benchmark owners

### M4CLI-S3: Add focused tests

Create:

- `tests/unit/test_m4_benchmark_cli.py`

Test cases:

1. parser default behavior
   - default manifest path points to `config/benchmark/validation_seed_manifest.json`
   - `--dry-run` defaults to `False`
2. parser explicit arguments
   - custom `--manifest`
   - custom `--project-root`
   - `--dry-run`
3. end-to-end dry run
   - invoke `main()` with `validation_seed_manifest.json`
   - capture stdout
   - assert JSON payload fields
   - assert no ledger/artifact file was written
4. end-to-end materialization path
   - invoke `main()` with `validation_seed_v2_manifest.json`
   - capture stdout
   - assert ledger/artifact files exist under temp project root
   - assert output paths match persisted files

Test style:

- run against the real config manifests
- use temp directories for output isolation
- keep assertions on caller behavior, not re-test internal batch-runner semantics exhaustively

Completion check:

- parser and runtime exposure are both locked

### M4CLI-S4: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/benchmark/cli.py tests/unit/test_m4_benchmark_cli.py`
- `.venv/bin/python -m pytest tests/unit/test_m4_benchmark_cli.py tests/unit/test_m4_benchmark_batch_runner.py tests/unit/test_m4_benchmark_run_ledger.py tests/unit/test_m4_benchmark_artifact_writer.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - `build_parser()`
  - `main()` in dry-run mode
  - `main()` in write mode with a temp project root

Completion check:

- syntax validation passes
- focused verification passes with the best available runner in the environment

### M4CLI-S5: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m4-mainline-runner-path-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m4-mainline-runner-path-plan.md`
- `neotrade3/benchmark/cli.py`
- `tests/unit/test_m4_benchmark_cli.py`

Must exclude:

- changes to `config/benchmark/*`
- changes to `batch_runner.py`
- changes to `artifact_writer.py`
- changes to `run_ledger.py`
- any orchestrator config or worker change
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- adding a CLI that re-implements logic already frozen in benchmark owners

Guard:

- the CLI may orchestrate calls only
- do not duplicate manifest parsing or ledger-writing internals

Risk 2:

- letting the new tests become another indirect copy of batch-runner tests

Guard:

- test parser contract and CLI integration behavior only
- rely on existing benchmark owner tests for internals

Risk 3:

- widening into scheduled/orchestrated execution because the new entrypoint looks "production ready"

Guard:

- explicitly keep orchestrator untouched in this slice
- leave scheduled integration to a later dedicated workstream

## 6. Success Criteria

This slice is complete when:

- `neotrade3.benchmark.cli` exists as a formal runnable entrypoint
- the default benchmark manifest can be executed without test-only scaffolding
- dry-run mode returns a stable JSON summary without writing files
- write mode persists the existing artifact and ledger outputs
- focused verification passes
- syntax verification passes
