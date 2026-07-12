Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance orchestrator-fit baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Orchestrator-Fit Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-orchestrator-fit-baseline-design.md`

## 1. Goal

This plan implements only the next narrow `M5` slice after the governance runtime/entrypoint baseline:

- add one truthful `M5 governance` slot in the existing orchestrator phase model
- let the worker execute one governance task through the real phase-to-executor dispatch path
- preserve manifest-driven governance upstream input through task-level config instead of hard-coded worker behavior
- reuse one shared governance runtime owner between CLI and worker
- lock the new orchestrator-fit surface with one focused test carrier

This slice explicitly does not include:

- governance API
- scheduler or cron registration
- `M6` delivery/UI projection
- typed reconstruction of `BenchmarkBatchRunResult` from persisted `M4` artifacts
- direct consumption of worker daily snapshots as governance upstream truth
- dynamic `task.entrypoint` loading
- rewrite of orchestrator dispatch semantics
- mutation of governance persistence contracts in:
  - `neotrade3/governance/artifact_writer.py`
  - `neotrade3/governance/run_ledger.py`
- mutation of benchmark manifest execution internals in `neotrade3/benchmark/batch_runner.py`

## 2. Starting Point

Repository evidence before this slice:

- `M5` already has a runnable CLI path in `neotrade3/governance/cli.py`
- that CLI already proves the canonical upstream composition chain:
  - `load_benchmark_run_manifest(...)`
  - `run_benchmark_manifest(...)`
  - `build_governance_handoff_from_batch_run(...)`
  - `materialize_governance_handoff(...)`
- `DailyMasterOrchestrator` dispatches only by phase via `task_executors.get(task.phase)`
- worker currently registers no governance executor
- orchestrator config currently declares no governance phase/task
- `TaskRegistration.args_template` exists, but `PlannedTask` does not carry it into execution
- `tests/unit/test_bootstrap_skeleton.py` instantiates many `PlannedTask(...)` objects directly

So the implementation strategy is:

- extract the already-proven governance composition chain into one non-CLI shared runtime owner
- keep the CLI as a thin caller over that shared runtime
- add one explicit `GOVERNANCE` phase plus one governance task in orchestrator config
- pass `args_template` through the planning layer with a backward-safe default
- add one governance executor in the worker that consumes task config and shared runtime output
- verify the whole fit with one focused orchestrator-fit test file instead of widening bootstrap test carriers

## 3. File Boundary

Production files:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `neotrade3/orchestration/models.py`
- `neotrade3/orchestration/daily_master_orchestrator.py`
- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`

Primary test file:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Documentation files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-orchestrator-fit-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-orchestrator-fit-baseline-plan.md`

Files intentionally reused but not modified unless implementation evidence proves it necessary:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/benchmark/batch_runner.py`
- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_bootstrap_skeleton.py`

Files explicitly not in scope:

- `apps/api/*`
- `neotrade3/benchmark/run_ledger.py`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `docs/superpowers/specs/*m6*`

Plan note:

- keep `tests/unit/test_bootstrap_skeleton.py` untouched by default
- preserve backward compatibility by giving the new `PlannedTask.args_template` field a default value instead of bulk-editing existing test carriers

## 4. Execution Steps

### M5ORCH-S1: Extract the shared governance runtime owner

Create:

- `neotrade3/governance/runtime.py`

Implement one reusable callable, for example:

- `run_governance_manifest(...)`

Recommended signature:

- accepts `project_root`
- accepts `manifest_path`
- accepts `dry_run`

Runtime flow:

1. resolve `manifest_path`
2. call `load_benchmark_run_manifest(...)`
3. call `run_benchmark_manifest(...)`
4. call `build_governance_handoff_from_batch_run(...)`
5. call `materialize_governance_handoff(...)`
6. return the resulting governance record

Implementation rule:

- keep all benchmark and governance business logic inside existing owners
- this new module is runtime composition only

Completion check:

- one shared callable exists that returns structured data and prints nothing

### M5ORCH-S2: Rewire the CLI to the shared runtime

Modify:

- `neotrade3/governance/cli.py`

Implement:

- replace inline benchmark/governance composition with a call into the shared runtime owner
- keep the existing parser contract unchanged
- keep the existing JSON summary contract unchanged

Must preserve:

- `--project-root`
- `--manifest`
- `--dry-run`
- stable JSON summary fields:
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

Completion check:

- CLI remains behaviorally stable while no longer owning runtime composition directly

### M5ORCH-S3: Extend orchestration contracts just enough for governance

Modify:

- `neotrade3/orchestration/models.py`
- `neotrade3/orchestration/daily_master_orchestrator.py`

Contract changes:

1. extend `OrchestrationPhase` with:
   - `GOVERNANCE = "governance"`
2. extend `PlannedTask` with:
   - `args_template: dict[str, object]`

Compatibility rule:

- `PlannedTask.args_template` must default to an empty dict so existing direct test instantiations remain valid

Planning pass-through:

- `build_run_plan(...)` must copy `task.args_template` into `PlannedTask`

Implementation rule:

- do not change `_find_executor(...)`
- do not add dynamic `entrypoint` execution
- do not redesign dependency semantics

Completion check:

- governance config values can survive registration -> planning -> execution without breaking current direct `PlannedTask(...)` callers

### M5ORCH-S4: Register the governance phase and task in orchestrator config

Modify:

- `config/orchestrator/daily_master_orchestrator.json`

Config changes:

1. append `"governance"` as the final phase
2. add one governance task, for example:
   - `task_id`: `governance.materialize_handoff`
   - `phase`: `governance`
   - `entrypoint`: governance runtime module path, documentary only
   - `args_template`:
     - `manifest`: `config/benchmark/validation_seed_manifest.json`
   - `depends_on`: `[]`
   - `outputs`:
     - governance artifact
     - governance ledger

Implementation rule:

- keep `depends_on` empty in this baseline
- use config order plus final-phase placement to express “run last”
- do not invent fake dependency semantics on worker-produced snapshots

Completion check:

- orchestrator config loads with one explicit governance slot and one config-backed manifest path

### M5ORCH-S5: Add the governance executor in the worker

Modify:

- `apps/worker/main.py`

Implement:

- add one `_create_governance_executor()` factory
- register it in `task_executors` under `OrchestrationPhase.GOVERNANCE`

Executor behavior:

1. read `manifest` from `task.args_template`
2. fall back to `config/benchmark/validation_seed_manifest.json` if absent
3. read `project_root` and `dry_run` from shared context
4. call the shared governance runtime owner
5. map the returned record into `TaskResult`

`TaskResult` minimum shape:

- `status`
  - `RunStatus.OK` on successful governance materialization
  - `RunStatus.FAILED` on exception
- `artifact_refs`
  - governance artifact path
  - governance ledger path
- `details`
  - `source_run_id`
  - `source_layer`
  - `projected_assessment_count`
  - `projected_issue_count`
  - `diagnostic_count`
  - `change_request_count`
  - `experiment_request_count`
  - `promotion_blocker_count`
  - `dry_run`
  - resolved `manifest`

Implementation rule:

- do not shell out to `python -m neotrade3.governance.cli`
- do not emit extra governance-only worker artifacts
- do not consume `task.entrypoint` dynamically

Completion check:

- the worker can execute one governance task through the real phase map and return a structured `TaskResult`

### M5ORCH-S6: Add focused orchestrator-fit tests

Create:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Test carrier pattern:

- reuse the temp project-root benchmark config preparation style from `tests/unit/test_m5_governance_cli.py`
- instantiate or call the real orchestrator/worker owners directly
- avoid broad assertions on unrelated bootstrap snapshots

Test cases:

1. phase contract
   - `OrchestrationPhase` includes `GOVERNANCE`
2. planning pass-through
   - governance task loaded from config survives into `PlannedTask`
   - `args_template["manifest"]` survives the planning layer
3. backward compatibility
   - direct `PlannedTask(...)` construction without `args_template` still works because of the default
4. worker governance dry-run
   - governance executor runs through the worker/orchestrator-style path
   - task result is `RunStatus.OK`
   - no governance artifact or ledger files are written
   - task result details expose summary counts and resolved manifest
5. worker governance materialization
   - governance executor writes canonical artifact and ledger outputs
   - `artifact_refs` and `details` align with persisted governance outputs

Testing rule:

- do not re-test benchmark grading semantics
- do not re-test governance projection semantics already locked by prior M5 tests
- test only the new orchestrator-fit contract:
  - shared runtime reuse
  - phase registration
  - args propagation
  - executor dispatch
  - canonical materialization side effects

Completion check:

- the new fit surface is locked independently of API, scheduler, and `M6`

### M5ORCH-S7: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/governance/runtime.py neotrade3/governance/cli.py neotrade3/orchestration/models.py neotrade3/orchestration/daily_master_orchestrator.py apps/worker/main.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `.venv/bin/python -m pytest tests/unit/test_m5_governance_orchestrator_fit.py tests/unit/test_m5_governance_cli.py tests/unit/test_m5_governance_handoff_adapter.py tests/unit/test_m5_governance_run_ledger.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - `OrchestrationPhase.GOVERNANCE`
  - `PlannedTask` default backward compatibility
  - planning pass-through of `args_template["manifest"]`
  - governance dry-run execution through worker/orchestrator-style path
  - governance write-mode execution through worker/orchestrator-style path
  - persisted artifact/ledger alignment with returned `TaskResult`

Completion check:

- syntax passes
- best-available focused verification passes

### M5ORCH-S8: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-orchestrator-fit-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-orchestrator-fit-baseline-plan.md`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `neotrade3/orchestration/models.py`
- `neotrade3/orchestration/daily_master_orchestrator.py`
- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Must exclude:

- `apps/api/*`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/run_ledger.py`
- `tests/unit/test_bootstrap_skeleton.py` unless concrete compatibility evidence forces a minimal edit
- unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- duplicating governance runtime composition between CLI and worker

Guard:

- freeze one shared runtime owner in `neotrade3/governance/runtime.py`
- keep both CLI and worker as thin callers

Risk 2:

- breaking existing direct `PlannedTask(...)` callers by expanding the dataclass contract

Guard:

- give `args_template` a default empty dict
- avoid bulk edits to `tests/unit/test_bootstrap_skeleton.py` unless concrete failures prove they are necessary

Risk 3:

- hard-coding the manifest path in worker code and bypassing orchestrator config

Guard:

- pass `args_template` through `PlannedTask`
- read manifest from task config first

Risk 4:

- widening into fake upstream semantics by claiming governance now consumes worker-produced evidence

Guard:

- keep governance upstream truth as benchmark-manifest execution through the shared runtime owner
- do not claim worker daily snapshots are governance inputs

Risk 5:

- widening into plugin-style dynamic dispatch because config already has `entrypoint`

Guard:

- keep dispatch phase-based only
- treat `entrypoint` as documentary only in this slice

Risk 6:

- widening into `M6` because governance outputs become available in orchestrator execution

Guard:

- stop at orchestrator-fit and task-result visibility
- add no API, report, or frontend delivery work

## 6. Success Criteria

This slice is complete when:

- one explicit `GOVERNANCE` phase exists in the orchestration model and config
- governance task config can carry a manifest path through registration, planning, and execution
- CLI and worker share one governance runtime composition owner
- worker can execute governance through the real phase-to-executor path
- dry-run governance execution returns a structured `TaskResult` without writing governance files
- write-mode governance execution writes the canonical governance artifact and ledger outputs
- focused verification passes
- syntax verification passes
