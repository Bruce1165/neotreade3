Status: active
Owner: lowfreq / governance / operations-docs
Scope: Implementation plan for the narrow `M5 reject execution operations/docs baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution Operations/Docs Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-operations-docs-baseline-design.md`

## 1. Goal

This slice only makes the already-existing reject execution entrypoints operable from the formal runbook.

This slice must:

- document the worker reject mode
- document the API reject mode
- state the required request/CLI fields precisely
- document the dedicated reject persistence namespace

This slice explicitly does not:

- change production code
- add new entrypoints
- clean up the broader user manual

## 2. File Boundary

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-operations-docs-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-operations-docs-baseline-plan.md`

Focused docs file:

- `docs/operations/bootstrap_runbook.md`

Files intentionally not modified:

- `docs/user_manual.md`
- `apps/api/main.py`
- `apps/api/router.py`
- `apps/worker/main.py`
- `neotrade3/governance/*`

## 3. Execution Steps

### M5DOC-S1: Add worker reject runbook section

Modify:

- `docs/operations/bootstrap_runbook.md`

Implementation:

1. add a new worker subsection for `--mode governance_reject`
2. state the hard requirement for `--source-run-id` and `--validation-id`
3. provide one concrete command example
4. describe `--dry-run` behavior for this mode

### M5DOC-S2: Add API reject runbook section

Modify:

- `docs/operations/bootstrap_runbook.md`

Implementation:

1. add a new API subsection for `POST /api/orchestration/run`
2. provide one concrete `curl` example with:
   - `date`
   - `mode`
   - `source_run_id`
   - `validation_id`
   - `requested_by`
3. document optional `dry_run`
4. state that this path is on-demand rather than scheduled daily orchestration

### M5DOC-S3: Add persistence and boundary notes

Modify:

- `docs/operations/bootstrap_runbook.md`

Implementation:

1. document the dedicated reject artifact path
2. document the dedicated reject ledger path
3. clarify that these outputs are separate from bootstrap `orchestration_runs`
4. clarify that the runbook change does not imply new production scheduling ownership

### M5DOC-S4: Minimum verification

Run at minimum:

- `python3 -m py_compile apps/worker/main.py apps/api/router.py apps/api/main.py`
- `python3 -m py_compile tests/integration/test_http_smoke.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: documenting behavior that is not actually implemented**
  - Guardrail: every statement must map to current code or test evidence
- **Risk: widening into stale user-manual cleanup**
  - Guardrail: only modify `bootstrap_runbook.md`
- **Risk: implying scheduled production ownership**
  - Guardrail: explicitly label reject execution as on-demand
- **Risk: inventing automatic parameter derivation**
  - Guardrail: explicitly state that `source_run_id` and `validation_id` must be supplied

## 5. Done Criteria

- the runbook documents both reject entrypoints with concrete examples
- the runbook states the required parameters and persistence locations accurately
- no production files are modified
- minimum verification completes without diff-format issues

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in operations documentation supporting `M5`
- `G1-G6` target mapping:
  - this hardens `G2` by moving reject trigger knowledge from spec/test-only evidence into the formal runbook
- new contract introduced:
  - operator-facing documentation for the existing reject execution flow
- boundaries not touched:
  - no API behavior changes
  - no worker/runtime rewrite
  - no dashboard work
  - no `docs/user_manual.md` cleanup
  - no `M4`
  - no `M6`
