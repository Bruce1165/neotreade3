# Lowfreq M3 Cross-Sector Wave Policy Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `market filter note owner` extraction.

This slice only freezes:

- the duplicated `跨板块允许波段集合 + wave mismatch 判定` rule now repeated in:
  - `neotrade3/decision_engine/signal_seed.py`
  - `scripts/generate_lowfreq_top200_attribution_report.py`

The goal is to:

- move the cross-sector wave policy into one shared owner
- keep `generate_buy_signals()` orchestration stable
- keep attribution report stage taxonomy stable
- preserve the current `wave_uncertain` downgrade and `global_wave_filtered` exclusion semantics exactly
- add direct owner-focused coverage for the shared wave-policy contract

This design is not:

- a rewrite of `generate_buy_signals()`
- a rewrite of `get_global_candidates()`
- a rewrite of attribution report reasoning stages
- a rewrite of signal seed shaping outside the wave-policy fragment

Project-phase note:

- domain: `M3 cross-sector policy`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- the `allowed_waves` construction and mismatch rule inside [signal_seed.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/signal_seed.py#L29-L58)
- the duplicated `allowed_waves` construction and mismatch rule inside [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L613-L621)
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the shared rule
- focused regression for:
  - [test_lowfreq_engine_v16_signal_seed.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_seed.py)
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

Excluded:

- `generate_buy_signals()` loop/orchestration changes
- `get_global_candidates()` logic
- attribution report stage/copy changes
- market-filter note resolution
- signal payload / formal-front logic

## 3. Existing Context

Current repository evidence shows three important facts:

- cross-sector signal seeds use an inline wave-policy rule:
  - when `wave3_only` is true and `wave_phase` is outside the allowed set, append:
    - reason: `capture-first: 波段不符，降权保留`
    - soft flag: `wave_uncertain`
- attribution report uses the same allowed-wave rule, but as a hard exclusion reason:
  - stage: `global_wave_filtered`
  - reason: `跨板块分支波段不符（{cand.wave_phase}）`
- both call sites build the same allowed-wave set:
  - base: `{"3浪"}`
  - optional add: `"1浪"` when `CROSS_SECTOR_ALLOW_WAVE1` is truthy

Repository evidence:

- [signal_seed.py:L35-L40](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/signal_seed.py#L35-L40)
- [generate_lowfreq_top200_attribution_report.py:L613-L621](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L613-L621)

The problem is not uncertainty about behavior. The problem is:

- the same cross-sector wave-policy is now duplicated across production and report code
- the duplicated rule is already semantically important
- there is no direct owner-focused test for the shared policy itself

## 4. Approach Options

### Option A: Extract a dedicated shared wave-policy owner (Recommended)

- add one small shared module under `neotrade3/decision_engine/`
- move the allowed-wave set building and mismatch predicate there
- let both `signal_seed.py` and the attribution report import it

Pros:

- removes real duplication with evidence
- keeps each consumer's own behavior distinct
- avoids further breaking apart engine orchestration artificially

Cons:

- adds one extra production file

### Option B: Reuse `signal_seed.py` as the shared owner

- keep the policy helper inside `signal_seed.py`
- let the report import from that module

Pros:

- fewer files

Cons:

- weak module naming for a rule consumed outside signal-seed shaping
- mixes reusable policy into a more specific owner

### Option C: Keep both copies and add tests only

- preserve both call-site copies
- add duplication-covering tests

Pros:

- smallest code diff

Cons:

- leaves duplicated policy in place
- still no single owner

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- building the allowed cross-sector wave set from config flags
- deciding whether a candidate wave phase mismatches that policy

These responsibilities should be treated as:

- `M3 cross-sector wave policy`

They should not be treated as:

- signal seed shaping
- attribution stage formatting
- candidate sourcing
- report aggregation

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/cross_sector_wave_policy.py`

This module should own:

- `build_cross_sector_allowed_waves(...)`
- `is_cross_sector_wave_mismatch(...)`

Recommended signatures:

- `build_cross_sector_allowed_waves(*, allow_wave1: bool) -> set[str]`
- `is_cross_sector_wave_mismatch(wave_phase: Any, *, wave3_only: bool, allow_wave1: bool) -> bool`

This module should:

- centralize the current allowed-wave set
- treat `"3浪"` as always allowed
- treat `"1浪"` as optional based on `allow_wave1`
- preserve the current mismatch predicate exactly

This module should not own:

- reason/copy generation
- `wave_uncertain` soft-flag append
- attribution stage names

### 5.3 Consumer Boundaries

`signal_seed.py` should continue to own:

- mapping candidate fields
- appending the downgrade reason and `wave_uncertain` flag when mismatch is true

The attribution report should continue to own:

- emitting `global_wave_filtered`
- formatting `跨板块分支波段不符（{cand.wave_phase}）`

Only the shared policy predicate moves out.

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- base allowed waves always contain `"3浪"`
- `"1浪"` is added only when `allow_wave1` is truthy
- mismatch returns `False` when `wave3_only` is false
- mismatch returns `True` only when `wave3_only` is true and `wave_phase` is outside the allowed set
- `signal_seed.py` still appends:
  - `capture-first: 波段不符，降权保留`
  - `wave_uncertain`
- attribution report still returns:
  - stage `global_wave_filtered`
  - reason `跨板块分支波段不符（{cand.wave_phase}）`

No copy changes and no threshold changes are included in this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_cross_sector_wave_policy.py`

This carrier should directly exercise the shared policy and cover at least:

- base allowed set contains `"3浪"`
- optional `"1浪"` inclusion tracks `allow_wave1`
- mismatch is false when `wave3_only` is false
- mismatch is true for unsupported waves under `wave3_only`

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_signal_seed.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_seed.py)
- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

The attribution reasoning carrier may need one narrow addition if current assertions do not directly touch `global_wave_filtered`.

## 6. Risks and Guardrails

Main risk:

- changing one consumer's semantics while deduplicating the policy

Guardrails:

- move only the shared predicate, not consumer-specific copy
- preserve `signal_seed.py` downgrade behavior unchanged
- preserve attribution report stage/copy unchanged
- keep this slice limited to the cross-sector wave-policy fragment

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/decision_engine/cross_sector_wave_policy.py`
2. move the allowed-wave set and mismatch predicate there
3. switch `signal_seed.py` to import the shared helper
4. switch `generate_lowfreq_top200_attribution_report.py` to import the shared helper
5. add owner-focused tests
6. add or reuse a focused attribution guard for `global_wave_filtered`
7. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the cross-sector wave-policy has one shared owner
- `signal_seed.py` and the attribution report no longer duplicate the rule
- downgrade and exclusion behavior stay unchanged
- an owner-focused test directly protects the policy
- signal-seed and attribution reasoning consumers still pass
