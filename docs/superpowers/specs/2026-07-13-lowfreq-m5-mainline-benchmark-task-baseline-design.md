Status: active
Owner: lowfreq / orchestration / benchmark
Scope: Narrow `M5 mainline benchmark task baseline` slice for upstream M4 production-path registration
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Mainline Benchmark Task Baseline Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M4 benchmark mainline runner path`
- `M5 governance runtime/entrypoint baseline`
- `M5 governance orchestrator-fit baseline`
- `M5 governance persisted-M4 consumption switch`

Current repository evidence shows:

- `M4` already has a runnable formal path through:
  - `neotrade3/benchmark/cli.py`
  - `run_benchmark_manifest(...)`
  - `materialize_benchmark_batch_run(...)`
- `M5` already has a formal persisted-consumption path through:
  - `run_governance_for_benchmark_run(...)`
- but the orchestrator/worker mainline still has no `benchmark` phase and no benchmark task:
  - `OrchestrationPhase` has no `BENCHMARK`
  - `apps/worker/main.py` registers no benchmark executor
  - `config/orchestrator/daily_master_orchestrator.json` contains no benchmark task
- therefore the current mainline is missing the upstream production path that should produce the `M4` run consumed later by governance

So the narrow problem is not:

- how to run a benchmark batch
- how to persist a benchmark artifact
- how governance consumes a persisted benchmark run

It is:

- how to let the existing worker/orchestrator truthfully host one benchmark task as a first-class phase
- how to do that without pretending `benchmark_run_id` dynamic propagation is already solved
- how to do that without widening into `M5` dynamic handoff chaining, `M6`, API, or scheduler work

Project-phase note:

- domain: `M5 mainline bootstrap`
- change type: `upstream task registration baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M4/M5 / G5`

## 2. Scope

Included:

- add one dedicated orchestration phase for benchmark execution
- add one benchmark task registration to the daily master orchestrator config
- add one shared benchmark runtime callable so CLI and worker can reuse the same owner
- add one worker benchmark executor for the new phase
- return real benchmark artifact refs and run metadata through `TaskResult`
- add focused tests that lock:
  - phase/config propagation
  - benchmark executor dispatch
  - orchestrated benchmark materialization

Excluded:

- no dynamic `benchmark_run_id` propagation into governance
- no new `depends_on` edge from governance to benchmark yet
- no change to governance task `args_template`
- no rewrite of benchmark manifests, samples, fixtures, or scoring rules
- no new API or scheduler surface
- no `M6`

## 3. Existing Evidence

### 3.1 M4 Already Has A Real Runtime Owner

Current repository evidence in:

- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/cli.py)
- [batch_runner.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py)
- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/run_ledger.py)

shows that `M4` is already runnable and materializable.

So this slice must not rebuild benchmark execution.

It should only expose that owner to the existing worker/orchestrator execution truth.

### 3.2 Worker/Orchestrator Currently Cannot Run Benchmark Tasks

Current repository evidence in:

- [models.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/models.py)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py)
- [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json)

shows:

- no `BENCHMARK` phase exists
- no benchmark executor exists
- no benchmark task exists

This is the real upstream mainline gap.

### 3.3 Governance Still Uses A Static `benchmark_run_id`

Current repository evidence shows:

- governance task config still hard-codes `benchmark_run_id`
- worker governance executor still reads it from `task.args_template`

This means the benchmark task slice must not falsely claim:

- governance is now dynamically chained to the latest benchmark run

That remains a later slice.

## 4. Approach Options

### Option A: Reuse Existing Phases And Branch On `task_id`

Pros:

- fewer enum/config changes

Cons:

- phase semantics become false
- benchmark ownership becomes hidden in unrelated executors
- future dynamic chaining becomes harder to audit

### Option B: Add One Dedicated `BENCHMARK` Phase With One Benchmark Task (Recommended)

Pros:

- matches the phase-driven dispatcher truthfully
- establishes upstream production path without faking downstream chaining
- keeps the slice narrow and auditable
- preserves a clean later handoff point for dynamic `run_id` propagation

Cons:

- touches orchestration config, enum, worker executor map, and benchmark runtime surface

### Option C: Skip Mainline And Only Update Docs

Pros:

- smallest diff

Cons:

- leaves the real code gap untouched
- does not create an upstream production task

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice introduces one new shared owner and one new execution registration path:

- `neotrade3/benchmark/runtime.py`
- `neotrade3/orchestration/models.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `apps/worker/main.py`

Supporting exports/tests may also change.

Files intentionally not modified in this slice:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- governance task dependency wiring

### 5.2 Benchmark Runtime Freeze

This slice should add one reusable runtime callable:

- `run_benchmark_for_manifest(...)`

Minimum inputs:

- `project_root`
- `manifest_path`
- `dry_run`

Behavior:

1. resolve manifest path against `project_root` if relative
2. load manifest
3. run benchmark batch
4. materialize artifact + ledger
5. return the resulting benchmark ledger record

Design rule:

- benchmark CLI should become a thin caller over this runtime helper
- worker benchmark executor should use the same helper

### 5.3 Phase And Task Freeze

Add one new phase:

- `benchmark`

Add one new task:

- `benchmark.materialize_run`

Recommended config shape:

- `phase = "benchmark"`
- `entrypoint = "neotrade3.benchmark.runtime:run_benchmark_for_manifest"`
- `args_template = {"manifest": "config/benchmark/validation_seed_manifest.json"}`
- `depends_on = []`
- `outputs = ["benchmark_run_artifact", "benchmark_run_ledger"]`

Design rule:

- this task exists as an upstream production task only
- it does not yet feed governance automatically

### 5.4 Worker Executor Freeze

Add one benchmark executor in `apps/worker/main.py`.

Behavior:

- read manifest path from `task.args_template["manifest"]`
- call `run_benchmark_for_manifest(...)`
- emit `TaskResult` with:
  - `artifact_refs`
  - `details.run_id`
  - `details.status`
  - `details.sample_count`
  - `details.executed_sample_ids`
  - `details.grade_summary`
  - `details.bucket_summary`
  - `details.manifest`
  - `details.dry_run`

Design rule:

- use the same `TaskResult` envelope pattern already used by governance
- do not invent a second benchmark execution report object here

### 5.5 Why Governance Chaining Is Out Of Scope

This slice intentionally stops before:

- governance `depends_on = ["benchmark.materialize_run"]`
- governance reading upstream `run_id` from `TaskResult`
- replacing static `benchmark_run_id`

Reason:

- those changes belong to the next mainline slice
- mixing them here would combine “task existence” and “dynamic handoff propagation” into one non-atomic change

## 6. Testing Strategy

Focused tests should lock:

1. orchestrator planning includes the new `BENCHMARK` phase and benchmark task
2. worker benchmark executor can materialize a benchmark run in dry-run mode
3. worker benchmark executor can materialize a benchmark run in write mode and return stable `TaskResult`
4. benchmark CLI still works while reusing the shared runtime owner

Testing rule:

- do not widen into governance dynamic propagation
- do not widen into scheduler/API
- do not widen into benchmark assessment internals already covered elsewhere

## 7. Risks And Guardrails

### 7.1 Main Risk

The main risk is accidentally implying that `M4 -> M5` dynamic chaining is solved once the benchmark task exists.

Guardrail:

- keep governance task config and dependency graph unchanged in this slice

### 7.2 Ownership Risk

Another risk is duplicating benchmark runtime logic between CLI and worker.

Guardrail:

- move runtime ownership into `neotrade3/benchmark/runtime.py`
- keep both CLI and worker as thin callers

### 7.3 Scope Risk

Another risk is widening into scheduler or governance consumption.

Guardrail:

- only add the upstream benchmark task and executor
- leave `run_id` propagation to the next slice

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- the orchestrator model includes a real `benchmark` phase
- config declares one benchmark task
- worker can execute that task through a dedicated executor
- benchmark execution uses a shared runtime owner, not duplicated flow
- focused tests prove planning and execution behavior
- governance remains unchanged and still static by design

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- governance `depends_on` benchmark wiring
- dynamic `benchmark_run_id` propagation
- automatic “latest benchmark run” discovery
- full `M4 -> M5` worker-level E2E chain
- `M5` closure objects
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice spans `M4` and `M5` mainline infrastructure, but only to establish the missing upstream `M4` production task within the worker/orchestrator truth
- `G1-G6` target mapping:
  - this is a `G5` mainline-connectivity step that prepares later dynamic `M4 -> M5` chaining without faking it early
- new contract introduced:
  - `benchmark` orchestration phase
  - `benchmark.materialize_run` orchestrator task
  - `run_benchmark_for_manifest(...)`
- boundaries not touched:
  - no governance dynamic propagation
  - no governance dependency rewrite
  - no `M6`
