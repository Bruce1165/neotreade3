Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow attribution wave-segment contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Wave Segment Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-wave-segment-design.md`

## 1. Goal

This plan covers only the next narrow slice after the attribution artifact-payload extraction.

This slice only handles:

- the wave-segment result contract inside `_compute_wave_segment(...)`
- one analysis owner for the three status-specific payload builders
- owner-focused tests for those payloads

The goal is to:

- move the visible segment result contract out of the scorecard script
- keep sqlite reads, row selection, and window orchestration in the script
- preserve the current `missing_2025_prices` / `insufficient_history` / `ok` payloads exactly

This slice does not:

- rewrite `_analyze_topk(...)`
- rewrite row projection
- rewrite `_load_price_series(...)`
- move sqlite access into analysis

## 2. Starting Point

Current repository evidence shows:

- the scorecard script still owns the literal wave-segment payloads
- downstream code already consumes those payloads as a stable contract
- no existing analysis owner freezes this contract shape

So the correct next slice is:

- add one attribution-specific wave-segment contract owner
- keep the rest of `_compute_wave_segment(...)` as the script-side orchestrator

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_wave_segment.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_wave_segment.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-wave-segment-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-wave-segment-plan.md`

## 4. Execution Steps

### AWS-S1: Freeze the wave-segment result contract

Freeze the current payloads exactly as:

- missing prices:
  - `status="missing_2025_prices"`
  - `code=str(code)`
- insufficient history:
  - `status="insufficient_history"`
  - `code=str(code)`
  - `top_date=top_date.isoformat()`
  - `top_close=round(top_close, 4)`
- success:
  - `status="ok"`
  - `code=str(code)`
  - `segment_window_trading_days=int(lookback_trading_days)`
  - `start_date`
  - `start_close=round(..., 4)`
  - `top_date`
  - `top_close=round(..., 4)`
  - `segment_return_pct=round(..., 2)`
  - `segment_basis` literal unchanged

Completion check:

- no field is added, removed, renamed, or reworded

### AWS-S2: Add the analysis owner

Create:

- `neotrade3/analysis/attribution_wave_segment.py`

Public functions:

- `build_missing_wave_segment(...)`
- `build_insufficient_history_wave_segment(...)`
- `build_ok_wave_segment(...)`

Implementation rules:

- perform only payload projection and coercion
- do not query sqlite
- do not select rows
- do not mutate input row dictionaries

Completion check:

- the visible segment contract has one dedicated owner outside the script

### AWS-S3: Switch `_compute_wave_segment(...)`

In `_compute_wave_segment(...)`:

- keep `rows_2025` query unchanged
- keep `top_row` selection unchanged
- keep `_load_price_series(...)` usage unchanged
- keep `start_row` selection and `segment_return` math unchanged
- replace the three inline return payloads with owner calls

Do not change:

- function signature
- `lookback_trading_days` default
- downstream consumer call sites

Completion check:

- only the literal payload assembly leaves the script

### AWS-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_wave_segment.py`

Minimum cases:

- projects the current missing-prices payload
- projects the current insufficient-history payload with 4-decimal `top_close`
- projects the current success payload with 4-decimal prices, 2-decimal return, and unchanged basis text

Completion check:

- the contract is directly locked without broad integration coverage

### AWS-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_wave_segment.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_wave_segment.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_wave_segment.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against the owner functions

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### AWS-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-wave-segment-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-wave-segment-plan.md`
- `neotrade3/analysis/attribution_wave_segment.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_wave_segment.py`

Must exclude:

- changes to `_analyze_topk(...)`
- changes to row projection owners
- changes to reasoning owners
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally changing the literal `segment_basis` text or rounding rules

Guard:

- lock all visible fields and rounding behavior in owner-focused tests

Risk 2:

- widening into sqlite or window-loading extraction

Guard:

- keep data access and row selection in the script

## 6. Success Criteria

This slice is complete when:

- the wave-segment result contract has one analysis-side owner
- the script no longer owns the three literal return payloads
- sqlite and orchestration remain in the script
- downstream payload shape remains unchanged
- focused verification passes
- syntax verification passes
