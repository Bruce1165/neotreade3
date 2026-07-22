Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report row projection extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Row Projection Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-row-projection-design.md`

## 1. Goal

This plan covers only the next narrow report-prep slice after the attribution primary reason decision extraction.

This slice only handles:

- the pure report-row projection used inline in `_analyze_topk(...)`
- reuse of one dedicated analysis owner for row payload assembly
- direct owner-focused tests plus minimum nearby regression verification

The goal is to:

- remove the inline row dictionary from the script
- keep upstream fact preparation stable
- preserve the current row payload schema and coercion semantics exactly

This slice does not:

- rewrite `_extract_execution_reason(...)`
- rewrite signal pick summary logic
- rewrite trade window logic
- rewrite primary reason selection
- rewrite aggregate summary or markdown rendering

## 2. Starting Point

Current repository evidence shows:

- the script still owns the final row dictionary assembly after all facts have already been prepared
- upstream owners already exist for signal pick summary, reasoning, trade window, and aggregate summary
- the remaining row block is pure once scalar values and pass-through collections already exist

So the correct next slice is:

- extract only the final row projection
- keep all upstream preparation in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_report_row.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_report_row.py`

## 4. Execution Steps

### ARR-S1: Freeze observable row payload contract

Freeze the visible row behavior:

- the output field set stays unchanged
- field names stay unchanged
- numeric values continue to coerce through the current `int(...)` and `float(...)` boundaries
- strings continue to coerce through the current `str(... or "")` boundaries
- booleans continue to coerce through the current `bool(...)` boundaries
- `daily_audits` and `relevant_trades` remain pass-through collections

Completion check:

- no field is added, removed, renamed, or reinterpreted in this slice

### ARR-S2: Add the row projection owner

Create `neotrade3/analysis/attribution_report_row.py` with:

- `build_attribution_report_row(...) -> dict[str, Any]`

Implementation rules:

- use only prepared scalar values and pass-through collections
- do not call DB, engine, context, or orchestration helpers
- keep payload assembly independently understandable from the report script

Completion check:

- the row contract has one dedicated owner with no execution-time dependencies

### ARR-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- prepare the same values as today
- replace the inline row dictionary with one `build_attribution_report_row(...)` call
- keep `summary_counters[reason_bucket] += 1` in the script

Do not change:

- `signal_pick_summary`
- `trade_window`
- `primary_reason`
- `reason_bucket`
- aggregate summary call

Completion check:

- the script no longer owns the final inline row projection block

### ARR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_report_row.py`

Minimum owner cases:

- projects one full row with the current field set and coercions
- keeps `picked` independently sourced from `signal_pick_summary["picked"]`
- passes through `daily_audits` and `relevant_trades` unchanged

Completion check:

- the row payload contract has direct focused coverage

### ARR-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_report_row.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_report_row.py`
- `.venv/bin/python` inline smoke assertions for `build_attribution_report_row(...)`

Completion check:

- owner syntax validation passes
- row projection smoke assertions pass

### ARR-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-row-projection-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-row-projection-plan.md`
- `neotrade3/analysis/attribution_report_row.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_report_row.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- silently cleaning or collapsing payload fields that currently look redundant

Guard:

- freeze the exact field-to-source mapping from the current inline row dictionary

Risk 2:

- broadening into upstream orchestration responsibilities

Guard:

- pass only prepared values into the new owner and keep data preparation in the script

## 6. Success Criteria

This slice is complete when:

- the report row projection contract has one analysis owner
- the report script no longer owns the inline row dictionary
- row payload fields remain unchanged
- owner-focused tests pass
- syntax verification passes
