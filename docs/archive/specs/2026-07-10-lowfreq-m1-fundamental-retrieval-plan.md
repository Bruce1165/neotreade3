# Lowfreq M1 Fundamental Retrieval Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m1-fundamental-retrieval-design.md`

## 1. Goal

This plan covers only the next narrow `M1 retrieval` slice after the `weekly returns owner` extraction.

This slice only handles:

- `_get_fundamentals_batch()`
- `get_fundamentals()`

The goal is to:

- move the real financial-report retrieval logic into a dedicated `data_control` adapter
- keep engine methods as thin compatibility facades
- preserve the current `ann_date` visibility and missing-table fallback behavior
- add owner-focused tests for the new adapter

This slice does not:

- rewrite `check_fundamentals()`
- rewrite `get_market_sentiment()`
- rewrite `generate_buy_signals()`
- redesign any fundamentals scoring semantics
- introduce new projections or contracts

## 2. Starting Point

The current owner still lives fully inside:

- `lowfreq_engine_v16_advanced.py`

The engine currently owns both:

- single-code fundamentals retrieval through `get_fundamentals()`
- batch fundamentals retrieval through `_get_fundamentals_batch()`

Existing engine-facing coverage exists here:

- `tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py`

That carrier already protects:

- `ann_date` visibility
- batch-vs-single retrieval behavior
- the global-candidates path choosing batch retrieval over per-code fanout

What is still missing is a standalone `M1` owner module plus direct owner-focused tests.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as earlier slices, but place the owner under `data_control` rather than `cycle_intelligence`:

- add a new owner module:
  - `neotrade3/data_control/financial_report_adapter.py`
- move the real SQL and fallback logic into:
  - `load_fundamentals_batch(...)`
  - `load_fundamentals(...)`
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - passing DB handles and current `_has_financial_reports` cache state
  - receiving `(payload, refreshed_flag)` from the adapter
  - updating `self._has_financial_reports`
  - returning the payload unchanged
- add one new owner-focused test carrier:
  - `tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`
- keep the existing engine-facing tests as compatibility guards

## 4. Execution Steps

### M1-FR-S1: Freeze file boundary and output contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/financial_report_adapter.py`
- `tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`

Keep the existing engine-facing carrier as a regression-only consumer guard:

- `tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py`

Freeze the output contracts:

- single retrieval returns `dict[str, Any]`
- batch retrieval returns `dict[str, dict[str, Any]]`
- fallback payload keys remain:
  - `pe_ttm`
  - `profit_growth`
  - `revenue_growth`
  - `roe`
  - `table_exists`
- no-row fallback remains `table_exists: False`

Completion check:

- no existing consumer should need to change how it calls or interprets fundamentals retrieval

### M1-FR-S2: Implement the shared retrieval owner

Create:

- `neotrade3/data_control/financial_report_adapter.py`

Move the owner logic into that module:

- `load_fundamentals_batch(...)`
- `load_fundamentals(...)`

Implementation rules:

- the module must not import engine state directly
- table existence detection must be driven by the supplied `has_financial_reports` cache value plus DB inspection when needed
- the module must return `(payload, refreshed_flag)` instead of mutating engine state directly
- `refreshed_flag` may remain `None` for early-return paths that currently do not force cache initialization
- the module must preserve the current SQL ordering and `COALESCE(ann_date, report_date)` visibility rule exactly

Completion check:

- the financial-report retrieval contract can be understood independently from engine orchestration

### M1-FR-S3: Convert engine methods to thin facades

In `lowfreq_engine_v16_advanced.py`:

- import the adapter functions
- keep `_get_fundamentals_batch()` and `get_fundamentals()` as compatibility methods
- make each method only:
  - pass current `_has_financial_reports`
  - pass the required DB handle
  - receive `(payload, refreshed_flag)`
  - assign `self._has_financial_reports = refreshed_flag`
  - return the payload unchanged

Do not change:

- `check_fundamentals()`
- selector modules
- `get_market_sentiment()`
- `generate_buy_signals()`

Completion check:

- engine no longer owns the real retrieval body

### M1-FR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`

Minimum owner cases:

- missing-table fallback for single retrieval
- missing-table fallback for batch retrieval
- `ann_date` visibility for single retrieval
- `ann_date` visibility for batch retrieval
- empty/blank input normalization

Keep and re-run the existing engine-facing compatibility guard:

- `tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py`

Optional confidence check only if implementation reveals unexpected selector-facing drift:

- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

Completion check:

- the real retrieval owner has a direct focused carrier
- engine-facing contract tests still pass unchanged

### M1-FR-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/data_control/financial_report_adapter.py tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`

Add this only if the final diff touches selector-facing integration in practice:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

Completion check:

- owner tests pass
- engine-facing visibility tests pass
- syntax validation passes

### M1-FR-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/financial_report_adapter.py`
- `tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`

Must exclude:

- `tests/unit/test_bootstrap_skeleton.py`
- selector production files unless strictly required for compatibility
- `get_market_sentiment()` and `generate_buy_signals()` edits
- API/report files
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing `ann_date` visibility semantics while moving the owner

Guard:

- preserve the current `COALESCE(ann_date, report_date)` filter and SQL ordering exactly

Risk 2:

- breaking `_has_financial_reports` cache behavior during facade conversion

Guard:

- let the adapter return the refreshed cache flag explicitly and update engine state only in the facade

Risk 3:

- splitting batch and single retrieval across different ownership lines

Guard:

- both retrieval paths move together into the same adapter module

Risk 4:

- drifting into scoring or selector logic because fundamentals retrieval sits near M2 paths in the engine

Guard:

- this slice only touches retrieval, not scoring or orchestration

## 6. Success Criteria

This slice is complete when:

- the real financial-report retrieval owner lives in `data_control`
- engine keeps only thin compatibility facades for single and batch retrieval
- `ann_date` visibility behavior stays unchanged
- engine-facing regression tests still pass
- a focused owner test protects the adapter directly
- no scoring, orchestration, API, or report consumers are changed

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-10-lowfreq-m1-fundamental-retrieval-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/*`
- `tests/unit/*`
- `apps/api/main.py`
- any other workspace changes
