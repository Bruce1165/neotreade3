Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow M3 rotation-candidate snapshot and selection extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Rotation Candidate Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-rotation-candidate-design.md`

## 1. Goal

This plan covers only the next narrow `rotation candidate` slice after the `system_exit_application` contract alignment cleanup.

This slice only handles:

- weak-hold rotation candidate snapshot interpretation
- best-candidate selection ordering
- owner-focused coverage for the rotation snapshot and selection contract

The goal is to:

- move the real rotation-candidate rule kernel into one shared owner
- keep runtime execution orchestration unchanged in the engine
- keep market and sector exit snapshot generation unchanged
- keep rotation cache semantics unchanged
- preserve current threshold, priority, and details semantics exactly

This slice does not:

- rewrite `run_backtest()`
- rewrite `_market_exit_snapshot(...)`
- rewrite `_sector_exit_snapshot(...)`
- rewrite `_profit_keep_ratio(...)`
- rewrite `_get_bar(...)`
- rewrite any rotation sell execution behavior
- rewrite any M2 cycle-intelligence contract

## 2. Starting Point

Current repository evidence shows:

- the next narrow self-contained M3 rule pair is still inline in:
  - `_rotation_candidate_snapshot(...)`
  - `_select_rotation_candidate(...)`
- `_select_rotation_candidate(...)` only consumes snapshot results and chooses the best candidate
- the snapshot helper returns a dict or `None`, and does not mutate `trade`
- repository search shows no direct owner-focused tests for this kernel

Relevant current engine helpers:

- `lowfreq_engine_v16_advanced.py:_rotation_candidate_snapshot(...)`
- `lowfreq_engine_v16_advanced.py:_select_rotation_candidate(...)`

So the correct next slice is:

- extract only the pure snapshot-shaping and selection kernel
- keep runtime collaborator calls and orchestration in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/rotation_candidate.py`

Move the pure rule helpers there:

- `build_rotation_candidate_snapshot(...)`
- `select_rotation_candidate(...)`

Keep the engine methods as thin facades:

- `_rotation_candidate_snapshot(...)`
- `_select_rotation_candidate(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_rotation_candidate.py`

## 4. Execution Steps

### RCN-S1: Freeze file boundary and observable contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/rotation_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_rotation_candidate.py`

Freeze the observable contract:

- disabled execution rotation still returns `None`
- insufficient `score_gap` still returns `None`
- missing or non-positive current price still returns `None`
- cached base snapshot still uses `(trade.code, current_date.isoformat())`
- current return above `EXECUTION_ROTATION_MAX_CURRENT_RETURN_PCT` still returns `None`
- candidates without weakening and without sufficient evidence still return `None`
- `priority` still equals:
  - `score_gap`
  - plus `max_evidence * 10.0`
  - plus `5.0` when `watch_active`
  - plus `3.0` when `weakening`
  - minus `max(current_return_pct, 0.0) * 0.1`
- details copy still remains:
  - `"弱化持仓换仓候选 | score_gap=... | market_evidence=... | sector_evidence=... | current_return=... | keep_ratio=..."`
- best-candidate ordering still remains:
  - higher `priority`
  - then higher `score_gap`
  - then lower `current_return_pct`

Completion check:

- no backtest execution flow, trade mutation, or exit snapshot generation changes are part of this slice

### RCN-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/rotation_candidate.py`

Move the pure rule bodies into:

- `build_rotation_candidate_snapshot(...)`
- `select_rotation_candidate(...)`

Implementation rules:

- accept normalized scalar inputs rather than the engine instance
- do not read config directly inside the owner
- do not fetch bars inside the owner
- do not read or write `rotation_cache` inside the owner
- do not call market or sector snapshot helpers inside the owner
- do not mutate `trade`
- do not emit events

Completion check:

- the rotation snapshot and selection rules can be understood independently from engine runtime orchestration

### RCN-S3: Switch engine helpers to thin facades

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helpers
- keep config lookup in the engine
- keep cache lookup/writeback in the engine
- keep bar, market snapshot, and sector snapshot lookup in the engine
- replace the dense inline threshold and comparison logic with owner delegation

Do not change:

- `run_backtest()`
- `_market_exit_snapshot(...)`
- `_sector_exit_snapshot(...)`
- `_profit_keep_ratio(...)`
- `_get_bar(...)`

Completion check:

- the engine keeps the same helper names but no longer owns the dense rule body inline

### RCN-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_rotation_candidate.py`

Minimum owner cases:

- disabled execution rotation returns `None`
- insufficient score-gap returns `None`
- current return above ceiling returns `None`
- no weakening and insufficient evidence returns `None`
- weakening candidate with valid evidence returns the expected snapshot contract
- watch-active candidate receives the expected priority bonus
- selector returns `None` for an empty candidate list
- selector prefers higher `priority`
- selector uses `score_gap` as the second tie-break
- selector uses lower `current_return_pct` as the third tie-break

Completion check:

- the rotation kernel has direct focused coverage

### RCN-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_rotation_candidate.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/rotation_candidate.py tests/unit/test_lowfreq_engine_v16_rotation_candidate.py`

Completion check:

- owner tests pass
- syntax validation passes

### RCN-S6: Narrow commit

Before implementation, keep the plan commit limited to:

- `docs/superpowers/specs/2026-07-11-lowfreq-rotation-candidate-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/rotation_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_rotation_candidate.py`

Must exclude:

- `run_backtest()` orchestration changes
- market and sector snapshot helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into runtime execution flow or sell-side mutation

Guard:

- keep extraction limited to snapshot shaping and best-candidate selection only

Risk 2:

- drifting cache semantics while extracting the pure rule body

Guard:

- keep cache lookup/writeback in the engine facade and pass normalized snapshot inputs into the owner

Risk 3:

- changing candidate ordering when priorities tie

Guard:

- preserve the current tuple ordering and verify each tie-break directly in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the rotation-candidate rule kernel has one shared owner
- the dense rule body no longer lives inline in the engine
- backtest orchestration, trade mutation, and exit snapshot generation remain unchanged
- owner-focused rotation tests pass
- syntax verification passes

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-rotation-candidate-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/rotation_candidate.py`
- `tests/unit/*`
- any other workspace changes
