Status: active
Owner: lowfreq / decision_engine
Scope: Narrow M3 rotation-candidate snapshot and selection extraction from the lowfreq engine
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Rotation Candidate Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `system_exit_application` contract alignment cleanup.

This slice only freezes:

- the weak-hold rotation candidate snapshot rule still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_rotation_candidate_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3097-L3204)
- the best-candidate selection rule still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_select_rotation_candidate](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3205-L3245)

The goal is to:

- move the pure rotation-candidate rule kernel into one shared owner
- keep runtime execution orchestration unchanged in the engine
- keep market and sector exit snapshot generation unchanged
- keep rotation cache semantics unchanged
- keep candidate priority math, threshold math, and details copy unchanged
- add direct owner-focused coverage for the rotation snapshot and selection contract

This design is not:

- a rewrite of `run_backtest()`
- a rewrite of `_market_exit_snapshot(...)`
- a rewrite of `_sector_exit_snapshot(...)`
- a rewrite of `_profit_keep_ratio(...)`
- a rewrite of `_get_bar(...)`
- a rewrite of rotation sell execution or buy reservation behavior
- a rewrite of any M2 cycle-intelligence contract

Project-phase note:

- domain: `rotation candidate rule kernel`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G2-G5-G6`

## 2. Scope

Included:

- execution-rotation enable flag interpretation
- incoming-versus-held score-gap threshold interpretation
- cached base-snapshot reuse
- current-price/current-return/peak-return snapshot shaping
- weakening and evidence threshold interpretation
- keep-ratio calculation passthrough
- priority calculation
- best-candidate comparison and tie-break ordering
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for snapshot and selection behavior

Excluded:

- position iteration outside the current rotation-candidate loop
- trade mutation
- sell signal creation
- reservation queue behavior
- market proxy resolution semantics
- market/sector exit evidence production
- backtest capital allocation flow

## 3. Existing Context

Current repository evidence shows:

- the engine still owns a self-contained rotation-candidate rule pair:
  - [_rotation_candidate_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3097-L3204)
  - [_select_rotation_candidate](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3205-L3245)
- `_select_rotation_candidate(...)` only consumes `_rotation_candidate_snapshot(...)` and compares candidate keys
- the snapshot helper is pure before reading runtime collaborators:
  - it returns a dict or `None`
  - it does not mutate `trade`
  - it does not emit events
- repository search shows no direct owner-focused tests for:
  - `rotation_candidate`
  - `_rotation_candidate_snapshot`
  - `_select_rotation_candidate`
- many adjacent rule kernels have already been ownerized into `neotrade3/decision_engine/` or `neotrade3/cycle_intelligence/`, so this pair is now one of the clearest remaining inline M3 kernels

Repository evidence:

- [lowfreq_engine_v16_advanced.py:L3097-L3245](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3097-L3245)
- [lowfreq_engine_v16_advanced.py imports](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L25-L103)

The problem is not missing business definition. The problem is:

- the engine still owns a dense but isolated rule cluster for weak-hold rotation replacement
- that cluster already has a natural internal boundary: snapshot building then best-candidate selection
- extracting this cluster keeps the engine focused on orchestration while preserving current runtime semantics

## 4. Approach Options

### Option A: Extract the pure rotation snapshot and selection kernel into one M3 owner and keep orchestration in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move snapshot shaping and best-candidate comparison there
- keep bar lookup, market/sector snapshot calls, and outer backtest orchestration in the engine facade

Pros:

- isolates the remaining pure rule kernel cleanly
- avoids broadening into execution flow changes
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps the outer rotation orchestration branch

### Option B: Extract the whole runtime rotation branch from the engine

Pros:

- removes more code from the engine at once

Cons:

- broadens into execution flow and sell-side behavior
- mixes pure selection with runtime orchestration
- raises regression risk

### Option C: Keep the helper pair inline and rely only on backtest coverage

Pros:

- smallest production diff

Cons:

- leaves one of the clearest remaining inline M3 rule kernels in the engine
- keeps the rule unprotected by owner-focused tests

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure rotation-candidate rule side:

- reject rotation when execution rotation is disabled
- reject rotation when incoming score margin is below threshold
- build a normalized rotation snapshot from already-available collaborators
- reject candidates above the current-return ceiling
- reject candidates without weakening evidence or minimum evidence count
- derive keep ratio
- derive priority
- render details copy
- compare candidates using the current ordering:
  - `priority`
  - `score_gap`
  - lower `current_return_pct` wins on tie

This slice should not own:

- iterating the broader backtest loop
- mutating `trade`
- generating exit snapshots
- resolving bars from the database
- recording events
- creating any sell signal

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/rotation_candidate.py`

Recommended ownership in that module:

- `build_rotation_candidate_snapshot(...)`
- `select_rotation_candidate(...)`

Recommended signatures:

- `build_rotation_candidate_snapshot(*, rotation_enabled: bool, incoming_score: float, held_score: float, min_score_margin: float, base_snapshot: dict[str, Any] | None, max_current_return_pct: float, min_evidence: int, current_price: float, current_return_pct: float, peak_return_pct: float, market_evidence: int, sector_evidence: int, watch_active: bool, weakening: bool, keep_ratio: float, trade_code: str) -> dict[str, Any] | None`
- `select_rotation_candidate(*, candidate_snapshots: list[tuple[str, dict[str, Any]]]) -> tuple[str, dict[str, Any]] | None`

Why split it this way:

- the snapshot builder owns all threshold and priority interpretation
- the selector owns only comparison and best-candidate choice
- the engine facade keeps runtime collaborator calls and cache lookup/writeback

### 5.3 Engine Facade Boundary

The engine should keep:

- `_rotation_candidate_snapshot(...)`
- `_select_rotation_candidate(...)`

But with narrower roles:

- `_rotation_candidate_snapshot(...)`
  - resolve config values
  - read/write `rotation_cache`
  - fetch bar data
  - compute market/sector snapshots
  - derive scalar inputs
  - delegate final contract shaping to the new owner
- `_select_rotation_candidate(...)`
  - iterate positions
  - collect non-`None` candidate snapshots
  - delegate best-candidate selection to the new owner

Why keep the facade:

- current runtime code already calls these engine helpers directly
- this preserves private surface stability while moving the dense rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- disabled execution rotation still returns `None`
- insufficient `score_gap` still returns `None`
- missing or non-positive current price still returns `None`
- `rotation_cache` still caches only the base snapshot keyed by `(trade.code, current_date.isoformat())`
- current return above `EXECUTION_ROTATION_MAX_CURRENT_RETURN_PCT` still returns `None`
- candidates without weakening and without sufficient evidence still return `None`
- `priority` remains:
  - `score_gap`
  - plus `max_evidence * 10.0`
  - plus `5.0` when `watch_active`
  - plus `3.0` when `weakening`
  - minus `max(current_return_pct, 0.0) * 0.1`
- details copy remains:
  - `"弱化持仓换仓候选 | score_gap=... | market_evidence=... | sector_evidence=... | current_return=... | keep_ratio=..."`
- best-candidate ordering remains:
  - higher `priority`
  - then higher `score_gap`
  - then lower `current_return_pct`

No market-exit, sector-exit, or execution-flow changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_rotation_candidate.py`

Minimum owner cases:

- disabled execution rotation returns `None`
- insufficient score-gap returns `None`
- current return above ceiling returns `None`
- no weakening and insufficient evidence returns `None`
- weakening candidate with valid evidence returns the expected snapshot contract
- watch-active candidate receives the expected priority bonus
- selector returns `None` for empty candidate list
- selector prefers higher `priority`
- selector uses `score_gap` as the second tie-break
- selector uses lower `current_return_pct` as the third tie-break

Keep and re-run nearby consumer guards:

- focused regression on the owner test itself
- minimal syntax verification for:
  - [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into runtime execution flow or sell-side mutation

Guardrail:

- keep extraction limited to snapshot shaping and best-candidate selection only

Secondary risk:

- drifting cache semantics while extracting the pure rule body

Guardrail:

- keep cache lookup/writeback in the engine facade and pass a normalized base snapshot into the owner

Third risk:

- changing candidate ordering when priorities tie

Guardrail:

- preserve the exact tuple comparison order and verify it directly in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/rotation_candidate.py`
2. move the pure snapshot-shaping rule body there
3. move the best-candidate comparison rule there
4. turn the engine helpers into thin facades
5. add owner-focused tests
6. run focused syntax and contract verification

## 8. Success Criteria

This slice is complete when:

- the rotation-candidate rule kernel has one shared owner
- the dense rule body no longer lives inline in the engine
- backtest orchestration, trade mutation, and exit snapshot generation remain unchanged
- owner-focused rotation candidate tests pass
- focused syntax verification passes
