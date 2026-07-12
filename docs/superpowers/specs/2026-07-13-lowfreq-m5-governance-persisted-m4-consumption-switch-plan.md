Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance persisted M4 consumption switch` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Persisted M4 Consumption Switch Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-persisted-m4-consumption-switch-design.md`

## 1. Goal

This plan implements only the next narrow `M5` slice after the already-landed:

- `M4 benchmark artifact typed readback baseline`
- `M5 governance orchestrator-fit baseline`

This slice must:

- remove benchmark manifest recomputation from shared governance runtime
- switch governance runtime, CLI, and worker/orchestrator callers to `benchmark_run_id`
- consume persisted typed `M4` artifacts through `read_benchmark_batch_run_result(...)`
- keep `M4 -> M5` handoff and governance materialization semantics unchanged
- update `PROJECT_STATUS.md` so repository truth matches current implementation state

This slice explicitly does not include:

- `M3 backhalf` work
- `M4` benchmark expansion
- `M5` governance closure objects
- `M6`
- version unification
- API route changes
- scheduler changes

## 2. Starting Point

Repository evidence before this slice:

- `M4` already exposes `read_benchmark_batch_run_result(...)` in `neotrade3/benchmark/run_ledger.py`
- `M5` runtime still resolves a manifest path and reruns benchmark execution in `neotrade3/governance/runtime.py`
- `M5` CLI still accepts `--manifest` in `neotrade3/governance/cli.py`
- worker governance executor still reads `task.args_template["manifest"]` in `apps/worker/main.py`
- orchestrator config still carries a governance `manifest` arg in `config/orchestrator/daily_master_orchestrator.json`
- `PROJECT_STATUS.md` was stale and has now been updated in this same workstream to reflect current `M4/M5` baseline facts

So the implementation strategy is:

- keep typed `M4 -> M5` handoff unchanged
- replace only the runtime input contract and its direct callers
- fail loudly on missing persisted upstream artifacts
- add focused tests for the new truth source and caller contract

## 3. File Boundary

Production files:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `PROJECT_STATUS.md`

Focused test files:

- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Possible new focused test file only if existing carriers become too noisy:

- `tests/unit/test_m5_governance_runtime.py`

Files intentionally reused but not modified unless implementation evidence proves it necessary:

- `neotrade3/benchmark/run_ledger.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/contracts.py`

Files explicitly not in scope:

- `apps/api/*`
- `neotrade3/benchmark/contracts.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/governance/assembler.py`
- any `M6` file

## 4. Execution Steps

### M5PERSIST-S1: Switch shared governance runtime to `benchmark_run_id`

Modify:

- `neotrade3/governance/runtime.py`

Implementation:

1. remove manifest-path resolution helpers from the shared runtime owner
2. add one narrow benchmark-run-id resolver if needed
3. add or rename the shared runtime entry so it consumes:
   - `project_root`
   - `benchmark_run_id`
   - `dry_run`
4. call `read_benchmark_batch_run_result(...)`
5. if the artifact is missing, raise `FileNotFoundError`
6. build governance handoff from the typed batch result
7. materialize governance handoff

Implementation rule:

- shared runtime must no longer import or call:
  - `load_benchmark_run_manifest(...)`
  - `run_benchmark_manifest(...)`

Completion check:

- governance runtime has exactly one upstream truth source: persisted typed `M4`

### M5PERSIST-S2: Switch CLI input contract

Modify:

- `neotrade3/governance/cli.py`

Implementation:

1. replace `--manifest` with required `--benchmark-run-id`
2. keep `--project-root`
3. keep `--dry-run`
4. call the shared runtime with `benchmark_run_id`
5. preserve existing JSON summary contract as much as possible

Implementation rule:

- CLI should remain a thin caller over shared runtime
- do not duplicate runtime readback or materialization logic

Completion check:

- CLI can no longer run governance by recomputing benchmark manifests

### M5PERSIST-S3: Switch worker/orchestrator governance task args

Modify:

- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`

Implementation:

1. worker governance executor reads `task.args_template["benchmark_run_id"]`
2. keep narrow fallback behavior explicit:
   - if missing or blank, fail instead of inventing a default
3. update orchestrator config to carry `benchmark_run_id`

Implementation rule:

- this slice does not add automatic benchmark-run discovery
- config continues to be only a baseline carrier

Completion check:

- governance phase uses the same upstream truth contract in both CLI and worker paths

### M5PERSIST-S4: Focused test updates

Modify existing focused carriers first:

- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Add a dedicated runtime test file only if current carriers become unclear.

Test cases:

1. runtime materializes governance from a persisted benchmark artifact
2. runtime raises `FileNotFoundError` for missing `benchmark_run_id`
3. CLI parser requires `--benchmark-run-id`
4. CLI end-to-end path succeeds when the benchmark artifact already exists
5. CLI no longer depends on benchmark manifest execution
6. worker governance executor reads `benchmark_run_id` from task args
7. orchestrator config round-trips the renamed arg contract

Testing rule:

- do not re-test benchmark grading semantics
- do not widen into governance closure semantics
- do not widen into `M6`

Completion check:

- the truth-switch boundary is locked independently of later governance work

### M5PERSIST-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/governance/runtime.py neotrade3/governance/cli.py apps/worker/main.py tests/unit/test_m5_governance_cli.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `.venv/bin/python -m pytest tests/unit/test_m5_governance_cli.py tests/unit/test_m5_governance_orchestrator_fit.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run one inline assertion script that:
  - materializes a benchmark run into a temp project root
  - runs governance by `benchmark_run_id`
  - asserts missing-artifact failure
  - asserts CLI/worker argument contract behavior

Additional boundary check:

- `git diff --check`

## 5. Risks And Guardrails

- **Risk: accidental fallback to manifest rerun**
  - Guardrail: remove manifest imports/calls from shared runtime in the same slice
- **Risk: implicit default run id**
  - Guardrail: require explicit `benchmark_run_id` in CLI and worker task args
- **Risk: widening into orchestration automation**
  - Guardrail: do not add dynamic benchmark-run lookup in this slice
- **Risk: stale project truth**
  - Guardrail: keep the `PROJECT_STATUS.md` update in the same slice

## 6. Done Criteria

This slice is done only when all of the following are true:

- shared governance runtime consumes persisted typed `M4` artifacts by run id
- shared governance runtime no longer reruns benchmark manifests
- CLI contract is `benchmark_run_id` based
- worker/orchestrator governance task contract is `benchmark_run_id` based
- missing upstream artifacts fail loudly
- focused tests and minimum verification pass
- `PROJECT_STATUS.md` matches current completed facts and next-step truth

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - implementation belongs to `M5`, depending on already-landed `M4` typed persistence
- `G1-G6` target mapping:
  - this is a `G5` truth-convergence slice before later `G6` delivery
- new contract introduced:
  - governance runtime callers pass `benchmark_run_id` instead of `manifest`
- boundaries not touched:
  - no `M3 backhalf`
  - no `M4` scoring changes
  - no `M5` closure objects
  - no version unification
  - no `M6`
