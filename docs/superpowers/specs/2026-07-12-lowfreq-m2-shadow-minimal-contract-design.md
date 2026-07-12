Status: active
Owner: lowfreq / cycle_intelligence
Scope: Narrow `M2 shadow minimal contract` slice to unblock benchmark fixture import and M4 seed execution
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M2 Shadow Minimal Contract Design

Date: 2026-07-12

## 1. Goal

This slice is the next direct follow-up after the completed `M3 hold/exit formal bridge -> M4` slice.

Current repository evidence shows:

- `benchmark fixture` and `benchmark batch runner` currently import six `cycle_intelligence` shadow builders:
  - [fixture_catalog.py:L8-L17](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py#L8-L17)
  - [test_m4_benchmark_batch_runner.py:L16-L24](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_batch_runner.py#L16-L24)
- `cycle_intelligence` currently exports only `SmallCycle` and `build_small_cycle*`:
  - [__init__.py:L1-L23](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/__init__.py#L1-L23)
- `contracts.py` only defines `SmallCycle`:
  - [contracts.py:L1-L56](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/contracts.py#L1-L56)
- full-text repository search shows those six shadow builders have no actual definitions in the codebase

So the real blocker is not “benchmark not wired yet”.

The real blocker is:

- `M4` already assumes a shadow-side `M2` object family exists
- but the corresponding `M2` shadow contracts and builders do not exist in the repository

This slice exists to fix that one concrete dependency gap.

Project-phase note:

- domain: `M2 shadow minimal contract for M4 fixture chain`
- change type: `skeleton completion / dependency unblock`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M2-M4 / G2-G4`

## 2. Scope

Included:

- add the minimum `M2 shadow` object family required by `fixture_catalog`, `batch_runner`, and `benchmark seed` tests
- add the minimum builders currently imported by `benchmark`
- add one aggregate builder:
  - `build_shadow_cycle_intelligence_from_m1(...)`
- export those builders and objects from `neotrade3.cycle_intelligence`
- make `neotrade3.benchmark` package importable again through the normal package path
- add focused tests for the new shadow objects and import path recovery

Excluded:

- no upgrade of `mid_cycle / large_cycle / super_long_cycle` into formal mainline objects
- no real strategy algorithm redesign
- no change to `SmallCycle` semantics
- no new `M3` contract changes
- no `M4` gap taxonomy expansion
- no `M5/M6` governance or delivery work

## 3. Existing Consumer Contract

The required consumer surface is already frozen by current code.

### 3.1 Required shadow bundle keys

`benchmark` expects the shadow bundle to contain:

- `wave_hypothesis`
- `mid_cycle_states`
- `cycle_linkage_state`
- `growth_potential_profile`
- `top_risk_profile`

Evidence:

- [fixture_catalog.py:L111-L115](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py#L111-L115)
- [fixture_catalog.py:L207-L223](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py#L207-L223)
- [benchmark/assembler.py:L58-L72](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py#L58-L72)

### 3.2 Required object behaviors

Current tests and fixture builders prove the minimal behavior contract:

- `mid_cycle_states["fund_cycle"].to_payload()["state"]`
- `mid_cycle_states["industry_cycle"].to_payload()["state"]`
- `cycle_linkage_state.supports_continuation`
- `cycle_linkage_state.local_end_vs_global_end`
- `cycle_linkage_state.mid_cycle_ref[...]`
- `growth_potential_profile.status`
- `top_risk_profile.risk_level`

Evidence:

- [test_m4_benchmark_fixture_catalog.py:L35-L52](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_fixture_catalog.py#L35-L52)
- [test_m4_benchmark_seed.py:L159-L168](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_seed.py#L159-L168)
- [test_m4_benchmark_seed.py:L333-L355](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_seed.py#L333-L355)

### 3.3 Required builder names

The existing repository already froze the public API names:

- `build_small_cycle_wave_hypothesis_from_formal_inputs(...)`
- `build_mid_cycle_states_from_m1(...)`
- `build_cycle_linkage_state(...)`
- `build_growth_potential_profile_from_formal_inputs(...)`
- `build_top_risk_profile_from_formal_inputs(...)`
- `build_shadow_cycle_intelligence_from_m1(...)`

This slice should implement those exact names instead of inventing a different interface.

## 4. Approach Options

### Option A: Add a minimal M2 shadow object family that satisfies current benchmark consumers without promoting them to formal mainline objects (Recommended)

- create lightweight shadow contract dataclasses
- derive simple, deterministic values from current `SmallCycle`, `D7`, and `PF1`
- keep object semantics intentionally shallow and explicit

Pros:

- directly unblocks `fixture_catalog`, `batch_runner`, and `benchmark` imports
- aligns with existing docs that left these objects out of the first formal mainline
- keeps the slice narrow and testable

Cons:

- the first implementation is structural, not full trading intelligence

### Option B: Delete `fixture_catalog` and all shadow-bundle consumers for now

Pros:

- removes the immediate import blocker

Cons:

- destroys current `M4` benchmark seed infrastructure
- moves the codebase backward instead of forward

### Option C: Promote full mid-cycle and shadow intelligence to complete formal objects in one step

Pros:

- potentially more future-proof

Cons:

- broadens into a much larger architecture slice
- conflicts with existing phased plan that intentionally deferred this work

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should stay inside `neotrade3/cycle_intelligence/` and only touch `benchmark` where import recovery needs focused tests.

New or extended owners:

- extend `neotrade3/cycle_intelligence/contracts.py`
- extend `neotrade3/cycle_intelligence/assembler.py`
- extend `neotrade3/cycle_intelligence/__init__.py`

No new top-level package is needed.

Why:

- these objects are `M2 shadow intelligence`
- the dependency hole originates in `cycle_intelligence`, not in `benchmark`

### 5.2 Minimal Object Family

Add five minimum object types.

#### A. `MidCycleState`

One reusable dataclass for both:

- `fund_cycle`
- `industry_cycle`

Minimum fields:

- `stock_code`
- `trade_date`
- `scope`
- `state`
- `confidence`
- `evidence_bundle`
- `rule_version`

Required behavior:

- `to_payload()["state"]` must work

Recommended state vocabulary for this slice:

- `advancing`
- `repairing`
- `neutral`
- `weakening`

#### B. `SmallCycleWaveHypothesis`

Minimum fields:

- `stock_code`
- `trade_date`
- `replay_consistency_status`
- `wave_label_candidate`
- `evidence_bundle`
- `rule_version`

Required behavior:

- `to_payload()["replay_consistency_status"]`

Recommended first-stage status:

- default to `pending_benchmark` when `SmallCycle` is in advancing-style states

#### C. `CycleLinkageState`

Minimum fields:

- `stock_code`
- `trade_date`
- `small_cycle_ref`
- `mid_cycle_ref`
- `linkage_phase`
- `supports_continuation`
- `local_end_vs_global_end`
- `confidence`
- `evidence_bundle`
- `rule_version`

Required behavior:

- attribute access for `supports_continuation`
- attribute access for `local_end_vs_global_end`
- attribute access for `mid_cycle_ref`
- `to_payload()` for `benchmark/assembler`

Recommended first-stage `local_end_vs_global_end` vocabulary:

- `local_end_only`
- `needs_global_confirmation`
- `possible_global_end`

#### D. `GrowthPotentialProfile`

Minimum fields:

- `stock_code`
- `trade_date`
- `status`
- `confidence`
- `evidence_bundle`
- `rule_version`

Required behavior:

- attribute access for `status`
- `to_payload()["status"]`

Recommended status vocabulary:

- `promising`
- `uncertain`
- `negative`

#### E. `TopRiskProfile`

Minimum fields:

- `stock_code`
- `trade_date`
- `risk_level`
- `risk_flags`
- `evidence_bundle`
- `rule_version`

Required behavior:

- attribute access for `risk_level`
- `to_payload()["risk_level"]`

Recommended risk vocabulary:

- `low`
- `watch`
- `high`

### 5.3 Derivation Strategy

This slice must not pretend to implement full research logic.

The correct move is to define simple, deterministic derivation rules from already available inputs:

- `SmallCycle`
- `D7SecurityMasterMinimal`
- `PF1TradingProfile`

Recommended first-stage rules:

#### `MidCycleState`

- if `SmallCycle.cycle_state` is `S2 Advancing` and `PF1.return_20d > 0`:
  - state = `advancing`
- if `return_20d` stays non-negative but momentum weakens:
  - state = `repairing`
- if `return_20d < 0` or `positive_days_5d <= 2`:
  - state = `weakening`
- else:
  - state = `neutral`

For this slice, `fund_cycle` and `industry_cycle` may share the same simple heuristic with slightly different evidence labels. That is acceptable because the goal is dependency completion, not deep cycle differentiation.

#### `SmallCycleWaveHypothesis`

- if `SmallCycle.cycle_state == "S2 Advancing"`:
  - `replay_consistency_status = "pending_benchmark"`
  - `wave_label_candidate = "advance_wave"`
- else:
  - keep `pending_benchmark` but use a neutral label such as `unclassified_wave`

#### `CycleLinkageState`

- if both mid-cycle states are in `{"advancing", "repairing"}`:
  - `supports_continuation = True`
  - `local_end_vs_global_end = "local_end_only"`
  - `linkage_phase = "continuation_supported"`
- otherwise:
  - `supports_continuation = False`
  - `local_end_vs_global_end = "needs_global_confirmation"`
  - `linkage_phase = "continuation_at_risk"`

`fixture_catalog` and tests already override this object for B2/B4 failure paths, so the default path only needs to support the reference-positive case.

#### `GrowthPotentialProfile`

- if both mid-cycle states are positive and `return_20d > 0`:
  - `status = "promising"`
- if one side weakens or momentum is mixed:
  - `status = "uncertain"`
- otherwise:
  - `status = "negative"`

#### `TopRiskProfile`

- if `return_20d < 0` or `positive_days_5d <= 1`:
  - `risk_level = "high"`
- if `positive_days_5d <= 3`:
  - `risk_level = "watch"`
- else:
  - `risk_level = "low"`

### 5.4 Aggregate Builder

Add:

- `build_shadow_cycle_intelligence_from_m1(...) -> dict[str, Any]`

Minimum inputs:

- `cycle`
- `security_master`
- `trading_profile`

Output shape:

- `wave_hypothesis`
- `mid_cycle_states`
- `cycle_linkage_state`
- `growth_potential_profile`
- `top_risk_profile`

Rules:

- `mid_cycle_states` returns a mapping:
  - `{"fund_cycle": MidCycleState, "industry_cycle": MidCycleState}`
- all other entries return dataclass objects with `to_payload()`
- keep keys exactly aligned with current `benchmark` consumer expectations

### 5.5 Export Boundary

`neotrade3/cycle_intelligence/__init__.py` should export:

- the five new object types
- the six new builders

This is required because both `benchmark` production code and tests import them from the package root.

## 6. Risks and Guardrails

Risk 1:

- overstating these objects as already “formal mainline truth”

Guardrail:

- document them as `shadow minimal contract`
- keep them inside `cycle_intelligence`, not as a new promoted mainline layer

Risk 2:

- letting heuristic choices leak into broader strategy behavior

Guardrail:

- only `benchmark` fixture and seed paths consume them in this slice
- do not connect them into live trading engine decision paths

Risk 3:

- widening into full mid-cycle architecture

Guardrail:

- support only the fields currently read by `benchmark` consumers
- do not add `large_cycle` or `super_long_cycle`

## 7. Implementation Outline

Planned steps:

1. extend `cycle_intelligence/contracts.py` with five shadow dataclasses
2. extend `cycle_intelligence/assembler.py` with six builders
3. export them from `cycle_intelligence/__init__.py`
4. add focused tests for:
   - object payloads
   - aggregate bundle shape
   - package import recovery for `neotrade3.benchmark`
5. run syntax checks and focused verification

## 8. Success Criteria

This slice is complete when:

- the six missing shadow builders exist
- `neotrade3.cycle_intelligence` exports them from package root
- `build_shadow_cycle_intelligence_from_m1(...)` returns the exact key set expected by `benchmark`
- `neotrade3.benchmark` becomes importable through the normal package path
- fixture and seed paths can construct B1-B4 runtime payloads without import failure

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M2`
- directly unblocked consumer: `M4`

Goal mapping:

- `G2`: provide minimal cycle linkage and mid-cycle context for benchmark interpretation
- `G4`: provide minimal growth/risk structure for positive vs blocked benchmark samples

Not claimed in this slice:

- no claim that full mid-cycle truth model is complete
- no claim that live decision engine now consumes these shadow contracts
- no claim that `M4` is fully governance-ready
