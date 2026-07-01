# Lowfreq Top200 Capacity Experiment Design

## Context

The current `2025 Top200` attribution result under the widened market-cap band (`100e8 -> 2500e8`) shows:

- `picked_count`: `50 -> 135`
- `bought_count`: `9 -> 11`
- `held_to_top_count`: `0 -> 1`
- `picked_not_bought`: `41 -> 124`

This confirms the primary bottleneck has shifted from seed-entry coverage to execution capacity. Most newly captured bull-stock signals are now blocked by `信号存在但同期仓位已满`.

The user explicitly requested:

- keep this work as an experiment only, not a new default model baseline;
- increase initial capital to `5000万`;
- prioritize increasing position count instead of keeping the current `3` slots;
- align limit-up / limit-down execution blocking with actual trading conditions, using an `only one-price limit board blocks execution` rule.

## Goal

Run one isolated `2025 Top200` experiment that answers whether capacity constraints, not signal quality, are the dominant reason newly surfaced bull stocks still fail to convert from `picked` to `bought`.

## Approved Experiment Scope

The experiment changes apply only to the `2025` payload rerun and the refreshed `Top200` attribution report used for comparison.

It does not change the default low-frequency engine baseline.

### Experiment Parameters

- `initial_capital = 50_000_000`
- `MAX_POSITIONS = 8`
- buy / sell limit blocking rule changes from `touching limit pct blocks execution` to `one-price limit board blocks execution`

### Explicit Non-Goals

- no default change to `LowFreqTradingEngineV16`
- no default change to `LowFreqV16Config`
- no change to `BUY_THRESHOLD`, `HOT_SECTOR_COUNT`, `CROSS_SECTOR_SCAN_LIMIT`, or market-top logic
- no attempt to redesign full portfolio sizing logic beyond the temporary `8`-slot experiment

## Design

### 1. Experiment Injection

Implement the experiment via explicit overrides at run time so the default engine remains unchanged.

The rerun path should:

- instantiate `LowFreqTradingEngineV16()`;
- override `MAX_POSITIONS` to `8`;
- call `run_backtest(..., initial_capital=50_000_000, include_trades=True)`;
- persist a dedicated payload artifact with clear experiment metadata.

### 2. One-Price Limit Board Execution Rule

The current execution gate blocks on daily `pct_change` reaching the configured limit threshold. This is stricter than real trading conditions because non-one-price limit days may still have intraday executable liquidity.

For this experiment only:

- buy-side blocking should occur only when the security is effectively a one-price涨停 board;
- sell-side blocking should occur only when the security is effectively a one-price跌停 board.

Operationally, the execution check should use the daily bar shape, not only `pct_change`.

The minimum acceptable detection rule is:

- `high == low == close` and the daily percentage move is at or beyond the configured limit threshold.

This is intentionally conservative and should be implemented as an experiment-only override, not as a permanent default.

### 3. Output Artifacts

The experiment must produce:

- a dedicated backtest payload JSON;
- a dedicated `2025 Top200` attribution report directory;
- a delta summary against the current widened-market-cap experiment.

## Validation

The comparison must report:

- `picked_count`
- `bought_count`
- `held_to_top_count`
- `not_picked`
- `picked_not_bought`
- the top reasons inside `picked_not_bought`
- the newly bought examples and newly held-to-top examples

## Risks

- Increasing slots from `3` to `8` changes portfolio concentration materially, so results must be interpreted as a capacity experiment, not as the new production strategy.
- The one-price-board proxy is still a daily-bar approximation and cannot perfectly reconstruct intraday queue conditions.
- Higher initial capital may interact with execution participation constraints if those are tightened later, so conclusions should stay limited to the current execution model.
