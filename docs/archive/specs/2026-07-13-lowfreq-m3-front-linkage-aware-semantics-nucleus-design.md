Status: active
Owner: lowfreq / decision_engine / cycle_intelligence
Scope: Narrow `M3 front linkage-aware semantics nucleus` slice for canonical tracking/entry translation
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Front Linkage-Aware Semantics Nucleus Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M3 identify / tracking / entry` formal contract baseline
- `M4 benchmark m3 front formal expansion`

Current repository evidence shows:

- canonical `M3 front` builders exist and are the only formal owner for:
  - `IdentifyState`
  - `TrackingState`
  - `EntryState`
- those builders currently consume only:
  - `SmallCycle`
  - `m1_constraints_ref`
- `cycle_linkage_state` already exists as canonical `M2 shadow` truth
- but `M3 front` does not consume it at all
- therefore `B2/B4`-style continuation-risk semantics still cannot truthfully influence front maturity or entry actionability

So the narrow problem is not:

- how to rebuild front contracts
- how to redesign benchmark scoring
- how to introduce new persistence
- how to change hold/exit semantics

It is:

- how to let canonical `tracking / entry` translation understand `cycle_linkage_state`
- how to do that without widening into full benchmark expectation updates or new decision subsystems

Project-phase note:

- domain: `M3 front formal semantics`
- change type: `canonical translation nucleus`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3/M4 / G2-G5`

## 2. Scope

Included:

- extend canonical `M3 front` builders to accept an optional `cycle_linkage_state_ref`
- make `tracking` and `entry` translation linkage-aware when continuation is blocked
- preserve current behavior when no linkage input is provided
- thread the optional linkage input through:
  - lowfreq formal-front runtime assembly
  - benchmark fixture front-payload generation
- add focused tests for the new linkage-aware branch

Excluded:

- no change to `IdentifyState` fields or identify decision thresholds
- no change to `M3` persistence surfaces
- no change to `M4` seed registry expectations
- no benchmark gap-rule redesign
- no hold/exit rewrite
- no `M5` closure objects
- no `M6`

## 3. Existing Evidence

### 3.1 Current M3 Front Owner Ignores Linkage Truth

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L102-L215)

shows that:

- `build_identify_state_from_formal_inputs(...)`
- `build_tracking_state_from_formal_inputs(...)`
- `build_entry_state_from_formal_inputs(...)`

all accept only:

- `cycle`
- `m1_constraints_ref`

and read only:

- `cycle.cycle_state`
- `cycle.state_stability_level`
- `cycle.confidence`
- `m1_constraints_ref.blocked`
- `m1_constraints_ref.blocking_reasons`

So canonical front translation is currently blind to `cycle_linkage_state`.

### 3.2 Canonical M2 Linkage Truth Already Exists

Current repository evidence in:

- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/contracts.py#L125-L156)
- [test_m2_shadow_contract_minimal.py](file:///Users/mac/NeoTrade3/tests/unit/test_m2_shadow_contract_minimal.py#L87-L99)

shows that canonical `cycle_linkage_state` already provides:

- `linkage_phase`
- `supports_continuation`
- `local_end_vs_global_end`

This is the correct upstream truth for continuation-risk semantics.

### 3.3 Runtime And Benchmark Both Reuse The Same Front Builders

Current repository evidence in:

- [formal_front.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L114-L145)
- [fixture_catalog.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py#L109-L140)

shows that both:

- lowfreq runtime formal-front generation
- benchmark fixture front-payload generation

reuse the same canonical front builders.

So if linkage-aware semantics are added in the canonical owner and wired into these two call sites, both runtime and benchmark carriers improve together.

### 3.4 Why B2/B4 Still Cannot Truthfully Declare Front Expectations

Current repository evidence in:

- [2026-07-13-lowfreq-m4-benchmark-m3-front-formal-expansion-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-13-lowfreq-m4-benchmark-m3-front-formal-expansion-design.md#L335-L340)

already documents the real blocker:

- current front builders derive from `small_cycle + m1_constraints`
- they do not consume linkage-risk semantics

So the next truthful move must happen in `M3` first, not in benchmark config.

## 4. Approach Options

### Option A: Keep Linkage Semantics Only In M4

Pros:

- no change to decision-engine owner

Cons:

- duplicates front semantics in benchmark
- breaks canonical ownership
- does not help runtime formal-front output

### Option B: Add Optional Linkage Input To Canonical Front Builders (Recommended)

Pros:

- keeps decision semantics in the current owner
- improves runtime and benchmark simultaneously
- preserves backward compatibility by making the new input optional
- stays narrow: only `tracking / entry` continuation gating

Cons:

- requires small signature expansion across call sites
- needs focused regression coverage

### Option C: Redesign Front Contracts To Embed Full Linkage Objects

Pros:

- future-flexible

Cons:

- much wider than current need
- changes public payload shape unnecessarily
- creates downstream migration cost

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

This slice introduces linkage-aware translation inside the canonical `M3 front` owner.

Primary owners:

- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/benchmark/fixture_catalog.py`

Files intentionally not modified in this slice:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/benchmark/assembler.py`
- `config/benchmark/validation_seed_samples.json`
- `neotrade3/governance/*`
- `neotrade3/orchestration/*`

### 5.2 Signature Freeze

The following canonical builders should accept one new optional parameter:

- `cycle_linkage_state_ref: Mapping[str, Any] | None = None`

Affected functions:

- `build_identify_state_from_formal_inputs(...)`
- `build_tracking_state_from_formal_inputs(...)`
- `build_entry_state_from_formal_inputs(...)`

Design rules:

- the parameter is optional
- omitting it must preserve current behavior
- `identify` may accept the parameter for future symmetry, but this slice does not change identify decision logic

### 5.3 Linkage Semantics Freeze

The only linkage rule introduced in this slice is:

- when `cycle_linkage_state_ref.supports_continuation is False`, front translation must not produce an entry-ready continuation posture

Concretely:

- `tracking`
  - may stay `status="tracking"`
  - but must not remain `maturity="ready_for_entry"`
  - should downgrade to `maturity="not_ready"`
  - should set `transition_reason="cycle_linkage_blocks_continuation"`
- `entry`
  - must become `actionable=False`
  - must set `decision="wait"`
  - must not remain `status="ready"`
  - should set `status="not_ready"`
  - should append `cycle_linkage_blocks_continuation` to `blocking_reasons`

Reason for keeping `tracking.status="tracking"`:

- the stock may still remain in observation scope even when continuation is blocked
- this preserves a conservative distinction between:
  - `not_tracking` because the cycle is structurally unsuitable
  - `tracking but not mature` because linkage semantics block continuation

### 5.4 Evidence Projection Freeze

When linkage input is provided, `tracking_state.evidence_ref` and `entry_state.evidence_ref` should include a narrow projection of:

- `supports_continuation`
- `local_end_vs_global_end`
- `linkage_phase`

Design rule:

- do not embed the full linkage object into front payload
- only project the minimum evidence fields needed for audit

### 5.5 Call-Site Freeze

Two production call sites must pass linkage truth when available:

- lowfreq formal-front runtime assembly
- benchmark fixture front-payload assembly

Behavior:

- compute or reuse canonical `cycle_linkage_state`
- pass its payload into the canonical front builders

Design rule:

- do not build benchmark-local linkage semantics
- do not fork runtime-vs-benchmark front translation

### 5.6 Backward Compatibility Freeze

This slice must remain backward compatible:

- if a caller omits `cycle_linkage_state_ref`, the current `cycle + m1_constraints_ref` logic remains unchanged
- existing payload fields stay the same
- no object version bump in `IdentifyState / TrackingState / EntryState`

## 6. Testing Strategy

Focused tests should lock:

1. default front translation remains unchanged when linkage input is absent
2. `supports_continuation=False` downgrades tracking maturity away from `ready_for_entry`
3. `supports_continuation=False` makes entry non-actionable and adds the linkage block reason
4. formal-front runtime wiring still produces front payloads successfully
5. benchmark fixture front payload generation includes the linkage-aware branch when the fixture carries blocked continuation semantics

Testing rule:

- do not widen into benchmark scoring redesign
- do not widen into seed-registry expectation updates
- prefer owner-focused contract tests

## 7. Risks And Guardrails

### 7.1 Scope Widening Risk

The main risk is expanding this into full front-state redesign.

Guardrail:

- only `tracking / entry` continuation gating
- no identify threshold rewrite
- no benchmark config update

### 7.2 Ownership Drift Risk

Another risk is re-implementing linkage semantics differently in runtime and benchmark.

Guardrail:

- one canonical decision-engine owner
- both call sites reuse the same builder behavior

### 7.3 Backward Compatibility Risk

Another risk is breaking existing callers that do not have linkage truth yet.

Guardrail:

- new input stays optional
- omitted linkage preserves old behavior

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- canonical `tracking / entry` builders accept optional linkage truth
- `supports_continuation=False` blocks `ready_for_entry` / `actionable=True` continuation posture
- runtime formal-front generation passes linkage truth when available
- benchmark fixture front generation passes linkage truth when available
- focused tests prove both unchanged-default and linkage-aware branches

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- benchmark seed updates for `B2/B4` front expectations
- finer front-gap labels in `M4`
- identify-state linkage-aware threshold changes
- lifecycle-event linkage semantics
- `M5` closure objects
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M3` canonical translation, with immediate downstream benefit for `M4` carriers; it does not modify governance or delivery layers
- `G1-G6` target mapping:
  - this is a `G2/G5` semantics-alignment step that lets continuation-risk truth reach front maturity and entry actionability
- new contract introduced:
  - optional `cycle_linkage_state_ref` input to canonical front builders
  - linkage-aware `transition_reason` / `blocking_reasons` projection
- boundaries not touched:
  - no new persistence
  - no benchmark seed update
  - no governance closure
  - no `M6`
