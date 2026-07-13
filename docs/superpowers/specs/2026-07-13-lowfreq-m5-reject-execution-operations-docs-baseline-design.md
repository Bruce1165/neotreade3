Status: active
Owner: lowfreq / governance / operations-docs
Scope: Narrow `M5 reject execution operations/docs baseline` slice for the existing worker and API entrypoints
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution Operations/Docs Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- `worker` already supports `--mode governance_reject`
- `POST /api/orchestration/run` already supports `mode="governance_reject"`
- integration and unit tests already cover the required request fields and HTTP round trip

But the formal operator-facing runbook still does not explain how to invoke this path.

So the narrow next problem is:

- document the existing reject execution entrypoints in the operations runbook
- keep the slice strictly in formal operator docs
- avoid widening into more API/runtime work that is already implemented

Project-phase note:

- domain: `M5 governance`
- change type: `operations/docs baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add one runbook subsection for `worker --mode governance_reject`
- add one runbook subsection for `POST /api/orchestration/run` with `mode="governance_reject"`
- document the required fields:
  - `source_run_id`
  - `validation_id`
  - `requested_by`
  - `dry_run`
- document the currently materialized reject artifact/ledger locations

Excluded:

- no API behavior changes
- no worker/runtime changes
- no dashboard work
- no `docs/user_manual.md` edits in this slice
- no `M4` or `M6`

## 3. Existing Evidence

- the runbook currently documents worker daily usage but not reject mode: [bootstrap_runbook.md](file:///Users/mac/NeoTrade3/docs/operations/bootstrap_runbook.md#L73-L122)
- the runbook currently documents read-only API endpoints but not `POST /api/orchestration/run`: [bootstrap_runbook.md](file:///Users/mac/NeoTrade3/docs/operations/bootstrap_runbook.md#L123-L234)
- the worker parser already exposes `--mode governance_reject`, `--source-run-id`, and `--validation-id`: [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L848-L909)
- the router already validates `mode="governance_reject"` and requires non-empty `source_run_id` and `validation_id`: [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2555-L2654)
- the API service already dispatches the reject path and persists `mode` into orchestration envelopes: [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1341-L1434)
- reject execution persistence already uses a dedicated namespace:
  - artifact writer: [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L92-L94)
  - ledger writer: [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L162-L173)
- HTTP smoke already proves the API example shape end-to-end: [test_http_smoke.py](file:///Users/mac/NeoTrade3/tests/integration/test_http_smoke.py#L223-L329)

So the missing owner is not implementation. The missing owner is the formal operations runbook.

## 4. Approach

Recommended option:

- update only `docs/operations/bootstrap_runbook.md`
- add the reject flow beside the already-documented daily flow
- keep `docs/user_manual.md` untouched because it is broader product documentation and would widen the slice

Reasons:

- `bootstrap_runbook.md` is the current operator-facing owner for local execution and API usage
- this keeps the slice narrow and evidence-based
- it avoids mixing governance operations with broader end-user manual cleanup

## 5. Design

### 5.1 Worker subsection

Add one worker subsection that states:

- reject mode is an explicit on-demand governance path
- it requires both `--source-run-id` and `--validation-id`
- it does not derive `validation_id` automatically
- `--dry-run` remains supported for non-persistent verification

Document one concrete command example using:

- `./.venv/bin/python -m apps.worker.main`
- `--mode governance_reject`
- `--date`
- `--source-run-id`
- `--validation-id`

### 5.2 API subsection

Add one API subsection that states:

- `POST /api/orchestration/run` supports `mode="governance_reject"`
- required request fields are `date`, `mode`, `source_run_id`, `validation_id`
- `requested_by` is optional but should be explicitly populated for auditability
- `dry_run` is optional and defaults to `false`

Document one concrete `curl` example matching the validated request shape.

### 5.3 Persistence notes

Document the currently materialized reject outputs as operator-facing evidence:

- `var/artifacts/governance_rejections/<validation_id>/governance_reject_execution.json`
- `var/ledgers/governance_rejections/<validation_id>/governance_reject_execution_run.json`

Also state the boundary:

- these reject outputs are separate from bootstrap `orchestration_runs`
- the reject path is on-demand and should not be described as a scheduled daily task

## 6. Testing Strategy

Run:

- `python3 -m py_compile apps/worker/main.py apps/api/router.py apps/api/main.py`
- `python3 -m py_compile tests/integration/test_http_smoke.py`
- `git diff --check`

Rationale:

- this slice changes docs only, so minimum verification is structural and truth-source alignment against current code/test evidence

## 7. Acceptance Criteria

- `bootstrap_runbook.md` documents the worker reject entrypoint
- `bootstrap_runbook.md` documents the API reject entrypoint
- the runbook lists the required parameters without inventing derived behavior
- the runbook points to the dedicated reject artifact/ledger namespace
- `docs/user_manual.md` remains untouched in this slice

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in `M5` operations documentation ownership and does not cross into implementation layers
- `G1-G6` target mapping:
  - this strengthens `G2` by making the already-implemented external reject trigger operable without relying on specs/tests as the only truth source
- new contract introduced:
  - formal operator-facing runbook coverage for existing reject execution entrypoints
- boundaries not touched:
  - no API behavior changes
  - no worker/runtime rewrite
  - no dashboard work
  - no `docs/user_manual.md` cleanup
  - no `M4`
  - no `M6`
