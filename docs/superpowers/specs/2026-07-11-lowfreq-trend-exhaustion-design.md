# Lowfreq Trend Exhaustion Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `system exit snapshots` extraction.

This slice only freezes:

- the sell-side `trend_exhaustion` snapshot policy still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_trend_exhaustion_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2673-L2723)

The goal is to:

- move the real `trend_exhaustion` snapshot policy into one shared owner
- keep hold-days fallback calculation unchanged in the engine
- keep `SellSignal` construction unchanged in the engine
- preserve current drawdown, armed-level, and early-entry semantics exactly
- add direct owner-focused coverage for the snapshot contract

This design is not:

- a rewrite of `_trend_exhaustion_signal(...)`
- a rewrite of `check_sell_signal_v2()`
- a rewrite of `_position_contract_snapshot(...)`
- a rewrite of `_thesis_invalidation_signal(...)`
- a rewrite of system-exit state mutation

Project-phase note:

- domain: `sell-side trend exhaustion snapshot policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- trend-exhaustion snapshot interpretation and confirmation predicate
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the snapshot contract
- focused regression for:
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
  - [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)

Excluded:

- `hold_days` fallback derivation via `_count_trading_days(...)`
- `SellSignal("trend_exhausted", ...)` construction
- sell/grace audit-event emission
- system-exit states
- stop-loss / invalidation logic

## 3. Existing Context

Current repository evidence shows:

- market/sector exit snapshots have already been ownerized into `system_exit_snapshots.py`
- the next remaining pure sell-side rule kernel is `_trend_exhaustion_snapshot(...)`
- this snapshot is consumed both by:
  - [check_sell_signal_v2](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3378-L3391)
  - [_position_contract_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L678-L731)

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_trend_exhaustion_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2673-L2723)
- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L136-L157)
- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L558-L573)

The problem is not missing rule definition. The problem is:

- the real `trend_exhaustion` predicate is still bundled into the engine
- the snapshot rule is denser and more reusable than the surrounding sell facade
- extracting the snapshot leaves the engine responsible only for:
  - resolving effective hold days
  - deciding whether to build a `SellSignal`
  - recording downstream audit events

## 4. Approach Options

### Option A: Extract only the trend-exhaustion snapshot policy and keep hold-days fallback plus SellSignal creation in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move snapshot interpretation and `condition_pass` logic there
- keep temporal fallback and sell facade in the engine

Pros:

- isolates the real rule kernel cleanly
- avoids broadening into sell-path orchestration
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps the date-derived hold-days fallback

### Option B: Extract the whole `trend_exhaustion` flow including hold-days fallback and SellSignal creation

Pros:

- removes more code from the engine at once

Cons:

- broadens into trade/date-derived context assembly
- mixes snapshot rule with sell facade
- raises regression risk

### Option C: Keep the snapshot inline and rely only on existing sell-logic coverage

Pros:

- smallest production diff

Cons:

- leaves the clearest remaining sell-side pure rule kernel inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure snapshot policy side:

- peak/current return calculation from explicit scalar prices
- drawdown-from-peak calculation
- armed-level computation from trailing/partial profit settings
- hold/early-entry/profit-positive gates
- final `condition_pass` decision
- exact `details` string formatting

This slice should not own:

- resolving fallback `hold_days`
- reading `trade.buy_date`
- calling `_count_trading_days(...)`
- constructing `SellSignal`
- recording audit events

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/trend_exhaustion.py`

Recommended ownership in that module:

- `build_trend_exhaustion_snapshot(...)`

Recommended signature:

- `build_trend_exhaustion_snapshot(*, buy_price: float, peak_price: float, current_price: float, hold_days: int, buy_progress_label: str, trailing_profit_level: float, partial_profit_level: float, trailing_stop_pct: float, min_hold_days: int) -> dict[str, Any] | None`

The owner should accept explicit already-derived inputs rather than the engine instance itself.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_trend_exhaustion_snapshot(...)`
- `_trend_exhaustion_signal(...)`

But with narrower roles:

- `_trend_exhaustion_snapshot(...)` keeps fallback `hold_days` derivation and delegates the snapshot rule body
- `_trend_exhaustion_signal(...)` stays a thin facade over the snapshot result and `SellSignal` creation

Why keep the facades:

- current consumers already call these engine helpers directly
- existing tests exercise both sell-path and contract-path consumption
- this preserves private surface stability while moving the real rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- return `None` when `buy_price <= 0` or `current_price <= 0`
- when `peak_price <= 0`, fall back to `buy_price`
- `armed_level = max(TRAILING_PROFIT_LEVEL, PARTIAL_PROFIT_LEVEL)`
- `drawdown_from_peak_pct = current_return_pct - peak_return_pct`
- `armed` still means `peak_return_pct > armed_level`
- `drawdown_triggered` still means `drawdown_from_peak_pct <= TRAILING_STOP_PCT`
- `hold_ready` still means `hold_days >= MIN_HOLD_DAYS`
- `current_profit_positive` still means `current_return_pct > 0.0`
- `early_quality_entry` still means `buy_progress_label in {"早窗", "前置布局"}`
- `condition_pass` still requires:
  - `armed`
  - `drawdown_triggered`
  - `hold_ready`
  - `current_profit_positive`
  - `not early_quality_entry`
- the exact `details` text format must remain unchanged

No sell-priority, audit, or state semantics are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_trend_exhaustion.py`

Minimum owner cases:

- profitable matured trade with sufficient drawdown returns `condition_pass = True`
- trade before `MIN_HOLD_DAYS` keeps `condition_pass = False`
- early-quality entry keeps `condition_pass = False`
- non-positive current profit keeps `condition_pass = False`
- non-positive buy/current price returns `None`
- non-positive peak price falls back to buy price

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into date/hold-days fallback logic

Guardrail:

- keep the owner limited to already-derived scalar inputs

Secondary risk:

- drifting the current `armed_level` or early-entry exclusion rule

Guardrail:

- preserve the rule expressions exactly and test the returned flags directly

Third risk:

- changing the current `details` string

Guardrail:

- preserve the string template exactly and keep consumer regressions unchanged

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/trend_exhaustion.py`
2. move the snapshot rule body there
3. turn engine `_trend_exhaustion_snapshot(...)` into a thin facade
4. add owner-focused tests
5. run focused syntax and sell-side regression verification

## 8. Success Criteria

This slice is complete when:

- `trend_exhaustion` snapshot policy has one shared owner
- the real snapshot rule body no longer lives inline in the engine
- hold-days fallback and sell facade remain unchanged
- owner-focused snapshot tests pass
- current sell-side consumer regressions still pass
