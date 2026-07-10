# Lowfreq M2 Weekly Returns Owner Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-weekly-returns-owner-design.md`

## 1. Goal

This plan covers only the next narrow `E4: M2 legacy recognition zone` slice after the `fundamental gate` extraction.

This slice only handles:

- `_weekly_returns_view()`
- the duplicated `weekly_returns_from_series()` helper body currently embedded in `sector_entry_selector.py`

The goal is to:

- consolidate the weekly-return calculation into one shared `cycle_intelligence` owner module
- keep the engine method as a thin compatibility facade
- preserve the current selector injection contract and return shape
- add owner-focused tests for the real weekly-return contract

This slice does not:

- rewrite `_weekly_series_view()`
- rewrite `get_global_candidates()`
- rewrite `get_market_sentiment()`
- rewrite `generate_buy_signals()`
- rewrite fundamentals retrieval
- touch API or report consumers

## 2. Starting Point

The current owner logic exists twice:

- `lowfreq_engine_v16_advanced.py` owns `_weekly_returns_view()`
- `neotrade3/cycle_intelligence/sector_entry_selector.py` owns `weekly_returns_from_series()`

The current consumer contract already exists here:

- `neotrade3/cycle_intelligence/global_entry_selector.py`

And the current focused consumer coverage exists here:

- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`

The missing piece is a single shared owner plus a direct owner-focused test carrier.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as earlier E4 slices, but applied to a duplicated helper:

- add a new owner module:
  - `neotrade3/cycle_intelligence/weekly_returns.py`
- move the real `weekly_returns_from_series(view)` logic there
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - loading the weekly view through `_weekly_series_view()`
  - delegating to the shared owner through `_weekly_returns_view()`
- keep `sector_entry_selector.py` as a consumer only:
  - import the shared helper
  - remove the duplicated local implementation body
- add one new owner-focused test carrier:
  - `tests/unit/test_lowfreq_engine_v16_weekly_returns.py`
- keep the existing selector tests as consumer guards

## 4. Execution Steps

### E4-WR-S1: Freeze file boundary and output contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/weekly_returns.py`
- `neotrade3/cycle_intelligence/sector_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_weekly_returns.py`

Freeze the output contract of `weekly_returns_from_series(...)` / `_weekly_returns_view()`:

- insufficient data returns `{"status": "insufficient", "weeks": len(closes)}`
- success returns:
  - `status`
  - `ret_1w`
  - `ret_4w`
  - `ret_12w`
- branch order and `0.0` fallback behavior remain unchanged

Completion check:

- no global or sector selector consumer needs to change its call shape or expected keys

### E4-WR-S2: Implement the shared owner module

Create:

- `neotrade3/cycle_intelligence/weekly_returns.py`

Move the owner logic into that module:

- `weekly_returns_from_series(view: dict[str, Any]) -> dict[str, Any]`

Implementation rules:

- the module must not read engine state directly
- the module reads only the provided `view` payload
- the module preserves the exact insufficient and success shapes
- the module preserves the current close-filtering and base-price guards

Completion check:

- the weekly-return math can be understood independently from engine loading and selector orchestration

### E4-WR-S3: Convert engine to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import `weekly_returns_from_series(...)`
- keep `_weekly_returns_view()` as the compatibility method
- make that method only:
  - call `self._weekly_series_view(str(code), target_date)`
  - pass the result into `weekly_returns_from_series(...)`
  - return the dict unchanged

Do not change:

- `_weekly_series_view()`
- `get_global_candidates()`
- `get_market_sentiment()`
- `generate_buy_signals()`

Completion check:

- engine no longer holds the owner body of the weekly-return calculation

### E4-WR-S4: Remove the duplicated selector-local owner

In `neotrade3/cycle_intelligence/sector_entry_selector.py`:

- import `weekly_returns_from_series(...)` from the new shared module
- remove the duplicated local helper body
- keep all existing selector logic and call sites unchanged

Do not change:

- selector scoring rules
- role assignment rules
- history/resonance logic

Completion check:

- `sector_entry_selector.py` becomes a consumer of the shared owner instead of a second owner

### E4-WR-S5: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_weekly_returns.py`

Minimum owner cases:

- insufficient series length returns the current fallback shape
- fully valid series returns the expected `ret_1w`, `ret_4w`, and `ret_12w`
- non-dict or null-close items are ignored
- zero-or-negative base close windows return `0.0`

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`

Optional confidence check only if implementation reveals facade-sensitive drift:

- `tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py`

Completion check:

- the real shared owner logic has a direct focused carrier
- selector consumers still work unchanged

### E4-WR-S6: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_weekly_returns.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/weekly_returns.py neotrade3/cycle_intelligence/sector_entry_selector.py tests/unit/test_lowfreq_engine_v16_weekly_returns.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### E4-WR-S7: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/weekly_returns.py`
- `neotrade3/cycle_intelligence/sector_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_weekly_returns.py`

Must exclude:

- `_weekly_series_view()` changes beyond import-adjacent noise avoidance
- `global_entry_selector.py`
- `get_market_sentiment()` and `generate_buy_signals()` edits
- API/report files
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing the weekly-return math while consolidating the duplicate owners

Guard:

- preserve the existing branch order, close filtering, and `0.0` fallback behavior exactly

Risk 2:

- drifting into series-loading refactor because `_weekly_returns_view()` sits next to `_weekly_series_view()`

Guard:

- this slice only moves return calculation ownership, not weekly series loading

Risk 3:

- expanding into selector refactors because the duplicate helper lives inside `sector_entry_selector.py`

Guard:

- selector file edits stay limited to import wiring and duplicate helper removal

Risk 4:

- introducing broad regression work because the engine facade is monkeypatched in an existing test

Guard:

- keep `_weekly_returns_view()` present with the same name and return shape

## 6. Success Criteria

This slice is complete when:

- the weekly-return calculation owner exists only once in `cycle_intelligence`
- engine keeps only a thin `_weekly_returns_view()` facade
- `sector_entry_selector.py` no longer owns a duplicate implementation
- selector consumers keep working without call-site changes
- a focused owner test protects the shared implementation
- no orchestration, API, or report consumers are changed

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-weekly-returns-owner-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- any other workspace changes
