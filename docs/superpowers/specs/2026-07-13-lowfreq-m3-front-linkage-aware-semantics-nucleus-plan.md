Status: active
Owner: lowfreq / decision_engine / cycle_intelligence
Scope: Implementation plan for the narrow `M3 front linkage-aware semantics nucleus` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Front Linkage-Aware Semantics Nucleus Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m3-front-linkage-aware-semantics-nucleus-design.md`

## 1. Goal

This slice only adds continuation-risk awareness to canonical `M3 front` translation.

This slice must:

- let canonical `tracking / entry` builders consume optional linkage truth
- downgrade entry-ready continuation posture when `supports_continuation=False`
- pass linkage truth through both runtime formal-front wiring and benchmark fixture front-payload wiring
- lock the new branch with focused tests

This slice explicitly does not:

- redesign `identify` decision logic
- update benchmark seed expectations
- redesign benchmark scoring
- add any new persistence owner
- touch `M5` closure or `M6`

## 2. Starting Point

Repository evidence before implementation:

- canonical front builders only consume `cycle + m1_constraints_ref`
- canonical `cycle_linkage_state` truth already exists in `cycle_intelligence`
- runtime formal-front and benchmark fixture front payloads both reuse those same builders
- therefore continuation-risk truth cannot currently influence front maturity or entry actionability

So the correct narrow move is:

- extend canonical builder signatures with an optional linkage input
- introduce one conservative gating rule for `tracking / entry`
- pass linkage truth at the two existing call sites
- prove both default and linkage-aware branches through focused tests

## 3. File Boundary

Production files:

- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/benchmark/fixture_catalog.py`

Focused test files:

- `tests/unit/test_m2_m3_contract_skeleton.py`
- `tests/unit/test_m4_benchmark_fixture_catalog.py`
- `tests/unit/test_m4_benchmark_seed.py`

Optional supporting test file only if strictly needed:

- `tests/unit/test_m4_benchmark_batch_runner.py`

Files intentionally not modified:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/benchmark/assembler.py`
- `config/benchmark/validation_seed_samples.json`
- `neotrade3/governance/*`
- `neotrade3/orchestration/*`

## 4. Execution Steps

### M3LA-S1: Extend canonical front builders with optional linkage input

Modify:

- `neotrade3/decision_engine/assembler.py`

Implementation:

1. add optional parameter:
   - `cycle_linkage_state_ref: Mapping[str, Any] | None = None`
   to:
   - `build_identify_state_from_formal_inputs(...)`
   - `build_tracking_state_from_formal_inputs(...)`
   - `build_entry_state_from_formal_inputs(...)`
2. keep `identify` behavior unchanged in this slice
3. add a small helper to project linkage evidence safely from mapping input

Implementation rule:

- omitted linkage must preserve current behavior
- do not change public payload field names

### M3LA-S2: Introduce conservative linkage-aware gating for tracking and entry

Modify:

- `neotrade3/decision_engine/assembler.py`

Implementation:

1. if `supports_continuation=False`:
   - `tracking.status` remains `tracking`
   - `tracking.maturity` downgrades to `not_ready`
   - `tracking.transition_reason` becomes `cycle_linkage_blocks_continuation`
2. if `supports_continuation=False`:
   - `entry.status` becomes `not_ready`
   - `entry.decision` becomes `wait`
   - `entry.actionable` becomes `False`
   - `entry.blocking_reasons` includes `cycle_linkage_blocks_continuation`
3. project linkage evidence into `tracking_state.evidence_ref` and `entry_state.evidence_ref`

Implementation rule:

- do not mark linkage gating as `m1_constraints_blocked`
- do not create new front contract fields
- do not downgrade `tracking` all the way to `not_tracking`

### M3LA-S3: Pass linkage truth through runtime formal-front assembly

Modify:

- `neotrade3/decision_engine/formal_front.py`

Implementation:

1. build canonical shadow bundle from the already-available `small_cycle`, `security_master`, and `trading_profile`
2. extract `cycle_linkage_state`
3. pass that linkage payload into canonical front builders

Implementation rule:

- reuse canonical `cycle_intelligence` builders
- do not handcraft a runtime-local linkage object

### M3LA-S4: Pass linkage truth through benchmark front-payload fixture generation

Modify:

- `neotrade3/benchmark/fixture_catalog.py`

Implementation:

1. reuse the already-built fixture `shadow_bundle["cycle_linkage_state"]`
2. pass its payload into canonical front builders when constructing `m3_context`

Implementation rule:

- do not duplicate linkage semantics in benchmark
- benchmark remains a consumer of canonical `decision_engine` behavior

### M3LA-S5: Lock the slice with focused tests

Modify:

- `tests/unit/test_m2_m3_contract_skeleton.py`
- `tests/unit/test_m4_benchmark_fixture_catalog.py`
- `tests/unit/test_m4_benchmark_seed.py`

Required coverage:

1. front builders still produce the old positive outputs when linkage input is omitted
2. linkage `supports_continuation=False` downgrades `tracking.maturity` and rewrites `transition_reason`
3. linkage `supports_continuation=False` makes `entry` non-actionable and adds the linkage block reason
4. benchmark guardrail fixture now carries linkage-aware front payloads
5. current positive benchmark front path remains stable

Testing rule:

- prefer owner-focused contract tests
- do not widen into new benchmark expectation config

### M3LA-S6: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/decision_engine/assembler.py neotrade3/decision_engine/formal_front.py neotrade3/benchmark/fixture_catalog.py tests/unit/test_m2_m3_contract_skeleton.py tests/unit/test_m4_benchmark_fixture_catalog.py tests/unit/test_m4_benchmark_seed.py`
- `python3 -m pytest tests/unit/test_m2_m3_contract_skeleton.py tests/unit/test_m4_benchmark_fixture_catalog.py tests/unit/test_m4_benchmark_seed.py`
- `git diff --check`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run inline assertions for:
  - old default branch unchanged
  - linkage-aware tracking downgrade
  - linkage-aware entry block
  - fixture front payload propagation

## 5. Risks And Guardrails

- **Risk: over-widen into identify redesign**
  - Guardrail: `identify` signature may expand, but behavior stays unchanged
- **Risk: runtime and benchmark diverge**
  - Guardrail: both call sites use the same canonical builder contract
- **Risk: break old callers**
  - Guardrail: linkage input stays optional and omission preserves old semantics

## 6. Done Criteria

This slice is done only when all of the following are true:

- canonical `tracking / entry` builders accept optional linkage truth
- `supports_continuation=False` blocks entry-ready continuation posture
- runtime formal-front assembly passes linkage truth
- benchmark fixture front payload generation passes linkage truth
- focused tests pass

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M3` canonical front translation and only wires its downstream consumers in runtime and benchmark fixture generation
- `G1-G6` target mapping:
  - this is a `G2/G5` semantics-alignment step that lets continuation-risk truth affect front maturity and actionability before benchmark re-expands `B2/B4`
- new contract introduced:
  - optional `cycle_linkage_state_ref` input in canonical front builders
  - conservative linkage-aware `transition_reason` and `blocking_reasons`
- boundaries not touched:
  - no benchmark seed update
  - no benchmark scoring redesign
  - no governance closure
  - no `M6`
