Status: active
Owner: lowfreq / api / worker / governance
Scope: Narrow `M5 reject execution API trigger baseline` slice for reusing `/api/orchestration/run` as the formal external POST surface
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution API Trigger Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- reject runtime exists
- worker on-demand governance reject trigger exists
- API already owns one formal orchestration POST surface: `/api/orchestration/run`

But one gap remains:

- external callers can only trigger the daily orchestration flow through API
- governance reject execution still has no formal API-owned POST trigger

So the narrow next problem is:

- how to expose the already-existing worker `governance_reject` trigger through API
- how to do so without adding a parallel endpoint or changing the runtime owner

Project-phase note:

- domain: `M5 governance`
- change type: `API trigger baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- extend `/api/orchestration/run` with one explicit `mode`
- add API-service branching for `governance_reject`
- add focused service/router tests for the new payload mode

Excluded:

- no new API route
- no governance runtime changes
- no daily orchestration config changes
- no auto `validation_id` selection
- no approval flow
- no `M6`

## 3. Existing Evidence

- existing service owner only drives daily worker flow: [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1323-L1417)
- existing router already treats `/api/orchestration/run` as the formal POST entrypoint: [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2555-L2604)
- existing worker now owns a dedicated on-demand governance reject trigger: [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L598-L668)
- existing HTTP tests only cover the daily orchestration POST payload: [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L3789-L3835)

So the missing owner is not execution. The missing owner is an API-level trigger branch.

## 4. Approach

Recommended option:

- reuse `/api/orchestration/run`
- add request field `mode`
- keep default `mode="daily"`
- add `mode="governance_reject"` that requires:
  - `source_run_id`
  - `validation_id`

Reasons:

- preserves one canonical orchestration POST surface
- avoids route proliferation
- keeps the new path thin and explicit
- preserves backward compatibility for current daily callers

## 5. Design

### 5.1 Service Branch

Extend `BootstrapApiService.orchestration_run_view(...)` to accept:

- `mode`
- optional `source_run_id`
- optional `validation_id`

Behavior:

- `daily`:
  - retain current behavior unchanged
- `governance_reject`:
  - call `worker_app.run_governance_reject_on_demand(...)`
  - do not materialize lab runs
  - still write the standard orchestration run ledger/artifact envelope under `var/orchestration_runs/<date>/...`

### 5.2 Router Contract

Request body for `/api/orchestration/run` gains:

- optional `mode`

Validation rules:

- unsupported mode -> `invalid_mode`
- `governance_reject` without `source_run_id` -> `invalid_source_run_id`
- `governance_reject` without `validation_id` -> `invalid_validation_id`
- `daily` keeps current `publish_succeeded` behavior

### 5.3 Why This Stays Narrow

This slice does not introduce:

- a dedicated `/api/governance/reject/run`
- a general manual-task API
- automatic governance target selection

It only promotes one existing worker trigger into the already-existing orchestration POST surface.

## 6. Testing Strategy

Focused tests should lock:

1. service `governance_reject` mode calls the worker on-demand reject owner
2. router accepts the new payload and returns `200`
3. router rejects missing `source_run_id`
4. router rejects missing `validation_id`
5. legacy daily orchestration POST remains unchanged

## 7. Acceptance Criteria

- `/api/orchestration/run` supports explicit `mode="governance_reject"`
- API service delegates to `worker_app.run_governance_reject_on_demand(...)`
- orchestration POST remains backward compatible for current daily callers
- focused service/router tests pass

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in `M5` trigger exposure under the API owner
- `G1-G6` target mapping:
  - this is the minimum `G2` external trigger closure after worker trigger baseline
- new contract introduced:
  - `/api/orchestration/run` request field `mode`
  - `mode="governance_reject"` request payload branch
- boundaries not touched:
  - no new route namespace
  - no governance runtime rewrite
  - no daily config mutation
  - no auto validation selection
  - no approval flow
  - no `M6`
