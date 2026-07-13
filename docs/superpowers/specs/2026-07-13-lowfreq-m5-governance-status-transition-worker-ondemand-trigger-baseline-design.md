Status: active
Owner: lowfreq / governance / worker
Scope: Narrow `M5 governance status transition worker/on-demand trigger baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition Worker On-Demand Trigger Baseline Design

Date: 2026-07-13

## 1. Goal

This slice continues the current `M5 governance` mainline after:

- status transition persistence/runtime baseline
- status transition CLI baseline

Repository evidence now shows:

- `run_governance_status_transition(...)` already exists as the runtime owner
- governance CLI already exposes `status-transition`
- `apps/worker/main.py` already has a complete on-demand worker surface for reject execution:
  - `run_governance_reject_on_demand(...)`
  - `--mode governance_reject`
  - `--source-run-id`
  - `--validation-id`
- API and orchestration surfaces still only know `governance_reject`, not status transition

So the current narrow gap is not:

- status transition semantics
- status transition artifact/ledger schemas
- CLI formal surface

It is:

- there is still no worker-owned on-demand formal trigger for status transition
- `BootstrapWorkerApp` cannot materialize the transition as a governance on-demand run
- worker CLI cannot run the transition through the existing orchestration snapshot envelope

Project-phase note:

- domain: `M5 governance`
- change type: `closure / worker formal trigger baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add one worker-owned on-demand owner:
  - `run_governance_status_transition_on_demand(...)`
- add one new worker mode:
  - `governance_status_transition`
- wire the new mode to the existing runtime owner:
  - `run_governance_status_transition(...)`
- reuse the existing on-demand orchestration pattern already used by reject execution
- add focused worker and governance-executor regressions

Excluded:

- no change to runtime semantics
- no change to transition artifact or ledger schemas
- no change to governance CLI surface
- no API adoption
- no router mode expansion
- no orchestrator scheduled config adoption
- no downstream consumer migration
- no `M6`

## 3. Existing Evidence

### 3.1 Runtime Owner Already Exists

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py)
- [test_m5_governance_status_transition.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_status_transition.py)

shows that:

- `run_governance_status_transition(...)` already exists
- the runtime already enforces persisted reject-proof consumption
- the runtime already materializes independent transition artifact and ledger outputs

So this slice must not redesign the runtime.

### 3.2 CLI Formal Surface Already Exists

Current repository evidence in:

- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L71-L169)
- [test_m5_governance_cli.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_cli.py#L144-L584)

shows that:

- governance CLI already exposes `status-transition`
- parser coverage and persisted-write coverage already exist

So the missing owner has moved below the CLI layer.

### 3.3 Worker Already Has A Complete Reject On-Demand Pattern

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L600-L670)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L850-L938)
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1656-L1782)

shows that:

- `BootstrapWorkerApp.run_governance_reject_on_demand(...)` already exists
- worker parser already supports `--mode governance_reject`
- worker main already validates `source_run_id` and `validation_id`
- focused worker tests already lock the on-demand snapshot contract

This is the strongest evidence for choosing a symmetric worker slice next.

### 3.4 Governance Executor Pattern Already Exists For Reject

Current repository evidence in:

- [test_m5_governance_orchestrator_fit.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_orchestrator_fit.py#L145-L599)

shows that:

- there is already a governance executor regression carrier for reject execution
- on-demand `PlannedTask` and `OnDemandTaskRequest` already support the exact argument shape we need:
  - `source_run_id`
  - `validation_id`

So the new worker slice can follow the same owner boundary without inventing a new test carrier.

### 3.5 API Is Still Wider Than Necessary

Current repository evidence in:

- [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2574-L2639)
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1341-L1367)
- [test_http_smoke.py](file:///Users/mac/NeoTrade3/tests/integration/test_http_smoke.py#L223-L329)

shows that:

- API currently only accepts `daily` and `governance_reject`
- API currently dispatches only to `run()` or `run_governance_reject_on_demand()`
- HTTP smoke only covers reject as the governance special mode

So API adoption is real work, but it is strictly wider than the worker gap.

## 4. Approach Options

### Option A: Add Worker On-Demand Trigger First (Recommended)

- add `BootstrapWorkerApp.run_governance_status_transition_on_demand(...)`
- add `--mode governance_status_transition`
- add worker CLI branch for that mode
- add symmetric worker and governance-executor tests

Pros:

- smallest truthful owner for the current missing trigger
- mirrors the already-established reject execution pattern
- keeps API and orchestration surfaces unchanged
- preserves the current narrow-step progression

Cons:

- API consumers still cannot trigger it yet

### Option B: Add API Adoption First

- extend `/api/orchestration/run` to accept a new governance mode before worker formalization

Pros:

- would give HTTP access sooner

Cons:

- wider than the current missing owner
- still needs the worker on-demand owner underneath
- would mix worker completion with router/main/API smoke changes

### Option C: Add Orchestrator Scheduled Adoption First

- add a formal scheduled governance status-transition task to config/orchestrator

Pros:

- useful later for full system automation

Cons:

- requires wider lifecycle decisions
- current repository does not yet have the worker on-demand surface that such scheduling should sit on
- violates the “smallest owner first” rule

Decision:

- choose Option A

## 5. Boundary Decisions

Frozen decisions for this slice:

- new owner layer: `apps/worker/main.py`
- new mode name: `governance_status_transition`
- runtime owner remains:
  - `neotrade3.governance.runtime:run_governance_status_transition`
- input shape remains:
  - `source_run_id`
  - `validation_id`
- task remains governance-only and on-demand

This slice must not:

- change API mode validation
- change API dispatch
- change `daily_master_orchestrator.json`
- auto-chain reject and status transition together
- infer transition without persisted reject proof

## 6. Design

### 6.1 Production Ownership

Primary production owner:

- `apps/worker/main.py`

Focused test owners:

- `tests/unit/test_bootstrap_skeleton.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Files intentionally not modified:

- `apps/api/main.py`
- `apps/api/router.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`

### 6.2 New Worker Owner

Recommended new owner:

- `BootstrapWorkerApp.run_governance_status_transition_on_demand(...)`

Recommended signature:

- `target_date`
- `source_run_id`
- `validation_id`
- `requested_by`
- `dry_run`

Why this shape is correct:

- it matches the reject on-demand owner shape
- it matches the transition runtime input shape
- it avoids adding any new inferred or synthetic identifiers

### 6.3 On-Demand Planned Task Shape

Recommended `OnDemandTaskItem`:

- `task_id`: `governance.status_transition`
- `phase`: `OrchestrationPhase.GOVERNANCE`
- `entrypoint`: `neotrade3.governance.runtime:run_governance_status_transition`
- `args_template`:
  - `source_run_id`
  - `validation_id`
- `outputs`:
  - `governance_status_transition_artifact`
  - `governance_status_transition_ledger`

Why a distinct task id is required:

- reject execution and status transition are different persisted actions
- the task ledger should not present transition materialization as reject execution
- this preserves audit clarity inside orchestration snapshots

### 6.4 Worker CLI Surface

Recommended parser extension in `apps/worker/main.py`:

- extend `--mode` choices with:
  - `governance_status_transition`
- reuse:
  - `--source-run-id`
  - `--validation-id`

Recommended `main()` branch:

- if mode is `governance_status_transition`
  - require both `source_run_id` and `validation_id`
  - call `run_governance_status_transition_on_demand(...)`

This slice should keep the CLI summary envelope unchanged:

- `status`
- `target_date`
- `summary`
- `write_outputs`

Why that is preferred:

- worker main is currently a stable bootstrap-style envelope
- changing output shape here would widen the slice beyond trigger formalization

### 6.5 Snapshot Contract

Recommended snapshot shape mirrors reject on-demand:

- `status`
- `target_date`
- `orchestration`
  - `plan`
  - `task_results`
  - `run_ledger`
  - `task_ledger`
- `summary`
  - `planned_task_count`
  - `executed_task_count`
  - `ok_task_count`

This slice should not add a new top-level special-case payload.

### 6.6 Error Behavior

Worker-owned deterministic failures should remain pass-through:

- missing `source_run_id`
- missing `validation_id`
- missing reject proof in runtime
- missing mapped blocker or attention item

This slice must not suppress or rewrite runtime semantic failures.

## 7. Testing Strategy

### 7.1 Worker-Focused Tests

Extend:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. `BootstrapWorkerApp.run_governance_status_transition_on_demand(...)`
   - materializes outputs on the happy path
2. worker `main()` in `governance_status_transition` mode
   - returns `0` for ok snapshot
3. worker `main()` in `governance_status_transition` mode
   - returns non-zero for failed snapshot

Why this carrier is correct:

- it already owns reject on-demand worker coverage
- it already has governance input preparation helpers

### 7.2 Governance Executor-Focused Tests

Extend:

- `tests/unit/test_m5_governance_orchestrator_fit.py`

Required coverage:

1. dry-run via `execute_run_plan`
2. persisted outputs via `execute_run_plan`
3. failure for missing validation or missing reject proof

Why this carrier is correct:

- it already owns governance executor parity tests
- it already locks the on-demand `PlannedTask` and `args_template` pattern

### 7.3 Excluded Tests

Do not add in this slice:

- API router tests
- API main tests
- HTTP smoke for a new API mode
- scheduled orchestrator config tests

## 8. Verification

Minimum verification for this design slice:

- self-review for ambiguity, placeholder, and scope drift
- `git diff --check`

Implementation verification is intentionally deferred to the later plan and execution slice.

## 9. Dual-Axis Audit

### 9.1 M-Axis

- `M5`: yes
  - this slice adds the missing worker-owned formal trigger for an existing governance runtime
- `M1-M4`: no
  - no upstream semantic change
- `M6`: no
  - no delivery/observability integration

### 9.2 G-Axis

- `G5`: yes
  - improves governance operability by making status transition runnable through the worker on-demand path
- `G1/G2/G3/G4/G6`: no direct expansion

## 10. Non-Claims

This slice does not claim:

- API already supports status transition mode
- scheduled orchestration already supports status transition
- reject execution and status transition should be auto-chained
- any runtime semantic or artifact schema change is required

It only defines the next smallest truthful owner:

- `M5 governance status transition worker/on-demand trigger baseline`
