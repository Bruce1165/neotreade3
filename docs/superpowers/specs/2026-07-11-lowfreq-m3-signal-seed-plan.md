# Lowfreq M3 Signal Seed Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-signal-seed-design.md`

## 1. Goal

This plan covers only the next narrow `M3 signal seed shaping` slice after the `formal front payload finalize` extraction.

This slice only handles:

- the hot-sector and cross-sector `StockCandidate -> signal seed dict` blocks inside `generate_buy_signals()`

The goal is to:

- move the real seed-building logic into a dedicated `decision_engine` owner
- keep the engine loops and `_decorate_signal_with_phase1_contracts(...)` call surfaces stable
- preserve the current field mapping, reason assembly, market-filter append, and cross-sector soft-penalty semantics exactly
- add owner-focused coverage for the seed-building contract

This slice does not:

- rewrite `generate_buy_signals()` orchestration
- rewrite `_decorate_signal_with_phase1_contracts(...)`
- rewrite selector ownership or candidate sourcing
- rewrite dedup, payload assembly, or formal-front handling

## 2. Starting Point

The current seed owner still lives inline inside:

- `lowfreq_engine_v16_advanced.py`

The current blocks own exactly these rules:

- map core `StockCandidate` fields into a signal seed dict
- build hot-sector `reasons` from `buy_reasons` plus optional `market_filter_note`
- build cross-sector `reasons` from a fixed prefix plus `buy_reasons`
- add cross-sector `wave_uncertain` soft-penalty only under the current rule
- preserve default `signal_source` values

Existing engine-facing coverage already exists here:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`

Those carriers protect downstream behavior through `generate_buy_signals()`, but they still do not directly pin the seed owner semantics as a standalone unit.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as earlier slices, with one dedicated owner module under `decision_engine`:

- add a new owner module:
  - `neotrade3/decision_engine/signal_seed.py`
- move the real seed bodies into:
  - `build_hot_sector_signal_seed(...)`
  - `build_cross_sector_signal_seed(...)`
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - iterating candidate lists
  - passing explicit parameters into the owner
  - passing the returned seed into `_decorate_signal_with_phase1_contracts(...)`
- add one new owner-focused carrier:
  - `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- keep the existing convergence and formal-front tests as compatibility guards

## 4. Execution Steps

### M3-SS-S1: Freeze file boundary and seed contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/signal_seed.py`
- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`

Keep these existing consumer guards unchanged:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`

Freeze the observable seed contract:

- hot-sector seeds map the current core fields unchanged
- hot-sector reasons start from `list(c.buy_reasons)`
- hot-sector appends `market_filter_note` only when provided
- cross-sector reasons start from `["跨板块扫描"] + list(c.buy_reasons)`
- cross-sector soft-penalty triggers only under the current `wave3_only + not in allowed_waves` rule
- the soft-penalty appends reason `"capture-first: 波段不符，降权保留"` and flag `"wave_uncertain"`
- default `signal_source` values remain `"hot_sector"` and `"cross_sector"`

Completion check:

- no current `generate_buy_signals()` consumer should need to change its assertions or access path

### M3-SS-S2: Implement the shared signal-seed owner

Create:

- `neotrade3/decision_engine/signal_seed.py`

Move the rule bodies into that module:

- `build_hot_sector_signal_seed(...)`
- `build_cross_sector_signal_seed(...)`

Implementation rules:

- the module must not read engine state directly
- the module reads only the provided candidate object and explicit parameters
- the module preserves current reason and `soft_flags` append order exactly
- the module preserves current field names and default values exactly

Completion check:

- the pre-decoration seed contract can be understood independently from `generate_buy_signals()`

### M3-SS-S3: Convert engine loops to thin call sites

In `lowfreq_engine_v16_advanced.py`:

- import the new seed builders
- keep the current hot-sector and cross-sector loops
- replace inline seed dict bodies with owner calls
- keep `_decorate_signal_with_phase1_contracts(...)` unchanged

Do not change:

- market sentiment calculation
- hot-sector and cross-sector candidate discovery
- `_decorate_signal_with_phase1_contracts(...)`
- deduplication
- payload assembly
- formal-front build/finalize

Completion check:

- engine no longer owns the real seed-building bodies

### M3-SS-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`

Minimum owner cases:

- hot-sector seed maps core fields and appends `market_filter_note`
- cross-sector seed uses the fixed `"跨板块扫描"` prefix
- cross-sector seed adds the wave soft-penalty only when current rules require it
- cross-sector seed keeps `cross_sector=True`
- both seed builders preserve default `signal_source` values

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`

Completion check:

- the seed owner has a direct focused carrier
- engine-facing consumers still pass unchanged

### M3-SS-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/signal_seed.py tests/unit/test_lowfreq_engine_v16_signal_seed.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### M3-SS-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/signal_seed.py`
- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`

Must exclude:

- `signal_payload.py`
- `signal_dedup.py`
- `formal_front.py`
- API/report files
- `tests/unit/test_bootstrap_skeleton.py`
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing reasons or `soft_flags` ordering while moving the owner

Guard:

- preserve the current append order exactly

Risk 2:

- drifting into phase1 decoration because the seed builders sit immediately before `_decorate_signal_with_phase1_contracts(...)`

Guard:

- keep `_decorate_signal_with_phase1_contracts(...)` unchanged in this slice

Risk 3:

- broadening the helper into generic candidate conversion infrastructure

Guard:

- keep the owner narrowly named and scoped to lowfreq signal seeds only

Risk 4:

- moving loop/orchestration responsibilities out of engine

Guard:

- keep sector/global loops and error handling in `generate_buy_signals()`

## 6. Success Criteria

This slice is complete when:

- the real signal-seed owner lives in `decision_engine`
- engine keeps only thin call-through seed sites
- public `generate_buy_signals()` behavior stays unchanged
- an owner-focused test directly protects the seed owner
- convergence and formal-front consumer tests still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-signal-seed-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/*`
- `tests/unit/*`
- any other workspace changes
