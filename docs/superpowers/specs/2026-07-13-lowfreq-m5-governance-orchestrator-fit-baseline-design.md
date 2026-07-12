Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance orchestrator-fit baseline` slice after runtime/entrypoint baseline
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Orchestrator-Fit Baseline Design

Date: 2026-07-13

## 1. Goal

This slice advances `M5 governance` one narrow step beyond the already-landed runtime/entrypoint baseline.

Current repository evidence shows:

- `M5` already has:
  - formal governance contracts in `neotrade3/governance/contracts.py`
  - formal `M4 -> M5` projection in `neotrade3/governance/handoff.py`
  - canonical governance artifact persistence in `neotrade3/governance/artifact_writer.py`
  - canonical governance ledger/readback helpers in `neotrade3/governance/run_ledger.py`
  - one formal package CLI entrypoint in `neotrade3/governance/cli.py`
- the current orchestrator/worker runtime is real and phase-driven:
  - `DailyMasterOrchestrator._find_executor(...)` returns `task_executors.get(task.phase)` in `neotrade3/orchestration/daily_master_orchestrator.py`
  - `apps/worker/main.py` registers executors only for:
    - `PREFLIGHT`
    - `DATA_PIPELINE`
    - `PUBLISH_GATED_JOBS`
    - `DAILY_LAB_JOBS`
    - `LEARNING_LOOP`
    - `ISSUE_AGGREGATION_AND_CLOSEOUT`
- current orchestrator config has no governance phase and no governance task:
  - `config/orchestrator/daily_master_orchestrator.json`
- current `M5` runtime still depends on benchmark-manifest execution:
  - `neotrade3/governance/cli.py` calls `load_benchmark_run_manifest(...)`
  - `neotrade3/governance/cli.py` calls `run_benchmark_manifest(...)`
  - `build_governance_handoff_from_batch_run(...)` still consumes `BenchmarkBatchRunResult`
- current orchestration registration carries `args_template` only at config-load level:
  - `TaskRegistration.args_template` exists in `neotrade3/orchestration/models.py`
  - `build_run_plan(...)` does not copy it into `PlannedTask`
  - no current executor reads task-level `args_template`

So the narrow problem is no longer:

- how to define governance objects
- how to persist governance outputs
- how to run governance manually from a CLI

It is:

- how to let `M5 governance` enter the existing orchestrator/worker execution model truthfully
- how to do that without pretending the worker already produces `BenchmarkBatchRunResult`
- how to keep the governance upstream input config-backed instead of hard-coded
- how to do that without widening into `M6`, API, scheduler ownership, or a new parallel orchestrator framework

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `runtime/entrypoint baseline -> orchestrator-fit baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- extend the existing orchestrator model just enough to host one governance execution phase
- add one governance task registration under the existing orchestrator config
- let the worker register one governance executor for that phase
- preserve manifest-driven governance upstream input through task-level config
- extract or expose one reusable non-CLI governance runtime callable so both CLI and worker can use the same owner
- keep governance materialization on the existing artifact + ledger contracts
- add focused tests that lock:
  - phase/config propagation
  - governance executor dispatch
  - manifest-configured orchestration execution

Excluded:

- no new governance API route
- no new scheduler or cron registration
- no `M6` delivery or UI projection
- no new delivery download/report surface
- no typed reconstruction of `BenchmarkBatchRunResult` from persisted `M4` artifacts
- no direct consumption of worker daily-run outputs as governance upstream truth
- no rewrite of `DailyMasterOrchestrator` dispatch semantics
- no generic dynamic entrypoint loader based on `task.entrypoint`
- no new top-level orchestrator framework separate from `DailyMasterOrchestrator`

## 3. Existing Evidence

### 3.1 Real Dispatch Is Phase-Based, Not Entrypoint-Based

Current repository evidence in `neotrade3/orchestration/daily_master_orchestrator.py` is unambiguous:

- `_find_executor(...)` returns `task_executors.get(task.phase)`

That means:

- adding only a new config task is not enough
- changing only `entrypoint` strings is not enough
- any real governance integration must land in the phase/executor map

This is the first hard boundary of the slice.

### 3.2 Worker Owns The Current Execution Truth

Current repository evidence in `apps/worker/main.py` shows the worker registers executors only for six existing phases:

- `PREFLIGHT`
- `DATA_PIPELINE`
- `PUBLISH_GATED_JOBS`
- `DAILY_LAB_JOBS`
- `LEARNING_LOOP`
- `ISSUE_AGGREGATION_AND_CLOSEOUT`

No governance phase currently exists in that map.

So the real missing fit is not "another config string." It is:

- one new registered phase
- one new executor wired by the worker

### 3.3 Current M5 Runtime Depends On Benchmark Manifest Execution, Not Worker Outputs

Current repository evidence in `neotrade3/governance/cli.py` shows:

1. resolve manifest path
2. `load_benchmark_run_manifest(...)`
3. `run_benchmark_manifest(...)`
4. `build_governance_handoff_from_batch_run(...)`
5. `materialize_governance_handoff(...)`

And the already-frozen `M5 runtime/entrypoint baseline` design explicitly records:

- `build_governance_handoff_from_batch_run(...)` consumes `BenchmarkBatchRunResult`
- no existing typed readback builder reconstructs full `BenchmarkBatchRunResult` from persisted `M4` artifacts

So this slice must not fabricate a false upstream like:

- "governance now consumes worker daily snapshot"
- "governance can now read benchmark artifact and rebuild the same typed batch result"

Neither claim is supported by repository evidence.

### 3.4 Task-Level Args Exist In Registration But Not In Execution

Current repository evidence in `neotrade3/orchestration/models.py` and `neotrade3/orchestration/daily_master_orchestrator.py` shows:

- `TaskRegistration` has `args_template`
- `PlannedTask` has no `args_template`
- `build_run_plan(...)` copies:
  - `task_id`
  - `phase`
  - `lab_id`
  - `entrypoint`
  - `depends_on`
  - `outputs`
  - `requires_publish_status`
  - `status`
  - `skip_reason`
- therefore current executors cannot consume task-scoped manifest configuration

This matters because governance is already manifest-driven.

If this slice wants governance to be config-driven rather than hard-coded, the minimum truthful change is:

- carry `args_template` through the planning layer into execution

### 3.5 Orchestrator Config Currently Has No Governance Slot

Current repository evidence in `config/orchestrator/daily_master_orchestrator.json` shows:

- phases end at `issue_aggregation_and_closeout`
- tasks are currently data control and lab tasks only

So governance is outside the current orchestrator config surface today.

This confirms `orchestrator-fit` is a new independent theme, not drift inside the previous runtime slice.

## 4. Approach Options

### Option A: Reuse An Existing Phase And Branch On `task_id`

- keep the current six phases unchanged
- register a governance task under an existing phase such as `ISSUE_AGGREGATION_AND_CLOSEOUT`
- teach that existing executor to special-case one governance `task_id`

Pros:

- smaller enum/config change set

Cons:

- phase semantics become false
- governance runtime becomes hidden inside another layer's executor
- task-level manifest input is still awkward because current execution model does not surface `args_template`
- makes future audit harder because one phase starts owning unrelated layer work

### Option B: Add One Dedicated `GOVERNANCE` Phase And One Governance Executor (Recommended)

- extend `OrchestrationPhase` with one `GOVERNANCE` member
- extend orchestrator config with one new final phase and one governance task
- propagate `args_template` into `PlannedTask`
- add one governance executor in `apps/worker/main.py`
- extract one reusable non-CLI governance runtime callable that both the CLI and worker executor can use

Pros:

- matches the real phase-based dispatcher
- keeps governance ownership explicit and auditable
- preserves config-backed manifest input truthfully
- avoids shelling out to the CLI or duplicating governance composition logic
- keeps `M5` aligned with the six-layer architecture instead of burying it inside another phase

Cons:

- touches both orchestration and governance surfaces
- requires a small contract expansion in `PlannedTask`

### Option C: Create A Separate Governance-Orchestrator Framework

- add a new governance-only orchestrator or another worker path

Pros:

- isolates governance concerns

Cons:

- duplicates orchestration concepts already present in the repository
- widens far beyond a baseline fit slice
- creates a second runtime truth source during bootstrap

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice should introduce or modify only the minimum owners required for real orchestrator fit:

- `neotrade3/governance/runtime.py` or an equivalent reusable runtime owner
  - recommended responsibility:
    - accept `project_root`
    - accept `manifest_path`
    - accept `dry_run`
    - call the already-existing benchmark and governance owners
    - return the structured materialization record without printing
- `neotrade3/governance/cli.py`
  - becomes a thin caller over the reusable runtime owner
  - keeps the existing CLI contract frozen
- `neotrade3/orchestration/models.py`
  - extend `OrchestrationPhase`
  - extend `PlannedTask` so task-level args survive into execution
- `neotrade3/orchestration/daily_master_orchestrator.py`
  - pass through the extra planned-task field without redesigning dispatch
- `apps/worker/main.py`
  - register one governance executor under the new phase
- `config/orchestrator/daily_master_orchestrator.json`
  - add one governance phase and one governance task

These owners must not:

- introduce a second governance persistence format
- shell out to `python -m neotrade3.governance.cli`
- reinterpret worker snapshot outputs as governance upstream truth
- add API or scheduler coupling

### 5.2 Runtime Reuse Freeze

The worker must not call `main()` from `neotrade3/governance/cli.py`.

Reason:

- `main()` is CLI-shaped
- it parses argv
- it prints JSON summary
- it returns only an exit code

The worker needs structured data, not stdout side effects.

So this slice should freeze one reusable runtime callable, for example:

- `run_governance_manifest(...)`

Recommended behavior:

1. resolve manifest path
2. load manifest
3. run benchmark manifest
4. build governance handoff bundle
5. materialize governance handoff
6. return the resulting structured record

CLI then:

- calls the reusable runtime owner
- prints the existing JSON summary

Worker executor then:

- calls the same reusable runtime owner
- maps the returned record into `TaskResult`

### 5.3 Phase And Config Freeze

Recommended new orchestration phase:

- `GOVERNANCE = "governance"`

Recommended config placement:

- append `"governance"` as the final phase in `config/orchestrator/daily_master_orchestrator.json`
- add one governance task near the end of the task list

Recommended governance task shape:

- `task_id`: stable governance-specific id such as `governance.materialize_handoff`
- `phase`: `governance`
- `entrypoint`: documentary only, pointing to the reusable runtime owner or governance runtime module
- `args_template`:
  - at minimum carry `manifest`
  - optionally carry `dry_run_override` only if later evidence needs it
- `depends_on`: `[]`
- `outputs`:
  - governance artifact
  - governance ledger

Why `depends_on` should stay empty in the baseline:

- current governance upstream truth is benchmark-manifest execution, not worker daily-run outputs
- no repository evidence proves governance must wait for issue aggregation or learning outputs
- config order plus final-phase placement is enough to keep governance visually last without fabricating data dependency semantics

### 5.4 PlannedTask Contract Expansion

This slice should extend `PlannedTask` with:

- `args_template: dict[str, object]`

And `build_run_plan(...)` should pass through `task.args_template`.

Rationale:

- the field already exists in task registration
- governance needs manifest path at execution time
- this is smaller and more truthful than hard-coding the manifest path inside the worker executor

Guardrail:

- do not widen this into a generic runtime templating framework
- only preserve the already-existing config payload so executors can read it

### 5.5 Governance Executor Contract

The worker should add one executor factory, for example:

- `_create_governance_executor()`

The executor should:

- read `manifest` from `task.args_template`
- fall back to `config/benchmark/validation_seed_manifest.json` if the manifest key is absent
- read `project_root` and `dry_run` from shared context
- call the reusable governance runtime owner
- return `TaskResult`

Recommended `TaskResult` mapping:

- `status`
  - `RunStatus.OK` when governance materialization completes
  - `RunStatus.FAILED` on exception
- `artifact_refs`
  - include governance artifact path
  - include governance ledger path
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

This executor must not:

- emit another custom governance JSON artifact just for worker convenience
- duplicate governance summary shaping in multiple places
- consume `task.entrypoint` dynamically

### 5.6 Why This Slice Must Not Rebuild From Persisted M4 Outputs

A tempting alternative is:

- use the existing orchestrator/worker run
- read some persisted `M4` artifact later
- rebuild `BenchmarkBatchRunResult`
- then feed that into governance

Current repository evidence does not support that path because:

- the frozen `M5 runtime` design already records there is no typed reconstruction path
- current production callers still use `run_benchmark_manifest(...)` directly

So this baseline should keep the truthful upstream:

- governance executor runs benchmark manifest execution itself through the shared runtime owner

This is not elegant final-state architecture.

It is the narrowest evidence-backed fit.

### 5.7 File Boundary

Likely production files in scope:

- `neotrade3/governance/runtime.py` or equivalent shared runtime owner
- `neotrade3/governance/cli.py`
- `neotrade3/orchestration/models.py`
- `neotrade3/orchestration/daily_master_orchestrator.py`
- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`

Recommended focused test files:

- one new focused test file for orchestrator-fit behavior, such as:
  - `tests/unit/test_m5_governance_orchestrator_fit.py`
- optionally update one existing bootstrap/orchestration carrier only if a narrow focused file cannot cover the contract truthfully

Files explicitly not in scope:

- `apps/api/*`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/run_ledger.py`
- `docs/superpowers/specs/*m6*`

## 6. Testing Strategy

Add one focused test file for this slice.

Tests should lock at least:

1. phase contract
   - `OrchestrationPhase` includes `GOVERNANCE`
2. planning pass-through
   - governance task loaded from config survives into `PlannedTask`
   - `args_template["manifest"]` survives the planning layer
3. worker dispatch
   - governance task receives the governance executor through phase lookup
   - no dynamic `entrypoint` execution is required
4. dry-run governance execution under orchestrator
   - governance task runs through orchestrator/worker-style execution
   - no governance artifact or ledger files are written
   - task result details reflect the structured governance record
5. real materialization
   - governance task writes canonical artifact and ledger paths
   - task result artifact refs and details match persisted outputs

Fixture rule:

- reuse the same temp project-root benchmark config carrier pattern already proven by `tests/unit/test_m5_governance_cli.py`
- do not retest benchmark scoring semantics
- do not retest governance projection semantics already covered by prior M5 tests
- test only the new orchestrator-fit contract:
  - phase registration
  - args propagation
  - executor wiring
  - runtime reuse

Validation rule:

- if `pytest` remains unavailable, preserve the same fallback discipline already used in previous M5 slices:
  - `py_compile`
  - targeted inline assertions

## 7. Risks And Guardrails

Risk 1:

- hiding governance inside an existing non-governance phase to reduce file count

Guardrail:

- add one explicit `GOVERNANCE` phase
- keep executor ownership explicit in the worker map

Risk 2:

- duplicating the existing governance runtime composition between CLI and worker

Guardrail:

- freeze one reusable non-CLI runtime owner
- let both callers reuse it

Risk 3:

- hard-coding manifest paths in worker code and silently bypassing config

Guardrail:

- pass `args_template` through `PlannedTask`
- let governance executor read manifest from task config

Risk 4:

- claiming governance now consumes orchestrator-produced evidence

Guardrail:

- state clearly that this baseline still runs the benchmark manifest path inside the governance executor
- do not claim worker daily-run outputs are now the governance upstream source

Risk 5:

- widening into a generic plugin/runtime loader because config has `entrypoint`

Guardrail:

- keep dispatch exactly phase-based in this slice
- do not add dynamic import/execution behavior

Risk 6:

- widening into `M6` because governance results become available in orchestrator snapshots

Guardrail:

- claim only orchestrator-fit and worker execution visibility
- do not add API, report, or frontend delivery work

## 8. Success Criteria

This slice is complete when:

- `M5 governance` has one explicit place in the current orchestrator phase model
- the worker registers one governance executor for that phase
- governance task config can carry a manifest path truthfully into execution
- CLI and worker share one governance runtime composition owner instead of duplicating logic
- orchestrator-driven dry-run governance execution returns structured task results without writing files
- orchestrator-driven non-dry-run governance execution writes the canonical governance artifact and ledger outputs
- focused tests lock the new phase/config/executor/runtime-reuse contract without widening into API or `M6`

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M5`
- reused upstream runtime dependency: `M4 benchmark manifest execution`
- reused orchestration carrier: `bootstrap orchestrator/worker`

Goal mapping:

- `G5`: move governance from manual CLI-only invocation to a formally registered orchestrator/worker execution slot
- not yet `G6`: no delivery/UI/API/scheduler surface is added here

New contract introduced by this slice:

- governance becomes an explicit orchestration phase
- `args_template` becomes part of the execution-facing planned-task contract
- one shared governance runtime owner serves both CLI and worker callers

Not claimed in this slice:

- no claim that benchmark itself has been absorbed into the worker mainline as a first-class daily phase
- no claim that governance consumes worker daily snapshot outputs
- no claim that persisted `M4` artifacts can reconstruct typed governance upstream input
- no claim that `M6` now exposes governance results
