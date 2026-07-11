# Lowfreq Chase Entry Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-chase-entry-design.md`

## 1. Goal

This plan covers only the next narrow `chase entry` slice after the `elite execution candidate` extraction.

This slice only handles:

- enable/disable passthrough
- non-positive reference-price passthrough
- minimum-history-window passthrough
- near-high and fast-run-up chase-entry interpretation
- owner-focused coverage for the chase-entry contract

The goal is to:

- move the real chase-entry hard-block rule body into one shared owner
- keep history loading in the engine
- keep final queue blocking, audit-event flow, and counters unchanged
- preserve current thresholds, return formulas, blocked semantics, and `details` copy exactly
- add direct focused coverage for the chase-entry policy

This slice does not:

- rewrite `_recent_closes_before_date(...)`
- rewrite `run_backtest()`
- rewrite queue blocking or buy execution orchestration
- rewrite `_record_buy_signal_audit_event(...)`
- rewrite reservation or rotation flows

## 2. Starting Point

Current repository evidence shows:

- `_chase_entry_snapshot(...)` is the next narrow reusable buy-side kernel
- the helper already has direct focused tests
- the helper is consumed in one runtime final-queue branch inside `run_backtest()`
- the helper itself has no trade writes, queue mutation, or audit side effects

Relevant current engine helper:

- `_chase_entry_snapshot(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

So the correct next slice is:

- extract only the pure chase-entry policy
- keep history retrieval and orchestration side effects in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/chase_entry.py`

Move the pure rule helper there:

- `build_chase_entry_snapshot(...)`

Keep the engine method as a thin facade:

- `_chase_entry_snapshot(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_chase_entry.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 4. Execution Steps

### CE-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/chase_entry.py`
- `tests/unit/test_lowfreq_engine_v16_chase_entry.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Freeze the observable contract:

- disabled gate still returns `None`
- non-positive `ref_price` still returns `None`
- fewer than 5 closes still returns `None`
- near-high detection still uses 5d or 10d highs times `near_high_ratio`
- recent run-up detection still uses pre3 or pre5 percentage thresholds
- `blocked` still requires both `near_high_flag` and `recent_runup_flag`
- `details` copy and numeric formatting remain unchanged

Completion check:

- no history retrieval, queue blocking, audit-event emission, or counter mutation is part of this slice

### CE-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/chase_entry.py`

Move the pure chase-entry body into:

- `build_chase_entry_snapshot(...)`

Implementation rules:

- accept explicit history and scalar inputs rather than the engine instance
- do not read config directly inside the owner
- do not call SQLite or cursor methods
- do not emit events
- do not mutate queue state

Completion check:

- the chase-entry policy can be understood independently from history retrieval and buy orchestration

### CE-S3: Switch `_chase_entry_snapshot(...)` to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- keep calling `_recent_closes_before_date(...)`
- replace the real chase-entry rule body of `_chase_entry_snapshot(...)`

Do not change:

- `_recent_closes_before_date(...)`
- `run_backtest()`
- final queue blocking
- trade-block counters
- buy-signal audit-event emission

Completion check:

- the engine keeps the same helper name but no longer owns the real chase-entry rule body inline

### CE-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_chase_entry.py`

Minimum owner cases:

- disabled gate returns `None`
- non-positive `ref_price` returns `None`
- insufficient history returns `None`
- near-high plus fast run-up blocks
- near-high without enough run-up does not block
- fast run-up without near-high does not block
- details copy keeps current formatting

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Completion check:

- the chase-entry policy has direct focused coverage
- current buy-path consumer tests still pass unchanged

### CE-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_chase_entry.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/chase_entry.py tests/unit/test_lowfreq_engine_v16_chase_entry.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### CE-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-chase-entry-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-chase-entry-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/chase_entry.py`
- `tests/unit/test_lowfreq_engine_v16_chase_entry.py`

Must exclude:

- `_recent_closes_before_date(...)`
- `run_backtest()` orchestration changes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into history retrieval or buy orchestration

Guard:

- keep extraction limited to `_chase_entry_snapshot(...)` only

Risk 2:

- drifting current thresholds or percentage formulas

Guard:

- preserve the current formulas exactly and test blocked/non-blocked cases directly

Risk 3:

- changing passthrough `None` behavior

Guard:

- test disabled, invalid-price, and short-history cases directly

## 6. Success Criteria

This slice is complete when:

- the chase-entry hard-block policy has one shared owner
- the real rule body no longer lives inline in the engine
- history loading, counters, and audit-event flow remain unchanged
- owner-focused chase-entry tests pass
- current buy-path regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-chase-entry-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/chase_entry.py`
- `tests/unit/*`
- any other workspace changes
