# Lowfreq System Exit Snapshots Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `system_exit_grace eligibility policy` extraction.

This slice only freezes:

- the sell-side snapshot policy still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_market_exit_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2418-L2471)
  - [lowfreq_engine_v16_advanced.py:_sector_exit_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2473-L2517)

The goal is to:

- move the real market/sector exit snapshot policy into one shared owner
- keep market and sector data acquisition unchanged in the engine
- keep sell-state mutation unchanged in the engine
- preserve current `details` copy and evidence semantics exactly
- preserve current `condition_pass` thresholds exactly
- add direct owner-focused coverage for the snapshot contract

This design is not:

- a rewrite of `check_sell_signal_v2()`
- a rewrite of `_apply_system_exit_state(...)`
- a rewrite of `_position_contract_snapshot(...)`
- a rewrite of `_market_top_snapshot(...)`
- a rewrite of `_market_drawdown_snapshot(...)`
- a rewrite of `detect_sector_cooldown(...)`

Project-phase note:

- domain: `sell-side exit snapshot policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- market exit snapshot evidence normalization and confirmation predicate
- sector exit snapshot evidence normalization and confirmation predicate
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for market/sector snapshot policy
- focused regression for:
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
  - [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)

Excluded:

- market proxy resolution
- fetching `top_snapshot` / `drawdown_snapshot`
- calling `detect_sector_cooldown(...)`
- sell-state review/confirm transitions
- `trade.market_exit_*` / `trade.sector_exit_*` writes
- sell/grace audit-event emission
- trend exhaustion logic

## 3. Existing Context

Current repository evidence shows:

- `generate_buy_signals()` has largely collapsed to orchestration shell after the recent M3-owner extractions
- the next dense engine-owned kernel is on the sell side, not the buy side
- `_market_exit_snapshot(...)` and `_sector_exit_snapshot(...)` are both pure snapshot builders returning dict payloads without mutating `trade`
- these snapshots are consumed in two places:
  - direct sell decision flow in [check_sell_signal_v2](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3348-L3422)
  - hold/exit contract assembly in [_position_contract_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L664-L833)

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_market_exit_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2418-L2471)
- [lowfreq_engine_v16_advanced.py:_sector_exit_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2473-L2517)
- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L445-L615)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py#L1-L78)

The problem is not missing business definition. The problem is:

- the real market/sector snapshot rule body is still bundled into the engine
- the snapshot policy is denser and more reusable than the surrounding state-machine shell
- extracting the snapshot policy leaves the engine responsible only for:
  - collecting source data
  - applying state transitions
  - consuming snapshot payloads in sell/hold contracts

## 4. Approach Options

### Option A: Extract only the market/sector snapshot policy and keep data acquisition plus state mutation in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move snapshot interpretation and `condition_pass` logic there
- keep upstream snapshot sourcing and downstream state transitions in the engine

Pros:

- isolates the real rule kernel cleanly
- avoids broadening into sell-state orchestration
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps the upstream sourcing helpers

### Option B: Extract the whole sell-side exit-confirm chain including state mutation

Pros:

- removes more code from the engine at once

Cons:

- broadens into write-path logic and audit side effects
- mixes snapshot policy with state machine
- raises regression risk

### Option C: Keep snapshots inline and rely only on existing sell-logic coverage

Pros:

- smallest production diff

Cons:

- leaves the clearest remaining sell-side snapshot kernel inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure snapshot policy side:

- interpret `top_snapshot` plus `drawdown_snapshot` into a normalized market snapshot payload
- interpret `detect_sector_cooldown(...)` output into a normalized sector snapshot payload
- compute evidence flags and `condition_pass`
- preserve exact `details` rendering semantics

This slice should not own:

- resolving `market_key`
- fetching upstream market/sector inputs
- writing `trade.market_exit_*` or `trade.sector_exit_*`
- applying review/confirm transitions
- emitting audit events
- generating `SellSignal`

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/system_exit_snapshots.py`

Recommended ownership in that module:

- `build_market_exit_snapshot(...)`
- `build_sector_exit_snapshot(...)`

Recommended signatures:

- `build_market_exit_snapshot(*, top_snapshot: dict[str, Any] | None, drawdown_snapshot: dict[str, Any] | None, fallback_market_label: str, fallback_market_key: str, min_drawdown_pct: float) -> dict[str, Any] | None`
- `build_sector_exit_snapshot(*, sector: str, cooldown_info: dict[str, Any] | None) -> dict[str, Any] | None`

The owner should accept already-fetched explicit inputs rather than the engine instance itself.

### 5.3 Engine Facade Boundary

The engine should keep these helper names:

- `_market_exit_snapshot(...)`
- `_sector_exit_snapshot(...)`

But they should become thin facades:

- the market facade still resolves proxy and fetches `top_snapshot` / `drawdown_snapshot`
- the sector facade still fetches `detect_sector_cooldown(...)`
- both facades delegate the interpretation work to the new owner

Why keep the facades:

- `check_sell_signal_v2()` and `_position_contract_snapshot(...)` already call these engine helpers directly
- existing tests stub these helper names on the engine instance
- this preserves private surface stability while moving the real rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- market label falls back from `top_snapshot` to `drawdown_snapshot` to `"市场"`
- market key falls back from `market_key` input to resolved proxy key
- `price_trend_weak = break_ma20 or ma20_weak`
- `breadth_weak` still means `breadth_ratio < 0.40`
- `drawdown_weak` still means `drawdown_pct <= MARKET_EXIT_MIN_DRAWDOWN_PCT`
- market `condition_pass` still requires:
  - `price_trend_weak`
  - `breadth_weak`
  - `evidence_count >= 2`
- market snapshot still returns `None` only when no evidence exists at all
- `drawdown_weak` remains observation-only evidence and does not independently confirm exit
- sector `follower_weak` still means `follower_weakness > 0.6`
- sector `trend_deteriorating` still means `trend_state in {"diverging", "falling"}`
- sector `leader_rollover` still means `leader_strength < 0.55 or leader_avg < 8.0`
- sector `condition_pass` still requires both:
  - `trend_deteriorating`
  - `follower_weak`
- sector snapshot still returns `None` only when all observation signals are absent
- `cooldown_detected` and `leader_rollover` remain observation-only evidence
- the exact `details` text format must remain unchanged

No state, threshold, or copy changes beyond ownerization are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_snapshots.py`

Minimum owner cases:

- market snapshot confirms with trend weak plus breadth weak even when drawdown is not weak
- market snapshot keeps large drawdown as observation-only evidence
- market snapshot does not confirm on drawdown-only weakness
- market snapshot returns `None` when no market evidence exists
- sector snapshot confirms only when both trend deterioration and follower weakness are present
- sector snapshot keeps cooldown plus leader rollover as observation-only evidence
- sector snapshot returns `None` when sector is blank
- sector snapshot returns `None` when cooldown info is missing

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into sell-state mutation or upstream data-fetch logic

Guardrail:

- keep extraction limited to interpreting already-fetched inputs

Secondary risk:

- drifting the existing `details` strings or observation-only semantics

Guardrail:

- preserve existing string templates exactly and test the returned flags directly

Third risk:

- changing the snapshot return-null boundary

Guardrail:

- keep the current `None` behavior tied only to complete absence of evidence

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/system_exit_snapshots.py`
2. move market/sector snapshot interpretation there
3. turn the engine snapshot helpers into thin facades
4. add owner-focused tests
5. run focused syntax and sell-side regression verification

## 8. Success Criteria

This slice is complete when:

- market and sector exit snapshots have one shared owner
- the real snapshot rule bodies no longer live inline in the engine
- upstream sourcing and downstream sell-state mutation remain unchanged
- owner-focused snapshot tests pass
- current sell-side consumer regressions still pass
