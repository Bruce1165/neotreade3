# Lowfreq M2 Fundamental Gate Design

Date: 2026-07-10

## 1. Goal

This design only covers the next narrow slice after the `market focus snapshot adapter` extraction inside `E4: M2 legacy recognition zone`.

This slice only freezes:

- `check_fundamentals()`

The goal is to:

- extract the engine-owned fundamentals scoring and pass/fail rule set into a narrow `cycle_intelligence` owner module
- keep the boundary limited to `M2 candidate screening rules`, not `M1` data loading or buy-signal orchestration
- preserve the current injected usage from `sector/global selector`
- add owner-focused coverage for the real fundamentals scoring contract instead of relying only on selector tests that stub the dependency

This design is not:

- a rewrite of `generate_buy_signals()`
- a rewrite of `_get_fundamentals_batch()` or `get_fundamentals()`
- a shared utility merge between engine, API, and report scripts
- a market-sentiment refactor
- a production cutover or a NeoTrade2 dependency change

Project-phase note:

- domain: `E4 / M2 recognition`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- [check_fundamentals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2115-L2175) ownership extraction
- engine facade preservation for current selector consumers
- owner-focused tests for the real fundamentals scoring behavior
- focused regression for:
  - [sector_entry_selector.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py#L88-L103)
  - [global_entry_selector.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/global_entry_selector.py#L73-L89)

Excluded:

- [_get_fundamentals_batch](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1943-L2008)
- [get_fundamentals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2064-L2113)
- [_weekly_returns_view](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1678-L1697)
- [get_market_sentiment](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1737-L1792)
- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2344-L2481)
- `apps/api/main.py` or report-side direct sentiment consumers

## 3. Existing Context

Current repository evidence shows five important facts:

- `check_fundamentals()` is currently a pure scoring rule set embedded in the engine and only depends on engine thresholds plus the provided `fundamentals` dict:
  - [lowfreq_engine_v16_advanced.py:L2115-L2175](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2115-L2175)
- both selector owners already consume fundamentals evaluation through dependency injection instead of hard-coding engine internals:
  - [sector_entry_selector.py:L88-L103](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py#L88-L103)
  - [global_entry_selector.py:L73-L89](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/global_entry_selector.py#L73-L89)
- current focused selector tests stub `check_fundamentals()` as an injected callable, which means the consumer contract exists but the owner implementation is not directly protected:
  - [test_lowfreq_engine_v16_sector_entry_selector.py:L158-L208](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py#L158-L208)
  - [test_lowfreq_engine_v16_global_entry_selector.py:L123-L186](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_global_entry_selector.py#L123-L186)
- `generate_buy_signals()` remains a cross-layer orchestrator with broad consumer surface and should not be used as the next extraction point:
  - [lowfreq_engine_v16_advanced.py:L2344-L2481](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2344-L2481)
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
- `_get_fundamentals_batch()` and `get_fundamentals()` are data-access concerns and therefore are a different boundary from the scoring rule itself:
  - [lowfreq_engine_v16_advanced.py:L1943-L2008](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1943-L2008)
  - [lowfreq_engine_v16_advanced.py:L2064-L2113](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2064-L2113)

The problem is not that fundamentals rules are unused. The problem is:

- the real `M2` fundamentals gate is still embedded in the engine
- selector carriers only protect the injected consumer contract
- there is no owner-focused regression for the actual pass/score/reasons behavior

## 4. Approach Options

### Option A: Move only the fundamentals scoring rule into a new module and keep engine as a thin facade (Recommended)

- create a narrow module under `neotrade3/cycle_intelligence/`
- move the `check_fundamentals()` rule body into a pure function
- keep `LowFreqTradingEngineV16.check_fundamentals()` as a compatibility facade that only injects thresholds

Pros:

- keeps the boundary aligned with the selector injection pattern already in place
- isolates the real `M2` rule set without dragging in database access
- enables direct owner-focused tests with simple dict inputs

Cons:

- leaves fundamentals data loaders in the engine for now
- requires a small wrapper method to preserve current call sites

### Option B: Move `check_fundamentals()` together with fundamentals data loaders

- extract the rule and both fundamentals loaders in one slice

Pros:

- may look more complete at first glance

Cons:

- mixes `M2` scoring with `M1` retrieval responsibilities
- expands the diff across unrelated ownership lines
- weakens the narrow-slice discipline established in earlier E4 cuts

### Option C: Leave production code unchanged and only add direct tests around the engine method

- preserve the embedded implementation
- add an owner-like test against the current engine method

Pros:

- smallest diff

Cons:

- does not reduce engine ownership or improve file boundaries
- delays the real extraction and keeps the rule set buried in the monolith

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- fundamentals availability fallback behavior
- PE scoring and loss-growth exception handling
- profit growth scoring
- revenue growth scoring
- ROE scoring
- the final `(passed, score, reasons)` contract

These responsibilities should be treated as:

- `M2 candidate fundamentals gate`

They should not be treated as:

- fundamentals fact retrieval
- orchestration
- API/report payload shaping

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/cycle_intelligence/fundamental_gate.py`

This module should own:

- `score_fundamentals(...)`

Recommended signature:

- `score_fundamentals(fundamentals: dict[str, Any], *, max_pe: float, min_profit_growth: float, min_roe: float) -> tuple[bool, float, list[str]]`

It should not own:

- database reads
- engine config loading
- selector orchestration
- buy-signal assembly

### 5.3 Engine Compatibility Surface

The engine should keep:

- the method name `check_fundamentals()`

But its responsibility should shrink to:

- read `self.MAX_PE`
- read `self.MIN_PROFIT_GROWTH`
- read `self.MIN_ROE`
- call `score_fundamentals(...)`

This keeps current selector call sites unchanged:

- [sector_entry_selector.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py)
- [global_entry_selector.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/global_entry_selector.py)

### 5.4 Behavior Preservation Rules

This slice must preserve the current scoring semantics exactly:

- if `table_exists` is falsey, return `(True, 50, ["基本面数据不可用，跳过筛选"])`
- if `0 < pe < max_pe`, add `20` and append `PE{pe:.1f}合理`
- if `pe <= 0` and `profit_growth > 30`, add `10` and append `亏损但高增长`
- if `pe <= 0` and `profit_growth <= 30`, mark `passed = False` and append `PE无效且无高增长`
- if `pe >= max_pe`, add `5` and append `PE{pe:.1f}偏高`
- if `profit_growth >= min_profit_growth`, add `30` and append `净利增{profit_growth:.1f}%`
- if `0 < profit_growth < min_profit_growth`, add `15` and append `净利增{profit_growth:.1f}%（偏低）`
- if `profit_growth <= 0`, add `5` and append `净利下滑{profit_growth:.1f}%`
- if `revenue_growth >= 10`, add `20` and append `营收增{revenue_growth:.1f}%`
- if `0 < revenue_growth < 10`, add `10`
- if `roe >= min_roe`, add `30` and append `ROE{roe:.1f}%`
- if `0 < roe < min_roe`, add `15`

No semantic tightening is included in this slice. The purpose is ownership relocation, not rule redesign.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`

This carrier should directly exercise `score_fundamentals(...)` and cover at least:

- missing-table pass-through
- full healthy case
- `pe <= 0` with strong growth exception
- `pe <= 0` without strong growth
- high PE / low growth / low ROE soft-score composition

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_sector_entry_selector.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py)
- [test_lowfreq_engine_v16_global_entry_selector.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_global_entry_selector.py)

## 6. Risks and Guardrails

Main risk:

- changing score math or reason strings while moving ownership

Guardrails:

- preserve the exact existing branch order
- preserve the exact current reason strings
- keep the engine facade name unchanged
- avoid touching fundamentals loaders in the same slice

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/cycle_intelligence/fundamental_gate.py` with `score_fundamentals(...)`
2. convert `LowFreqTradingEngineV16.check_fundamentals()` into a thin facade
3. add `tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`
4. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the real fundamentals scoring owner lives outside `lowfreq_engine_v16_advanced.py`
- engine keeps only a thin compatibility facade
- selector consumers keep working without call-site edits
- an owner-focused test directly protects the scoring contract
- focused regressions pass without expanding scope into loaders or orchestration
