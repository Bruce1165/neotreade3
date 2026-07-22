# Lowfreq Trade Block Reason Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `chase entry snapshot` extraction.

This slice only freezes:

- the execution block-reason policy still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_trade_block_reason](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3355-L3396)

The goal is to:

- move the real execution block-reason policy into one shared owner
- keep price-bar loading and buy/sell runtime orchestration unchanged in the engine
- preserve current limit-up, limit-down, amount, and participation-rate semantics exactly
- preserve current config fallback behavior exactly
- add direct owner-focused coverage for the execution block-reason contract

This design is not:

- a rewrite of `_get_bar(...)`
- a rewrite of `run_backtest()`
- a rewrite of buy/sell audit-event emission
- a rewrite of `_normalize_execution_block_reason(...)`
- a rewrite of execution action field projection

Project-phase note:

- domain: `execution block reason policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- `missing_price_bar` passthrough handling
- limit-up block policy for buy side
- limit-down block policy for sell side
- one-price board detection
- min-amount block policy
- participation-rate block policy
- config fallback interpretation from `LowFreqV16Config.execution`
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the block-reason contract
- focused regression for:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L1088-L1125)

Excluded:

- `_get_bar(...)` price-bar retrieval
- buy and sell execution branches in `run_backtest()`
- audit-event emission and `trade_blocks` mutation
- execution block-reason normalization for API/report projection

## 3. Existing Context

Current repository evidence shows:

- `_trade_block_reason(...)` is a pure string-returning policy helper
- it has two active runtime consumers:
  - sell execution branch inside `run_backtest()`
  - buy execution branch inside `run_backtest()`
- it already has direct focused tests for the one-price limit-up case
- it does not mutate trades, queues, or audit state

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_trade_block_reason](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3355-L3396)
- [lowfreq_engine_v16_advanced.py:sell consumer](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3494-L3506)
- [lowfreq_engine_v16_advanced.py:buy consumer](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3699-L3711)
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L1088-L1125)

The problem is not missing business definition. The problem is:

- the real execution block policy still lives inline in the engine
- the helper is smaller and more reusable than the surrounding execution orchestration
- extracting it leaves the engine responsible only for price loading, audit, and position-side effects

## 4. Approach Options

### Option A: Extract only the pure block-reason policy and keep price loading plus execution orchestration in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move limit-board, amount, and participation checks there
- keep `_get_bar(...)` and `run_backtest()` side effects in the engine

Pros:

- isolates the real policy kernel cleanly
- avoids broadening into runtime orchestration
- aligns with the current thin-facade migration pattern

Cons:

- the engine still owns bar retrieval and consumer branching

### Option B: Extract the full execution pre-check branch from `run_backtest()`

Pros:

- removes more engine code at once

Cons:

- broadens into audit, counters, and order orchestration
- mixes pure policy with runtime side effects
- raises regression risk

### Option C: Keep `_trade_block_reason(...)` inline and rely on existing tests

Pros:

- smallest production diff

Cons:

- leaves one of the clearest remaining active execution-policy kernels inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure execution-policy side:

- interpret `bar` presence
- interpret limit-up / limit-down thresholds
- detect one-price board
- interpret min-amount threshold
- interpret participation-rate threshold
- return the normalized block reason string or `None`

This slice should not own:

- querying or shaping bars from SQLite
- selecting buy or sell execution branch flow
- emitting audit events
- mutating `trade_blocks`
- any position write or cash update

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/trade_block_reason.py`

Recommended ownership in that module:

- `resolve_trade_block_reason(...)`

Recommended signature:

- `resolve_trade_block_reason(*, bar: dict[str, Any] | None, side: str, trade_value: float, limit_up_pct: float, limit_down_pct: float, block_on_limit_up: bool, block_on_limit_down: bool, only_one_price_limit: bool, min_amount_cny: float, max_participation_rate: float) -> str | None`

The owner should accept explicit scalar inputs rather than the engine instance or config object.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_trade_block_reason(...)`

But with a narrower role:

- read `LowFreqV16Config.execution` fallback values
- resolve engine attribute overrides
- delegate the actual block policy to the new owner

Why keep the facade:

- current runtime code already calls this engine helper directly from active buy/sell paths
- this preserves private surface stability while moving the rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- if `bar` is not a dict, return `"missing_price_bar"`
- `buy` side still blocks on `limit_up` when enabled and threshold is hit
- `sell` side still blocks on `limit_down` when enabled and threshold is hit
- when `EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT` is enabled, limit-board block still requires `high == low == close`
- `min_amount` still blocks only when `amount < EXEC_MIN_AMOUNT_CNY`
- `participation_rate` still blocks only when `trade_value > amount * EXEC_MAX_PARTICIPATION_RATE`
- limit checks still run before amount / participation checks
- `None` remains the pass-through result when no block applies

No bar retrieval, audit-event, or execution-branch changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Minimum owner cases:

- missing bar returns `missing_price_bar`
- one-price `limit_up` blocks buy side when enabled
- non-one-price `limit_up` does not block when one-price mode is required
- `limit_down` blocks sell side when enabled
- insufficient amount blocks as `min_amount`
- oversized participation blocks as `participation_rate`
- non-blocked bar returns `None`

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L1088-L1125)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into execution orchestration

Guardrail:

- keep extraction limited to `_trade_block_reason(...)` only

Secondary risk:

- drifting config fallback precedence between engine attributes and `LowFreqV16Config.execution`

Guardrail:

- keep fallback resolution in the engine facade and test representative cases in the owner carrier

Third risk:

- changing reason precedence when multiple block conditions coexist

Guardrail:

- preserve the current check order: missing bar -> limit board -> amount -> participation

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/trade_block_reason.py`
2. move the pure block-reason policy there
3. turn `_trade_block_reason(...)` into a thin facade
4. add owner-focused tests
5. run focused syntax and execution-path regression verification

## 8. Success Criteria

This slice is complete when:

- the execution block-reason policy has one shared owner
- the real rule body no longer lives inline in the engine
- buy/sell execution branches remain unchanged
- owner-focused block-reason tests pass
- current execution-path regressions still pass
