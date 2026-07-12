Status: active
Owner: lowfreq / decision_engine
Scope: Narrow `M3 hold/exit formal bridge -> M4` slice for the six-layer back-half landing
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M3 Hold/Exit Formal Bridge Design

Date: 2026-07-12

## 1. Goal

This design covers the first acceleration slice after the six-layer closure audit.

The current repository evidence shows:

- `M3` formal objects stop at `identify / tracking / entry` in [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py)
- the existing hold/exit runtime semantics already live in one shared M3 owner:
  - [position_contract_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/position_contract_snapshot.py)
- `M4` already reserves `m3_context`, but only forwards it opaquely:
  - [assembler.py:L388-L407](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py#L388-L407)
- `M4` still hard-codes `hold_quality_risk_summary={"status": "not_in_scope"}`:
  - [assembler.py:L364-L386](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py#L364-L386)

So this slice exists to solve one narrow problem:

- turn the already-ownerized hold/exit runtime snapshot into formal `M3` objects and a stable `M3 -> M4` bridge payload
- let `M4` begin consuming that bridge for traceability and the first non-placeholder `hold_quality_risk_summary`

This design is not:

- a rewrite of lowfreq sell logic
- a rewrite of `build_position_contract_snapshot(...)`
- a full `M3 lifecycle log` implementation
- a full `M4 hold / exit gap taxonomy`
- any `M5` governance workflow
- any `M6` delivery projection

Project-phase note:

- domain: `lowfreq M3 hold/exit formal bridge`
- change type: `skeleton -> minimal formal bridge`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3-M4 / G5-G6`

## 2. Scope

Included:

- adding formal `M3` contract objects for hold and exit
- adding one shared bridge owner under `neotrade3/decision_engine/`
- translating the existing position snapshot contract into stable `m3_context`
- letting `M4` consume that bridge for:
  - `trace_bundle.m3_context`
  - `assessment_summary.hold_quality_risk_summary`
- focused tests for the new objects, bridge payload, and `M4` consumption

Excluded:

- changing the observable fields produced by `build_position_contract_snapshot(...)`
- changing API workbench rendering
- changing the `M4` gap-record framework for hold/exit errors
- adding `DecisionLifecycleLog`
- adding `timing / holding / exit` gap groups
- changing manifest, fixture registry, or batch-runner orchestration

## 3. Existing Context

Current repository evidence:

- existing formal `M3` objects:
  - [contracts.py:L9-L114](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L9-L114)
- existing M3 front-side builders:
  - [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py)
- existing hold/exit snapshot owner:
  - [position_contract_snapshot.py:L6-L191](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/position_contract_snapshot.py#L6-L191)
- existing hold/exit owner-focused tests:
  - [test_lowfreq_engine_v16_position_contract_snapshot.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py)
- `M4` contract already allows `m3_context` and `hold_quality_risk_summary` as formal fields:
  - [contracts.py:L90-L123](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L90-L123)
  - [contracts.py:L172-L205](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L172-L205)

What is still missing is not runtime meaning. What is missing is:

- a formal `M3` object for hold-side status
- a formal `M3` object for exit-ready / exit-side status
- a canonical bridge payload that `M4` can rely on
- the first minimal `M4` interpretation of hold quality

That makes this slice a bridge-completion step, not a greenfield rule design.

## 4. Approach Options

### Option A: Formalize hold/exit on top of the existing position snapshot owner and let M4 consume only the bridge payload (Recommended)

- keep `build_position_contract_snapshot(...)` as the runtime semantics owner
- add `HoldState` and `ExitState`
- add one bridge helper that translates snapshot output into formal payload
- let `M4` derive only a minimal summary from the bridge

Pros:

- directly reuses the strongest current evidence
- keeps the slice narrow and low-risk
- starts `M4` consumption without forcing premature gap taxonomy design
- preserves current API and engine behavior

Cons:

- `M4` still only gets minimal hold-quality interpretation, not full deviation analysis

### Option B: Build hold/exit formal objects directly from engine collaborators before the snapshot owner

Pros:

- could expose lower-level structure

Cons:

- reopens runtime collection logic that has already been ownerized
- broadens into sell-side execution and collaborator orchestration

### Option C: Skip formal objects and let M4 consume raw snapshot dictionaries

Pros:

- smallest production diff

Cons:

- leaves `M3` still incomplete as a formal layer
- makes `M4` depend on ad hoc dict semantics instead of formal objects
- does not help the six-layer back-half closure goal

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice introduces three bounded ownership moves:

1. extend `neotrade3/decision_engine/contracts.py`
   - add `HOLD_STATE_OBJECT_TYPE`
   - add `EXIT_STATE_OBJECT_TYPE`
   - add `HoldState`
   - add `ExitState`
2. add one bridge owner:
   - `neotrade3/decision_engine/hold_exit_bridge.py`
3. extend `neotrade3/benchmark/assembler.py`
   - consume the bridge payload into `trace_bundle.m3_context`
   - replace `hold_quality_risk_summary={"status": "not_in_scope"}` with a minimal summary builder

This slice does not add another runtime snapshot owner because that responsibility is already frozen in `position_contract_snapshot.py`.

### 5.2 Formal Object Freeze

`HoldState` should formalize the existing non-exit branch only.

Recommended minimum fields:

- `stock_code`
- `trade_date`
- `status`
- `hold_state`
- `warning_flags`
- `not_exit_reasons`
- `evidence_ref`
- `m2_cycle_ref`
- `m1_constraints_ref`

Semantics:

- `status` expresses whether the position remains formally in hold scope
- `hold_state` carries the runtime hold ladder already produced by snapshot owner:
  - `holding`
  - `review_watch`
  - `observe_watch`
  - `noise_watch`
  - `grace_hold`

`ExitState` should formalize the existing exit-ready branch only.

Recommended minimum fields:

- `stock_code`
- `trade_date`
- `status`
- `exit_ready`
- `exit_scope`
- `exit_reason_type`
- `exit_attribution_bucket`
- `evidence_ref`
- `m2_cycle_ref`
- `m1_constraints_ref`

Semantics:

- `status` remains `exit_ready` for the current bridge slice
- `exit_ready` preserves the explicit boolean gate
- `exit_scope`, `exit_reason_type`, and `exit_attribution_bucket` preserve current decision meaning without rewriting sell logic

### 5.3 Bridge Payload Freeze

The new bridge owner should expose one public helper:

- `build_m3_hold_exit_bridge(...) -> dict[str, Any]`

Recommended inputs:

- `stock_code`
- `trade_date`
- `position_snapshot`
- optional `m2_cycle_ref`
- optional `m1_constraints_ref`

Why this shape:

- the upstream hold/exit meaning is already concentrated in `position_snapshot`
- the bridge should translate from an already-frozen M3 owner, not rebuild semantics from raw collaborators
- optional refs let the bridge stay compatible with the current evidence level without inventing unavailable structure

Recommended output shape:

- `hold_state`: formal hold payload or `{}`
- `exit_state`: formal exit payload or `{}`
- `bridge_version`
- `source_contract`
- `position_status`
- `hold_quality_signal`

Behavior rules:

- when `position_snapshot["exit_ready"]` is `False`:
  - populate `hold_state`
  - leave `exit_state` empty
- when `position_snapshot["exit_ready"]` is `True`:
  - populate `exit_state`
  - leave `hold_state` empty
- preserve current `warning_flags`, `not_exit_reasons`, `exit_reason_type`, `exit_scope`, and attribution buckets
- do not mutate or rename snapshot keys outside the bridge output

### 5.4 Minimal M4 Consumption

`M4` should start consuming the bridge in two places only.

First:

- `trace_bundle.m3_context` should store the bridge payload directly

Second:

- `hold_quality_risk_summary` should stop being a placeholder and become a minimal interpretation with no new gap taxonomy

Recommended first-stage summary semantics:

- if no `m3_context` is provided:
  - `status = "missing_m3_hold_exit_bridge"`
- if `exit_state` is present:
  - `status = "exit_ready"`
  - include `exit_reason_type`
  - include `exit_scope`
  - include `risk_level = "high"`
- if `hold_state` is present and `hold_state` is one of:
  - `review_watch`
  - `observe_watch`
  - `noise_watch`
  - `grace_hold`
  then:
  - `status = "watch"`
  - `risk_level = "watch"`
  - include `hold_state`
  - include `warning_flag_count`
- if `hold_state` is present and `hold_state == "holding"`:
  - `status = "holding"`
  - `risk_level = "low"`
  - include `warning_flag_count`

Why keep it this small:

- current evidence supports watch/hold/exit classification
- current evidence does not yet support a stable formal `holding wrong` or `exit wrong` gap system
- this preserves a real forward step for `M4` without pretending `Governance Ready` is already complete

### 5.5 Export Boundary

`neotrade3/decision_engine/__init__.py` should export:

- `HOLD_STATE_OBJECT_TYPE`
- `EXIT_STATE_OBJECT_TYPE`
- `HoldState`
- `ExitState`
- `build_hold_state`
- `build_exit_state`
- `build_m3_hold_exit_bridge`

This keeps the decision-engine formal surface coherent for downstream consumers and tests.

`neotrade3/benchmark/__init__.py` does not need a new public symbol in this slice unless a helper becomes directly reused by tests.

## 6. Risks and Guardrails

Risk 1:

- widening into sell-logic rewrites while formalizing the bridge

Guardrail:

- treat `position_contract_snapshot.py` as canonical runtime meaning
- only translate its output into formal objects

Risk 2:

- overstating `M4` completion by adding too much hold/exit interpretation

Guardrail:

- keep `M4` consumption limited to trace payload and a minimal summary
- do not add new gap groups or governance outputs in this slice

Risk 3:

- inventing unavailable `M1/M2` references

Guardrail:

- keep `m2_cycle_ref` and `m1_constraints_ref` optional in the bridge API
- default them to empty mappings when not provided

## 7. Implementation Outline

Planned steps:

1. extend `contracts.py` with `HoldState` and `ExitState`
2. extend `assembler.py` with `build_hold_state(...)` and `build_exit_state(...)`
3. add `hold_exit_bridge.py`
4. export the new formal objects and builders
5. extend `benchmark/assembler.py` with minimal hold-quality summary consumption
6. add focused tests for:
   - new M3 objects
   - bridge payload translation
   - `M4` trace/summary consumption
7. run syntax checks and focused verification

## 8. Success Criteria

This slice is complete when:

- `M3` no longer stops at `identify / tracking / entry`
- the repository has formal `HoldState` and `ExitState`
- there is one canonical bridge from `position_snapshot` to `m3_context`
- `M4 trace_bundle.m3_context` can carry that bridge unchanged
- `M4 assessment_summary.hold_quality_risk_summary` is no longer `not_in_scope`
- tests lock the bridge semantics without widening into runtime sell-flow refactors

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M3`
- direct consumer layer: `M4`

Goal mapping:

- `G5`: formalize hold-side continuation semantics so the system can distinguish stable hold from watch-state hold
- `G6`: formalize exit-ready semantics so system-level invalidation and exhaustion signals become benchmark-visible

Not claimed in this slice:

- no claim that `M4` has finished full hold/exit deviation taxonomy
- no claim that `M5` governance loop is now complete
- no claim that `M6` delivery layer is now runnable end-to-end
