Status: active
Owner: lowfreq / analysis
Scope: Narrow extraction of attribution backtest payload envelope from scorecard script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Backtest Payload Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the ranking payload extraction.

This slice freezes only the backtest payload envelope that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the return payload block inside `_load_backtest_payload(...)`

The goal is to:

- move the visible attribution-side backtest payload contract into one analysis-side owner
- keep the script responsible for choosing between `--backtest-json` and live `run_backtest(...)`
- keep engine override behavior inside the script boundary
- preserve the current `_meta/summary/trade_blocks/config_snapshot/coverage_gaps/trades` payload shape exactly
- add direct owner-focused coverage for the payload envelope

This design is not:

- a rewrite of `run_backtest(...)`
- a rewrite of the `--backtest-json` fast path
- a rewrite of status progression
- a generic shared framework for all lowfreq backtest JSON payloads

Project-phase note:

- domain: `top200 attribution backtest payload`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the payload projection returned by `_load_backtest_payload(...)`
- preserving the current `_meta.status/requested_by/model/generated_at` field set
- preserving the current `summary/trade_blocks/config_snapshot/coverage_gaps/trades` top-level keys
- preserving current fallback behavior for non-dict / non-list inputs
- adding owner-focused tests for the backtest payload envelope

Excluded:

- changing how `backtest_json` is read
- changing `engine.MAX_POSITIONS` override behavior
- changing `engine.EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT` override behavior
- changing `engine.run_backtest(...)` arguments
- changing `status.json` writes
- changing the final report artifact writers
- migrating `scripts/run_lowfreq_top200_capacity_experiment.py` in this slice

## 3. Existing Context

Current repository evidence shows:

- the scorecard script still owns one visible backtest payload envelope:
  - [generate_lowfreq_top200_attribution_report.py:L91-L120](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L91-L120)
- that payload is consumed downstream as a structured contract, not as raw `run_backtest(...)` output:
  - [generate_lowfreq_top200_attribution_report.py:L690-L699](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L690-L699)
  - [generate_lowfreq_top200_attribution_report.py:L711-L717](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L711-L717)
- the visible field family is also repeated in a neighboring script, which supports that the envelope itself is stable:
  - [run_lowfreq_top200_capacity_experiment.py:L59-L80](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L59-L80)
- API readback paths also treat `trade_blocks/config_snapshot/coverage_gaps` as stable payload keys:
  - [main.py:L23168-L23207](file:///Users/mac/NeoTrade3/apps/api/main.py#L23168-L23207)

The current problem is:

- attribution-side backtest payload projection is still embedded inside the script helper
- execution orchestration and payload assembly remain mixed in the same function
- there is no dedicated owner under `neotrade3/analysis/` for this attribution report contract

## 4. Approach Options

### Option A: Add one attribution-specific backtest-payload owner and keep execution orchestration in the script (Recommended)

- create one dedicated analysis module for the payload envelope
- let the script keep:
  - local JSON read path
  - engine acquisition
  - engine overrides
  - `run_backtest(...)`
- let the owner project only the visible payload envelope

Pros:

- isolates one real contract without touching execution flow
- continues the current thin-consumer migration path
- avoids widening into service or API refactors

Cons:

- `_load_backtest_payload(...)` still owns orchestration after the slice

### Option B: Move the entire `_load_backtest_payload(...)` helper out of the script

Pros:

- fewer lines remain in the script

Cons:

- mixes file IO, engine lifecycle, overrides, and payload projection
- broadens into execution orchestration rather than a pure M3 contract

### Option C: Generalize one shared lowfreq backtest payload framework for all scripts and API responses

Pros:

- might reduce future duplication

Cons:

- current duplicate sites are not shape-identical
- would force premature abstraction across attribution, capacity experiment, and API payloads

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new analysis owner:

- `neotrade3/analysis/attribution_backtest_payload.py`

Recommended public function:

- `build_attribution_backtest_payload(...) -> dict[str, Any]`

Recommended inputs:

- `requested_by: str`
- `generated_at: str`
- `summary: Any`
- `trades: Any`

Why this file:

- the contract belongs to attribution-report analysis consumption, not to engine runtime ownership
- a dedicated file keeps this envelope discoverable without mixing it into artifact writers or reasoning owners

### 5.2 Contract Freeze

The helper must preserve the current observable payload shape:

- top-level keys:
  - `_meta`
  - `summary`
  - `trade_blocks`
  - `config_snapshot`
  - `coverage_gaps`
  - `trades`
- `_meta` fields:
  - `status`
  - `requested_by`
  - `model`
  - `generated_at`

The helper must preserve current coercions and fallbacks:

- `_meta.status -> "ok"`
- `_meta.requested_by -> str(... or "")`
- `_meta.model -> "lowfreq_engine_v16_advanced"`
- `_meta.generated_at -> str(... or "")`
- `summary -> summary if isinstance(summary, dict) else {}`
- `trade_blocks -> summary.get("trade_blocks", {}) if summary is dict else {}`
- `config_snapshot -> summary.get("config_snapshot", {}) if summary is dict else {}`
- `coverage_gaps -> summary.get("coverage_gaps", {}) if summary is dict else {}`
- `trades -> trades if isinstance(trades, list) else []`

The helper must not:

- read files
- create timestamps
- run backtests
- mutate engine config
- mutate `summary`
- mutate `trades`

### 5.3 Script Boundary

The script should keep:

- the `backtest_json.exists()` read branch
- engine acquisition from `BootstrapApiService`
- override handling for `MAX_POSITIONS`
- override handling for `EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT`
- `engine.run_backtest(...)`
- local `summary.pop("trades", None)` preparation

The script should stop owning:

- the inline return payload envelope inside `_load_backtest_payload(...)`

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_backtest_payload.py`

Minimum owner cases:

- projects the current payload keys and `_meta` coercions
- preserves summary-derived child payloads by reference
- falls back to `{}` and `[]` for invalid `summary` / `trades`
- keeps empty-string fallback for `requested_by` and `generated_at`

Nearby consumer rerun:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - syntax verification only; no broad integration harness is required for this slice

## 6. Risks and Guardrails

Main risk:

- accidentally moving engine override or `run_backtest(...)` ownership into the new helper

Guardrail:

- keep the helper signature payload-only and pass prepared values in

Secondary risk:

- over-generalizing to other lowfreq report payloads because of similar key names

Guardrail:

- limit the owner to the attribution-report backtest envelope only

## 7. Implementation Outline

Planned steps:

1. add `attribution_backtest_payload.py`
2. implement `build_attribution_backtest_payload(...)`
3. switch `_load_backtest_payload(...)` to call the new owner after local preparation
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the visible attribution backtest payload has one analysis-side owner
- `_load_backtest_payload(...)` no longer owns the inline payload envelope
- file/engine orchestration remain in the script
- payload shape remains unchanged
- owner-focused tests pass
- syntax verification passes
