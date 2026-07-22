Status: active
Owner: lowfreq / decision_engine
Scope: Narrow M3 position contract snapshot extraction from the lowfreq engine
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Position Contract Snapshot Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the `rotation candidate` owner extraction.

This slice freezes only the hold/exit position contract shaping that still lives inline in:

- [lowfreq_engine_v16_advanced.py:_position_contract_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L696-L865)

The goal is to:

- move the dense hold/exit attribution contract shaping into one shared owner
- keep runtime snapshot fetching unchanged in the engine
- keep API/workbench observable fields unchanged
- keep current hold-state, attribution-bucket, evidence, and warning semantics unchanged
- add direct owner-focused coverage for the position contract contract

This design is not:

- a rewrite of `check_sell_signal_v2(...)`
- a rewrite of `_market_exit_snapshot(...)`
- a rewrite of `_sector_exit_snapshot(...)`
- a rewrite of `_trend_exhaustion_snapshot(...)`
- a rewrite of API portfolio assembly
- a rewrite of trade mutation or exit execution

Project-phase note:

- domain: `position hold/exit attribution contract`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G5-G6`

## 2. Scope

Included:

- market/sector/grace state normalization into evidence and warning flags
- latest transition date selection
- exit-ready contract shaping
- hold-state classification
- not-exit reason shaping
- hold/exit attribution bucket assignment
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for hold and exit contract behavior

Excluded:

- price lookup
- market/sector/trend snapshot generation
- `SellSignal` generation
- API portfolio loop orchestration
- workbench summary rendering
- audit-event writing

## 3. Existing Context

Current repository evidence shows:

- `_position_contract_snapshot(...)` is still a dense inline rule cluster in the engine:
  - [lowfreq_engine_v16_advanced.py:L696-L865](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L696-L865)
- the engine method already separates runtime collaborator calls from final contract shaping:
  - `_get_price(...)`
  - `_market_exit_snapshot(...)`
  - `_sector_exit_snapshot(...)`
  - `_trend_exhaustion_snapshot(...)`
- the returned fields are consumed directly by API portfolio payload construction:
  - [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L18015-L18059)
- the returned `not_exit_reasons` and `warning_flags` are further consumed by workbench summary rendering:
  - [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L21643-L21650)
- nearby tests already lock two important observable behaviors:
  - hold-side partial weakness stays in hold layer
  - trend exhausted sell maps to `trend_exhaustion_exit`
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L556-L605)

So the problem is not missing business definition. The problem is:

- the engine still owns a dense but self-contained position contract shaping kernel
- the kernel already has a natural facade boundary: runtime snapshots in engine, contract assembly in owner
- extracting it improves owner clarity without changing execution flow

## 4. Approach Options

### Option A: Extract only the contract-shaping kernel into one M3 owner and keep runtime snapshot lookup in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move hold/exit contract shaping there
- keep runtime price/snapshot lookup in the engine facade

Pros:

- isolates the remaining dense M3 contract kernel cleanly
- preserves API/workbench contract surface
- avoids touching sell-side execution flow

Cons:

- the engine still keeps runtime snapshot collection

### Option B: Extract the whole position snapshot flow including runtime collaborators

Pros:

- removes more lines from the engine at once

Cons:

- broadens into DB access and runtime snapshot ownership
- raises regression risk across API portfolio construction

### Option C: Keep the helper inline and rely on current sell logic tests

Pros:

- smallest production diff

Cons:

- leaves a dense contract-shaping kernel inline
- leaves no direct owner-focused tests for the assembled contract

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the final position contract shaping:

- normalize market/sector/grace reasons into evidence
- normalize snapshot booleans into warning flags
- derive the latest transition date
- build the `exit_ready` contract branch
- build the hold-side branch
- derive:
  - `hold_state`
  - `hold_attribution_bucket`
  - `exit_attribution_bucket`
  - `not_exit_reasons`
  - `exit_evidence_bundle`

This slice should not own:

- fetching current price
- computing market/sector/trend snapshots
- computing sell signals
- mutating `trade`
- assembling the outer API position list

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/position_contract_snapshot.py`

Recommended ownership in that module:

- `build_position_contract_snapshot(...)`

Recommended signature:

- `build_position_contract_snapshot(*, market_state: str, sector_state: str, market_reason: str, sector_reason: str, grace_used: bool, grace_reason: str, market_snapshot: dict[str, Any] | None, sector_snapshot: dict[str, Any] | None, trend_snapshot: dict[str, Any] | None, sell_payload: dict[str, Any] | None, current_date_key: str, market_last_hit_date: str, sector_last_hit_date: str, grace_date: str, layer_contract_builder: Callable[..., dict[str, Any]]) -> dict[str, Any]`

Why keep one function:

- this kernel is primarily one observable payload contract
- splitting it further would not reduce risk meaningfully in this slice
- a single owner keeps API-consumed shape reviewable in one place

### 5.3 Engine Facade Boundary

The engine should keep:

- `_position_contract_snapshot(...)`

But with a narrower role:

- fetch current price
- fetch market/sector/trend snapshots
- normalize `SellSignal` into a plain payload
- pass scalar state into the new owner

The engine should not keep:

- the dense evidence/flag bucket shaping
- the hold-state ladder
- the exit bucket ladder

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- `market_exit_state:*` and `sector_exit_state:*` flags still appear when the state is present
- `system_exit_grace_used` still appears in warning flags when active
- market/sector/trend snapshot details still append into evidence only once
- `last_transition` still chooses the latest non-empty value from:
  - `market_exit_last_hit_date`
  - `sector_exit_last_hit_date`
  - `system_exit_grace_date`
- when `sell_payload` exists:
  - `hold_state` stays `exit_ready`
  - `exit_ready` stays `True`
  - exit attribution bucket still maps:
    - `thesis_invalidated -> invalidation_exit`
    - `trend_exhausted -> trend_exhaustion_exit`
    - `market_top_confirmed -> market_timing_exit`
    - `sector_top_confirmed -> sector_timing_exit`
    - fallback -> `exit_other`
- when `sell_payload` is absent:
  - hold-state ladder remains:
    - `review_watch`
    - `observe_watch`
    - `noise_watch`
    - `grace_hold`
    - fallback `holding`
  - not-exit reasons remain unchanged
  - hold attribution bucket remains:
    - `hold_grace`
    - `hold_noise_watch`
    - `hold_confirmed`

No API schema changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py`

Minimum owner cases:

- hold-side partial weakness stays `noise_watch` and `hold_noise_watch`
- active grace hold maps to `grace_hold` and appends grace note
- exit-side trend exhausted maps to `trend_exhaustion_exit`
- exit-side unknown reason falls back to `exit_other`
- latest transition picks the latest non-empty date

Keep and re-run nearby consumer guard:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L556-L605)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into runtime snapshot or API orchestration ownership

Guardrail:

- keep runtime collaborator calls in the engine facade and extract only final contract shaping

Secondary risk:

- changing API/workbench-observed field names or bucket strings

Guardrail:

- preserve field names and bucket labels exactly
- verify owner contract directly and re-run nearby consumer guards

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/position_contract_snapshot.py`
2. move the final contract-shaping kernel there
3. turn `_position_contract_snapshot(...)` into a thin facade
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the position hold/exit contract kernel has one shared owner
- the dense inline contract shaping no longer lives in the engine
- runtime snapshot lookup remains in the engine
- owner-focused tests pass
- nearby sell logic guards still pass
- syntax verification passes
