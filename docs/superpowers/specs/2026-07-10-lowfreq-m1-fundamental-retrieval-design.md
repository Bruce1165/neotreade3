# Lowfreq M1 Fundamental Retrieval Design

Date: 2026-07-10

## 1. Goal

This design covers only the next narrow slice after the `weekly returns owner` extraction.

This slice only freezes:

- `_get_fundamentals_batch()`
- `get_fundamentals()`

The goal is to:

- move the engine-owned fundamentals retrieval logic into a dedicated `M1` read-side adapter
- keep the engine methods as thin compatibility facades for existing selector and test consumers
- preserve the current `ann_date` visibility contract and missing-table fallback shape
- add direct owner-focused coverage for the shared retrieval owner instead of relying only on engine-facing tests

This design is not:

- a rewrite of `check_fundamentals()`
- a rewrite of `get_market_sentiment()`
- a rewrite of `generate_buy_signals()`
- a redesign of fundamentals scoring thresholds
- a new data model or projection contract
- a NeoTrade2 runtime dependency change

Project-phase note:

- domain: `M1 retrieval`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- [_get_fundamentals_batch](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1928-L1993) ownership extraction
- [get_fundamentals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2049-L2098) ownership extraction
- one new `data_control` read-side adapter module
- engine facade preservation for current global-selector and test consumers
- owner-focused tests for:
  - single-code retrieval
  - batch retrieval
  - `ann_date` visibility
  - missing-table fallback

Excluded:

- [check_fundamentals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2100-L2111)
- [_weekly_returns_view](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1679-L1681)
- [get_market_sentiment](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1722-L1777)
- [_build_signal_structure_payload](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2251-L2278)
- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2280-L2417)
- API/report-side direct consumers

## 3. Existing Context

Current repository evidence shows five important facts:

- the engine still owns both single-code and batch fundamentals retrieval:
  - [lowfreq_engine_v16_advanced.py:L1928-L1993](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1928-L1993)
  - [lowfreq_engine_v16_advanced.py:L2049-L2098](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2049-L2098)
- the current query contract is visibility-driven, not just `report_date`-driven:
  - `COALESCE(ann_date, report_date) <= ?`
- there is already direct focused protection for the engine-facing retrieval contract:
  - [test_lowfreq_engine_v16_financial_report_visibility.py:L44-L150](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py#L44-L150)
- global candidate selection already depends on batch retrieval rather than per-code fanout:
  - [test_lowfreq_engine_v16_financial_report_visibility.py:L153-L235](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py#L153-L235)
- the project already has a clear `M1 read-side adapter` pattern under `data_control`:
  - [formal_input_adapter.py](file:///Users/mac/NeoTrade3/neotrade3/data_control/formal_input_adapter.py)

The problem is not missing correctness evidence. The problem is:

- the real `M1` retrieval owner is still embedded in the engine
- single-code and batch retrieval share fallback semantics but are implemented locally inside the monolith
- there is no standalone owner module representing the financial-report read contract

## 4. Approach Options

### Option A: Extract both retrieval methods into one `data_control` adapter and keep engine as thin facades (Recommended)

- create a new read-side adapter under `neotrade3/data_control/`
- move table-presence checks, visibility filtering, and payload shaping there
- keep `get_fundamentals()` and `_get_fundamentals_batch()` as engine compatibility wrappers

Pros:

- aligns ownership with `M1 retrieval`
- preserves the current engine consumer surface
- keeps single-code and batch retrieval under one shared owner instead of duplicating fallback logic

Cons:

- touches two engine methods in the same slice

### Option B: Extract only batch retrieval first

- move `_get_fundamentals_batch()` out
- leave `get_fundamentals()` in engine for now

Pros:

- slightly smaller diff

Cons:

- leaves duplicate table-presence and fallback semantics split across engine and adapter
- weakens the owner boundary because the single-code path still lives in the monolith

### Option C: Keep production code unchanged and add more tests

- preserve the current embedded owner
- expand owner-like tests around engine methods

Pros:

- smallest code diff

Cons:

- does not reduce engine ownership
- does not establish a reusable `M1` adapter boundary

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- fundamentals table-presence detection for read paths
- normalization of incoming codes
- `ann_date` visibility filtering
- batch retrieval payload shaping
- single-code retrieval payload shaping
- missing-table and no-row fallback semantics

These responsibilities should be treated as:

- `M1 financial report retrieval`

They should not be treated as:

- M2 scoring logic
- selector orchestration
- market sentiment analysis
- buy-signal assembly

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/data_control/financial_report_adapter.py`

This module should own:

- `load_fundamentals_batch(...)`
- `load_fundamentals(...)`

Recommended signatures:

- `load_fundamentals_batch(cursor: sqlite3.Cursor, codes: list[str], *, target_date: date, has_financial_reports: bool | None) -> tuple[dict[str, dict[str, Any]], bool | None]`
- `load_fundamentals(conn: sqlite3.Connection, code: str, *, target_date: date, has_financial_reports: bool | None) -> tuple[dict[str, Any], bool | None]`

The returned cache flag is the refreshed table-presence state so the engine can keep its existing `_has_financial_reports` cache behavior without letting the adapter mutate engine state directly. It remains `None` for early-return paths that currently do not force cache initialization.

This module should not own:

- engine config
- fundamentals scoring
- selector decisions
- API/report payload composition

### 5.3 Engine Compatibility Surface

The engine should keep:

- `_get_fundamentals_batch()`
- `get_fundamentals()`

But each method should shrink to:

- pass the required DB handle plus current `_has_financial_reports` cache state into the adapter
- receive `(payload, refreshed_flag)`
- update `self._has_financial_reports`
- return the payload unchanged

This keeps current consumers unchanged, including:

- [test_lowfreq_engine_v16_financial_report_visibility.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py)
- global candidate wiring that already injects `_get_fundamentals_batch()`

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- empty code list returns `{}`
- blank single code returns:
  - `{"pe_ttm": 0, "profit_growth": 0, "revenue_growth": 0, "roe": 0, "table_exists": False}`
- if `financial_reports` does not exist, return the same fallback shape as today
- visibility rule remains:
  - `COALESCE(ann_date, report_date) <= target_date`
- ordering remains:
  - `ORDER BY code, COALESCE(ann_date, report_date) DESC, report_date DESC` for batch
  - `ORDER BY COALESCE(ann_date, report_date) DESC, report_date DESC LIMIT 1` for single
- payload keys remain:
  - `pe_ttm`
  - `profit_growth`
  - `revenue_growth`
  - `roe`
  - `table_exists`

No semantic tightening is included in this slice. The purpose is owner relocation, not query redesign.

### 5.5 Testing Strategy

Keep the existing engine-facing carrier:

- [test_lowfreq_engine_v16_financial_report_visibility.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py)

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`

This carrier should directly exercise the new adapter and cover at least:

- missing-table fallback for single and batch retrieval
- `ann_date` visibility for single retrieval
- `ann_date` visibility for batch retrieval
- blank/empty input normalization

Focused regression should continue to re-run:

- `tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py`

Optional confidence check if the final diff touches selector-facing integration more than expected:

- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

## 6. Risks and Guardrails

Main risk:

- changing the current `ann_date` visibility semantics while relocating ownership

Guardrails:

- preserve the current SQL ordering and `COALESCE(ann_date, report_date)` filter exactly
- preserve the exact fallback payload shape
- keep engine method names unchanged
- avoid moving scoring logic into this slice
- avoid changing selector or orchestration files unless strictly required for compatibility

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/data_control/financial_report_adapter.py`
2. move the real retrieval logic into adapter functions for batch and single-code loads
3. convert engine methods into thin facades that update `_has_financial_reports`
4. add `tests/unit/test_lowfreq_engine_v16_financial_report_adapter.py`
5. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the real financial-report retrieval owner lives outside `lowfreq_engine_v16_advanced.py`
- engine keeps only thin compatibility facades for single and batch retrieval
- `ann_date` visibility behavior stays unchanged
- existing engine-facing tests continue to pass
- a focused owner test directly protects the new adapter
