# Lowfreq M3 Formal Front Payload Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `signal dedup owner` extraction.

This slice only freezes:

- the post-formal-front payload finalization block inside `generate_buy_signals()`

The goal is to:

- move the engine-owned formal-front payload finalization into a dedicated `M3` owner
- keep the engine-side call site as a thin compatibility facade
- preserve the current candidate attach, entry filtering, and `formal` passthrough contract exactly
- add direct owner-focused coverage for the finalization rule set

This design is not:

- a rewrite of `generate_buy_signals()`
- a rewrite of `build_lowfreq_formal_front_payload(...)`
- a rewrite of `attach_lowfreq_formal_front_payloads(...)`
- a redesign of signal payload assembly before formal-front attachment
- a redesign of market filtering or candidate sourcing

Project-phase note:

- domain: `M3 decision refinement`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- the engine block that:
  - attaches `formal` payloads to `candidate_signals`
  - rebuilds `entry_signals`
  - rebuilds `buy_signals`
  - writes `formal` onto the returned payload
- one owner entry under `neotrade3/decision_engine/formal_front.py`
- engine/internal call-site preservation
- owner-focused tests for attach, clone, and passthrough semantics
- focused regression for:
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

Excluded:

- [build_lowfreq_formal_front_payload](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L43-L145)
- [attach_lowfreq_formal_front_payloads](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L29-L40) behavior changes
- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2183-L2313) orchestration changes beyond preserving the current call point
- signal sourcing from hot-sector or cross-sector candidates
- signal deduplication
- signal payload assembly before formal attachment

## 3. Existing Context

Current repository evidence shows four important facts:

- the engine still owns the final formal-front payload write-back block:
  - [lowfreq_engine_v16_advanced.py:L2304-L2312](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2304-L2312)
- the real formal-front attach helper already exists outside the engine:
  - [formal_front.py:L29-L40](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L29-L40)
- the real formal-front projection owner already exists outside the engine:
  - [formal_front.py:L43-L145](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L43-L145)
- current tests already protect the downstream behavior through `generate_buy_signals()`:
  - [test_lowfreq_engine_v16_formal_front.py:L126-L188](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py#L126-L188)
  - [test_lowfreq_engine_v16_signal_convergence.py:L132-L299](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L299)

The problem is not uncertainty about behavior. The problem is:

- the formal-front finalize step is still embedded in the engine monolith
- the existing `formal_front.py` owner is incomplete because the last write-back step still lives in engine code
- downstream tests do not directly pin the attach + rebuild + passthrough semantics as one owner contract

## 4. Approach Options

### Option A: Extend `formal_front.py` with one finalize helper and keep engine as a thin facade (Recommended)

- keep all formal-front post-processing ownership inside the existing module
- move the final payload write-back block there
- let engine only call the owner

Pros:

- aligns ownership with the current `formal_front.py` boundary
- avoids inventing a second tiny file for the same domain
- keeps `generate_buy_signals()` stable

Cons:

- adds one more helper to an existing module

### Option B: Create a new `formal_front_payload.py` file

- split the finalize block into a brand-new module
- keep `formal_front.py` limited to projection and low-level attach helpers

Pros:

- very explicit physical separation

Cons:

- over-fragments one already narrow subdomain
- weakens the “single formal-front owner” story

### Option C: Keep production code unchanged and add tests only

- preserve the block inside the engine
- only add direct engine-facing tests

Pros:

- smallest code diff

Cons:

- does not reduce engine ownership
- leaves `formal_front.py` ownership unfinished

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- taking `signal_payload["candidate_signals"]`
- attaching `formal` items by code
- rebuilding `entry_signals` from attached candidates
- mirroring `buy_signals` from rebuilt `entry_signals`
- writing the raw `formal_payload` onto the returned payload

These responsibilities should be treated as:

- `M3 formal-front payload finalization`

They should not be treated as:

- formal input retrieval
- formal projection building
- signal sorting
- signal dedup
- candidate generation

### 5.2 Recommended File Boundary

Recommended owner file:

- `neotrade3/decision_engine/formal_front.py`

This module should additionally own:

- `finalize_lowfreq_formal_front_payload(...)`

Recommended signature:

- `finalize_lowfreq_formal_front_payload(signal_payload: dict[str, Any], *, formal_payload: dict[str, Any]) -> dict[str, Any]`

This helper should:

- read only the provided `signal_payload` and `formal_payload`
- call `attach_lowfreq_formal_front_payloads(...)`
- rebuild `entry_signals` as copied dict rows
- rebuild `buy_signals` as `list(entry_signals)`
- return the finalized payload dict

This helper should not own:

- DB access
- formal projection SQL orchestration
- pre-formal signal payload assembly

### 5.3 Engine Compatibility Surface

The engine should keep a local compatibility point after the formal projection call, but the real finalize body should move out.

Recommended use:

- call `finalize_lowfreq_formal_front_payload(signal_payload, formal_payload=formal_payload)`
- return the finalized payload unchanged

This preserves the current downstream flow:

- dedup
- payload assembly
- formal payload build
- formal payload finalize

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- attach `formal` onto each candidate by normalized `code`
- default missing `formal` items to `{"status": "unavailable"}`
- rebuild `entry_signals` from attached `candidate_signals`
- keep only rows where `entry_ready` is truthy
- store rebuilt `entry_signals` as copied `dict(sig)` rows
- rebuild `buy_signals` as `list(entry_signals)`
- store the original `formal_payload` under `payload["formal"]`

No semantic tightening is included in this slice. The purpose is owner relocation, not payload redesign.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`

This carrier should directly exercise `finalize_lowfreq_formal_front_payload(...)` and cover at least:

- `formal` items attach by `code`
- missing `formal` items fall back to `{"status": "unavailable"}`
- `entry_signals` only contains attached rows where `entry_ready` is truthy
- `entry_signals` rows are copies rather than direct candidate references
- `buy_signals` mirrors the rebuilt `entry_signals`
- `formal` passthrough remains the raw `formal_payload`

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

## 6. Risks and Guardrails

Main risk:

- accidentally changing the rebuild semantics for `entry_signals` and `buy_signals` while moving the owner

Guardrails:

- preserve `dict(sig)` copy semantics exactly
- preserve `buy_signals = list(entry_signals)` exactly
- avoid changing `attach_lowfreq_formal_front_payloads(...)` behavior in the same slice
- avoid mixing pre-formal payload assembly into this slice

## 7. Implementation Outline

Planned implementation steps:

1. extend `neotrade3/decision_engine/formal_front.py`
2. move the real post-formal finalize body into `finalize_lowfreq_formal_front_payload(...)`
3. switch `generate_buy_signals()` to call the shared owner
4. add `tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`
5. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the real formal-front payload finalize owner lives outside `lowfreq_engine_v16_advanced.py`
- `generate_buy_signals()` keeps the same downstream behavior
- `entry_signals`, `buy_signals`, and `formal` write-back semantics stay unchanged
- an owner-focused test directly protects the finalize contract
- downstream formal-front and convergence tests still pass
