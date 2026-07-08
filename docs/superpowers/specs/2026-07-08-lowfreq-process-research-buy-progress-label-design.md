# Lowfreq Process Research Buy Progress Label Design

Date: 2026-07-08

## 1. Goal

This slice fixes one report-row semantics gap in `scripts/generate_lowfreq_top200_process_research_report.py`.

Current state:

- `_full_light_row()` always recomputes `buy_progress_label` from `buy_progress_pct`.

Target state:

- `_full_light_row()` prefers `relevant_trades[0]["buy_progress_label"]` when present.
- If the stored label is absent, `_full_light_row()` falls back to `_progress_label(buy_progress_pct)`.

This keeps the process research report aligned with the execution-side label when that authoritative label already exists.

## 2. Scope

Included:

- `scripts/generate_lowfreq_top200_process_research_report.py`
- one new focused unit test file under `tests/unit/`

Excluded:

- API projection changes
- engine behavior changes
- report-wide refactor
- changes to input artifact validation
- changes to other progress label fields such as `buy_price_progress_label`

## 3. Evidence

Current remaining script diff is one semantic hunk in `_full_light_row()`:

- old: `buy_progress_label = _progress_label(buy_progress)`
- new: `buy_progress_label = first_trade_item["buy_progress_label"] or _progress_label(buy_progress)`

The current focused carrier `tests/unit/test_lowfreq_process_research_inputs.py` only covers `_resolve_process_research_inputs()` and does not cover `_full_light_row()` semantics.

## 4. Approach Options

### Option A: New focused test file

Add a new dedicated test file:

- `tests/unit/test_lowfreq_process_research_buy_progress_label.py`

Pros:

- preserves clean boundary for the existing input-contract test file
- keeps this slice test intent explicit
- allows a narrow commit with minimal noise

Cons:

- introduces one more focused test file

### Option B: Extend the existing input-contract test file

Add report-row semantic tests into:

- `tests/unit/test_lowfreq_process_research_inputs.py`

Pros:

- fewer physical files

Cons:

- mixes two different concerns in one carrier
- weakens future boundary audits

Decision:

- choose Option A

## 5. Design

### 5.1 Production change

In `_full_light_row()`:

- keep current `buy_progress_pct` computation unchanged
- set `buy_progress_label` by preferring `first_trade_item.get("buy_progress_label")`
- only call `_progress_label(buy_progress)` when the stored label is missing or empty

No other fields should change.

### 5.2 Test design

Create two focused tests:

1. `prefers_stored_buy_progress_label`
   - construct a minimal `row` with one `relevant_trades` item carrying `buy_progress_label`
   - assert `_full_light_row()["base"]["buy_progress_label"]` equals the stored label

2. `falls_back_to_computed_buy_progress_label`
   - construct a minimal `row` without stored `buy_progress_label`
   - provide enough price data for `_progress_pct()` to produce a deterministic bucket
   - assert `_full_light_row()["base"]["buy_progress_label"]` equals `_progress_label(buy_progress_pct)`

Tests should call the script module directly via importlib, matching the existing script-test pattern in this repository.

## 6. Validation

Required validation:

- `python3 -m py_compile scripts/generate_lowfreq_top200_process_research_report.py tests/unit/test_lowfreq_process_research_buy_progress_label.py`
- `python3 -m pytest tests/unit/test_lowfreq_process_research_buy_progress_label.py -q`

## 7. Commit Boundary

This slice is commit-safe only if the staged changes are limited to:

- `scripts/generate_lowfreq_top200_process_research_report.py`
- `tests/unit/test_lowfreq_process_research_buy_progress_label.py`

No other report, engine, API, or documentation files should be staged with this slice.
