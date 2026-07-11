# Lowfreq Execution Signal Gate Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-execution-signal-gate-design.md`

## 1. Goal

This plan covers only the next narrow `execution signal gate` slice after the `system exit state machine` extraction.

This slice only handles:

- role / wave / score gate interpretation
- blocked-reason rendering
- owner-focused coverage for the gate contract

The goal is to:

- move the real execution gate rule body into one shared owner
- keep blocked-count mutation unchanged in the engine
- keep buy-signal audit-event flow unchanged in the engine
- preserve current thresholds, `min_score_required`, and `details` semantics exactly
- add direct focused coverage for the gate policy

This slice does not:

- rewrite `_elite_execution_candidate_snapshot(...)`
- rewrite `_rotation_candidate_snapshot(...)`
- rewrite `run_backtest()`
- rewrite `_record_buy_signal_audit_event(...)`
- rewrite trade-block aggregation
- rewrite chase-entry gating

## 2. Starting Point

Current repository evidence shows:

- the sell-side dense kernels have already been ownerized
- the next narrow reusable buy-side kernel is `_execution_signal_gate_snapshot(...)`
- the helper is consumed by both:
  - the direct blocked-buy branch in `run_backtest()`
  - `_elite_execution_candidate_snapshot(...)`
- current signal-convergence tests already pin observable runtime behavior for the blocked and allowed paths

Relevant current engine helper:

- `_execution_signal_gate_snapshot(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

So the correct next slice is:

- extract only the pure gate policy
- keep runtime blocking counters and audit side effects in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/execution_signal_gate.py`

Move the pure rule helper there:

- `build_execution_signal_gate_snapshot(...)`

Keep the engine method as a thin facade:

- `_execution_signal_gate_snapshot(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_execution_signal_gate.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 4. Execution Steps

### ESG-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/execution_signal_gate.py`
- `tests/unit/test_lowfreq_engine_v16_execution_signal_gate.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Freeze the observable contract:

- disabled gate still returns `blocked = False`
- follower candidates below `EXECUTION_FOLLOWER_MIN_BUY_SCORE` are still blocked
- non-`1浪` and non-`3浪` candidates below `EXECUTION_UNKNOWN_WAVE_MIN_BUY_SCORE` are still blocked
- combined role and wave blocking still keeps both soft flags
- `min_score_required` still takes the max of triggered thresholds
- `blocked_reason` remains `execution_signal_gate_blocked`
- `details` still joins reason strings with `；`
- the exact reason strings remain unchanged

Completion check:

- no blocked-count mutation, audit-event emission, or reservation flow is part of this slice

### ESG-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/execution_signal_gate.py`

Move the pure gate body into:

- `build_execution_signal_gate_snapshot(...)`

Implementation rules:

- accept explicit scalar inputs rather than the engine instance
- do not read config directly inside the owner
- do not emit events
- do not mutate counters
- do not perform buy execution

Completion check:

- the gate policy can be understood independently from runtime execution orchestration

### ESG-S3: Switch `_execution_signal_gate_snapshot(...)` to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- replace the real gate body of `_execution_signal_gate_snapshot(...)`

Do not change:

- `_elite_execution_candidate_snapshot(...)`
- `_rotation_candidate_snapshot(...)`
- `run_backtest()`
- trade-block counters
- buy-signal audit-event emission

Completion check:

- the engine keeps the same helper name but no longer owns the real gate rule body inline

### ESG-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_execution_signal_gate.py`

Minimum owner cases:

- disabled gate returns a non-blocked snapshot
- follower below threshold is blocked
- unknown-wave low-score candidate is blocked
- combined follower plus unknown-wave block keeps both reasons
- strong unknown-wave leader is allowed
- `1浪` and `3浪` candidates bypass the unknown-wave rule

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Completion check:

- the gate policy has direct focused coverage
- current execution-path consumer tests still pass unchanged

### ESG-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_execution_signal_gate.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/execution_signal_gate.py tests/unit/test_lowfreq_engine_v16_execution_signal_gate.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### ESG-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-execution-signal-gate-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-execution-signal-gate-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/execution_signal_gate.py`
- `tests/unit/test_lowfreq_engine_v16_execution_signal_gate.py`

Must exclude:

- `_elite_execution_candidate_snapshot(...)`
- `_rotation_candidate_snapshot(...)`
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into reservation or buy execution flow

Guard:

- keep extraction limited to `_execution_signal_gate_snapshot(...)` only

Risk 2:

- drifting combined-threshold behavior when both role and wave blocks trigger

Guard:

- preserve the current max-threshold behavior and test the combined case directly

Risk 3:

- changing blocked schema or reason copy

Guard:

- preserve the current keys and exact copy in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the execution gate policy has one shared owner
- the real gate rule body no longer lives inline in the engine
- blocked-count mutation and audit-event flow remain unchanged
- owner-focused gate tests pass
- current execution-path regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-execution-signal-gate-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/execution_signal_gate.py`
- `tests/unit/*`
- any other workspace changes
