# Lowfreq Elite Execution Candidate Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-elite-execution-candidate-design.md`

## 1. Goal

This plan covers only the next narrow `elite execution candidate` slice after the `execution signal gate` extraction.

This slice only handles:

- gate-block passthrough
- role / soft-flag / wave / score elite eligibility interpretation
- owner-focused coverage for the elite eligibility contract

The goal is to:

- move the real elite reservation eligibility rule body into one shared owner
- keep reservation queue lifecycle unchanged in the engine
- keep reservation audit-event flow unchanged in the engine
- preserve current thresholds, `min_score_required`, `details`, and `soft_flags` semantics exactly
- add direct focused coverage for the elite eligibility policy

This slice does not:

- rewrite `_execution_signal_gate_snapshot(...)`
- rewrite `_rotation_candidate_snapshot(...)`
- rewrite `run_backtest()`
- rewrite reservation queue lifecycle
- rewrite `_record_buy_signal_audit_event(...)`
- rewrite trade-block aggregation
- rewrite chase-entry gating

## 2. Starting Point

Current repository evidence shows:

- `_execution_signal_gate_snapshot(...)` has already been ownerized
- the next narrow reusable buy-side kernel is `_elite_execution_candidate_snapshot(...)`
- the helper is consumed in one runtime reservation branch inside `run_backtest()`
- current signal-convergence tests already pin reservation created / released / expired runtime behavior

Relevant current engine helper:

- `_elite_execution_candidate_snapshot(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

So the correct next slice is:

- extract only the pure elite eligibility policy
- keep reservation queue and audit side effects in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/elite_execution_candidate.py`

Move the pure rule helper there:

- `build_elite_execution_candidate_snapshot(...)`

Keep the engine method as a thin facade:

- `_elite_execution_candidate_snapshot(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_elite_execution_candidate.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 4. Execution Steps

### EEC-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_elite_execution_candidate.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Freeze the observable contract:

- gate-blocked candidates still return `eligible = False`
- gate-blocked candidates still mirror gate `details`
- gate-blocked candidates still preserve gate `min_score_required`
- non-`龙头` candidates still append the non-leader rejection copy
- any non-empty `soft_flags` still append the soft-retained rejection copy
- `1浪` and `3浪` still use `EXECUTION_ELITE_MIN_BUY_SCORE`
- other wave phases still use `EXECUTION_ELITE_UNKNOWN_LEADER_MIN_BUY_SCORE`
- `details` still joins reasons with `；`
- `blocked_reason` remains `elite_execution_candidate_rejected`
- `soft_flags` still round-trip in the returned snapshot

Completion check:

- no reservation queue lifecycle, audit-event emission, or counter mutation is part of this slice

### EEC-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/elite_execution_candidate.py`

Move the pure elite body into:

- `build_elite_execution_candidate_snapshot(...)`

Implementation rules:

- accept explicit scalar inputs rather than the engine instance
- do not read config directly inside the owner
- do not emit events
- do not mutate queue state
- do not perform reservation orchestration

Completion check:

- the elite eligibility policy can be understood independently from reservation runtime flow

### EEC-S3: Switch `_elite_execution_candidate_snapshot(...)` to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- keep calling `_execution_signal_gate_snapshot(...)`
- replace the real elite rule body of `_elite_execution_candidate_snapshot(...)`

Do not change:

- `_execution_signal_gate_snapshot(...)`
- `_rotation_candidate_snapshot(...)`
- `run_backtest()`
- reservation queue lifecycle
- trade-block counters
- buy-signal audit-event emission

Completion check:

- the engine keeps the same helper name but no longer owns the real elite rule body inline

### EEC-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_elite_execution_candidate.py`

Minimum owner cases:

- gate-blocked candidate is rejected with mirrored gate copy
- non-leader candidate is rejected
- candidate with `soft_flags` is rejected
- `1浪` / `3浪` leader below elite threshold is rejected
- unknown-wave leader below unknown-leader threshold is rejected
- eligible leader above threshold is accepted
- combined non-leader plus soft-flag case keeps both reasons in order

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Completion check:

- the elite policy has direct focused coverage
- current reservation-path consumer tests still pass unchanged

### EEC-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_elite_execution_candidate.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/elite_execution_candidate.py tests/unit/test_lowfreq_engine_v16_elite_execution_candidate.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### EEC-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-elite-execution-candidate-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-elite-execution-candidate-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_elite_execution_candidate.py`

Must exclude:

- reservation queue lifecycle code
- `_rotation_candidate_snapshot(...)`
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into reservation queue lifecycle

Guard:

- keep extraction limited to `_elite_execution_candidate_snapshot(...)` only

Risk 2:

- drifting gate-block early return semantics

Guard:

- preserve the current gate-first early return and test it directly

Risk 3:

- changing reason order when multiple rejection causes coexist

Guard:

- preserve the current append order and verify combined cases directly

## 6. Success Criteria

This slice is complete when:

- the elite reservation eligibility policy has one shared owner
- the real elite rule body no longer lives inline in the engine
- reservation queue lifecycle, counters, and audit-event flow remain unchanged
- owner-focused elite tests pass
- current reservation-path regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-elite-execution-candidate-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/*`
- any other workspace changes
