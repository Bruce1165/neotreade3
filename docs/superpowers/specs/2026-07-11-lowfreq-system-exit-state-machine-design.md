# Lowfreq System Exit State Machine Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `thesis invalidation snapshot` extraction.

This slice only freezes:

- the sell-side system-exit state machine still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_apply_system_exit_state](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2496-L2634)

The goal is to:

- move the real observe/review/confirm/expire transition kernel into one shared owner
- keep trade attribute writes unchanged in the engine
- keep audit-event emission unchanged in the engine
- keep grace-eligibility predicate ownership unchanged
- preserve current confirmation thresholds, event semantics, and final sell details exactly
- add direct owner-focused coverage for the state-machine contract

This design is not:

- a rewrite of `check_sell_signal_v2()`
- a rewrite of `_system_exit_attr_names(...)`
- a rewrite of `_reset_system_exit_state(...)`
- a rewrite of `_reset_all_system_exit_states(...)`
- a rewrite of `_record_system_exit_audit_event(...)`
- a rewrite of `_record_system_exit_grace_audit_event(...)`
- a rewrite of `_system_exit_expire_date(...)`
- a rewrite of market/sector exit snapshots
- a rewrite of `system_exit_grace` eligibility policy

Project-phase note:

- domain: `sell-side system exit state machine`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- state-machine transition interpretation for:
  - watch expiry
  - watch start
  - hit accumulation
  - review promotion
  - confirmation
  - grace downgrade versus final confirmation branch
- scope-aware confirmation window and confirm-hit calculation
- leader extra-hit application inside the state machine
- final confirmed details and `exit_scope` interpretation
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the transition contract
- focused regression for:
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L160-L443)
  - [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py#L194-L217)

Excluded:

- reading and writing `trade.market_exit_*` / `trade.sector_exit_*`
- computing `elapsed` trading days via `_count_trading_days(...)`
- computing expire dates via `_system_exit_expire_date(...)`
- computing `current_return_pct`, `peak_return_pct`, and `profit_keep_ratio`
- evaluating `system_exit_grace` eligibility itself
- emitting sell or grace audit events
- constructing `SellSignal`
- resetting the sibling scope after confirmation in `check_sell_signal_v2()`

## 3. Existing Context

Current repository evidence shows:

- hard invalidation, trend exhaustion, market/sector snapshots, and grace eligibility have already been ownerized
- the remaining dense sell-side kernel is now `_apply_system_exit_state(...)`
- the method already sits between ownerized snapshot/policy helpers and engine-owned side effects
- the method is called twice from the main sell chain:
  - market branch in [check_sell_signal_v2](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3300-L3315)
  - sector branch in [check_sell_signal_v2](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3317-L3329)

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_apply_system_exit_state](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2496-L2634)
- [lowfreq_engine_v16_advanced.py:_system_exit_attr_names](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2258-L2267)
- [lowfreq_engine_v16_advanced.py:_reset_system_exit_state](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2269-L2276)
- [lowfreq_engine_v16_advanced.py:_system_exit_expire_date](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2340-L2349)
- [lowfreq_engine_v16_advanced.py:_record_system_exit_grace_audit_event](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2358-L2390)
- [lowfreq_engine_v16_advanced.py:_record_system_exit_audit_event](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2453-L2494)
- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L160-L443)

The problem is not missing business definition. The problem is:

- the real observe/review/confirm state machine is still bundled into the engine
- the transition kernel is denser and more reusable than the surrounding attribute-write and audit shell
- extracting the transition kernel leaves the engine responsible only for:
  - deriving elapsed/watch metadata
  - applying returned mutations to `trade`
  - emitting audit events
  - constructing the final `SellSignal`

## 4. Approach Options

### Option A: Extract only the pure transition kernel and keep writes, audit, and final signal construction in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move state transition interpretation and confirmation rendering there
- keep `trade` mutation and audit side effects in the engine

Pros:

- isolates the real state-machine kernel cleanly
- avoids broadening into write-path and audit concerns
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps mutation and side-effect orchestration

### Option B: Extract the whole `_apply_system_exit_state(...)` flow including `trade` writes and audit emission

Pros:

- removes more code from the engine at once

Cons:

- broadens into mutable runtime state
- mixes pure transition policy with side effects
- raises regression risk

### Option C: Keep the state machine inline and rely only on existing sell-logic coverage

Pros:

- smallest production diff

Cons:

- leaves the clearest remaining sell-side state kernel inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure transition-policy side:

- interpret current watch metadata plus snapshot presence into the next transition
- decide whether the current watch expires before processing the current snapshot
- decide whether the current hit starts watch, promotes review, or confirms
- decide whether the confirm branch downgrades via grace or produces final confirmation
- render confirmed details and final `exit_scope`

This slice should not own:

- reading attr names from `_system_exit_attr_names(...)`
- writing `trade.market_exit_*` or `trade.sector_exit_*`
- resetting state through engine helpers
- emitting audit events
- computing `current_return_pct`, `peak_return_pct`, or `profit_keep_ratio`
- evaluating grace eligibility itself
- constructing `SellSignal`

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/system_exit_state_machine.py`

Recommended ownership in that module:

- `evaluate_system_exit_transition(...)`

Recommended signature:

- `evaluate_system_exit_transition(*, scope: str, window: int, confirm_hits: int, current_key: str, start_value: str, state_value: str, hit_count: int, last_hit_date: str, snapshot: dict[str, Any] | None, elapsed_watch_days: int | None, grace_eligible: bool, grace_used: bool) -> dict[str, Any]`

The owner should accept already-derived explicit inputs rather than the engine instance or `trade`.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_apply_system_exit_state(...)`

But with a narrower role:

- derive scope config and elapsed-watch metadata
- call `_eligible_for_system_exit_grace(...)` only at confirm time
- delegate the transition interpretation to the new owner
- apply returned writes to `trade`
- emit audit events based on returned transition flags
- construct `SellSignal` from the returned confirmation payload

Why keep the facade:

- `check_sell_signal_v2()` already calls this helper directly for market and sector paths
- current tests pin runtime side effects through the engine helper chain
- this preserves the private surface while moving the real transition kernel out

### 5.4 Returned Transition Contract

The owner should return one normalized transition payload that may include:

- `expired_before_processing`
- `start_watch`
- `advance_hit`
- `enter_review`
- `confirm_signal`
- `use_grace`
- `emit_grace_then_confirmed_event`
- `next_state`
- `next_hits`
- `confirmed_details`
- `exit_scope`
- `audit_event_type`

The payload should describe intent only. The engine remains responsible for applying side effects.

### 5.5 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- market scope still uses:
  - `MARKET_EXIT_CONFIRM_WINDOW`
  - `MARKET_EXIT_CONFIRM_HITS`
- sector scope still uses:
  - `SECTOR_EXIT_CONFIRM_WINDOW`
  - `SECTOR_EXIT_CONFIRM_HITS`
- leader hold still adds `LEADER_CONFIRM_EXTRA_HITS`
- a started watch still expires when `elapsed > window`
- invalid or non-passing snapshots still do not start or advance a watch
- the first valid hit still starts `observe`
- a second valid hit still promotes `review`
- hit count still does not double-increment on the same day
- confirmation still requires `hit_count >= confirm_hits`
- grace downgrade still takes priority over final confirmation when eligible
- a previously used grace still triggers `system_exit_downgraded_then_confirmed` before final confirmation
- confirmed details still replace `"确认候选"` with `"确认"`
- market confirmation still maps to `exit_scope = "portfolio"`
- sector confirmation still maps to `exit_scope = "sector_only"`

No mutation, audit, or sibling-scope reset changes are part of this slice.

### 5.6 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_state_machine.py`

Minimum owner cases:

- no passing snapshot returns a no-op transition
- expired watch emits the expiry transition before current processing
- first valid hit starts observe with hit count `1`
- second distinct-day hit enters review
- same-day repeat hit does not increment hit count
- confirm branch produces `confirm_signal = True` when hits reach threshold
- grace-eligible confirm branch returns `use_grace = True`
- previously downgraded confirm branch emits `emit_grace_then_confirmed_event = True`
- market scope returns `exit_scope = "portfolio"`
- sector scope returns `exit_scope = "sector_only"`

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L160-L443)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py#L194-L217)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into `trade` mutation or audit emission

Guardrail:

- keep the owner limited to intent-level transition output only

Secondary risk:

- drifting hit-count or same-day increment semantics

Guardrail:

- test repeated-day and threshold transitions directly in the owner carrier

Third risk:

- changing final confirmed details or `exit_scope`

Guardrail:

- preserve the current string replacement and scope mapping exactly

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/system_exit_state_machine.py`
2. move pure transition interpretation there
3. turn `_apply_system_exit_state(...)` into a thin facade around the owner
4. add owner-focused tests
5. run focused syntax and sell-side regression verification

## 8. Success Criteria

This slice is complete when:

- the system-exit transition kernel has one shared owner
- the real transition rule body no longer lives inline in the engine
- trade mutation, audit emission, and outer sell-chain orchestration remain unchanged
- owner-focused state-machine tests pass
- current sell-side consumer regressions still pass
