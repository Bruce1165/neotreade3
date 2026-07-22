Status: active
Owner: lowfreq / api / integration-tests / governance
Scope: Implementation plan for the narrow `M5 reject execution HTTP smoke baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution HTTP Smoke Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-http-smoke-baseline-design.md`

## 1. Goal

This slice only adds one HTTP-level regression anchor for the already-existing governance reject API mode.

This slice must:

- add one integration smoke test for `POST /api/orchestration/run`
- exercise `mode="governance_reject"` through the real handler stack
- verify ledger/artifact/readback behavior at HTTP level

This slice explicitly does not:

- modify production API behavior
- execute real governance runtime
- add documentation changes

## 2. File Boundary

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-http-smoke-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-http-smoke-baseline-plan.md`

Focused test file:

- `tests/integration/test_http_smoke.py`

Files intentionally not modified:

- `apps/api/main.py`
- `apps/api/router.py`
- `apps/worker/main.py`
- `neotrade3/governance/*`

## 3. Execution Steps

### M5SMOKE-S1: Add governance reject HTTP smoke

Modify:

- `tests/integration/test_http_smoke.py`

Implementation:

1. prepare temporary orchestration ledger/artifact directories
2. stub `service.worker_app.run_governance_reject_on_demand(...)`
3. override `_orchestration_run_paths(...)`
4. POST `/api/orchestration/run` with:
   - `date`
   - `mode`
   - `source_run_id`
   - `validation_id`
   - `requested_by`
5. verify response payload, stored files, detail endpoint, and download endpoint

### M5SMOKE-S2: Minimum verification

Run at minimum:

- `python3 -m py_compile tests/integration/test_http_smoke.py`
- `python3 -m pytest tests/integration/test_http_smoke.py -k governance_reject`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: accidentally retest business runtime instead of HTTP contract**
  - Guardrail: stub `run_governance_reject_on_demand(...)`
- **Risk: over-expand into API behavior changes**
  - Guardrail: test file only
- **Risk: duplicate daily smoke behavior too broadly**
  - Guardrail: reuse the current daily smoke pattern and only assert the new mode-specific fields

## 5. Done Criteria

- one integration smoke covers `mode="governance_reject"`
- the smoke verifies stored ledger/artifact readback via HTTP
- verification passes with no production code changes

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in API integration verification supporting `M5`
- `G1-G6` target mapping:
  - this hardens `G2` by preventing silent regressions on the external reject trigger
- new contract introduced:
  - HTTP smoke regression for `/api/orchestration/run` `mode="governance_reject"`
- boundaries not touched:
  - no production route changes
  - no governance runtime rewrite
  - no worker feature expansion
  - no docs updates
  - no `M6`
