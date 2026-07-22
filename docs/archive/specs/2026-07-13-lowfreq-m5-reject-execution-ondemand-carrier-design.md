Status: active
Owner: lowfreq / orchestration / governance
Scope: Narrow `M5 reject execution on-demand carrier` slice for explicit-task planning without changing daily config
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution On-Demand Carrier Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- reject runtime exists
- reject CLI exists
- governance worker executor now supports reject execution
- the missing formal carrier is not execution, but explicit task planning outside daily config

So the narrow next problem is:

- how to represent one explicit on-demand task request
- how to turn that request into an executable `DailyRunPlan`
- how to do so without touching `daily_master_orchestrator.json`

This slice is not:

- a new daily scheduled reject task
- auto selection of rejected validations
- promotion approval

Project-phase note:

- domain: `orchestration carrier for M5 reject execution`
- change type: `on-demand planned-task carrier`
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add one on-demand task request contract
- add one orchestrator helper that builds an executable plan from explicit tasks
- add focused tests proving the carrier can drive reject execution

Excluded:

- no production config changes
- no scheduler changes
- no governance runtime changes
- no `M6`

## 3. Existing Evidence

- current `DailyRunRequest` only models daily config-based planning: [models.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/models.py)
- current `build_run_plan(...)` only expands tasks from `self.config.tasks`: [daily_master_orchestrator.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/daily_master_orchestrator.py)
- synthetic tests prove explicit `PlannedTask` execution works, but there is no formal carrier for producing them: [test_m5_governance_orchestrator_fit.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_orchestrator_fit.py)

So the missing owner is a formal explicit-task planning carrier.

## 4. Approach

Recommended option:

- add a small `OnDemandTaskRequest` contract in orchestration models
- add `build_on_demand_plan(...)` on `DailyMasterOrchestrator`
- reuse existing `execute_run_plan(...)`

Reasons:

- avoids mutating daily config
- avoids inventing a second execution engine
- formalizes what current tests already do ad hoc

## 5. Design

### 5.1 Carrier Contract

New model:

- `OnDemandTaskRequest`

Fields:

- `target_date`
- `tasks`

Each task item should carry the exact minimum needed to create a `PlannedTask`:

- `task_id`
- `phase`
- `entrypoint`
- `args_template`
- `outputs`
- optional `lab_id`
- optional `depends_on`
- optional `requires_publish_status`

### 5.2 Orchestrator Helper

New helper on `DailyMasterOrchestrator`:

- `build_on_demand_plan(request: OnDemandTaskRequest) -> DailyRunPlan`

Behavior:

- build `PlannedTask` objects directly from explicit request tasks
- mark them `planned`
- keep phases ordered by first appearance
- do not consult `self.config.tasks`
- do not apply publish gating or lab-enable gating

### 5.3 Why Gating Is Excluded

This carrier is explicitly for non-daily, manually scoped execution.

So it should not:

- inherit daily config enablement rules
- pretend to be a scheduled task

That keeps it honest and narrow.

## 6. Testing Strategy

Focused tests should lock:

1. on-demand plan builds `PlannedTask` from explicit request
2. phases are preserved in first-seen order
3. reject execution can run through the new carrier
4. production daily config remains untouched

## 7. Acceptance Criteria

- `OnDemandTaskRequest` exists
- `build_on_demand_plan(...)` exists
- reject execution can be driven through the new carrier in focused tests
- daily config is unchanged

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in orchestration carrier design supporting `M5`
- `G1-G6` target mapping:
  - this is the minimum `G2` formal planning carrier for explicit reject execution
- new contract introduced:
  - `OnDemandTaskRequest`
  - `build_on_demand_plan(...)`
- boundaries not touched:
  - no daily config mutation
  - no auto validation selection
  - no promotion approval
  - no `M6`
