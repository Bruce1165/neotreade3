# Lowfreq M3 Signal Dedup Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m3-signal-dedup-design.md`

## 1. Goal

This plan covers only the next narrow `M3 signal survivor selection` slice after the `signal payload owner` extraction.

This slice only handles:

- the `raw_signals -> deduped` collapse inside `generate_buy_signals()`

The goal is to:

- move the real dedup body into a dedicated `decision_engine` owner
- keep the engine-side call surface as a thin compatibility facade
- preserve the current blank-code skip, strict higher-score replacement, tie preservation, and clone semantics exactly
- add owner-focused coverage for the dedup contract

This slice does not:

- rewrite `generate_buy_signals()` orchestration
- rewrite signal payload assembly
- rewrite formal-front attachment
- redesign scoring or candidate sourcing

## 2. Starting Point

The current dedup owner still lives inline inside:

- `lowfreq_engine_v16_advanced.py`

The current block owns exactly these rules:

- normalize `code` with `str(sig.get("code") or "").strip()`
- skip rows when normalized `code` is blank
- keep at most one survivor per `code`
- replace the current survivor only when the new row has a strictly greater `buy_score`
- store the survivor as `dict(sig)`

Existing engine-facing coverage already exists here:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

That carrier protects downstream behavior through `generate_buy_signals()`, but it still does not directly pin the dedup owner semantics.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as earlier slices, but keep the owner physically separate from payload projection:

- add a new owner module:
  - `neotrade3/decision_engine/signal_dedup.py`
- move the real rule body into:
  - `dedupe_signals_by_code(...)`
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - delegating `raw_signals`
  - returning the owner result unchanged
- add one new owner-focused carrier:
  - `tests/unit/test_lowfreq_engine_v16_signal_dedup.py`
- keep the existing convergence test as the consumer guard

## 4. Execution Steps

### M3-SD-S1: Freeze file boundary and dedup contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/signal_dedup.py`
- `tests/unit/test_lowfreq_engine_v16_signal_dedup.py`

Keep this existing consumer guard unchanged:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Freeze the observable dedup contract:

- blank normalized `code` rows are skipped
- each normalized `code` keeps only one survivor
- replacement happens only when the new `buy_score` is strictly greater than the current survivor
- equal-score ties keep the earlier survivor
- stored survivors are copied with `dict(sig)`

Completion check:

- no downstream `generate_buy_signals()` assertions need to change

### M3-SD-S2: Implement the shared dedup owner

Create:

- `neotrade3/decision_engine/signal_dedup.py`

Move the rule body into that module:

- `dedupe_signals_by_code(...)`

Implementation rules:

- the module must not read engine state directly
- the module reads only the provided `raw_signals`
- the module preserves the current iteration order
- the module preserves the strict `>` replacement comparison exactly
- the module preserves `dict(sig)` clone semantics exactly

Completion check:

- the survivor-selection contract can be understood independently from `generate_buy_signals()`

### M3-SD-S3: Convert engine call site to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import `dedupe_signals_by_code(...)`
- keep a thin engine compatibility helper for dedup
- make the existing `generate_buy_signals()` flow delegate the real body to the shared owner

Do not change:

- sector/global candidate collection
- market-filter logic
- payload assembly
- formal-front attachment

Completion check:

- engine no longer owns the real dedup body

### M3-SD-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_signal_dedup.py`

Minimum owner cases:

- blank-code rows are skipped
- a higher-score row replaces the current survivor
- an equal-score row does not replace the current survivor
- a lower-score row does not replace the current survivor
- the stored survivor is a copy rather than the original dict reference

Keep and re-run the existing consumer guard:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

Completion check:

- the dedup owner has a direct focused carrier
- engine-facing consumer behavior stays unchanged

### M3-SD-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_dedup.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/signal_dedup.py tests/unit/test_lowfreq_engine_v16_signal_dedup.py`

Completion check:

- owner tests pass
- consumer test passes
- syntax validation passes

### M3-SD-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/signal_dedup.py`
- `tests/unit/test_lowfreq_engine_v16_signal_dedup.py`

Must exclude:

- `signal_payload.py`
- formal-front files
- API/report files
- `tests/unit/test_bootstrap_skeleton.py`
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing tie semantics while moving the owner

Guard:

- preserve the strict `>` replacement rule exactly

Risk 2:

- changing stored-row identity semantics

Guard:

- preserve `dict(sig)` clone behavior exactly

Risk 3:

- broadening this slice into generic dedup infrastructure

Guard:

- keep the owner narrowly named and scoped to signal-by-code survivor selection

Risk 4:

- drifting into payload assembly because the dedup block sits immediately before `_build_signal_structure_payload(...)`

Guard:

- keep payload assembly unchanged and out of this file boundary

## 6. Success Criteria

This slice is complete when:

- the real signal dedup owner lives in `decision_engine`
- engine keeps only a thin dedup facade
- public `generate_buy_signals()` behavior stays unchanged
- an owner-focused test directly protects the dedup contract
- the convergence consumer guard still passes

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-10-lowfreq-m3-signal-dedup-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/*`
- `tests/unit/*`
- any other workspace changes
