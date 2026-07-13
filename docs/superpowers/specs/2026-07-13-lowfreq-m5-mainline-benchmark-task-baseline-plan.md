Status: active
Owner: lowfreq / orchestration / benchmark
Scope: Implementation plan for the narrow `M5 mainline benchmark task baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Mainline Benchmark Task Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-mainline-benchmark-task-baseline-design.md`

## 1. Goal

This slice only establishes the missing upstream `M4` production task inside the current worker/orchestrator truth.

This slice must:

- add a real `benchmark` orchestration phase
- register one benchmark task in the daily master orchestrator config
- add one shared benchmark runtime callable
- add one worker executor for the benchmark phase
- emit stable `TaskResult` metadata and artifact refs
- lock the behavior with focused tests

This slice explicitly does not:

- dynamically pass `run_id` into governance
- add governance `depends_on` benchmark
- rewrite governance task args
- change benchmark internals
- touch `M6`

## 2. Starting Point

Repository evidence before implementation:

- `M4` benchmark runtime already exists, but only as CLI/library capability
- `M5` governance runtime already exists, but still consumes a static `benchmark_run_id`
- worker/orchestrator has no `BENCHMARK` phase, no benchmark executor, and no benchmark task registration

So the correct narrow move is:

- expose the existing benchmark runtime as a shared callable
- let worker/orchestrator execute it as one first-class task
- leave dynamic governance chaining to the next slice

## 3. File Boundary

Production files:

- `neotrade3/benchmark/runtime.py`
- `neotrade3/benchmark/cli.py`
- `neotrade3/benchmark/__init__.py`
- `neotrade3/orchestration/models.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `apps/worker/main.py`

Focused test files:

- `tests/unit/test_m4_benchmark_orchestrator_fit.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- governance task dependency graph

## 4. Execution Steps

### M5BM-S1: Add shared benchmark runtime owner

Create:

- `neotrade3/benchmark/runtime.py`

Implementation:

1. add default manifest constant
2. add manifest-path resolver
3. add `run_benchmark_for_manifest(...)`
4. return the existing `BenchmarkRunLedgerRecord`

Implementation rule:

- runtime owner orchestrates existing benchmark owners only
- no benchmark scoring or fixture logic duplication

### M5BM-S2: Repoint benchmark CLI to the shared runtime owner

Modify:

- `neotrade3/benchmark/cli.py`
- `neotrade3/benchmark/__init__.py`

Implementation:

1. let CLI call `run_benchmark_for_manifest(...)`
2. keep output JSON shape stable
3. export the new runtime helper if needed by tests/worker

Implementation rule:

- CLI remains a thin caller

### M5BM-S3: Extend orchestration phase/config surface

Modify:

- `neotrade3/orchestration/models.py`
- `config/orchestrator/daily_master_orchestrator.json`

Implementation:

1. add `OrchestrationPhase.BENCHMARK`
2. insert `"benchmark"` into orchestrator phase order before `governance`
3. add `benchmark.materialize_run` task with:
   - `entrypoint = "neotrade3.benchmark.runtime:run_benchmark_for_manifest"`
   - `args_template.manifest = "config/benchmark/validation_seed_manifest.json"`
   - `outputs = ["benchmark_run_artifact", "benchmark_run_ledger"]`

Implementation rule:

- governance task stays unchanged and still static
- no new dependency edge in this slice

### M5BM-S4: Add worker benchmark executor

Modify:

- `apps/worker/main.py`

Implementation:

1. import the shared benchmark runtime helper
2. add `_create_benchmark_executor(...)`
3. read `manifest` from `task.args_template`
4. return `TaskResult` with:
   - artifact refs
   - `run_id`
   - `status`
   - `sample_count`
   - `executed_sample_ids`
   - `grade_summary`
   - `bucket_summary`
   - `manifest`
   - `dry_run`
5. register the benchmark executor in `task_executors`

Implementation rule:

- do not touch governance executor behavior
- use the same envelope pattern as the governance executor

### M5BM-S5: Lock with focused tests

Create or modify:

- `tests/unit/test_m4_benchmark_orchestrator_fit.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Required coverage:

1. orchestrator plan contains `BENCHMARK` phase and `benchmark.materialize_run`
2. benchmark task keeps manifest path in `args_template`
3. worker benchmark executor succeeds in dry-run mode
4. worker benchmark executor succeeds in write mode and persists artifact/ledger
5. governance config remains static and unchanged by this slice

Testing rule:

- do not widen into governance run_id propagation
- do not re-test benchmark internals already covered by benchmark tests

### M5BM-S6: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/benchmark/runtime.py neotrade3/benchmark/cli.py neotrade3/benchmark/__init__.py neotrade3/orchestration/models.py apps/worker/main.py tests/unit/test_m4_benchmark_orchestrator_fit.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `python3 -m pytest tests/unit/test_m4_benchmark_orchestrator_fit.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `git diff --check`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run inline assertions for:
  - benchmark runtime helper
  - benchmark executor dry-run
  - benchmark executor write mode
  - orchestrator config phase/task registration

## 5. Risks And Guardrails

- **Risk: fake M4->M5 closure**
  - Guardrail: do not change governance dependency graph or dynamic run_id flow
- **Risk: duplicated benchmark runtime flow**
  - Guardrail: move shared orchestration into `benchmark/runtime.py` and reuse it from CLI and worker
- **Risk: phase misuse**
  - Guardrail: add a dedicated `benchmark` phase instead of hiding benchmark under governance or issue phases

## 6. Done Criteria

This slice is done only when all of the following are true:

- worker/orchestrator has a real benchmark phase
- config declares one benchmark task
- worker executes that task through a dedicated executor
- benchmark runtime is shared between CLI and worker
- focused tests pass
- governance remains static by design

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice spans `M4` and `M5` mainline infrastructure, but only to establish the missing upstream benchmark production task
- `G1-G6` target mapping:
  - this is a `G5` mainline-connectivity step that prepares later dynamic `M4 -> M5` chaining without faking it
- new contract introduced:
  - `benchmark` orchestration phase
  - `benchmark.materialize_run` task
  - `run_benchmark_for_manifest(...)`
- boundaries not touched:
  - no governance dynamic propagation
  - no governance dependency rewrite
  - no `M6`
