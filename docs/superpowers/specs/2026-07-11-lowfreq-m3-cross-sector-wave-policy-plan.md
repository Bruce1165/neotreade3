# Lowfreq M3 Cross-Sector Wave Policy Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-cross-sector-wave-policy-design.md`

## 1. Goal

This plan covers only the next narrow `M3 cross-sector wave policy` slice after the `market filter note owner` extraction.

This slice only handles:

- the duplicated allowed-wave set and mismatch predicate now shared by:
  - `lowfreq_engine_v16_advanced.py`
  - `scripts/generate_lowfreq_top200_attribution_report.py`
- the shared mismatch predicate consumed by:
  - `neotrade3/decision_engine/signal_seed.py`

The goal is to:

- move the shared policy into one owner module
- keep both consumers' behavior unchanged
- preserve the current `wave_uncertain` downgrade and `global_wave_filtered` exclusion semantics exactly
- add owner-focused coverage for the shared rule

This slice does not:

- rewrite `generate_buy_signals()`
- rewrite attribution report stage taxonomy
- rewrite signal seed field mapping
- rewrite `get_global_candidates()`

## 2. Starting Point

The current policy has two evidence-backed fragments:

- allowed-wave set construction is duplicated in:
  - `lowfreq_engine_v16_advanced.py`
  - `scripts/generate_lowfreq_top200_attribution_report.py`
- the mismatch predicate is consumed in:
  - `neotrade3/decision_engine/signal_seed.py`
  - `scripts/generate_lowfreq_top200_attribution_report.py`

The duplicated contract owns exactly these rules:

- allowed waves always start with `"3浪"`
- `"1浪"` is added only when `CROSS_SECTOR_ALLOW_WAVE1` is truthy
- mismatch only matters when `CROSS_SECTOR_WAVE3_ONLY` is truthy
- unsupported waves trigger:
  - signal-seed downgrade in one consumer
  - report exclusion stage in the other consumer

Existing consumer-facing coverage already exists here:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

Those carriers protect each consumer, but they still do not directly pin the shared policy as a standalone unit.

## 3. Implementation Strategy

Use one dedicated shared policy owner under `decision_engine`:

- add a new owner module:
  - `neotrade3/decision_engine/cross_sector_wave_policy.py`
- move the real shared logic into:
  - `build_cross_sector_allowed_waves(...)`
  - `is_cross_sector_wave_mismatch(...)`
- keep `signal_seed.py` responsible only for:
  - appending its own downgrade reason and `wave_uncertain` flag
- keep the attribution report responsible only for:
  - emitting `global_wave_filtered`
  - formatting its own exclusion reason
- add one new owner-focused carrier:
  - `tests/unit/test_lowfreq_engine_v16_cross_sector_wave_policy.py`
- keep the existing signal-seed test and attribution reasoning test as consumer guards

## 4. Execution Steps

### M3-CSWP-S1: Freeze file boundary and policy contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/cross_sector_wave_policy.py`
- `neotrade3/decision_engine/signal_seed.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_engine_v16_cross_sector_wave_policy.py`

Keep these consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

Freeze the observable policy contract:

- base allowed waves always contain `"3浪"`
- optional `"1浪"` inclusion tracks `allow_wave1`
- mismatch returns `False` when `wave3_only` is false
- mismatch returns `True` only when `wave3_only` is true and `wave_phase` is outside the allowed set
- `signal_seed.py` still appends:
  - `capture-first: 波段不符，降权保留`
  - `wave_uncertain`
- attribution report still emits:
  - stage `global_wave_filtered`
  - reason `跨板块分支波段不符（{cand.wave_phase}）`

Completion check:

- no existing consumer needs to change its externally visible contract

### M3-CSWP-S2: Implement the shared policy owner

Create:

- `neotrade3/decision_engine/cross_sector_wave_policy.py`

Move the real shared rule body into that module:

- `build_cross_sector_allowed_waves(...)`
- `is_cross_sector_wave_mismatch(...)`

Implementation rules:

- the owner must not know anything about consumer-specific copy
- the owner must preserve the current allowed-wave set exactly
- the owner must accept a generic `wave_phase` value and compare by string form

Completion check:

- the shared policy can be understood independently from both consumers

### M3-CSWP-S3: Switch `signal_seed.py` to the shared owner

In `neotrade3/decision_engine/signal_seed.py`:

- import the shared policy helper
- replace the inline allowed-wave set and mismatch predicate
- keep all consumer-specific copy and `soft_flags` behavior unchanged

Do not change:

- field mapping
- `signal_source`
- reason ordering outside the wave downgrade append

Completion check:

- `signal_seed.py` no longer duplicates the wave-policy predicate

### M3-CSWP-S4: Switch engine allowed-wave construction to the shared owner

In `lowfreq_engine_v16_advanced.py`:

- import the shared policy helper
- replace the inline cross-sector allowed-wave set construction
- keep `_build_cross_sector_signal_seed(...)` signature and orchestration flow unchanged

Do not change:

- cross-sector scan ordering
- candidate loop structure
- cross-sector score filtering
- any unrelated engine-owned logic

Completion check:

- engine no longer owns an inline copy of the allowed-wave set rule

### M3-CSWP-S5: Switch attribution report to the shared owner

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import the shared policy helper
- replace the inline allowed-wave set and mismatch predicate
- keep `global_wave_filtered` stage and reason copy unchanged

Do not change:

- report stage taxonomy
- report aggregation flow
- score filtering
- resonance filtering

Completion check:

- the report no longer duplicates the wave-policy predicate

### M3-CSWP-S6: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_cross_sector_wave_policy.py`

Minimum owner cases:

- base allowed set contains `"3浪"`
- `allow_wave1=True` adds `"1浪"`
- mismatch is false when `wave3_only` is false
- mismatch is true for unsupported waves under `wave3_only`

If needed, add one narrow attribution guard case to:

- `tests/unit/test_lowfreq_attribution_reasoning.py`

That guard should pin:

- `global_wave_filtered`
- `跨板块分支波段不符（{cand.wave_phase}）`

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

Completion check:

- the shared policy has a direct focused carrier
- both consumers still pass unchanged

### M3-CSWP-S7: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_cross_sector_wave_policy.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_seed.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/cross_sector_wave_policy.py neotrade3/decision_engine/signal_seed.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_engine_v16_cross_sector_wave_policy.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### M3-CSWP-S8: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/cross_sector_wave_policy.py`
- `neotrade3/decision_engine/signal_seed.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_engine_v16_cross_sector_wave_policy.py`
- one focused attribution test file only if it actually changes

Must exclude:

- `signal_payload.py`
- `formal_front.py`
- API files
- `tests/unit/test_bootstrap_skeleton.py`
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing one consumer's behavior while deduplicating the policy

Guard:

- move only the shared predicate, not consumer-specific copy

Risk 2:

- silently changing the allowed-wave set

Guard:

- keep the owner test focused on exact `"3浪"` and optional `"1浪"` membership

Risk 3:

- broadening the slice into report refactoring

Guard:

- limit report changes to the duplicated predicate only

Risk 4:

- broadening the slice into engine orchestration refactoring

Guard:

- keep `lowfreq_engine_v16_advanced.py` untouched in this slice

## 6. Success Criteria

This slice is complete when:

- the cross-sector wave-policy has one shared owner
- `signal_seed.py` and the attribution report no longer duplicate the rule
- downgrade and exclusion behavior stay unchanged
- an owner-focused test directly protects the policy
- signal-seed and attribution reasoning consumers still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-cross-sector-wave-policy-plan.md`

It must exclude:

- `neotrade3/decision_engine/*`
- `scripts/*`
- `tests/unit/*`
- any other workspace changes
