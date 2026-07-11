# Lowfreq Chase Entry Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `elite execution candidate` extraction.

This slice only freezes:

- the buy-side chase-entry hard-block policy still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_chase_entry_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2782-L2840)

The goal is to:

- move the real chase-entry hard-block policy into one shared owner
- keep history loading and cursor access in the engine
- keep final queue blocking, audit-event emission, and trade-block counters unchanged
- preserve current near-high, run-up, and details rendering semantics exactly
- add direct owner-focused coverage for the chase-entry contract

This design is not:

- a rewrite of `_recent_closes_before_date(...)`
- a rewrite of `run_backtest()`
- a rewrite of final queue blocking or buy execution orchestration
- a rewrite of `_record_buy_signal_audit_event(...)`
- a rewrite of reservation or rotation logic

Project-phase note:

- domain: `buy-side chase entry hard-block policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- enable/disable gate passthrough
- non-positive reference-price passthrough
- minimum-history-window passthrough
- near-5d-high and near-10d-high detection
- pre-3d and pre-5d run-up detection
- blocked flag and details rendering
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the chase-entry contract
- focused regression for:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L346-L377)
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L380-L463)

Excluded:

- SQL history retrieval in `_recent_closes_before_date(...)`
- final buy queue branch in `run_backtest()`
- audit-event emission
- `trade_blocks["buy_chase_entry_blocked"]` mutation
- reservation and rotation flows

## 3. Existing Context

Current repository evidence shows:

- `_chase_entry_snapshot(...)` is a pure dict-returning rule helper after history has already been loaded
- the helper has direct focused tests already
- the helper has one main runtime consumer in the final buy queue branch inside `run_backtest()`
- the helper does not mutate trades, queues, or audit state

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_chase_entry_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2782-L2840)
- [lowfreq_engine_v16_advanced.py:run_backtest chase-entry consumer](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3700-L3722)
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L346-L377)

The problem is not missing business definition. The problem is:

- the actual chase-entry policy still lives inline in the engine
- the helper is narrower and more reusable than its surrounding buy orchestration
- extracting it keeps the engine focused on history loading, queue blocking, and audit side effects only

## 4. Approach Options

### Option A: Extract only the pure chase-entry policy and keep history loading plus buy orchestration in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move near-high, run-up, and details rendering there
- keep `_recent_closes_before_date(...)` and `run_backtest()` side effects in the engine

Pros:

- isolates the real rule kernel cleanly
- avoids broadening into SQL retrieval and buy orchestration
- aligns with the current thin-facade migration pattern

Cons:

- the engine still owns history loading

### Option B: Extract both history loading and chase-entry policy together

Pros:

- removes more code from the engine at once

Cons:

- broadens into cursor/SQL access
- mixes pure policy with repository access
- increases regression risk

### Option C: Keep the helper inline and rely on current tests

Pros:

- smallest production diff

Cons:

- leaves a reusable hard-block policy inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure chase-entry side:

- normalize `closes` and scalar thresholds
- detect near-5d-high and near-10d-high flags
- compute pre-3d and pre-5d return percentages
- derive `near_high_flag`, `recent_runup_flag`, and `blocked`
- render the final `details` string
- return the normalized snapshot payload

This slice should not own:

- querying price history from SQLite
- validating cursor behavior
- incrementing `trade_blocks`
- emitting audit events
- selecting whether final queue should continue or block

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/chase_entry.py`

Recommended ownership in that module:

- `build_chase_entry_snapshot(...)`

Recommended signature:

- `build_chase_entry_snapshot(*, enabled: bool, closes: list[float], ref_price: float, near_high_ratio: float, pre3_threshold: float, pre5_threshold: float) -> dict[str, Any] | None`

The owner should accept normalized history values rather than the engine instance or cursor.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_chase_entry_snapshot(...)`

But with a narrower role:

- check config passthrough inputs
- call `_recent_closes_before_date(...)`
- load threshold config values
- delegate the actual policy evaluation to the new owner

Why keep the facade:

- current runtime code already calls this engine helper directly
- this preserves private surface stability while moving the rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- if `CHASE_ENTRY_BLOCK_ENABLED` is disabled, return `None`
- if `ref_price <= 0`, return `None`
- if fewer than 5 closes are available, return `None`
- `near_5d_high` and `near_10d_high` still use `ref_price >= max(window) * near_high_ratio`
- `pre3_return_pct` and `pre5_return_pct` still use the current percentage formula
- `near_high_flag` still means either 5d or 10d near-high is true
- `recent_runup_flag` still means either pre3 or pre5 return threshold is exceeded
- `blocked` still requires both `near_high_flag` and `recent_runup_flag`
- `details` copy remains:
  - `"追高型买点硬禁：近5日高位=... | 近10日高位=... | 前3日涨幅... | 前5日涨幅..."`
- when return windows are missing, `details` remains:
  - `"追高型买点硬禁：历史窗口不足"`

No buy queue, audit-event, or counter changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_chase_entry.py`

Minimum owner cases:

- disabled gate returns `None`
- non-positive `ref_price` returns `None`
- insufficient history returns `None`
- near-high plus fast run-up blocks
- only near-high without enough run-up does not block
- only fast run-up without near-high does not block
- details copy keeps the current numeric formatting

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L346-L463)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into SQL retrieval or queue orchestration

Guardrail:

- keep extraction limited to `_chase_entry_snapshot(...)` only

Secondary risk:

- drifting numeric thresholds or details copy

Guardrail:

- preserve current formulas and test representative blocked/non-blocked cases directly

Third risk:

- changing the `None` passthrough contract for disabled gate, invalid price, or short history

Guardrail:

- test each passthrough case directly in the owner-focused carrier

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/chase_entry.py`
2. move the pure chase-entry rule body there
3. turn `_chase_entry_snapshot(...)` into a thin facade
4. add owner-focused tests
5. run focused syntax and buy-path regression verification

## 8. Success Criteria

This slice is complete when:

- the chase-entry hard-block policy has one shared owner
- the real rule body no longer lives inline in the engine
- history loading, counters, and audit-event flow remain unchanged
- owner-focused chase-entry tests pass
- current buy-path regressions still pass
