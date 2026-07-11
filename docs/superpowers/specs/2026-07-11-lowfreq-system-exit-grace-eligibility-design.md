# Lowfreq System Exit Grace Eligibility Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `formal-front build bridge` extraction.

This slice only freezes:

- the sell-side `system_exit_grace` eligibility policy still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_resolve_buy_progress_label](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2278-L2302)
  - [lowfreq_engine_v16_advanced.py:_profit_keep_ratio](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2304-L2307)
  - [lowfreq_engine_v16_advanced.py:_system_exit_grace_thresholds](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2309-L2322)
  - [lowfreq_engine_v16_advanced.py:_is_leader_hold_candidate](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2335-L2340)
  - [lowfreq_engine_v16_advanced.py:_eligible_for_system_exit_grace](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2376-L2424)

The goal is to:

- move the real `system_exit_grace` eligibility policy into one shared owner
- keep sell-state mutation in the engine unchanged
- preserve the current market-vs-sector grace thresholds exactly
- preserve the current `buy_progress_label` fallback semantics exactly
- preserve the current profit-keep ratio semantics exactly
- add direct owner-focused coverage for the grace-eligibility policy

This design is not:

- a rewrite of `check_sell_signal_v2()`
- a rewrite of `_apply_system_exit_state(...)`
- a rewrite of `_system_exit_expire_date(...)`
- a rewrite of `_record_system_exit_grace_audit_event(...)`
- a rewrite of market or sector exit snapshots

Project-phase note:

- domain: `sell-side grace eligibility policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- buy-progress-label resolution for grace eligibility
- profit-keep ratio calculation used by grace eligibility
- scope-aware grace threshold selection
- leader/candidate gate logic for grace eligibility
- the final boolean grace-eligibility predicate
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the policy contract
- focused regression for:
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
  - [test_lowfreq_intent_conflicts.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_intent_conflicts.py)

Excluded:

- `trade.system_exit_grace_*` writes
- grace-date / grace-scope / grace-reason persistence
- grace audit-event emission
- expiry-date calculation
- market/sector exit watch state mutation
- hard-stop / trend-exhaustion flow

## 3. Existing Context

Current repository evidence shows:

- the buy path around `generate_buy_signals()` is now effectively orchestration shell around already-ownerized helpers
- the next dense engine-owned kernel sits in the sell path inside `system_exit_grace`
- that kernel is already regression-anchored by multiple sell-logic tests covering:
  - market grace downgrade
  - one-time grace usage
  - peak-profit gating
  - early buy-progress gating
  - profit-keep gating
  - stricter sector thresholds
  - sector hold-days gating

Repository evidence:

- [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2278-L2424)
- [lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L254-L425)
- [lowfreq_intent_conflicts.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_intent_conflicts.py#L379-L409)

The problem is not missing business definition. The problem is:

- the grace-eligibility policy is still bundled into the engine
- the policy itself is denser and more reusable than the surrounding state-machine shell
- extracting the policy leaves the engine responsible only for:
  - applying the predicate result
  - mutating trade/grace state
  - emitting audit events

## 4. Approach Options

### Option A: Extract only the grace-eligibility policy and keep state mutation in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move the label/threshold/profit-keep/eligibility logic there
- keep state writes and audit side effects in the engine

Pros:

- isolates the real rule kernel cleanly
- avoids broadening into sell-state orchestration
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps some related but non-policy helpers

### Option B: Extract the entire `system_exit_grace` flow including state writes and audit emission

Pros:

- removes more code from the engine at once

Cons:

- broadens into trade mutation and audit side effects
- mixes policy with state machine
- raises regression risk

### Option C: Keep the policy inline and rely only on existing sell-logic tests

Pros:

- smallest production diff

Cons:

- leaves the densest remaining sell-side kernel inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure policy side of grace eligibility:

- resolving the buy-progress label from signal/trade data
- computing profit-keep ratio
- selecting scope-aware thresholds
- deciding whether the trade is a leader-hold candidate
- deciding whether the trade qualifies for grace under the current scope and sell price

This slice should not own:

- writing `trade.system_exit_grace_*`
- resetting system-exit states
- emitting sell/grace audit events
- deciding market/sector snapshots
- generating `SellSignal`

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/system_exit_grace.py`

Recommended ownership in that module:

- `resolve_buy_progress_label(...)`
- `profit_keep_ratio(...)`
- `system_exit_grace_thresholds(...)`
- `is_leader_hold_candidate(...)`
- `is_eligible_for_system_exit_grace(...)`

Recommended signatures:

- `resolve_buy_progress_label(*, wave_phase: str | None = None, explicit_label: str | None = None) -> str`
- `profit_keep_ratio(*, current_return_pct: float, peak_return_pct: float) -> float`
- `system_exit_grace_thresholds(*, scope: str, market_min_peak_return_pct: float, market_min_current_profit_pct: float, market_min_profit_keep_ratio: float, sector_min_peak_return_pct: float, sector_min_current_profit_pct: float, sector_min_profit_keep_ratio: float, sector_max_hold_days: int) -> tuple[float, float, float, int]`
- `is_leader_hold_candidate(*, role: str, peak_return_pct: float, leader_hold_min_peak_return_pct: float) -> bool`
- `is_eligible_for_system_exit_grace(...) -> bool`

The final predicate should accept only explicit scalar inputs rather than the engine instance itself.

### 5.3 Engine Facade Boundary

The engine should keep these helper names:

- `_resolve_buy_progress_label(...)`
- `_profit_keep_ratio(...)`
- `_system_exit_grace_thresholds(...)`
- `_is_leader_hold_candidate(...)`
- `_eligible_for_system_exit_grace(...)`

But they should become thin facades delegating to the new owner.

Why keep the facades:

- current sell logic still calls these engine helpers directly
- tests already exercise the engine’s sell chain through `check_sell_signal_v2()`
- this preserves private surface stability while moving the real rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- explicit `buy_progress_label` wins over wave fallback
- otherwise `1浪 -> 前置布局`
- otherwise `3浪 -> 早窗`
- otherwise `其它`
- profit-keep ratio returns `0.0` when `peak_return_pct <= 0`
- sector scope still uses:
  - `SYSTEM_EXIT_GRACE_SECTOR_MIN_PEAK_RETURN_PCT`
  - `SYSTEM_EXIT_GRACE_SECTOR_MIN_CURRENT_PROFIT_PCT`
  - `SYSTEM_EXIT_GRACE_SECTOR_MIN_PROFIT_KEEP_RATIO`
  - `SYSTEM_EXIT_GRACE_SECTOR_MAX_HOLD_DAYS`
- market scope still uses:
  - `SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT`
  - `SYSTEM_EXIT_GRACE_MARKET_MIN_CURRENT_PROFIT_PCT`
  - `SYSTEM_EXIT_GRACE_MARKET_MIN_PROFIT_KEEP_RATIO`
- market scope still enforces the max of:
  - `SYSTEM_EXIT_GRACE_MARKET_MIN_PEAK_RETURN_PCT`
  - legacy `SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT`
- sector scope still requires role in `{"龙头", "中军"}`
- market scope still requires leader-hold candidate
- accepted labels still limited to `{"早窗", "前置布局"}`
- positive-return gating still respects `SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN`

No state or copy changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_grace_policy.py`

Minimum owner cases:

- buy-progress-label fallback maps `1浪` to `前置布局`
- buy-progress-label fallback maps `3浪` to `早窗`
- profit-keep ratio returns `0.0` when peak return is non-positive
- sector thresholds return the stricter sector tuple
- market thresholds apply the market tuple
- grace eligibility accepts an eligible market leader case
- grace eligibility rejects a non-early label
- grace eligibility rejects insufficient profit-keep ratio
- grace eligibility rejects a sector candidate with excessive hold days

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
- [test_lowfreq_intent_conflicts.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_intent_conflicts.py)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into sell-state mutation or audit-event logic

Guardrail:

- keep the extraction limited to pure policy helpers only

Secondary risk:

- drifting current threshold precedence between market and legacy peak-return settings

Guardrail:

- explicitly preserve the `max(market_min_peak_return_pct, SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT)` rule in the owner

Third risk:

- mixing market and sector role rules

Guardrail:

- preserve current scope split exactly

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/system_exit_grace.py`
2. move the pure policy helpers there
3. turn the engine helpers into thin facades
4. add owner-focused tests
5. run focused syntax and sell-logic regression verification

## 8. Success Criteria

This slice is complete when:

- `system_exit_grace` eligibility rules have one shared owner
- the real rule body no longer lives inline in the engine
- trade mutation and audit-event flow remain unchanged
- owner-focused policy tests pass
- current sell-side grace regressions still pass
