# Lowfreq Trend Exhaustion Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-trend-exhaustion-design.md`

## 1. Goal

This plan covers only the next narrow `trend_exhaustion` slice after the `system exit snapshots` extraction.

This slice only handles:

- trend-exhaustion snapshot interpretation
- owner-focused coverage for the snapshot contract

The goal is to:

- move the real trend-exhaustion snapshot rule body into one shared owner
- keep hold-days fallback derivation unchanged in the engine
- keep `SellSignal` construction unchanged in the engine
- preserve current threshold, gating, and `details` semantics exactly
- add direct focused coverage for the snapshot policy

This slice does not:

- rewrite `_trend_exhaustion_signal(...)`
- rewrite `check_sell_signal_v2()`
- rewrite `_position_contract_snapshot(...)`
- rewrite `_thesis_invalidation_signal(...)`
- rewrite system-exit states or audit helpers

## 2. Starting Point

Current repository evidence shows:

- market/sector exit snapshots have already been ownerized
- the next remaining pure sell-side rule kernel is `_trend_exhaustion_snapshot(...)`
- existing sell tests already pin both the sell trigger and the contract-path projection

Relevant current engine helpers:

- `_trend_exhaustion_snapshot(...)`
- `_trend_exhaustion_signal(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

So the correct next slice is:

- extract only the pure snapshot interpretation kernel
- keep temporal fallback and sell facade in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/trend_exhaustion.py`

Move the pure snapshot helper there:

- `build_trend_exhaustion_snapshot(...)`

Keep the engine methods as thin facades:

- `_trend_exhaustion_snapshot(...)`
- `_trend_exhaustion_signal(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_trend_exhaustion.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

## 4. Execution Steps

### TEP-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/trend_exhaustion.py`
- `tests/unit/test_lowfreq_engine_v16_trend_exhaustion.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Freeze the observable contract:

- return `None` when `buy_price <= 0` or `current_price <= 0`
- `peak_price <= 0` still falls back to `buy_price`
- `armed_level` still uses `max(TRAILING_PROFIT_LEVEL, PARTIAL_PROFIT_LEVEL)`
- `drawdown_triggered` still means `drawdown_from_peak_pct <= TRAILING_STOP_PCT`
- `hold_ready` still means `hold_days >= MIN_HOLD_DAYS`
- `current_profit_positive` still means `current_return_pct > 0.0`
- `early_quality_entry` still means `buy_progress_label in {"早窗", "前置布局"}`
- `condition_pass` still requires armed, drawdown-triggered, hold-ready, current-profit-positive, and non-early-quality-entry
- the exact `details` string remains unchanged

Completion check:

- no temporal fallback, sell-priority, or state mutation behavior is part of this slice

### TEP-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/trend_exhaustion.py`

Move the pure interpretation body into:

- `build_trend_exhaustion_snapshot(...)`

Implementation rules:

- accept explicit already-derived scalar inputs rather than the engine instance
- do not derive `hold_days` inside the owner
- do not read `trade.buy_date` inside the owner
- do not write to `trade`
- do not emit events

Completion check:

- the snapshot policy can be understood independently from the sell facade

### TEP-S3: Switch engine helper to thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- replace the real body of `_trend_exhaustion_snapshot(...)`

Do not change:

- `_trend_exhaustion_signal(...)`
- `check_sell_signal_v2()`
- `_position_contract_snapshot(...)`
- `_thesis_invalidation_signal(...)`

Completion check:

- the engine keeps the same helper names but no longer owns the real snapshot rule body inline

### TEP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_trend_exhaustion.py`

Minimum owner cases:

- matured profitable trade with sufficient peak drawdown returns `condition_pass = True`
- trade before minimum hold days keeps `condition_pass = False`
- early-quality entry keeps `condition_pass = False`
- non-positive current profit keeps `condition_pass = False`
- non-positive buy/current price returns `None`
- non-positive peak price falls back to buy price

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Completion check:

- the snapshot policy has direct focused coverage
- current sell-side consumer tests still pass unchanged

### TEP-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_trend_exhaustion.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/trend_exhaustion.py tests/unit/test_lowfreq_engine_v16_trend_exhaustion.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### TEP-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-trend-exhaustion-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-trend-exhaustion-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/trend_exhaustion.py`
- `tests/unit/test_lowfreq_engine_v16_trend_exhaustion.py`

Must exclude:

- other sell-side helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into hold-days fallback derivation

Guard:

- keep the owner limited to already-derived scalar inputs

Risk 2:

- drifting the current drawdown or early-entry gating

Guard:

- preserve the rule expressions exactly

Risk 3:

- changing the current `details` copy

Guard:

- preserve the current string template exactly and keep consumer regressions unchanged

## 6. Success Criteria

This slice is complete when:

- `trend_exhaustion` snapshot policy has one shared owner
- the real snapshot rule body no longer lives inline in the engine
- hold-days fallback and sell facade remain unchanged
- owner-focused snapshot tests pass
- current sell-side consumer regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-trend-exhaustion-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/trend_exhaustion.py`
- `tests/unit/*`
- any other workspace changes
