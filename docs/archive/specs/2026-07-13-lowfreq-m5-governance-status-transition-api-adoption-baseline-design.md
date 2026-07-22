Status: active
Owner: lowfreq / governance / api
Scope: Narrow `M5 governance status transition API adoption baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition API Adoption Baseline Design

Date: 2026-07-13

## 1. Goal

This slice continues the current `M5 governance` mainline after:

- status transition persistence/runtime baseline
- status transition CLI baseline
- status transition worker/on-demand trigger baseline

Repository evidence now shows:

- `run_governance_status_transition(...)` already exists as the runtime owner
- `BootstrapWorkerApp.run_governance_status_transition_on_demand(...)` already exists as the worker-owned trigger
- the worker CLI already supports `governance_status_transition`
- the API surface still only accepts:
  - `daily`
  - `governance_reject`
- the API dispatch still only routes governance special-mode runs to:
  - `run_governance_reject_on_demand(...)`
- HTTP smoke still only covers reject as the governance-specific orchestration mode

So the current narrow gap is not:

- status transition semantics
- worker trigger ownership
- transition artifact or ledger schema

It is:

- there is still no API-visible mode for governance status transition
- `/api/orchestration/run` cannot trigger the existing worker-owned transition path
- API contract coverage and HTTP smoke have not yet been extended to this mode

Project-phase note:

- domain: `M5 governance`
- change type: `closure / API adoption baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add one API-visible orchestration mode:
  - `governance_status_transition`
- extend router validation so `/api/orchestration/run` accepts:
  - `source_run_id`
  - `validation_id`
  for the new mode
- extend API dispatch so `BootstrapApiService.orchestration_run_view(...)` routes the new mode to:
  - `BootstrapWorkerApp.run_governance_status_transition_on_demand(...)`
- add focused unit and HTTP smoke regressions for the new mode

Excluded:

- no change to governance runtime semantics
- no change to worker-owned status-transition trigger semantics
- no change to transition artifact or ledger schemas
- no change to governance CLI behavior
- no change to scheduled orchestrator config
- no downstream UI or docs adoption
- no `M6`

## 3. Existing Evidence

### 3.1 Worker Trigger Already Exists

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py)
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py)

shows that:

- `run_governance_status_transition_on_demand(...)` already exists
- worker CLI already supports `governance_status_transition`
- worker-focused tests already lock the status-transition trigger shape

So this slice must not redesign worker behavior.

### 3.2 API Service Still Dispatches Governance Else-Branch To Reject

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1323-L1367)

shows that:

- `orchestration_run_view(...)` normalizes the mode
- `daily` stays on the trading-day and lab-materialization path
- every non-daily governance branch currently dispatches to:
  - `self.worker_app.run_governance_reject_on_demand(...)`

So status transition cannot yet be reached from the API owner.

### 3.3 Router Validation Still Only Knows Daily And Reject

Current repository evidence in:

- [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2574-L2658)

shows that:

- valid modes are currently limited to:
  - `daily`
  - `governance_reject`
- `source_run_id` and `validation_id` are only enforced for `governance_reject`

So the current API contract itself blocks the new mode before service dispatch can run.

### 3.4 Existing Test Carriers Already Match The Needed Scope

Current repository evidence in:

- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1231-L1317)
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L2018-L2115)
- [test_http_smoke.py](file:///Users/mac/NeoTrade3/tests/integration/test_http_smoke.py#L223-L329)

shows that:

- there is already one API-service unit carrier for governance reject dispatch
- there is already one router validation carrier for governance reject
- there is already one HTTP smoke round-trip carrier for governance reject

So the next API slice can stay symmetric and narrow without introducing new test owners.

## 4. Approach Options

### Option A: Add API Adoption On Top Of Existing Worker Trigger (Recommended)

- extend router mode validation to accept `governance_status_transition`
- extend API service dispatch to call the existing worker owner
- add one service unit test, one router validation group, and one HTTP smoke test

Pros:

- smallest truthful owner after the worker trigger slice
- reuses the already-implemented worker formal trigger
- closes the API gap without widening into scheduling or docs
- keeps runtime and worker semantics unchanged

Cons:

- scheduled orchestrator adoption still remains for later

### Option B: Jump To Scheduled Orchestrator Adoption

- add config/orchestrator scheduling before API parity is complete

Pros:

- would move toward full automation

Cons:

- wider lifecycle decision
- skips the now-obvious API contract gap
- mixes config and runtime-trigger surfaces in one slice

### Option C: Fold API Adoption Into A Larger Operations Or Docs Slice

- combine API mode support with docs or broader operational surfaces

Pros:

- fewer later docs follow-ups

Cons:

- widens the current cut beyond the missing owner
- obscures whether API contract closure itself is sound

Decision:

- choose Option A

## 5. Boundary Decisions

Frozen decisions for this slice:

- new API mode name:
  - `governance_status_transition`
- API-required arguments remain:
  - `source_run_id`
  - `validation_id`
- API service owner remains:
  - `BootstrapApiService.orchestration_run_view(...)`
- router owner remains:
  - `BootstrapApiRouter.dispatch_post(...)`
- worker owner remains:
  - `BootstrapWorkerApp.run_governance_status_transition_on_demand(...)`

This slice must not:

- change worker output envelope
- change governance status-transition task ids or artifact refs
- change orchestration run ledger schema
- change runtime preconditions around persisted reject proof
- add new query params, aliases, or inferred ids

## 6. Design

### 6.1 Production Ownership

Primary production owners:

- `apps/api/main.py`
- `apps/api/router.py`

Focused test owners:

- `tests/unit/test_bootstrap_skeleton.py`
- `tests/integration/test_http_smoke.py`

Files intentionally not modified:

- `apps/worker/main.py`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

### 6.2 Router Contract

Recommended router extension in `apps/api/router.py`:

- extend accepted `mode` values with:
  - `governance_status_transition`
- reuse the existing validation shape for governance special modes:
  - require non-empty `source_run_id`
  - require non-empty `validation_id`

Why this is correct:

- the new API mode has the same required input shape as reject
- it preserves the existing reject contract rather than inventing a second validation model
- it keeps all mode validation centralized in the router owner

### 6.3 API Service Dispatch

Recommended dispatch extension in `apps/api/main.py`:

- keep `daily` on the existing trading-day and lab-materialization branch
- keep `governance_reject` on:
  - `self.worker_app.run_governance_reject_on_demand(...)`
- add `governance_status_transition` branch on:
  - `self.worker_app.run_governance_status_transition_on_demand(...)`

Why a dedicated branch is required:

- the current non-daily else-branch conflates all governance modes with reject
- reject execution and status transition are separate persisted actions
- orchestration run artifacts must report the true mode that was invoked

### 6.4 API Snapshot And Persistence Contract

This slice keeps the existing API response and orchestration-run persistence envelope unchanged:

- `_meta`
- `orchestrator_run`
- `orchestrator_result`
- stored run ledger payload
- stored run artifact payload

The only intended delta is:

- `mode` may now equal `governance_status_transition`
- the first task in `tasks`/`task_results` may now equal:
  - `governance.status_transition`

This slice must not add a new top-level special-case response payload.

### 6.5 Error Behavior

Router-owned validation failures remain deterministic:

- missing `source_run_id`
- missing `validation_id`
- invalid `mode`

Service-owned and worker-owned failures remain pass-through:

- missing persisted reject proof
- missing mapped blocker or attention item
- any worker/runtime failure that already surfaces through the snapshot envelope

This slice must not rewrite runtime semantic failures into new API-specific meanings.

## 7. Testing Strategy

### 7.1 API Service Unit Coverage

Extend:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. `BootstrapApiService.orchestration_run_view(...)`
   - uses `run_governance_status_transition_on_demand(...)`
2. governance status-transition mode
   - does not require trading day
3. governance status-transition mode
   - does not materialize lab runs
4. stored orchestration ledger/artifact
   - persist `mode="governance_status_transition"`
   - persist task id `governance.status_transition`

### 7.2 Router Coverage

Extend:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. router accepts `/api/orchestration/run` with:
   - `mode="governance_status_transition"`
2. router rejects missing `source_run_id`
3. router rejects missing `validation_id`

Why this carrier is correct:

- the reject API contract already lives here
- the new mode is symmetric, so this is the narrowest truthful extension

### 7.3 HTTP Smoke Coverage

Extend:

- `tests/integration/test_http_smoke.py`

Required coverage:

1. POST `/api/orchestration/run`
   - with `mode="governance_status_transition"`
2. GET orchestration run detail
3. GET orchestration run download
4. stored orchestration ledger/artifact
   - keep the new mode and task id

Why this carrier is correct:

- there is already one reject round-trip
- the new status-transition path should prove parity without adding a second integration harness

### 7.4 Excluded Tests

Do not add in this slice:

- worker-focused tests
- governance runtime tests
- scheduled orchestrator config tests
- operations runbook updates

## 8. Verification

Minimum verification for this design slice:

- self-review for ambiguity, placeholder, and scope drift
- `git diff --check`

Implementation verification is intentionally deferred to the later plan and execution slice.

## 9. Dual-Axis Audit

### 9.1 M-Axis

- `M5`: yes
  - this slice closes the API-visible trigger layer for an already-existing governance action
- `M1-M4`: no
  - no upstream semantic change
- `M6`: no
  - no delivery or observability expansion

### 9.2 G-Axis

- `G5`: yes
  - improves governance operability by exposing the existing transition trigger through the API contract
- `G1/G2/G3/G4/G6`: no direct expansion

## 10. Non-Claims

This slice does not claim:

- scheduled orchestration already supports status transition
- runtime semantics need to change
- worker trigger semantics need to change
- UI or docs already expose the new mode

It only defines the next smallest truthful owner:

- `M5 governance status transition API adoption baseline`
