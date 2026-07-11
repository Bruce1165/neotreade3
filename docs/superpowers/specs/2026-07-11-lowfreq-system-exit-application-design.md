# Lowfreq System Exit Application Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `trade block reason` extraction.

This slice only freezes:

- the remaining application-shell planning logic still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_apply_system_exit_state](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2511-L2682)

The goal is to:

- move the pure "transition intent -> application plan" logic into one shared owner
- keep transition evaluation unchanged in the engine
- keep `trade` mutation unchanged in the engine
- keep sell and grace audit-event emission unchanged in the engine
- keep final `SellSignal` construction unchanged in the engine
- preserve current expire / start / review / grace / confirm application semantics exactly
- add direct owner-focused coverage for the application-plan contract

This design is not:

- a rewrite of `evaluate_system_exit_transition(...)`
- a rewrite of `_eligible_for_system_exit_grace(...)`
- a rewrite of `_system_exit_attr_names(...)`
- a rewrite of `_reset_system_exit_state(...)`
- a rewrite of `_reset_all_system_exit_states(...)`
- a rewrite of `_record_system_exit_audit_event(...)`
- a rewrite of `_record_system_exit_grace_audit_event(...)`
- a rewrite of `check_sell_signal_v2()`

Project-phase note:

- domain: `system exit application shell`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- expire-existing-watch application planning
- start-watch application planning
- hit increment and last-reason update planning
- review-enter application planning
- grace downgrade application planning
- follow-up confirm-after-grace application planning
- final sell payload planning
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the application-plan contract
- focused regression for:
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L160-L443)

Excluded:

- elapsed watch-day calculation
- grace eligibility calculation
- return metric calculation
- direct `trade` attribute writes
- reset helper execution
- audit-event emission
- `SellSignal` construction

## 3. Existing Context

Current repository evidence shows:

- the pure transition kernel is already ownerized in:
  - [system_exit_state_machine.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/system_exit_state_machine.py)
- `_apply_system_exit_state(...)` still owns the dense remaining shell that interprets transition payloads into:
  - expire/start/review actions
  - grace downgrade actions
  - final confirm actions
- this helper is still in the active sell path through:
  - [check_sell_signal_v2](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3221-L3295)
- current sell-side regressions already cover:
  - observe/review/confirm
  - expiry reset
  - grace downgrade
  - confirm-after-grace
  - sibling-scope reset behavior

Repository evidence:

- [_apply_system_exit_state](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2511-L2682)
- [system_exit_state_machine.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/system_exit_state_machine.py)
- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L160-L443)

The problem is no longer a missing policy definition. The problem is:

- the engine still owns a dense mapping layer from transition payloads to concrete side-effect intent
- that mapping is deterministic and pure before actual `trade` mutation and event emission happen
- extracting that plan layer keeps the engine focused on side effects only

## 4. Approach Options

### Option A: Extract only the pure application-plan layer and keep all real side effects in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move expire/start/review/grace/confirm application planning there
- keep `trade` writes, reset helper calls, audit calls, and `SellSignal` construction in the engine

Pros:

- narrows the remaining shell without broadening into mutation infrastructure
- aligns with the current thin-facade migration pattern
- preserves the existing transition owner boundary

Cons:

- the engine still performs all actual side effects

### Option B: Extract the full `_apply_system_exit_state(...)` wrapper including side effects

Pros:

- removes more code from the engine at once

Cons:

- mixes pure planning with mutation and audit side effects
- increases regression risk
- breaks the current owner/pure-function discipline

### Option C: Stop here and keep the remaining shell inline

Pros:

- no new production movement

Cons:

- leaves the densest remaining active sell-side shell inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure planning side:

- interpret `expire_existing_watch`
- interpret `start_watch`
- interpret `increment_hit`
- interpret `enter_review`
- interpret `confirm_signal`
- map grace versus final confirm into concrete application intents
- derive the sell payload contract when confirmation should emit a sell signal

This slice should not own:

- resolving scope attr names
- computing elapsed trading days
- calling `evaluate_system_exit_transition(...)`
- calculating grace eligibility
- reading/writing `trade`
- calling reset helpers
- emitting audit events
- instantiating `SellSignal`

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/system_exit_application.py`

Recommended ownership in that module:

- `plan_system_exit_application(...)`

Recommended signature:

- `plan_system_exit_application(*, current_key: str, expire_date: str, transition: dict[str, Any], signal_reason: str, signal_confidence: float) -> dict[str, Any]`

The owner should accept already-derived transition payloads and scalar values rather than the engine instance or `trade`.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_apply_system_exit_state(...)`

But with a narrower role:

- derive window / confirm-hit settings
- compute elapsed watch days
- call `evaluate_system_exit_transition(...)`
- compute grace eligibility and return metrics when needed
- delegate the actual application planning to the new owner
- execute mutation, audit, reset, and `SellSignal` side effects

Why keep the facade:

- current runtime code already calls this engine helper directly
- this preserves private surface stability while removing the dense application-plan branch body

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- expired watch still emits the expire action before current-day processing
- non-passing snapshot still returns `None` after optional expiry handling
- first passing hit still starts `observe`, stores `start`, `expire`, `hits`, `last_reason`, and `last_hit`
- later passing hit still updates `last_reason`
- distinct-day follow-up hit still increments `hits` and updates `last_hit`
- review entry still happens only when the transition says `enter_review`
- grace downgrade still resets all system-exit states and does not emit a sell signal
- follow-up confirm after prior grace still carries the dedicated grace-follow-up event intent
- final confirmation still resets only the current scope and returns the current sell payload contract

No grace eligibility calculation, audit-event emission, or `SellSignal` construction changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

Minimum owner cases:

- expired non-passing snapshot returns expire intent and no sell payload
- start-watch transition returns the expected start/update plan
- review transition returns increment plus review intent
- grace-confirm transition returns grace fields plus reset-all intent and no sell payload
- confirm-after-grace returns follow-up grace event plus final sell payload
- plain confirm returns final sell payload and scope reset intent

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L160-L443)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into actual mutation or audit emission

Guardrail:

- keep the owner limited to pure application planning only

Secondary risk:

- drifting action precedence between expiry, start, grace, and final confirmation

Guardrail:

- preserve current branch ordering exactly and test each representative application shape directly

Third risk:

- leaking engine-only concerns like attr names or reset helper calls into the owner

Guardrail:

- keep the owner output semantic and attribute-name-agnostic

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/system_exit_application.py`
2. move the pure application-plan mapping there
3. turn `_apply_system_exit_state(...)` into a thinner facade
4. add owner-focused tests
5. run focused syntax and sell-path regression verification

## 8. Success Criteria

This slice is complete when:

- the remaining application-plan shell has one shared owner
- `_apply_system_exit_state(...)` no longer owns the dense branch mapping inline
- mutation, audit, and final sell construction remain unchanged in the engine
- owner-focused application-plan tests pass
- current sell-side consumer regressions still pass
