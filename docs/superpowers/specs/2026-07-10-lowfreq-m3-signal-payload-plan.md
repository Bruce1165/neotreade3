# Lowfreq M3 Signal Payload Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m3-signal-payload-design.md`

## 1. Goal

This plan covers only the next narrow `M3 decision payload` slice after the `financial report retrieval` extraction.

This slice only handles:

- `_build_signal_structure_payload()`

The goal is to:

- move the real signal payload assembly logic into a dedicated `decision_engine` owner
- keep the engine helper as a thin compatibility facade
- preserve the current payload order, clone behavior, and summary shape
- add owner-focused coverage for the payload contract

This slice does not:

- rewrite `generate_buy_signals()`
- rewrite `get_market_sentiment()`
- rewrite formal-front attachment
- rewrite candidate generation or deduplication

## 2. Starting Point

The current owner still lives fully inside:

- `lowfreq_engine_v16_advanced.py`

The helper currently owns:

- candidate sorting
- entry-ready filtering
- payload cloning for `entry_signals`
- summary counting
- date / mode / market note projection

Existing engine-facing coverage already exists here:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`

Those tests already protect the public behavior through `generate_buy_signals()`, but there is still no standalone owner module or direct owner-focused carrier.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as earlier slices, but place the owner under `decision_engine`:

- add a new owner module:
  - `neotrade3/decision_engine/signal_payload.py`
- move the real assembly logic into:
  - `build_signal_structure_payload(...)`
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - passing `deduped_signals`, `target_date`, and `market_filter_note`
  - returning the owner result unchanged
- add one new owner-focused test carrier:
  - `tests/unit/test_lowfreq_engine_v16_signal_payload.py`
- keep the existing convergence/formal-front tests as compatibility guards

## 4. Execution Steps

### M3-SP-S1: Freeze file boundary and payload contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/signal_payload.py`
- `tests/unit/test_lowfreq_engine_v16_signal_payload.py`

Keep these existing consumer guards unchanged:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`

Freeze the observable payload contract:

- `buy_signals`
- `candidate_signals`
- `entry_signals`
- `signal_summary`
- `date`
- `capture_first_mode`
- `market_filter_note`

Completion check:

- no current `generate_buy_signals()` consumer should need to change its assertions or access path

### M3-SP-S2: Implement the shared payload owner

Create:

- `neotrade3/decision_engine/signal_payload.py`

Move the owner logic into that module:

- `build_signal_structure_payload(...)`

Implementation rules:

- the module must not read engine state directly
- the module reads only the provided `deduped_signals`, `target_date`, and `market_filter_note`
- the module preserves the exact candidate sort key and reverse ordering
- the module preserves the `dict(sig)` clone behavior for entry-ready rows

Completion check:

- the signal payload contract can be understood independently from `generate_buy_signals()`

### M3-SP-S3: Convert engine helper to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import `build_signal_structure_payload(...)`
- keep `_build_signal_structure_payload()` as the compatibility method
- make that method only:
  - delegate to the shared owner
  - return the dict unchanged

Do not change:

- `generate_buy_signals()` orchestration
- formal-front attachment
- signal deduplication
- market-filter logic

Completion check:

- engine no longer owns the real payload assembly body

### M3-SP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_signal_payload.py`

Minimum owner cases:

- sort order by `buy_score` then `resonance`
- `entry_signals` contains only `entry_ready` rows
- `buy_signals` mirrors `entry_signals`
- `entry_signals` rows are copied objects rather than direct references
- `signal_summary` counts are correct
- `date`, `capture_first_mode`, and `market_filter_note` are preserved

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`

Completion check:

- the payload owner has a direct focused carrier
- engine-facing consumers still pass unchanged

### M3-SP-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_payload.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/signal_payload.py tests/unit/test_lowfreq_engine_v16_signal_payload.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### M3-SP-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/signal_payload.py`
- `tests/unit/test_lowfreq_engine_v16_signal_payload.py`

Must exclude:

- `generate_buy_signals()` logic changes beyond the call-through
- formal-front files
- API/report files
- `tests/unit/test_bootstrap_skeleton.py`
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing candidate ordering while moving the owner

Guard:

- preserve the current `(buy_score, resonance)` sort key with `reverse=True`

Risk 2:

- changing copy semantics of `entry_signals` and `buy_signals`

Guard:

- preserve `dict(sig)` cloning exactly
- keep `buy_signals` as `list(entry_signals)`

Risk 3:

- drifting into `generate_buy_signals()` orchestration because the helper sits immediately inside that method's flow

Guard:

- this slice only relocates payload assembly, not orchestration

Risk 4:

- mixing payload assembly with formal-front state ownership

Guard:

- place the owner in a dedicated `signal_payload.py` module rather than `assembler.py`

## 6. Success Criteria

This slice is complete when:

- the real signal payload assembly owner lives in `decision_engine`
- engine keeps only a thin `_build_signal_structure_payload()` facade
- public `generate_buy_signals()` behavior stays unchanged
- an owner-focused test directly protects the new payload owner
- convergence and formal-front consumer tests still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-10-lowfreq-m3-signal-payload-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/*`
- `tests/unit/*`
- `apps/api/main.py`
- any other workspace changes
