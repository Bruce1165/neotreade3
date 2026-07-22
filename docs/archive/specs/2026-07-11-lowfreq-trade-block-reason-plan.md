# Lowfreq Trade Block Reason Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-trade-block-reason-design.md`

## 1. Goal

This plan covers only the next narrow `trade block reason` slice after the `chase entry snapshot` extraction.

This slice only handles:

- missing-bar passthrough
- limit-up / limit-down execution block interpretation
- min-amount and participation-rate execution block interpretation
- owner-focused coverage for the block-reason contract

The goal is to:

- move the real execution block-reason rule body into one shared owner
- keep bar retrieval and buy/sell runtime orchestration unchanged in the engine
- preserve current thresholds, one-price board semantics, reason precedence, and fallback behavior exactly
- add direct focused coverage for the execution block-reason policy

This slice does not:

- rewrite `_get_bar(...)`
- rewrite `run_backtest()`
- rewrite buy/sell audit emission
- rewrite `_normalize_execution_block_reason(...)`
- rewrite execution action projection

## 2. Starting Point

Current repository evidence shows:

- `_trade_block_reason(...)` is an active reusable execution-policy kernel
- the helper has two runtime consumers in buy and sell execution branches
- the helper already has direct focused tests
- the helper itself has no trade writes, queue mutation, or audit side effects

Relevant current engine helper:

- `_trade_block_reason(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

So the correct next slice is:

- extract only the pure execution block policy
- keep config fallback resolution in the facade
- keep buy/sell orchestration side effects in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/trade_block_reason.py`

Move the pure rule helper there:

- `resolve_trade_block_reason(...)`

Keep the engine method as a thin facade:

- `_trade_block_reason(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 4. Execution Steps

### TBR-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/trade_block_reason.py`
- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Freeze the observable contract:

- missing `bar` still returns `missing_price_bar`
- buy-side `limit_up` still blocks when enabled and threshold is hit
- sell-side `limit_down` still blocks when enabled and threshold is hit
- one-price board mode still requires `high == low == close`
- amount check still returns `min_amount`
- participation check still returns `participation_rate`
- no block still returns `None`
- current reason precedence remains unchanged

Completion check:

- no bar retrieval, audit-event emission, or execution-branch side effects are part of this slice

### TBR-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/trade_block_reason.py`

Move the pure block-reason body into:

- `resolve_trade_block_reason(...)`

Implementation rules:

- accept explicit scalars rather than the engine instance or config object
- do not read config directly inside the owner
- do not call `_get_bar(...)`
- do not emit events
- do not mutate counters or positions

Completion check:

- the block-reason policy can be understood independently from buy/sell runtime orchestration

### TBR-S3: Switch `_trade_block_reason(...)` to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- keep resolving `LowFreqV16Config.execution` fallback values
- replace the real block-policy body of `_trade_block_reason(...)`

Do not change:

- `_get_bar(...)`
- `run_backtest()`
- buy/sell execution branches
- `trade_blocks` mutation
- audit-event emission

Completion check:

- the engine keeps the same helper name but no longer owns the real policy body inline

### TBR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Minimum owner cases:

- missing bar returns `missing_price_bar`
- one-price `limit_up` blocks buy side
- non-one-price `limit_up` passes when one-price mode is required
- `limit_down` blocks sell side
- `min_amount` blocks low-liquidity bar
- `participation_rate` blocks oversized order
- valid bar returns `None`

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Completion check:

- the block-reason policy has direct focused coverage
- current execution-path consumer tests still pass unchanged

### TBR-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/trade_block_reason.py tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### TBR-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-trade-block-reason-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-trade-block-reason-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/trade_block_reason.py`
- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Must exclude:

- `_get_bar(...)`
- `run_backtest()` orchestration changes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into buy/sell orchestration

Guard:

- keep extraction limited to `_trade_block_reason(...)` only

Risk 2:

- drifting engine attribute override precedence

Guard:

- keep all config fallback resolution in the engine facade

Risk 3:

- changing reason precedence when multiple block conditions coexist

Guard:

- preserve the current check order and test each representative reason directly

## 6. Success Criteria

This slice is complete when:

- the execution block-reason policy has one shared owner
- the real rule body no longer lives inline in the engine
- buy/sell execution branches remain unchanged
- owner-focused block-reason tests pass
- current execution-path regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-trade-block-reason-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/trade_block_reason.py`
- `tests/unit/*`
- any other workspace changes
