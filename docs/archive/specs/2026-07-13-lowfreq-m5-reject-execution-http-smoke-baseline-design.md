Status: active
Owner: lowfreq / api / integration-tests / governance
Scope: Narrow `M5 reject execution HTTP smoke baseline` slice for the existing `/api/orchestration/run` governance reject branch
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution HTTP Smoke Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- `worker` reject trigger exists
- `/api/orchestration/run` now supports `mode="governance_reject"`
- unit tests cover the service branch and router validation

But one gap remains:

- `tests/integration/test_http_smoke.py` still only covers the daily orchestration POST path
- there is no HTTP-level regression anchor proving the new governance reject API mode survives the real handler stack

So the narrow next problem is:

- add one HTTP smoke regression for `mode="governance_reject"`
- keep the slice focused on API contract survivability, not runtime semantics already covered elsewhere

Project-phase note:

- domain: `M5 governance`
- change type: `HTTP smoke baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add one integration smoke test for `POST /api/orchestration/run` with `mode="governance_reject"`
- assert the stored orchestration ledger/artifact carry `mode="governance_reject"`
- assert the detail/download endpoints can read back the written result

Excluded:

- no production code changes unless a test-only hook is strictly required
- no governance runtime changes
- no new API routes
- no new worker features
- no docs updates in this slice
- no `M6`

## 3. Existing Evidence

- current daily HTTP smoke exists and verifies the end-to-end orchestration POST path: [test_http_smoke.py](file:///Users/mac/NeoTrade3/tests/integration/test_http_smoke.py#L150-L220)
- the API service now persists `mode` in the orchestration ledger and artifact envelope: [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1382-L1411)
- router now validates and forwards `mode="governance_reject"`: [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2555-L2639)

So the missing owner is not service logic. The missing owner is the integration smoke layer.

## 4. Approach

Recommended option:

- mirror the existing daily HTTP smoke structure
- monkeypatch `service.worker_app.run_governance_reject_on_demand(...)` with a fast stub
- reuse the same embedded HTTP server and orchestration ledger/artifact path overrides

Reasons:

- keeps the test focused on HTTP handler + router + service envelope behavior
- avoids duplicating governance runtime semantics already covered in unit tests
- keeps the smoke test fast and deterministic

## 5. Design

### 5.1 Test Shape

Add one new integration test:

- boot the in-process HTTP server
- POST `/api/orchestration/run` with:
  - `date`
  - `mode="governance_reject"`
  - `source_run_id`
  - `validation_id`
  - `requested_by`
- verify:
  - `200 OK`
  - response `_meta.status == "ok"`
  - `orchestrator_run.mode == "governance_reject"`
  - stored ledger/artifact exist
  - stored ledger/artifact include `mode == "governance_reject"`
  - `GET /api/orchestration/runs/<date>` and `/download` can read back the same payload

### 5.2 Why This Stays Narrow

This slice does not:

- execute real governance rejection runtime
- revalidate worker business semantics
- widen into broader API documentation work

It only gives the new API mode one HTTP-level survivability anchor.

## 6. Testing Strategy

Run:

- `python3 -m py_compile tests/integration/test_http_smoke.py`
- `python3 -m pytest tests/integration/test_http_smoke.py -k governance_reject`
- `git diff --check`

## 7. Acceptance Criteria

- `tests/integration/test_http_smoke.py` covers `mode="governance_reject"`
- the HTTP smoke verifies stored orchestration ledger/artifact readback
- the test passes without touching the real governance runtime

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in `M5` API integration verification ownership
- `G1-G6` target mapping:
  - this strengthens `G2` by adding the first HTTP-level regression anchor for the external reject trigger
- new contract introduced:
  - one integration smoke regression for `/api/orchestration/run` `mode="governance_reject"`
- boundaries not touched:
  - no production route changes
  - no governance runtime rewrite
  - no worker feature expansion
  - no docs updates
  - no `M6`
