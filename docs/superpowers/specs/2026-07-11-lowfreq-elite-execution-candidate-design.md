# Lowfreq Elite Execution Candidate Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `execution signal gate` extraction.

This slice only freezes:

- the buy-side elite reservation eligibility policy still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_elite_execution_candidate_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3082-L3122)

The goal is to:

- move the real elite reservation eligibility policy into one shared owner
- keep reservation queue orchestration unchanged in the engine
- keep reservation audit-event emission unchanged in the engine
- preserve current role / soft-flag / wave / score thresholds exactly
- preserve current blocked-reason and details copy exactly
- add direct owner-focused coverage for the elite eligibility contract

This design is not:

- a rewrite of `_execution_signal_gate_snapshot(...)`
- a rewrite of `_rotation_candidate_snapshot(...)`
- a rewrite of `run_backtest()`
- a rewrite of reservation queue lifecycle
- a rewrite of `_record_buy_signal_audit_event(...)`
- a rewrite of trade-block aggregation
- a rewrite of chase-entry gating

Project-phase note:

- domain: `buy-side elite reservation eligibility`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- execution-gate precheck passthrough handling
- role-based elite eligibility interpretation
- soft-flag-based elite eligibility interpretation
- wave-specific minimum-score threshold selection
- blocked-reason and details rendering
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the elite eligibility contract
- focused regression for:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L584-L815)

Excluded:

- reservation queue creation / release / expiration
- trade-block counter mutation
- buy-signal audit-event emission
- blocked full-book branch selection in `run_backtest()`
- rotation candidate policy
- chase-entry gating

## 3. Existing Context

Current repository evidence shows:

- `_execution_signal_gate_snapshot(...)` has already been ownerized
- `_elite_execution_candidate_snapshot(...)` now sits directly on top of that gate helper
- the helper is a pure dict-returning rule kernel with no `trade` writes or side effects
- the helper currently has one runtime consumer in the full-book reservation branch inside `run_backtest()`
- current signal-convergence tests already pin reservation created / released / expired behavior around this eligibility gate

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_elite_execution_candidate_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3082-L3122)
- [lowfreq_engine_v16_advanced.py:run_backtest reservation consumer](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3683-L3717)
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L584-L815)

The problem is not missing business definition. The problem is:

- the real elite reservation rule body is still bundled into the engine
- the helper is denser and more reusable than the surrounding reservation orchestration
- extracting it leaves the engine responsible only for:
  - calling the elite eligibility helper
  - creating / releasing / expiring reservation queue entries
  - recording reservation audit events

## 4. Approach Options

### Option A: Extract only the elite eligibility policy and keep reservation orchestration in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move role / soft-flag / wave / score eligibility interpretation there
- keep reservation queue and audit flow in the engine

Pros:

- isolates the real rule kernel cleanly
- avoids broadening into queue lifecycle and execution orchestration
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps the outer reservation branch

### Option B: Extract the whole reservation branch from `run_backtest()`

Pros:

- removes more code from the engine at once

Cons:

- broadens into queue lifecycle, counters, and audit side effects
- mixes pure eligibility policy with runtime orchestration
- raises regression risk

### Option C: Keep the elite helper inline and rely only on current reservation tests

Pros:

- smallest production diff

Cons:

- leaves the clearest remaining reservation eligibility kernel inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure elite-eligibility side:

- reject candidates already blocked by execution gate
- reject non-`龙头` candidates
- reject candidates carrying any `soft_flags`
- derive wave-specific minimum-score thresholds
- render the final `details` string
- return normalized `eligible / blocked_reason / min_score_required / soft_flags`

This slice should not own:

- selecting whether `run_backtest()` should create a reservation
- incrementing `trade_blocks["buy_reserved_due_to_full_book"]`
- calling `_record_buy_signal_audit_event(...)`
- setting reservation expiry dates
- releasing reservations into real buys
- expiring reservations

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/elite_execution_candidate.py`

Recommended ownership in that module:

- `build_elite_execution_candidate_snapshot(...)`

Recommended signature:

- `build_elite_execution_candidate_snapshot(*, gate_blocked: bool, gate_details: str, gate_min_score_required: float | None, role: str, wave_phase: str, buy_score: float, soft_flags: list[str], elite_min_score: float, elite_unknown_leader_min_score: float, wave1_value: str, wave3_value: str) -> dict[str, Any]`

The owner should accept explicit scalar inputs rather than the engine instance or raw config lookup.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_elite_execution_candidate_snapshot(...)`

But with a narrower role:

- call `_execution_signal_gate_snapshot(...)`
- normalize `sig` fields
- load config values
- delegate the elite rule body to the new owner

Why keep the facade:

- current runtime code already calls this engine helper directly from `run_backtest()`
- this preserves private surface stability while moving the real rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- if execution gate is already blocked, elite helper still returns:
  - `eligible = False`
  - `blocked_reason = "elite_execution_candidate_rejected"`
  - `details = gate.details`
  - `min_score_required = gate.min_score_required`
- non-`龙头` still contributes:
  - `"非龙头不进入 elite execution 资格"`
- any non-empty `soft_flags` still contributes:
  - `"存在 soft-retained 标记，不进入 elite execution 资格"`
- `1浪` and `3浪` still use `EXECUTION_ELITE_MIN_BUY_SCORE`
- other wave phases still use `EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE`
- the exact threshold copy remains:
  - `"1浪/3浪龙头正式保留至少需要 {elite_min_score:.1f} 分"`
  - `"未知波段龙头正式保留至少需要 {elite_unknown_leader_min_score:.1f} 分"`
- `soft_flags` still round-trip back in the returned snapshot
- `details` still joins reasons with `"；"`
- `blocked_reason` remains `"elite_execution_candidate_rejected"`

No reservation queue, audit-event, or counter changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_elite_execution_candidate.py`

Minimum owner cases:

- gate-blocked candidate is rejected and mirrors gate details
- non-leader candidate is rejected with non-leader copy
- candidate with `soft_flags` is rejected with soft-retained copy
- `1浪` / `3浪` leader below elite threshold is rejected with wave1/wave3 copy
- unknown-wave leader below unknown-leader threshold is rejected with unknown-wave copy
- eligible `龙头` candidate above threshold is accepted and keeps `soft_flags = []`
- combined non-leader plus soft-flag case keeps both reasons in order

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L584-L815)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into reservation queue orchestration

Guardrail:

- keep extraction limited to `_elite_execution_candidate_snapshot(...)` only

Secondary risk:

- drifting gate-block passthrough semantics

Guardrail:

- preserve the current gate-first early return and test it directly

Third risk:

- changing reason ordering or copy when multiple rejection causes coexist

Guardrail:

- preserve list append order and verify combined cases in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/elite_execution_candidate.py`
2. move the pure elite eligibility interpretation there
3. turn `_elite_execution_candidate_snapshot(...)` into a thin facade
4. add owner-focused tests
5. run focused syntax and reservation-path regression verification

## 8. Success Criteria

This slice is complete when:

- the elite reservation eligibility policy has one shared owner
- the real rule body no longer lives inline in the engine
- reservation queue, counters, and audit-event flow remain unchanged
- owner-focused elite tests pass
- current reservation-path regressions still pass
