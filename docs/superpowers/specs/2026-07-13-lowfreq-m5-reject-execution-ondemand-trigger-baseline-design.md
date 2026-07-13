Status: active
Owner: lowfreq / orchestration / governance / worker
Scope: Narrow `M5 reject execution on-demand trigger baseline` slice for one formal worker entrypoint consuming the existing on-demand carrier
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution On-Demand Trigger Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence now shows:

- reject runtime exists
- reject CLI exists
- worker governance executor supports reject execution
- orchestration owns `OnDemandTaskRequest` and `build_on_demand_plan(...)`

But one formal gap remains:

- the on-demand carrier is only consumed inside focused tests
- `apps/worker/main.py` still exposes only the daily bootstrap run surface

So the narrow next problem is:

- how to give the existing on-demand carrier one formal worker-owned trigger surface
- how to do so without changing daily config, governance runtime, or scheduled execution

Project-phase note:

- domain: `M5 governance`
- change type: `bootstrap worker trigger baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add one worker-owned method that builds and executes the existing on-demand governance reject plan
- add one CLI mode that triggers that worker method
- add focused worker tests proving the formal trigger materializes reject execution through the existing carrier

Excluded:

- no changes to `config/orchestrator/daily_master_orchestrator.json`
- no changes to governance runtime owners
- no auto `validation_id` selection
- no promotion approval path
- no `M6`

## 3. Existing Evidence

- current worker CLI only accepts the daily bootstrap run flags and calls `BootstrapWorkerApp.run(...)`: [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py)
- the on-demand carrier already exists in orchestration contracts: [models.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/models.py)
- the orchestrator already builds executable on-demand plans from explicit tasks: [daily_master_orchestrator.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/daily_master_orchestrator.py)
- current formal usage of that carrier is still test-only: [test_m5_governance_orchestrator_fit.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_orchestrator_fit.py)

So the missing owner is not another runtime or planner. The missing owner is a formal worker trigger surface.

## 4. Approach

Recommended option:

- add a narrow worker method dedicated to `governance reject` on-demand execution
- build `OnDemandTaskRequest` inside that worker method
- reuse the existing governance executor and `execute_run_plan(...)`
- expose the path through a new worker CLI mode while preserving the existing daily default behavior

Reasons:

- keeps the new trigger inside the already-existing worker owner
- avoids widening the slice into a generic scheduler or API surface
- preserves backward compatibility for the current daily worker invocation
- promotes the on-demand carrier from test-only usage into formal runtime usage

## 5. Design

### 5.1 Worker Entry Method

Add one worker-owned method on `BootstrapWorkerApp`:

- `run_governance_reject_on_demand(...)`

Inputs:

- `target_date`
- `source_run_id`
- `validation_id`
- `requested_by`
- `dry_run`

Behavior:

- instantiate the orchestrator from the existing config files
- build one `OnDemandTaskRequest` containing exactly one governance reject task
- reuse the existing governance task executor
- execute the resulting plan through `execute_run_plan(...)`
- build orchestration ledger artifacts in memory for the result payload
- return a worker snapshot shaped like the existing worker output subset:
  - `status`
  - `target_date`
  - `orchestration.plan`
  - `orchestration.task_results`
  - `orchestration.run_ledger`
  - `orchestration.task_ledger`
  - `summary`

### 5.2 CLI Trigger Surface

Keep the existing daily worker mode as the default behavior.

Add one explicit CLI selector:

- `--mode`

Allowed values:

- `daily`
- `governance_reject`

For `governance_reject`:

- require `--source-run-id`
- require `--validation-id`
- continue reusing `--date`
- ignore `--publish-succeeded` semantically because the on-demand carrier does not inherit daily publish gating

This avoids a breaking parser conversion to subcommands while still making the non-daily trigger explicit.

### 5.3 Why This Stays Narrow

This slice deliberately does not introduce:

- a generic manual task launcher
- a new HTTP endpoint
- a new governance runtime
- a new scheduling concept

It only gives one already-existing on-demand carrier one worker-owned trigger.

## 6. Testing Strategy

Focused tests should lock:

1. worker on-demand reject path materializes the reject artifact and ledger
2. worker CLI `governance_reject` mode exits `0` for an `ok` snapshot
3. worker CLI `governance_reject` mode exits non-zero for a failed snapshot
4. legacy daily worker invocation stays unchanged

## 7. Acceptance Criteria

- `BootstrapWorkerApp.run_governance_reject_on_demand(...)` exists
- worker CLI supports an explicit `governance_reject` mode
- reject execution can be materially triggered through the worker-owned on-demand path
- daily worker mode remains backward compatible

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in `M5` governance trigger orchestration under the worker owner
- `G1-G6` target mapping:
  - this is the minimum `G2` trigger closure after carrier and executor baselines already exist
- new contract introduced:
  - `BootstrapWorkerApp.run_governance_reject_on_demand(...)`
  - worker CLI `--mode governance_reject`
- boundaries not touched:
  - no daily config mutation
  - no governance runtime rewrite
  - no auto validation selection
  - no approval flow
  - no `M6`
