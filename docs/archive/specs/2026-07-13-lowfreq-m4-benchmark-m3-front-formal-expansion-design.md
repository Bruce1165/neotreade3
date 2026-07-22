Status: active
Owner: lowfreq / decision_engine / benchmark
Scope: Narrow `M3 front formal -> M4 benchmark` expansion slice for default validation-seed benchmark runs
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M4 Benchmark M3 Front Formal Expansion Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M4 benchmark artifact typed readback baseline`
- `M5 benchmark-to-governance mainline chaining`
- `M3 local/global exit semantics nucleus`

Current repository evidence shows:

- `M4` already runs as a persisted benchmark mainline through fixture catalog, manifest batch runner, artifact materialization, typed readback, and governance handoff.
- `M4` currently consumes `M3` only in a narrow backhalf bridge:
  - `hold_state`
  - `exit_state`
  - derived `hold_quality_risk_summary`
- canonical `M3 front` formal outputs already exist in the decision engine:
  - `IdentifyState`
  - `TrackingState`
  - `EntryState`
- but default benchmark fixtures do not inject those formal outputs, and benchmark scoring does not compare them against any target-state expectation.

So the narrow problem is not:

- how to create `M3 front` contracts
- how to persist them independently
- how to redesign benchmark sample registry
- how to expand governance closure

It is:

- how to let default `M4` benchmark runs consume canonical `M3 identify / tracking / entry` payloads
- how to compare them against a narrow expected-target contract
- how to emit truthful `G1 Identify Gap` and `G2 Timing Gap` records without widening into a full M3 governance language

Project-phase note:

- domain: `M4 benchmark expansion`
- change type: `mainline benchmark semantics expansion`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3/M4 / G1-G2`

## 2. Scope

Included:

- inject canonical `identify_state`, `tracking_state`, and `entry_state` payloads into benchmark default fixtures
- reuse existing `decision_engine` formal builders as the only owner of those payload shapes
- extend benchmark expected-target evaluation with optional:
  - `identify_state`
  - `tracking_state`
  - `entry_state`
- emit `gap_record` objects for mismatches in those front states
- split front mismatches into:
  - `G1 Identify Gap`
  - `G2 Timing Gap`
- expose a narrow benchmark summary projection for current front-state status
- update default validation seed samples only where the expected M3 front state is already evidence-backed
- add focused tests for fixture injection, benchmark scoring, batch stability, and typed readback

Excluded:

- no new independent `M3` artifact, ledger, or run_ledger
- no change to `decision_engine/contracts.py` object definitions
- no change to `decision_engine/formal_front.py` runtime ownership
- no new benchmark sample-registry top-level schema outside `expected_target_state`
- no new generic rule DSL for benchmark expectations
- no lifecycle-event benchmarking in this slice
- no hold/exit rewrites
- no `M5` closure objects
- no `M6`

## 3. Existing Evidence

### 3.1 Canonical M3 Front Contracts Already Exist

Current repository evidence in:

- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L37-L124)
- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L102-L215)

shows that:

- `IdentifyState`
- `TrackingState`
- `EntryState`

already have formal dataclass contracts and canonical builders from formal `M1/M2` inputs.

So this slice must not invent a second front-state schema inside benchmark.

### 3.2 Benchmark Already Accepts M3 Context, But Barely Uses It

Current repository evidence in:

- [fixture_catalog.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py#L27-L40)
- [batch_runner.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py#L159-L172)
- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py#L83-L130)

shows that benchmark runtime already carries `m3_context` from fixture to assembler, but current scoring uses it only for hold/exit summary projection.

So the real gap is not transport. It is benchmark consumption semantics.

### 3.3 Default Fixtures Do Not Yet Carry M3 Front Formal Payloads

Current repository evidence in:

- [fixture_catalog.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py#L103-L225)

shows that default fixtures currently build:

- `cycle`
- `shadow_bundle`
- `m1_context`

but no canonical front-state payloads.

This means the default benchmark mainline still evaluates only `M2` plus a narrow backhalf bridge.

### 3.4 Validation Seed Samples Still Stop At M2 Expectations

Current repository evidence in:

- [validation_seed_samples.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_samples.json#L5-L160)

shows that all default expected-target definitions currently stop at:

- `small_cycle_state`
- `wave_hypothesis`
- `fund_cycle`
- `industry_cycle`
- `cycle_linkage_state`
- `growth_potential_profile`
- `top_risk_profile`

There is no formal expectation yet for:

- `identify_state`
- `tracking_state`
- `entry_state`

### 3.5 M4 Design Already Requires M3 Front Consumption

Current repository evidence in:

- [2026-07-07-m4-benchmark-layer-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m4-benchmark-layer-design.md#L124-L135)
- [2026-07-07-m4-benchmark-layer-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m4-benchmark-layer-design.md#L563-L569)

freezes that `M4` must consume `M3 identify / tracking / entry / hold / exit`, and that one first-phase question is whether the system gets `identify` right while `timing` is wrong, or the reverse.

So this slice is required to move `M4` from a validation-seed baseline toward its already-approved `Governance Ready` direction.

## 4. Approach Options

### Option A: Keep Front States Only In Trace Bundle

Pros:

- smallest code change
- low risk to batch stability

Cons:

- does not create formal benchmark evaluation
- still leaves `identify / timing` outside gap language
- fails the real missing owner: benchmark assessment

### Option B: Add Fixture-Injected Front States Plus State-Level Benchmark Gaps (Recommended)

Pros:

- reuses existing canonical M3 builders
- keeps the new expectation language narrow
- makes default benchmark runs start evaluating `identify / tracking / entry`
- creates truthful `G1` and `G2` outputs without new persistence systems

Cons:

- requires touching benchmark assembler and summary contract
- requires updating seed config and tests

### Option C: Create A Full M3 Front Benchmark Subsystem

Pros:

- future-flexible

Cons:

- far wider than the current need
- would force new schemas, scoring layers, and lifecycle-language decisions
- violates the required conservative scope

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

This slice introduces benchmark-side consumption of already-existing M3 front truth.

Primary owners:

- `neotrade3/benchmark/fixture_catalog.py`
- `neotrade3/benchmark/assembler.py`
- `neotrade3/benchmark/contracts.py`
- `config/benchmark/validation_seed_samples.json`
- focused benchmark tests

Files intentionally not modified in this slice:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/decision_engine/projections.py`
- `neotrade3/governance/*`
- `neotrade3/orchestration/*`

### 5.2 M3 Front Runtime Payload Freeze

Default benchmark fixtures should start returning a canonical `m3_context` segment containing:

```json
{
  "identify_state": { "...": "canonical IdentifyState payload" },
  "tracking_state": { "...": "canonical TrackingState payload" },
  "entry_state": { "...": "canonical EntryState payload" },
  "m1_constraints_ref": { "...": "same minimal constraint snapshot used by those builders" }
}
```

Design rules:

- use `decision_engine.assembler` builders only
- do not handcraft a benchmark-local copy of those payloads
- keep these keys sibling to existing hold/exit keys so `m3_context` remains one shared benchmark carrier
- trace bundle continues to hold the raw `m3_context` as the audit truth

### 5.3 Expected Target Contract Freeze

This slice should support one narrow expectation shape inside `sample.expected_target_state`:

```json
{
  "identify_state": {
    "allowed_status": ["identified"]
  },
  "tracking_state": {
    "allowed_status": ["tracking"],
    "allowed_maturity": ["ready_for_entry"]
  },
  "entry_state": {
    "allowed_status": ["ready"],
    "allowed_decision": ["enter"],
    "actionable": true
  }
}
```

Design rules:

- only direct top-level front states
- only direct scalar comparisons
- no nested path language
- no fallback expressions
- no rule scripting
- every key remains optional; benchmark only evaluates expectations that are declared

### 5.4 Gap Classification Freeze

Front-state mismatches should map into benchmark gap language as follows:

- `identify_state` mismatch -> `G1 Identify Gap`
- `tracking_state` mismatch -> `G2 Timing Gap`
- `entry_state` mismatch -> `G2 Timing Gap`

Label rule:

- keep label conservative as `L9 State-Drift` in this slice

Reason:

- current repository evidence is sufficient to split `identify` from `timing`
- but not sufficient to reliably infer narrower timing subclasses such as `Early-Entry` or `Late-Entry` from the current benchmark carriers alone

### 5.5 Summary Projection Freeze

`AssessmentSummary` should gain one narrow summary field:

- `front_quality_risk_summary`

This field should project:

- current `identify_state.status`
- current `tracking_state.status`
- current `tracking_state.maturity`
- current `entry_state.status`
- current `entry_state.decision`
- current `entry_state.actionable`
- count of front-state gaps grouped into `identify_gap_count` and `timing_gap_count`

Design rule:

- this is a summary projection only
- the canonical detail remains:
  - `gap_records`
  - `trace_bundle.m3_context`

### 5.6 Seed Update Freeze

Default seed config should be expanded only where front expectations are already evidence-backed by the canonical front builders for the reference advancing cycle.

Included sample updates:

- `B1 target opportunity`
- `B3 boundary complex advancing`

Excluded sample updates in this slice:

- `B2 control failure`
- `B4 interaction guardrail`

Reason:

- `B2/B4` are currently anchored to interaction and continuation semantics
- current front builders derive from `small_cycle + m1_constraints`
- they do not consume the linkage-risk semantics that define those negative samples
- forcing front expectations onto `B2/B4` now would create false precision

### 5.7 Failure Semantics Freeze

Failure handling stays conservative:

- if `m3_context` lacks front states, benchmark should not fabricate them in assembler
- front summary reports `missing_m3_front_formal` when absent
- no gap is emitted unless a corresponding expectation is declared
- typed readback must round-trip the new summary field without breaking existing artifacts

## 6. Testing Strategy

Focused tests should lock:

1. default fixture catalog returns canonical `identify/tracking/entry` payloads
2. positive seed samples with declared front expectations still pass
3. crafted front-state mismatches emit:
   - `G1 Identify Gap`
   - `G2 Timing Gap`
4. `front_quality_risk_summary` projects actual front states and front-gap counts
5. batch-runner default manifests remain stable after seed expansion
6. typed readback round-trips the expanded summary contract

Testing rule:

- do not widen into decision-engine runtime tests
- do not widen into governance tests
- do not widen into new persistence subsystems

## 7. Risks And Guardrails

### 7.1 Schema Drift Risk

The main risk is inventing a benchmark-local copy of `M3 front` semantics.

Guardrail:

- fixture catalog must use canonical decision-engine builders
- benchmark only reads canonical payload keys already emitted by those builders

### 7.2 Scope Widening Risk

Another risk is expanding this slice into full benchmark rule DSL or lifecycle evaluation.

Guardrail:

- only three front states
- only direct expectation keys
- only state-level mismatch checks

### 7.3 False Precision Risk

Another risk is over-labeling front mismatches with unsupported timing semantics.

Guardrail:

- split only `G1` vs `G2`
- keep the gap label at `L9 State-Drift`
- defer finer timing labels to a later slice with richer evidence carriers

### 7.4 Negative-Sample Misprojection Risk

Another risk is asserting `M3 front` expectations for `B2/B4` before front builders understand linkage-risk semantics.

Guardrail:

- update only `B1/B3` seed expectations in this slice
- leave `B2/B4` governed by their current interaction-focused expectations

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- default benchmark fixtures inject canonical `identify / tracking / entry` payloads
- benchmark assembler evaluates optional front expectations without introducing a new DSL
- `identify` mismatches emit `G1 Identify Gap`
- `tracking` and `entry` mismatches emit `G2 Timing Gap`
- `AssessmentSummary` exposes a narrow `front_quality_risk_summary`
- default positive seeds `B1/B3` declare front expectations and still pass
- batch-runner and typed readback remain stable

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- lifecycle-event benchmark consumption
- finer `L1-L7` front-gap labels
- `B2/B4` front expectation semantics tied to linkage-risk or thesis-end semantics
- hold/exit scoring redesign
- `M5` closure objects
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice spans `M3` formal output reuse and `M4` benchmark consumption only; it does not change `M3` ownership or `M5` governance runtime
- `G1-G6` target mapping:
  - this is the minimum `G1/G2` benchmark-evaluable baseline needed so `M4` can distinguish identify-vs-timing drift instead of collapsing both into generic M2 state checking
- new contract introduced:
  - optional benchmark `expected_target_state` keys for `identify_state`, `tracking_state`, and `entry_state`
  - `AssessmentSummary.front_quality_risk_summary`
- boundaries not touched:
  - no new M3 persistence
  - no lifecycle-event benchmarking
  - no governance closure
  - no `M6`
