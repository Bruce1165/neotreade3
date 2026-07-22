# Lowfreq Execution Signal Gate Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `system exit state machine` extraction.

This slice only freezes:

- the buy-side execution gate policy still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_execution_signal_gate_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3065-L3097)

The goal is to:

- move the real execution gate policy into one shared owner
- keep execution audit-event emission unchanged in the engine
- keep trade-block counters unchanged in the engine
- preserve current role / wave / score thresholds exactly
- preserve current blocked-reason and details copy exactly
- add direct owner-focused coverage for the execution gate contract

This design is not:

- a rewrite of `_elite_execution_candidate_snapshot(...)`
- a rewrite of `_rotation_candidate_snapshot(...)`
- a rewrite of `run_backtest()`
- a rewrite of `_record_buy_signal_audit_event(...)`
- a rewrite of trade-block aggregation
- a rewrite of chase-entry gating

Project-phase note:

- domain: `buy-side execution gate policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- role-based execution gate rule interpretation
- wave-phase-based execution gate rule interpretation
- minimum-score threshold selection
- blocked-reason and details rendering
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the execution gate contract
- focused regression for:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L512-L581)

Excluded:

- `run_backtest()` order execution flow
- trade-block counter mutation
- buy-signal audit-event emission
- reservation / elite-execution policy
- rotation candidate policy
- chase-entry gating

## 3. Existing Context

Current repository evidence shows:

- the recent sell-side refactor stream has already ownerized the remaining dense sell kernels
- the next narrow reusable rule kernel sits on the buy execution path, not the sell path
- `_execution_signal_gate_snapshot(...)` is a pure dict-returning rule helper with no `trade` writes
- the helper is consumed in one runtime location inside [run_backtest](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3685-L3697)
- the blocked path is already regression-anchored by signal-convergence tests

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_execution_signal_gate_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3065-L3097)
- [lowfreq_engine_v16_advanced.py:run_backtest gate consumer](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3685-L3697)
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L512-L581)

The problem is not missing business definition. The problem is:

- the real execution gate rule body is still bundled into the engine
- the helper is denser and more reusable than the surrounding execution orchestration
- extracting it leaves the engine responsible only for:
  - calling the gate
  - counting blocked buys
  - recording execution audit events

## 4. Approach Options

### Option A: Extract only the execution gate policy and keep buy execution orchestration in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move role / wave / score gate interpretation there
- keep `run_backtest()` blocked-count and audit flow in the engine

Pros:

- isolates the real rule kernel cleanly
- avoids broadening into order execution and reservation flow
- aligns with the current thin-facade migration pattern

Cons:

- the engine still keeps the outer execution branch

### Option B: Extract the whole buy execution gate branch from `run_backtest()`

Pros:

- removes more code from the engine at once

Cons:

- broadens into execution counters and audit side effects
- mixes pure gate policy with runtime orchestration
- raises regression risk

### Option C: Keep the gate inline and rely only on current runtime tests

Pros:

- smallest production diff

Cons:

- leaves the clearest remaining buy-side gate kernel inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure gate-policy side:

- determine whether execution gating is enabled
- derive follower minimum-score blocking
- derive unknown-wave minimum-score blocking
- combine soft block reasons
- compute `min_score_required`
- render the final `details` string

This slice should not own:

- incrementing `trade_blocks["buy_execution_signal_gate_blocked"]`
- calling `_record_buy_signal_audit_event(...)`
- deciding whether reservation flow should run
- deciding elite retention
- placing or skipping actual buys

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/execution_signal_gate.py`

Recommended ownership in that module:

- `build_execution_signal_gate_snapshot(...)`

Recommended signature:

- `build_execution_signal_gate_snapshot(*, enabled: bool, role: str, wave_phase: str, buy_score: float, follower_min_score: float, unknown_wave_min_score: float, wave1_value: str, wave3_value: str) -> dict[str, Any]`

The owner should accept explicit scalar inputs rather than the engine instance or raw config lookup.

### 5.3 Engine Facade Boundary

The engine should keep:

- `_execution_signal_gate_snapshot(...)`

But with a narrower role:

- normalize `sig` fields
- load config values
- delegate the rule body to the new owner

Why keep the facade:

- current runtime code already calls this engine helper directly from `run_backtest()`
- `_elite_execution_candidate_snapshot(...)` already depends on this helper
- this preserves private surface stability while moving the real rule body out

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- disabled gate still returns `{"blocked": False}`
- `role == "跟随"` still uses `EXECUTION_FOLLOWER_MIN_BUY_SCORE`
- non-`1浪` and non-`3浪` wave phases still use `EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE`
- the gate still allows:
  - non-follower candidates under the follower rule
  - strong unknown-wave leaders that meet the higher score rule
- `blocked_reason` remains `"execution_signal_gate_blocked"`
- `soft_role_blocked` and `soft_wave_blocked` remain independent flags
- `min_score_required` remains the max of the triggered thresholds
- `details` still joins reasons with `"；"`
- the exact reason copy remains:
  - `"跟随股正式执行至少需要 {follower_min_score:.1f} 分"`
  - `"未知波段正式执行至少需要 {unknown_wave_min_score:.1f} 分"`

No execution-flow, audit-event, or counter changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_execution_signal_gate.py`

Minimum owner cases:

- disabled gate returns `blocked = False`
- follower below threshold is blocked with follower copy
- unknown-wave low-score leader is blocked with wave copy
- follower unknown-wave low-score candidate accumulates both reasons and the max threshold
- strong unknown-wave leader above threshold is not blocked
- `1浪` and `3浪` candidates do not trigger the unknown-wave rule

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L512-L581)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into buy execution orchestration or reservation flow

Guardrail:

- keep extraction limited to the snapshot helper only

Secondary risk:

- drifting threshold precedence when both role and wave blocks trigger

Guardrail:

- preserve `min_score_required = max(triggered thresholds)` and test the combined case directly

Third risk:

- changing blocked-reason copy or returning a different blocked schema

Guardrail:

- preserve the current keys and exact reason strings in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/execution_signal_gate.py`
2. move the pure gate interpretation there
3. turn `_execution_signal_gate_snapshot(...)` into a thin facade
4. add owner-focused tests
5. run focused syntax and execution-path regression verification

## 8. Success Criteria

This slice is complete when:

- the execution gate policy has one shared owner
- the real rule body no longer lives inline in the engine
- execution counters and audit-event flow remain unchanged
- owner-focused gate tests pass
- current execution-path regressions still pass
