# Lowfreq M2 Weekly Returns Owner Design

Date: 2026-07-10

## 1. Goal

This design covers only the next narrow slice after the `fundamental gate` extraction inside `E4: M2 legacy recognition zone`.

This slice only freezes:

- `_weekly_returns_view()`
- the duplicated `weekly_returns_from_series()` owner logic currently embedded in `sector_entry_selector.py`

The goal is to:

- remove the duplicated weekly-return calculation owner from both engine and selector code paths
- place the real owner in one shared `cycle_intelligence` module
- keep `LowFreqTradingEngineV16._weekly_returns_view()` as a thin compatibility facade for the current `global_entry_selector` injection site
- preserve current selector behavior and return shape
- add owner-focused coverage for the actual weekly-return contract

This design is not:

- a rewrite of `_weekly_series_view()`
- a rewrite of `get_global_candidates()`
- a rewrite of `get_market_sentiment()`
- a rewrite of `generate_buy_signals()`
- a fundamentals retrieval extraction
- a NeoTrade2 runtime dependency change

Project-phase note:

- domain: `E4 / M2 recognition`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- [_weekly_returns_view](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1679-L1698) thin-facade extraction
- [weekly_returns_from_series](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py#L593-L614) owner relocation
- one new shared owner module under `neotrade3/cycle_intelligence/`
- owner-focused tests for the real weekly-return calculation contract
- focused regression for:
  - [sector_entry_selector.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py#L218)
  - [global_entry_selector.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/global_entry_selector.py#L184-L201)

Excluded:

- [_weekly_series_view](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1187-L1243)
- [get_global_candidates](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2226-L2265) orchestration changes beyond keeping the current injection site
- [get_market_sentiment](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1738-L1792)
- [_get_fundamentals_batch](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1943-L2008)
- [get_fundamentals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2064-L2113)
- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2296-L2433)
- API or report-side direct consumers of `get_market_sentiment()` / `generate_buy_signals()`

## 3. Existing Context

Current repository evidence shows four important facts:

- the engine still owns `_weekly_returns_view()` as a local adapter that reads weekly series and calculates `ret_1w`, `ret_4w`, and `ret_12w`:
  - [lowfreq_engine_v16_advanced.py:L1679-L1698](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1679-L1698)
- `global_entry_selector.py` already treats weekly returns as an injected dependency instead of owning the calculation:
  - [global_entry_selector.py:L29-L30](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/global_entry_selector.py#L29-L30)
  - [global_entry_selector.py:L184-L201](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/global_entry_selector.py#L184-L201)
- `sector_entry_selector.py` already contains the same weekly-return calculation as a local helper named `weekly_returns_from_series()`:
  - [sector_entry_selector.py:L593-L614](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py#L593-L614)
- `get_market_sentiment()` and `generate_buy_signals()` still have direct API and report consumers, so they remain broader contracts and should not be the next extraction point:
  - [apps/api/main.py:L27191-L27198](file:///Users/mac/NeoTrade3/apps/api/main.py#L27191-L27198)
  - [generate_lowfreq_top200_attribution_report.py:L339-L367](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L339-L367)

The problem is not that weekly-return math is missing. The problem is:

- the real owner already exists twice
- engine and selector currently share behavior through duplication rather than through one explicit module boundary
- there is no direct owner-focused carrier for the shared weekly-return contract

## 4. Approach Options

### Option A: Extract one shared owner module and let engine plus selector both call it (Recommended)

- create a dedicated shared module under `neotrade3/cycle_intelligence/`
- move the real `weekly_returns_from_series(view)` owner there
- keep `_weekly_returns_view()` as a thin engine facade that only loads series and delegates
- replace the local helper body in `sector_entry_selector.py` with the shared import

Pros:

- removes the proven duplication instead of moving it around
- keeps ownership aligned with `cycle_intelligence`, not with a sector-specific module
- preserves the existing engine compatibility surface and selector call shapes

Cons:

- touches one extra production file compared with an engine-only cut

### Option B: Let engine import `weekly_returns_from_series()` directly from `sector_entry_selector.py`

- keep the existing helper where it is
- reuse it from engine

Pros:

- smallest diff

Cons:

- creates cross-owner coupling from engine/global flow back into a sector-specific module
- leaves the owner in the wrong file even if duplication disappears

### Option C: Extract only the engine method into a new owner and leave the selector helper duplicated

- move `_weekly_returns_view()` math out of engine only
- keep the current `sector_entry_selector.py` helper untouched

Pros:

- narrowest production boundary

Cons:

- preserves known duplication
- lowers the value of the slice because the real ownership problem remains only half-solved

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- translating a weekly `series` view into the weekly-return contract
- the insufficient-data fallback shape
- the `ret_1w`, `ret_4w`, and `ret_12w` calculations

These responsibilities should be treated as:

- `M2 support adapter math`

They should not be treated as:

- weekly series loading
- selector orchestration
- market sentiment analysis
- buy-signal assembly

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/cycle_intelligence/weekly_returns.py`

This module should own:

- `weekly_returns_from_series(view: dict[str, Any]) -> dict[str, Any]`

Recommended signature:

- `weekly_returns_from_series(view: dict[str, Any]) -> dict[str, Any]`

It should not own:

- database reads
- cache lookup
- engine config loading
- selector scoring

### 5.3 Engine Compatibility Surface

The engine should keep:

- the method name `_weekly_returns_view()`

But its responsibility should shrink to:

- call `self._weekly_series_view(str(code), target_date)`
- pass that view to `weekly_returns_from_series(...)`
- return the resulting dict unchanged

This keeps the current injection surface unchanged:

- [lowfreq_engine_v16_advanced.py:L2252-L2258](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2252-L2258)

### 5.4 Selector Compatibility Surface

`sector_entry_selector.py` should stop owning its private copy of the weekly-return math.

After this slice, it should:

- import `weekly_returns_from_series(...)` from the new shared module
- keep all existing selector behavior and call sites unchanged

This keeps the weekly-return owner independent from both:

- engine-specific wiring
- sector-specific orchestration

### 5.5 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- read `view.get("series") or []`
- build `closes` only from dict items with non-null `close`
- if fewer than `16` closes exist, return `{"status": "insufficient", "weeks": len(closes)}`
- otherwise compute:
  - `ret_1w` from `k=1`
  - `ret_4w` from `k=4`
  - `ret_12w` from `k=12`
- if `t - k < 0`, the helper returns `0.0`
- if the base close is `<= 0`, the helper returns `0.0`
- the success shape remains:
  - `{"status": "ok", "ret_1w": ..., "ret_4w": ..., "ret_12w": ...}`

No semantic tightening is included in this slice. The purpose is owner consolidation, not math redesign.

### 5.6 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_weekly_returns.py`

This carrier should directly exercise `weekly_returns_from_series(...)` and cover at least:

- insufficient series length
- fully valid series with expected `1w / 4w / 12w` returns
- non-dict or null-close entries being ignored
- zero-or-negative base close windows returning `0.0`

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_global_entry_selector.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_global_entry_selector.py)
- [test_lowfreq_engine_v16_sector_entry_selector.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py)

Optional confidence check if the final diff touches the engine facade in a way that could affect existing monkeypatch assumptions:

- [test_lowfreq_engine_v16_financial_report_visibility.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py#L217-L235)

## 6. Risks and Guardrails

Main risk:

- accidentally changing weekly-return math while consolidating duplicate logic

Guardrails:

- preserve the exact branch order and thresholds
- preserve the exact return keys and fallback shape
- keep `_weekly_returns_view()` present as a compatibility facade
- avoid changing `_weekly_series_view()` in the same slice
- avoid expanding into selector scoring or market sentiment logic

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/cycle_intelligence/weekly_returns.py` with `weekly_returns_from_series(...)`
2. convert `LowFreqTradingEngineV16._weekly_returns_view()` into a thin facade
3. switch `sector_entry_selector.py` to import the shared owner instead of keeping a private copy
4. add `tests/unit/test_lowfreq_engine_v16_weekly_returns.py`
5. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the weekly-return calculation owner exists only once in `cycle_intelligence`
- engine keeps only a thin `_weekly_returns_view()` compatibility facade
- `sector_entry_selector.py` no longer owns a duplicate implementation
- global and sector selector behavior remains unchanged
- an owner-focused test directly protects the shared weekly-return contract
