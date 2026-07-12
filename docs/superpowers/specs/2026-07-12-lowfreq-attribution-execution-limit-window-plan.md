Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow execution limit-window extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Execution Limit Window Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-limit-window-design.md`

## 1. Goal

This plan covers only the next narrow slice after the execution fallback reason extraction.

This slice only handles:

- the three-bar `all_limit_up` window predicate in `_extract_execution_reason(...)`
- one analysis owner for that window predicate
- owner-focused tests for the window contract

The goal is to:

- move the inline one-price-board / limit-up loop out of the script
- reuse canonical trade-block semantics
- preserve current SQL window, limit-up threshold, one-price-only behavior, and fallback flow exactly

This slice does not:

- extract the whole `_extract_execution_reason(...)`
- move `positions_full`
- move `chase_blocked`
- change fallback reason ordering

## 2. Starting Point

Current repository evidence shows:

- the script still owns a local implementation of buy-side one-price-board limit-up detection
- the decision engine already owns the canonical per-bar limit-up blocking rule
- the attribution script only adds a consumer-specific “all bars in first 3 rows” fold

So the correct next slice is:

- add one attribution-side window helper
- delegate each bar’s limit-up check to `resolve_trade_block_reason(...)`

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_execution_limit_window.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Supporting dependency:

- `neotrade3/decision_engine/trade_block_reason.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_execution_limit_window.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-limit-window-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-limit-window-plan.md`

## 4. Execution Steps

### ELW-S1: Freeze the window predicate contract

Freeze the current observable rule as:

- empty rows => `False`
- only when every fetched bar hits buy-side `limit_up` block => `True`
- `one_price_only=True` requires one-price-board bars
- `limit_up_pct` remains parameterized

Completion check:

- no change to `LIMIT 3`
- no change to threshold semantics

### ELW-S2: Add the attribution-side owner

Create:

- `neotrade3/analysis/attribution_execution_limit_window.py`

Public function:

- `is_execution_limit_up_window(*, bars: list[dict[str, Any]], limit_up_pct: float, one_price_only: bool) -> bool`

Implementation rules:

- iterate normalized bar dicts only
- call `resolve_trade_block_reason(...)` per bar
- treat only `reason == "limit_up"` as a positive hit
- neutralize unrelated trade-block inputs:
  - `trade_value=0.0`
  - `block_on_limit_down=False`
  - `min_amount_cny=0.0`
  - `max_participation_rate=1.0`

Completion check:

- no one-price-board math remains duplicated in the new owner

### ELW-S3: Switch the script loop

In `_extract_execution_reason(...)`:

- keep the current SQL query and row fetch order
- normalize tuple rows into bar dict payloads
- replace the inline loop with one call to `is_execution_limit_up_window(...)`

Do not change:

- `positions_full`
- `chase_blocked`
- `resolve_execution_fallback_reason(...)`

Completion check:

- only the window predicate leaves the script

### ELW-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_execution_limit_window.py`

Minimum cases:

- empty bars => `False`
- all bars buy-side limit-up => `True`
- one non-limit-up bar => `False`
- non-one-price limit-up bar fails when `one_price_only=True`

Keep and rerun the script-level anchored cases in:

- `tests/unit/test_lowfreq_attribution_reasoning.py`

Completion check:

- owner contract is directly locked
- script observable behavior remains unchanged

### ELW-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_execution_limit_window.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_execution_limit_window.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_execution_limit_window.py tests/unit/test_lowfreq_attribution_reasoning.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against the new owner and the existing script anchor cases

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### ELW-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-limit-window-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-limit-window-plan.md`
- `neotrade3/analysis/attribution_execution_limit_window.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_execution_limit_window.py`

Must exclude:

- changes to `trade_block_reason.py`
- changes to fallback-reason owner logic
- changes to `positions_full` or `chase_blocked`
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally turning the helper into a general execution policy module

Guard:

- keep the owner focused on the attribution-side window predicate only

Risk 2:

- accidentally counting partial matches as `True`

Guard:

- lock exact “all bars must be blocked” behavior in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the script no longer owns one-price-board / limit-up math for the three-bar window
- the new owner reuses canonical trade-block semantics
- `_extract_execution_reason(...)` keeps the same SQL window and fallback flow
- focused verification passes
- syntax verification passes
