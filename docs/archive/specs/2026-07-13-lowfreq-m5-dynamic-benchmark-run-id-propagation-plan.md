Status: active
Owner: lowfreq / orchestration / governance
Scope: Implementation plan for the narrow `M5 dynamic benchmark_run_id propagation` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Dynamic Benchmark Run ID Propagation Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-dynamic-benchmark-run-id-propagation-design.md`

## 1. Goal

This slice only removes the last false static handoff inside the current `benchmark -> governance` mainline.

This slice must:

- make governance truthfully depend on `benchmark.materialize_run`
- resolve benchmark `TaskResult.details["run_id"]` into governance task args during the same orchestrator execution
- keep governance runtime and CLI unchanged
- lock the behavior with focused orchestrator-fit tests

This slice explicitly does not:

- add a generic templating engine
- read dynamic values from artifact refs or ledgers
- change governance domain contracts
- touch `M6`

## 2. Starting Point

Repository evidence before implementation:

- benchmark already emits `TaskResult.details["run_id"]`
- governance runtime already consumes a single `benchmark_run_id`
- orchestrator execution already tracks dependency `TaskResult` objects
- but governance config still hard-codes a static benchmark run id
- and orchestrator execution does not resolve dependency outputs into downstream args

So the correct narrow move is:

- add one small dependency-result resolution step inside orchestrator execution
- let governance executor consume the resolved scalar input
- change config so governance depends on benchmark and references benchmark `run_id`

## 3. File Boundary

Production files:

- `neotrade3/orchestration/daily_master_orchestrator.py`
- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`

Focused test files:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Optional supporting test file only if strictly needed:

- `tests/unit/test_m4_benchmark_orchestrator_fit.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/benchmark/runtime.py`
- `neotrade3/benchmark/cli.py`

## 4. Execution Steps

### M5RP-S1: Add dependency-result resolution inside orchestrator execution

Modify:

- `neotrade3/orchestration/daily_master_orchestrator.py`

Implementation:

1. add one narrow helper that inspects `task.args_template`
2. support only object references of the shape:
   - `{"from_task": "<task_id>", "detail_key": "<key>"}`
3. resolve those references only from already-completed dependency task results
4. build a resolved `PlannedTask` before calling the executor
5. surface missing task, missing detail, or invalid shape as narrow execution errors

Implementation rule:

- no nested path parsing
- no artifact-ref parsing
- no silent fallback to static defaults

### M5RP-S2: Keep governance executor a thin scalar consumer

Modify:

- `apps/worker/main.py`

Implementation:

1. read `benchmark_run_id` from the resolved `task.args_template`
2. optionally tighten the error message so failure distinguishes empty input from unresolved propagation
3. keep the call target as `run_governance_for_benchmark_run(...)`

Implementation rule:

- governance executor must not parse reference objects
- resolution ownership stays in orchestrator execution

### M5RP-S3: Rewrite governance task config to a truthful dependency

Modify:

- `config/orchestrator/daily_master_orchestrator.json`

Implementation:

1. set `depends_on = ["benchmark.materialize_run"]`
2. replace static:
   - `"benchmark_run_id": "validation_seed_v1_batch"`
3. with the narrow dynamic reference object:
   - `{"from_task": "benchmark.materialize_run", "detail_key": "run_id"}`

Implementation rule:

- keep phase order unchanged
- keep governance task id and entrypoint unchanged

### M5RP-S4: Lock the chain with focused governance orchestrator-fit tests

Modify:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Required coverage:

1. planning keeps governance in the `GOVERNANCE` phase and benchmark in the `BENCHMARK` phase
2. governance task now depends on `benchmark.materialize_run`
3. governance config exposes the dynamic reference object instead of a static literal
4. one execute-run-plan flow runs benchmark first, then governance consumes the resolved upstream `run_id`
5. governance remains blocked when benchmark dependency is not satisfied

Testing rule:

- prefer one integrated orchestrator-fit chain over new generic helper tests
- do not widen into CLI tests

### M5RP-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/orchestration/daily_master_orchestrator.py apps/worker/main.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `python3 -m pytest tests/unit/test_m4_benchmark_orchestrator_fit.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `git diff --check`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run inline assertions for:
  - governance config dependency shape
  - dynamic `run_id` resolution
  - governance dry-run and write-mode execution through benchmark dependency output

## 5. Risks And Guardrails

- **Risk: widen into generic template language**
  - Guardrail: only implement `from_task + detail_key`
- **Risk: duplicate resolution logic in worker**
  - Guardrail: orchestrator resolves, worker only consumes resolved scalar values
- **Risk: keep false static fallback**
  - Guardrail: remove static config truth and fail explicitly when upstream `run_id` cannot be resolved

## 6. Done Criteria

This slice is done only when all of the following are true:

- governance task truthfully depends on benchmark
- governance no longer carries a static benchmark run id in orchestrator config
- same-run execution resolves benchmark `run_id` into governance args
- governance worker execution succeeds without changing governance runtime/CLI contracts
- focused tests pass

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice spans `M4` and `M5` mainline execution truth, but only to bridge the benchmark result already emitted by worker into the governance consumer already implemented in runtime
- `G1-G6` target mapping:
  - this is a `G5` mainline-connectivity step that removes the remaining static handoff in `M4 -> M5`
- new contract introduced:
  - dynamic args reference object with `from_task + detail_key`
  - resolved governance dependency on `benchmark.materialize_run`
- boundaries not touched:
  - no governance runtime rewrite
  - no CLI rewrite
  - no artifact/ledger lookup language
  - no `M6`
