Status: active
Owner: lowfreq / benchmark
Scope: Narrow `B2/B4 front expectation expansion` slice for validation-seed benchmark truth
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M4 B2/B4 Front Expectation Expansion Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M4 benchmark m3 front formal expansion`
- `M3 front linkage-aware semantics nucleus`

Current repository evidence shows:

- `B1/B3` already declare front expectations in benchmark seed truth
- `B2/B4` still declare only `cycle_linkage_state` expectations
- canonical `M3 front` now consumes `cycle_linkage_state`
- actual blocked-continuation fixtures for `B2/B4` now produce stable front payloads:
  - `identify_state.status = identified`
  - `tracking_state.status = tracking`
  - `tracking_state.maturity = not_ready`
  - `tracking_state.transition_reason = cycle_linkage_blocks_continuation`
  - `entry_state.status = not_ready`
  - `entry_state.decision = wait`
  - `entry_state.actionable = false`

So the narrow problem is not:

- how to redesign `M3 front`
- how to redesign benchmark scoring
- how to add new persistence
- how to add new gap-rule language

It is:

- how to encode the now-evidence-backed `B2/B4` front expectations into benchmark seed truth
- how to lock them with focused tests and default batch runs

Project-phase note:

- domain: `M4 benchmark expansion`
- change type: `validation-seed truth expansion`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3/M4 / G2-G5`

## 2. Scope

Included:

- add `tracking_state` expectations to `B2/B4`
- add `entry_state` expectations to `B2/B4`
- keep `identify_state` unchanged for `B2/B4`
- update focused sample-registry and batch-runner tests
- update any fixture-backed benchmark tests that still carry stale non-linkage-aware `m3_context`

Excluded:

- no change to `decision_engine` owner
- no change to benchmark gap classification logic
- no change to `B1/B3`
- no new benchmark rule DSL
- no hold/exit scoring redesign
- no `M5` closure objects
- no `M6`

## 3. Existing Evidence

### 3.1 B2/B4 Seed Truth Is Still Incomplete

Current repository evidence in:

- [validation_seed_samples.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_samples.json#L71-L184)

shows that:

- `b2_control_failure_seed`
- `b4_local_global_guardrail_seed`

still only declare `cycle_linkage_state` expectations.

### 3.2 Canonical Front Semantics Now Support Linkage-Aware Blocking

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py)
- [formal_front.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py)
- [fixture_catalog.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py)

shows that canonical `tracking / entry` translation now consumes `cycle_linkage_state_ref`.

### 3.3 Actual B2/B4 Front Payloads Are Now Stable And Evidence-Backed

Repository execution evidence from current fixture catalog shows:

- `m2_control_failure_reference`
  - `identify_state.status = identified`
  - `tracking_state.status = tracking`
  - `tracking_state.maturity = not_ready`
  - `tracking_state.transition_reason = cycle_linkage_blocks_continuation`
  - `entry_state.status = not_ready`
  - `entry_state.decision = wait`
  - `entry_state.actionable = false`
  - `entry_state.blocking_reasons = ["cycle_linkage_blocks_continuation"]`
- `m2_local_global_guardrail_reference`
  - same front posture as above, with `local_end_vs_global_end = possible_global_end`

This is sufficient evidence to promote those front states into benchmark seed truth.

### 3.4 Why Identify Should Still Stay Out Of This Slice

Current fixture evidence also shows:

- `B2/B4` still produce `identify_state.status = identified`

So there is no evidence yet that blocked continuation should negate identify-scope membership.

Therefore:

- this slice must not add a negative `identify_state` expectation for `B2/B4`
- otherwise benchmark would encode a false rule not supported by current canonical owner

## 4. Approach Options

### Option A: Keep B2/B4 Only On M2 Linkage Expectations

Pros:

- no config change

Cons:

- benchmark truth remains incomplete
- cannot formally lock the newly-added canonical front semantics

### Option B: Add Only Tracking/Entry Expectations For B2/B4 (Recommended)

Pros:

- exactly matches current canonical evidence
- keeps scope narrow
- locks the new `M3 -> M4` semantics bridge without inventing extra rules

Cons:

- requires updating several focused tests and fixture-backed carriers

### Option C: Add Full Front Expectations Including Negative Identify

Pros:

- more aggressive closure

Cons:

- not evidence-backed
- would contradict current canonical front owner output

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

This slice only updates benchmark truth and its focused test carriers.

Primary owners:

- `config/benchmark/validation_seed_samples.json`
- focused benchmark tests

Files intentionally not modified in this slice:

- `neotrade3/decision_engine/*`
- `neotrade3/benchmark/assembler.py`
- `neotrade3/benchmark/contracts.py`
- `neotrade3/governance/*`
- `neotrade3/orchestration/*`

### 5.2 B2 Front Expectation Freeze

`b2_control_failure_seed.expected_target_state` should gain:

```json
{
  "tracking_state": {
    "allowed_status": ["tracking"],
    "allowed_maturity": ["not_ready"]
  },
  "entry_state": {
    "allowed_status": ["not_ready"],
    "allowed_decision": ["wait"],
    "actionable": false
  }
}
```

Design rule:

- do not add negative `identify_state` expectations
- do not encode `transition_reason` or `blocking_reasons` into seed truth in this slice

### 5.3 B4 Front Expectation Freeze

`b4_local_global_guardrail_seed.expected_target_state` should gain the same narrow front expectations:

```json
{
  "tracking_state": {
    "allowed_status": ["tracking"],
    "allowed_maturity": ["not_ready"]
  },
  "entry_state": {
    "allowed_status": ["not_ready"],
    "allowed_decision": ["wait"],
    "actionable": false
  }
}
```

Reason:

- current canonical evidence shows the same front posture for `B2` and `B4`
- the distinction between them remains in:
  - `cycle_linkage_state.local_end_vs_global_end`
  - benchmark interaction guardrail checks

### 5.4 Test Carrier Freeze

Any focused benchmark tests that build inline `m3_context` for `B2/B4` scenarios must align with the canonical linkage-aware front payloads.

This especially applies to:

- batch-runner inline fixture providers
- sample-registry driven tests that currently omit `m3_context`

Design rule:

- reuse canonical builder output where needed
- do not handcraft a benchmark-local front rule

## 6. Testing Strategy

Focused tests should lock:

1. seed registry loads `B2/B4` front expectations correctly
2. `B2` still fails under default batch conditions, now with front expectations included
3. `B4` still fails under default batch conditions, now with front expectations included
4. default batch manifests remain stable in pass/fail aggregate
5. sample-registry driven tests and batch-runner inline fixture providers no longer carry stale front payloads

Testing rule:

- do not widen into benchmark rule redesign
- do not widen into decision-engine tests

## 7. Risks And Guardrails

### 7.1 False Negative Identify Rule Risk

The main risk is encoding an unsupported belief that blocked continuation implies `identify_state != identified`.

Guardrail:

- keep `identify_state` untouched in `B2/B4`

### 7.2 Test Carrier Drift Risk

Another risk is that inline test fixture providers still emit pre-linkage front payloads, masking real default behavior.

Guardrail:

- update focused test carriers to reuse the linkage-aware front builders

### 7.3 Scope Widening Risk

Another risk is expanding seed truth to include transition reasons or full evidence bundles.

Guardrail:

- only `allowed_status`
- only `allowed_maturity`
- only `allowed_decision`
- only `actionable`

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- `B2/B4` seed truth declares evidence-backed `tracking / entry` expectations
- focused tests and default batch runs still pass
- no unsupported negative identify rule is introduced
- no benchmark rule language changes are required

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- negative identify expectations for blocked continuation
- transition-reason level benchmark expectations
- finer `B2` vs `B4` front semantics beyond current canonical outputs
- governance closure
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in `M4` seed truth and test carriers; it consumes completed `M3` semantics but does not modify `M3` owner code
- `G1-G6` target mapping:
  - this is the minimum `G2/G5` seed-truth completion step needed so blocked continuation semantics are benchmarked, not just transported
- new contract introduced:
  - `B2/B4` front expectation keys for `tracking_state` and `entry_state`
- boundaries not touched:
  - no decision-engine rewrite
  - no benchmark scoring redesign
  - no governance closure
  - no `M6`
