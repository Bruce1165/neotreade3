# Lowfreq M3 Formal Front Build Bridge Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-formal-front-build-bridge-design.md`

## 1. Goal

This plan covers only the next narrow `formal-front build bridge` slice after the `phase1 signal contracts` extraction.

This slice only handles:

- the inline DB lifecycle bridge in `generate_buy_signals()`
- one shared bridge helper in `neotrade3/decision_engine/formal_front.py`
- one thin engine facade for the formal-front build step

The goal is to:

- move the formal-front DB connection lifecycle bridge into the existing `formal_front.py` owner
- keep `build_lowfreq_formal_front_payload(...)` and `finalize_lowfreq_formal_front_payload(...)` unchanged
- preserve formal-front payload shape and error semantics exactly
- preserve current close-in-finally behavior
- add owner-focused bridge coverage

This slice does not:

- rewrite formal-front projection internals
- rewrite formal-front finalize logic
- rewrite hot-sector or cross-sector orchestration
- change API/report consumers

## 2. Starting Point

Current repository evidence shows:

- `formal_front.py` already owns the cursor-based build body and finalize body
- `lowfreq_engine_v16_advanced.py` still owns the connection lifecycle bridge around the build step
- current end-to-end regression already exists in:
  - `tests/unit/test_lowfreq_engine_v16_formal_front.py`
  - `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

So the correct next slice is:

- finish `formal_front.py` ownership with the connection bridge
- then shrink the engine to a thin `_build_formal_front_payload(...)` facade

## 3. Implementation Strategy

Extend the existing `formal_front.py` owner:

- add `build_lowfreq_formal_front_payload_from_connection(...)`

Then in the engine:

- add `_build_formal_front_payload(...)`
- replace the inline connection/cursor block in `generate_buy_signals()`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_formal_front_bridge.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 4. Execution Steps

### M3-FFB-S1: Freeze file boundary and contract

Freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front_bridge.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Freeze the observable contract:

- `formal_payload["status"]` remains unchanged
- `formal_payload["items_by_code"]` remains unchanged
- `formal_payload["summary"]` remains unchanged
- close happens in `finally`
- close failures remain suppressed
- `history_limit` remains fixed at `20`

Completion check:

- no payload shape or error semantics drift is introduced

### M3-FFB-S2: Add the shared bridge helper

In `neotrade3/decision_engine/formal_front.py`:

- add `build_lowfreq_formal_front_payload_from_connection(...)`

Implementation rules:

- accept an injected connection factory
- call `connect()`
- obtain a cursor
- delegate to `build_lowfreq_formal_front_payload(...)`
- always attempt `close()` in `finally`
- suppress close errors

Do not change:

- `build_lowfreq_formal_front_payload(...)` internals
- `finalize_lowfreq_formal_front_payload(...)`

Completion check:

- `formal_front.py` owns the DB bridge in addition to build/finalize bodies

### M3-FFB-S3: Switch engine to thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new bridge helper
- add `_build_formal_front_payload(...)`
- replace the inline build block inside `generate_buy_signals()`

Do not change:

- hot-sector loop structure
- cross-sector loop structure
- signal payload build flow
- formal-front finalize flow

Completion check:

- the engine no longer owns the inline DB bridge body

### M3-FFB-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_formal_front_bridge.py`

Minimum owner cases:

- the bridge helper delegates through a provided connection factory
- the connection is closed on success
- the connection is also closed when delegated build raises

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Completion check:

- the bridge has a direct focused carrier
- current end-to-end formal-front behavior still passes

### M3-FFB-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_front_bridge.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_front.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/formal_front.py tests/unit/test_lowfreq_engine_v16_formal_front_bridge.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### M3-FFB-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front_bridge.py`

Must exclude:

- `apps/api/main.py`
- `neotrade3/data_control/*`
- other `decision_engine` files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into formal-front projection internals

Guard:

- keep `build_lowfreq_formal_front_payload(...)` unchanged

Risk 2:

- changing current connection-close semantics

Guard:

- preserve `finally`-based close with suppressed close failures

Risk 3:

- over-refactoring `generate_buy_signals()` shell

Guard:

- only replace the formal-front build bridge block

## 6. Success Criteria

This slice is complete when:

- `formal_front.py` owns the connection bridge in addition to build/finalize helpers
- `generate_buy_signals()` no longer owns the inline DB lifecycle bridge
- formal-front payload shape stays unchanged
- owner-focused bridge tests pass
- current formal-front end-to-end regression still passes

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-formal-front-build-bridge-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `tests/unit/*`
- any other workspace changes
