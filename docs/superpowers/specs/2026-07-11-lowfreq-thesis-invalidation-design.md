# Lowfreq Thesis Invalidation Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `trend exhaustion snapshot` extraction.

This slice only freezes:

- the sell-side `thesis invalidation / entry stop loss` rule kernel still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_thesis_invalidation_signal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2633-L2665)

The goal is to:

- move the real hard-invalidation exit predicate into one shared owner
- keep hold-days fallback derivation unchanged in the engine
- keep `SellSignal` construction unchanged in the engine
- preserve current stop-loss threshold, early/late window, and details copy exactly
- add direct owner-focused coverage for the rule contract

This design is not:

- a rewrite of `_entry_stop_loss_signal(...)`
- a rewrite of `check_sell_signal_v2()`
- a rewrite of `_position_contract_snapshot(...)`
- a rewrite of `_trend_exhaustion_signal(...)`
- a rewrite of system-exit grace or audit-event flow

Project-phase note:

- domain: `sell-side thesis invalidation policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- thesis-invalidation predicate and snapshot interpretation
- early/late invalidation-window derivation from explicit hold-days input
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the rule contract
- focused regression for:
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
  - [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)

Excluded:

- `hold_days` fallback derivation via `_count_trading_days(...)`
- `SellSignal("thesis_invalidated", ...)` construction
- `check_sell_signal_v2()` priority ordering
- grace-downstream audit recording
- position-contract assembly

## 3. Existing Context

Current repository evidence shows:

- market/sector exit snapshots and trend-exhaustion snapshot have already been ownerized
- the next remaining earliest sell-path pure rule kernel is `_thesis_invalidation_signal(...)`
- this rule executes before all other sell branches in [check_sell_signal_v2](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3252-L3326)
- `_entry_stop_loss_signal(...)` is already a thin alias over `_thesis_invalidation_signal(...)`

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_thesis_invalidation_signal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2633-L2665)
- [lowfreq_engine_v16_advanced.py:_entry_stop_loss_signal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2667-L2674)
- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L106-L125)
- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L388-L405)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py#L210-L217)

The problem is not missing business definition. The problem is:

- the real hard-invalidation predicate is still bundled into the engine
- the rule body is denser and more reusable than the surrounding sell facade
- extracting the rule leaves the engine responsible only for:
  - resolving fallback hold days
  - constructing the final `SellSignal`
  - enforcing sell-branch priority and grace interactions

## 4. Approach Options

### Option A: Extract only the hard-invalidation rule kernel and keep hold-days fallback plus SellSignal creation in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move predicate interpretation and details rendering there
- keep temporal fallback and sell facade in the engine

Pros:

- isolates the real rule kernel cleanly
- avoids broadening into sell-path orchestration
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps temporal fallback and final signal construction

### Option B: Extract the whole `_thesis_invalidation_signal(...)` flow including hold-days fallback and SellSignal creation

Pros:

- removes more code from the engine at once

Cons:

- broadens into date-derived context assembly and sell-facade semantics
- raises regression risk

### Option C: Keep the rule inline and rely only on existing sell-logic coverage

Pros:

- smallest production diff

Cons:

- leaves the earliest sell-path pure rule kernel inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure rule side:

- current-return-percent calculation from explicit scalar prices
- stop-loss threshold comparison
- invalidation-window derivation from explicit hold days
- details string formatting
- final `condition_pass` and normalized payload output

This slice should not own:

- reading `trade.buy_date`
- calling `_count_trading_days(...)`
- constructing `SellSignal`
- recording audit events
- enforcing sell priority against trend/system-exit branches

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/thesis_invalidation.py`

Recommended ownership in that module:

- `build_thesis_invalidation_snapshot(...)`

Recommended signature:

- `build_thesis_invalidation_snapshot(*, buy_price: float, sell_price: float, stop_loss_pct: float, hold_days: int) -> dict[str, Any] | None`

The owner should accept explicit already-derived inputs rather than the engine instance itself.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_thesis_invalidation_signal(...)`
- `_entry_stop_loss_signal(...)`

But with narrower roles:

- `_thesis_invalidation_signal(...)` keeps hold-days fallback derivation and delegates the rule body
- `_entry_stop_loss_signal(...)` remains a thin alias
- `_thesis_invalidation_signal(...)` still constructs `SellSignal` from the owner snapshot

Why keep the facades:

- current consumers already call these engine helpers directly
- existing tests pin `SellSignal` fields rather than a bare snapshot
- this preserves private surface stability while moving the real rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- return `None` when `buy_price <= 0`
- compute `current_return_pct = (sell_price - buy_price) / buy_price * 100`
- return `None` when `current_return_pct > STOP_LOSS_PCT`
- derive `invalidated_window = "early"` when `hold_days < 12`, else `"late"`
- derive `window_label = "建仓早期"` for `early`, else `"持仓期"`
- keep the exact `details` template:
  - `"{window_label}硬证伪退出：跌破买入价{current_return:.1f}%（阈值{stop_loss_pct:.1f}%）"`
- preserve final `SellSignal` fields exactly:
  - `reason = "thesis_invalidated"`
  - `source_layer = "invalidation"`
  - `exit_scope = "position_only"`
  - `invalidated_reason = "entry_stop_loss"`
  - `invalidated_window = early|late`
  - `confidence = 0.99`

No grace, priority, or state-reset semantics are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_thesis_invalidation.py`

Minimum owner cases:

- negative return breaching stop-loss returns `condition_pass = True`
- return above stop-loss threshold returns `None`
- hold-days below 12 produces `invalidated_window = "early"`
- hold-days 12 or above produces `invalidated_window = "late"`
- non-positive buy price returns `None`
- details string preserves current copy format

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into hold-days fallback derivation or sell priority

Guardrail:

- keep the owner limited to already-derived scalar inputs

Secondary risk:

- drifting the current stop-loss threshold comparison or early/late cutoff

Guardrail:

- preserve the rule expressions exactly and test the returned fields directly

Third risk:

- changing the current details string or `SellSignal` semantics

Guardrail:

- preserve the string template exactly and keep consumer regressions unchanged

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/thesis_invalidation.py`
2. move the pure hard-invalidation rule body there
3. turn engine `_thesis_invalidation_signal(...)` into a thin facade
4. add owner-focused tests
5. run focused syntax and sell-side regression verification

## 8. Success Criteria

This slice is complete when:

- hard-invalidation rule policy has one shared owner
- the real rule body no longer lives inline in the engine
- hold-days fallback, alias facade, and sell priority remain unchanged
- owner-focused rule tests pass
- current sell-side consumer regressions still pass
