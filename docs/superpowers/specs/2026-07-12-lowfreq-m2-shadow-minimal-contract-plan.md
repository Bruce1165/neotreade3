Status: active
Owner: lowfreq / cycle_intelligence
Scope: Implementation plan for the narrow `M2 shadow minimal contract` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M2 Shadow Minimal Contract Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m2-shadow-minimal-contract-design.md`

## 1. Goal

This slice exists to close one concrete dependency gap:

- `benchmark fixture / batch runner / seed tests` already import an `M2 shadow` object family
- the repository does not actually define those objects or builders

This plan only covers the minimum implementation needed to:

- restore the missing `cycle_intelligence` shadow builders
- restore the package-root exports required by `benchmark`
- make `neotrade3.benchmark` importable through the normal package path
- allow B1-B4 benchmark fixture construction to proceed without import failure

This slice does not:

- promote `mid_cycle` into formal mainline
- redesign lowfreq heuristics
- modify `SmallCycle` semantics
- change `M3` or `M4` logic beyond dependency recovery

## 2. Starting Point

Current evidence:

- `cycle_intelligence/contracts.py` only defines `SmallCycle`
- `cycle_intelligence/__init__.py` only exports `SmallCycle` and `build_small_cycle*`
- `benchmark/fixture_catalog.py` and multiple benchmark tests import six shadow builders that do not exist

So the correct narrow move is:

- implement the exact builder names already assumed by the current code
- keep semantics minimal and deterministic
- verify import recovery and bundle shape through focused tests

## 3. Implementation Boundary

Production files:

- `neotrade3/cycle_intelligence/contracts.py`
- `neotrade3/cycle_intelligence/assembler.py`
- `neotrade3/cycle_intelligence/__init__.py`

Focused tests:

- `tests/unit/test_m2_shadow_contract_minimal.py`
- `tests/unit/test_m4_benchmark_fixture_catalog.py`

Potential touch only if strictly necessary:

- `tests/unit/test_m4_benchmark_seed.py`
- `tests/unit/test_m4_benchmark_batch_runner.py`

Must not touch:

- `neotrade3/decision_engine/`
- live lowfreq engine runtime files
- `neotrade3/benchmark/assembler.py`
- `config/benchmark/*.json`

## 4. Execution Steps

### MSC-S1: Extend M2 shadow contract objects

In `neotrade3/cycle_intelligence/contracts.py` add five dataclasses:

- `MidCycleState`
- `SmallCycleWaveHypothesis`
- `CycleLinkageState`
- `GrowthPotentialProfile`
- `TopRiskProfile`

Contract requirements:

- all dataclasses expose `to_payload()`
- `CycleLinkageState` must support direct attribute access for:
  - `supports_continuation`
  - `local_end_vs_global_end`
  - `mid_cycle_ref`
- `GrowthPotentialProfile.status` and `TopRiskProfile.risk_level` must be direct attributes

Completion check:

- object payloads can be asserted independently in focused tests

### MSC-S2: Add minimum builders

In `neotrade3/cycle_intelligence/assembler.py` add:

- `build_small_cycle_wave_hypothesis_from_formal_inputs(...)`
- `build_mid_cycle_states_from_m1(...)`
- `build_cycle_linkage_state(...)`
- `build_growth_potential_profile_from_formal_inputs(...)`
- `build_top_risk_profile_from_formal_inputs(...)`
- `build_shadow_cycle_intelligence_from_m1(...)`

Rules:

- consume current `SmallCycle`, `D7SecurityMasterMinimal`, and `PF1TradingProfile`
- keep derivation deterministic and intentionally shallow
- return the exact bundle keys expected by `benchmark`

Completion check:

- `build_shadow_cycle_intelligence_from_m1(...)` returns:
  - `wave_hypothesis`
  - `mid_cycle_states`
  - `cycle_linkage_state`
  - `growth_potential_profile`
  - `top_risk_profile`

### MSC-S3: Restore package exports

In `neotrade3/cycle_intelligence/__init__.py` export:

- the five new object classes
- the six new builders

Completion check:

- `from neotrade3.cycle_intelligence import ...` works for all names already used by `benchmark`

### MSC-S4: Add focused tests

Add new owner-focused test file:

- `tests/unit/test_m2_shadow_contract_minimal.py`

Test coverage:

- object payload shape
- default positive-path derivation
- aggregate shadow bundle keys
- status / risk / linkage values in the reference path

Update `tests/unit/test_m4_benchmark_fixture_catalog.py` minimally to lock:

- `build_benchmark_fixture_bundle(...)` works through the normal package path
- B1-B4 fixtures can construct reference bundles

Only update other benchmark tests if import-path or payload assumptions must be aligned.

### MSC-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/cycle_intelligence/contracts.py neotrade3/cycle_intelligence/assembler.py neotrade3/cycle_intelligence/__init__.py tests/unit/test_m2_shadow_contract_minimal.py tests/unit/test_m4_benchmark_fixture_catalog.py`
- `.venv/bin/python -m pytest tests/unit/test_m2_shadow_contract_minimal.py tests/unit/test_m4_benchmark_fixture_catalog.py`

Fallback if `pytest` remains unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions for:
  - package-root imports from `neotrade3.cycle_intelligence`
  - `build_shadow_cycle_intelligence_from_m1(...)`
  - `build_default_benchmark_fixture_catalog()`
  - `build_benchmark_fixture_bundle(...)`

Completion check:

- normal package import path works
- fixture construction works for B1-B4

### MSC-S6: Narrow commit

Stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m2-shadow-minimal-contract-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m2-shadow-minimal-contract-plan.md`
- `neotrade3/cycle_intelligence/contracts.py`
- `neotrade3/cycle_intelligence/assembler.py`
- `neotrade3/cycle_intelligence/__init__.py`
- `tests/unit/test_m2_shadow_contract_minimal.py`
- `tests/unit/test_m4_benchmark_fixture_catalog.py`

Exclude:

- unrelated benchmark registry/manifest files
- lowfreq engine runtime files
- decision engine files

## 5. Risks and Guards

Risk 1:

- widening into a full mid-cycle architecture slice

Guard:

- implement only fields directly read by current benchmark consumers

Risk 2:

- making the first-stage heuristics look more authoritative than they are

Guard:

- keep naming as `shadow minimal contract`
- keep derivation rules simple and explicit

Risk 3:

- modifying benchmark logic instead of fixing the upstream dependency

Guard:

- treat `benchmark` as the fixed consumer
- do the real work inside `cycle_intelligence`

## 6. Success Criteria

This slice is complete when:

- the missing `cycle_intelligence` shadow builders exist
- package-root imports succeed
- `build_shadow_cycle_intelligence_from_m1(...)` returns the expected bundle
- `build_benchmark_fixture_bundle(...)` can build B1-B4 without import failure
- syntax verification passes
- focused verification passes with the best available runner in the environment
