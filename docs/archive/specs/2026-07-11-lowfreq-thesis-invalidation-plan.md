# Lowfreq Thesis Invalidation Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-thesis-invalidation-design.md`

## 1. Goal

This plan covers only the next narrow `thesis invalidation / entry stop loss` slice after the `trend exhaustion snapshot` extraction.

This slice only handles:

- hard-invalidation rule interpretation
- owner-focused coverage for the rule contract

The goal is to:

- move the real hard-invalidation rule body into one shared owner
- keep hold-days fallback derivation unchanged in the engine
- keep `SellSignal` construction unchanged in the engine
- preserve current stop-loss, invalidation-window, and details semantics exactly
- add direct focused coverage for the rule policy

This slice does not:

- rewrite `_entry_stop_loss_signal(...)`
- rewrite `check_sell_signal_v2()`
- rewrite `_position_contract_snapshot(...)`
- rewrite trend/system-exit branches
- rewrite grace audit flow

## 2. Starting Point

Current repository evidence shows:

- market/sector exit snapshots and trend-exhaustion snapshot have already been ownerized
- the next earliest remaining sell-path pure rule kernel is `_thesis_invalidation_signal(...)`
- existing sell tests already pin both its priority and grace-isolation behavior

Relevant current engine helpers:

- `_thesis_invalidation_signal(...)`
- `_entry_stop_loss_signal(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

So the correct next slice is:

- extract only the pure hard-invalidation rule kernel
- keep temporal fallback, alias facade, and final `SellSignal` construction in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/thesis_invalidation.py`

Move the pure rule helper there:

- `build_thesis_invalidation_snapshot(...)`

Keep the engine methods as thin facades:

- `_thesis_invalidation_signal(...)`
- `_entry_stop_loss_signal(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_thesis_invalidation.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

## 4. Execution Steps

### TIP-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/thesis_invalidation.py`
- `tests/unit/test_lowfreq_engine_v16_thesis_invalidation.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Freeze the observable contract:

- return `None` when `buy_price <= 0`
- compute `current_return_pct` from `sell_price` and `buy_price`
- return `None` when `current_return_pct > STOP_LOSS_PCT`
- `invalidated_window = "early"` when `hold_days < 12`, else `"late"`
- `window_label = "建仓早期"` for early, else `"持仓期"`
- preserve the exact details template
- preserve final `SellSignal` fields exactly:
  - `reason = "thesis_invalidated"`
  - `source_layer = "invalidation"`
  - `exit_scope = "position_only"`
  - `invalidated_reason = "entry_stop_loss"`
  - `invalidated_window = early|late`
  - `confidence = 0.99`

Completion check:

- no hold-days fallback, sell-priority, or grace behavior is part of this slice

### TIP-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/thesis_invalidation.py`

Move the pure rule body into:

- `build_thesis_invalidation_snapshot(...)`

Implementation rules:

- accept explicit already-derived scalar inputs rather than the engine instance
- do not derive hold days inside the owner
- do not read `trade.buy_date` inside the owner
- do not construct `SellSignal` inside the owner
- do not emit events

Completion check:

- the hard-invalidation rule can be understood independently from the sell facade

### TIP-S3: Switch engine helper to thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- replace the real body of `_thesis_invalidation_signal(...)`

Do not change:

- `_entry_stop_loss_signal(...)`
- `check_sell_signal_v2()`
- trend/system-exit branches
- grace audit flow

Completion check:

- the engine keeps the same helper names but no longer owns the real rule body inline

### TIP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_thesis_invalidation.py`

Minimum owner cases:

- negative return breaching stop-loss returns `condition_pass = True`
- return above stop-loss threshold returns `None`
- hold-days below 12 produces `invalidated_window = "early"`
- hold-days 12 or above produces `invalidated_window = "late"`
- non-positive buy price returns `None`
- details string preserves current copy format

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Completion check:

- the rule policy has direct focused coverage
- current sell-side consumer tests still pass unchanged

### TIP-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_thesis_invalidation.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/thesis_invalidation.py tests/unit/test_lowfreq_engine_v16_thesis_invalidation.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### TIP-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-thesis-invalidation-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-thesis-invalidation-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/thesis_invalidation.py`
- `tests/unit/test_lowfreq_engine_v16_thesis_invalidation.py`

Must exclude:

- other sell-side helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into hold-days fallback derivation

Guard:

- keep the owner limited to already-derived scalar inputs

Risk 2:

- drifting the current stop-loss comparison or early/late cutoff

Guard:

- preserve the rule expressions exactly

Risk 3:

- changing the current details copy or final signal semantics

Guard:

- preserve the current string template exactly and keep consumer regressions unchanged

## 6. Success Criteria

This slice is complete when:

- hard-invalidation rule policy has one shared owner
- the real rule body no longer lives inline in the engine
- hold-days fallback, alias facade, and sell priority remain unchanged
- owner-focused rule tests pass
- current sell-side consumer regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-thesis-invalidation-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/thesis_invalidation.py`
- `tests/unit/*`
- any other workspace changes
