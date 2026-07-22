Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 reject execution worker baseline` slice using the existing GOVERNANCE phase executor without changing production daily orchestrator config
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution Worker Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- reject execution runtime already exists
- reject execution persistence already exists
- reject execution CLI already exists
- worker/orchestrator execution still only supports governance handoff materialization
- the production daily orchestrator config currently has no safe way to carry a static `validation_id`

So the narrow next problem is:

- how to let the existing `GOVERNANCE` phase executor trigger reject execution
- how to prove that the orchestrator execution engine can carry that task shape
- without adding an unsafe static reject task into the production daily schedule

This slice is not:

- a production daily scheduled reject task
- automatic validation discovery
- promotion approval
- blocker or attention status transitions

Project-phase note:

- domain: `M5 governance worker/orchestrator execution baseline`
- change type: `worker executor adoption + synthetic orchestrator-fit`
- NeoTrade2 remains reference only
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- extend the existing governance phase worker executor to support reject execution
- add focused synthetic orchestrator-fit tests for reject execution

Excluded:

- no change to `config/orchestrator/daily_master_orchestrator.json`
- no new production scheduled reject task
- no automatic derivation of `validation_id`
- no CLI changes
- no `M6`

## 3. Existing Evidence

### 3.1 Reject Runtime Is Already Ready

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py)

shows that reject execution already has a narrow runtime owner requiring:

- `source_run_id`
- `validation_id`
- `dry_run`

### 3.2 Worker Still Only Handles Handoff

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L307-L356)

shows that the governance phase worker executor currently only:

- reads `benchmark_run_id`
- calls `run_governance_for_benchmark_run(...)`

So reject execution is missing only at the worker/executor layer.

### 3.3 Production Orchestrator Config Cannot Safely Carry Reject Yet

Current repository evidence in:

- [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json)
- [models.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/models.py)

shows that:

- task registrations are active daily config entries
- there is no separate manual/on-demand task contract in the orchestrator model
- adding a production reject task would require hard-coding a `validation_id` or inventing a new upstream detail contract

That would be unsafe and outside the current narrow boundary.

### 3.4 Synthetic Orchestrator-Fit Is Already An Existing Pattern

Current repository evidence in:

- [test_m5_governance_orchestrator_fit.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_orchestrator_fit.py)

shows the established pattern:

- construct `PlannedTask` objects directly in tests
- execute them through `DailyMasterOrchestrator.execute_run_plan(...)`
- validate executor behavior without changing production config first

That is the safest baseline for reject execution too.

## 4. Approach

Recommended option:

- keep one `GOVERNANCE` phase executor
- branch inside it on args presence:
  - `validation_id + source_run_id` -> reject execution
  - otherwise -> handoff materialization
- prove the shape with synthetic planned-task tests

Reasons:

- phase model remains unchanged
- production config remains unchanged
- executor stays thin and future-compatible

## 5. Design

### 5.1 Executor Branch Freeze

Inside `_create_governance_executor()`:

- if `task.args_template` contains non-empty `validation_id`
  - require non-empty `source_run_id`
  - call `run_governance_reject_execution(...)`
  - emit reject execution details and artifact refs
- else
  - keep current handoff branch unchanged

This branch decision is narrow and explicit.

### 5.2 Reject Worker Output Freeze

Reject execution `TaskResult.details` should expose:

- `validation_id`
- `source_run_id`
- `status`
- `baseline_run_id`
- `candidate_run_id`
- `decision_id`
- `decision`
- `dry_run`

Artifact refs should be:

- independent reject artifact path
- independent reject ledger path

### 5.3 No Production Config Mutation

This slice intentionally does not add a new task to:

- [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json)

Reason:

- production config currently represents active daily tasks
- reject execution still requires explicit subject selection
- there is no stable upstream producer of `validation_id` in production task details yet

## 6. Testing Strategy

Focused tests should lock:

1. governance executor can run reject execution in dry-run mode
2. governance executor can materialize reject execution outputs
3. synthetic `execute_run_plan(...)` can carry reject task args through the existing governance phase
4. missing `validation_id` or missing `source_run_id` fails deterministically in the reject branch
5. handoff branch remains unchanged

Do not test:

- production config scheduling
- CLI
- worker app outer run loop

## 7. Acceptance Criteria

- governance phase worker executor supports reject execution
- focused synthetic orchestrator-fit tests pass
- production daily orchestrator config remains unchanged
- handoff governance execution remains unchanged

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` worker/orchestrator execution compatibility
- `G1-G6` target mapping:
  - this is the minimum `G2` executor adoption step after reject runtime and CLI already exist
- new runtime contract introduced:
  - governance phase executor reject branch keyed by explicit `source_run_id + validation_id`
- boundaries not touched:
  - no production scheduled reject task
  - no auto validation selection
  - no promotion approval
  - no `M6`
