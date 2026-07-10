# Lowfreq M3 Formal Front Payload Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-formal-front-payload-design.md`

## 1. Goal

This plan covers only the next narrow `M3 formal-front payload finalization` slice after the `signal dedup owner` extraction.

This slice only handles:

- the post-formal-front payload write-back block inside `generate_buy_signals()`

The goal is to:

- move the real finalize logic into the existing `formal_front.py` owner
- keep the engine-side call surface as a thin compatibility facade
- preserve the current attach, entry rebuild, buy mirror, and `formal` passthrough semantics exactly
- add owner-focused coverage for the finalize contract

This slice does not:

- rewrite `generate_buy_signals()` orchestration
- rewrite formal projection building
- rewrite signal payload assembly before formal attachment
- rewrite signal deduplication

## 2. Starting Point

The current finalize owner still lives inline inside:

- `lowfreq_engine_v16_advanced.py`

The current block owns exactly these rules:

- attach `formal` items onto `candidate_signals`
- rebuild `entry_signals` from attached candidates where `entry_ready` is truthy
- rebuild `buy_signals` as `list(entry_signals)`
- store the raw `formal_payload` under `payload["formal"]`

Existing engine-facing coverage already exists here:

- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Those carriers protect downstream behavior through `generate_buy_signals()`, but they still do not directly pin the finalize owner semantics as a standalone unit.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as earlier slices, but extend the existing `formal_front.py` owner instead of creating a new file:

- extend `neotrade3/decision_engine/formal_front.py`
- move the real finalize body into:
  - `finalize_lowfreq_formal_front_payload(...)`
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - building `formal_payload`
  - delegating `signal_payload` and `formal_payload`
  - returning the owner result unchanged
- add one new owner-focused carrier:
  - `tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`
- keep the existing formal-front and convergence tests as compatibility guards

## 4. Execution Steps

### M3-FFP-S1: Freeze file boundary and finalize contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`

Keep these existing consumer guards unchanged:

- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Freeze the observable finalize contract:

- `formal` items attach by code to `candidate_signals`
- missing formal rows fall back to `{"status": "unavailable"}`
- rebuilt `entry_signals` keeps only truthy `entry_ready` rows
- rebuilt `entry_signals` rows are copied dict objects
- `buy_signals` mirrors `entry_signals`
- `formal` stores the raw `formal_payload`

Completion check:

- no current `generate_buy_signals()` consumer should need to change its assertions or access path

### M3-FFP-S2: Implement the shared finalize owner

In `neotrade3/decision_engine/formal_front.py`:

- add `finalize_lowfreq_formal_front_payload(...)`

Implementation rules:

- the helper must not read engine state directly
- the helper reads only the provided `signal_payload` and `formal_payload`
- the helper reuses `attach_lowfreq_formal_front_payloads(...)`
- the helper preserves `dict(sig)` copy semantics when rebuilding `entry_signals`
- the helper preserves `buy_signals = list(entry_signals)` exactly

Completion check:

- the finalize contract can be understood independently from `generate_buy_signals()`

### M3-FFP-S3: Convert engine call site to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import `finalize_lowfreq_formal_front_payload(...)`
- keep `generate_buy_signals()` responsible only for building `formal_payload`
- replace the inline finalize block with one owner call

Do not change:

- market-filter logic
- hot-sector and cross-sector sourcing
- signal deduplication
- signal payload assembly before formal attach
- formal projection build

Completion check:

- engine no longer owns the real finalize body

### M3-FFP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`

Minimum owner cases:

- `formal` items attach by code
- missing `formal` items fall back to unavailable
- `entry_signals` includes only truthy `entry_ready` rows
- rebuilt `entry_signals` rows are copies rather than direct candidate references
- `buy_signals` mirrors rebuilt `entry_signals`
- `formal` passthrough remains the raw `formal_payload`

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Completion check:

- the finalize owner has a direct focused carrier
- engine-facing consumers still pass unchanged

### M3-FFP-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_front.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/formal_front.py tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### M3-FFP-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front_payload.py`

Must exclude:

- `signal_payload.py`
- `signal_dedup.py`
- API/report files
- `tests/unit/test_bootstrap_skeleton.py`
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing `entry_signals` rebuild semantics while moving the owner

Guard:

- preserve the current `entry_ready` filter and `dict(sig)` clone behavior exactly

Risk 2:

- changing `buy_signals` identity or ordering semantics

Guard:

- preserve `buy_signals = list(entry_signals)` exactly

Risk 3:

- drifting into formal projection building because the finalize block sits immediately after `build_lowfreq_formal_front_payload(...)`

Guard:

- keep `build_lowfreq_formal_front_payload(...)` unchanged in this slice

Risk 4:

- broadening the helper into a generic payload mutator

Guard:

- keep the helper narrowly named and scoped to lowfreq formal-front finalization

## 6. Success Criteria

This slice is complete when:

- the real formal-front finalize owner lives in `decision_engine`
- engine keeps only a thin call-through after formal payload build
- public `generate_buy_signals()` behavior stays unchanged
- an owner-focused test directly protects the finalize owner
- formal-front and convergence consumer tests still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-formal-front-payload-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/*`
- `tests/unit/*`
- any other workspace changes
