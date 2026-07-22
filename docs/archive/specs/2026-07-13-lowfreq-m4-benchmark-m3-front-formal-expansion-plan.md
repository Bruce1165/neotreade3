Status: active
Owner: lowfreq / decision_engine / benchmark
Scope: Implementation plan for the narrow `M3 front formal -> M4 benchmark` expansion slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M4 Benchmark M3 Front Formal Expansion Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m4-benchmark-m3-front-formal-expansion-design.md`

## 1. Goal

This slice only moves default `M4` benchmark runs from:

- `M2 shadow + narrow hold/exit bridge`

to:

- `M2 shadow + M3 front formal + existing hold/exit bridge`

This slice must:

- inject canonical `identify / tracking / entry` payloads into benchmark default fixtures
- evaluate optional front expectations from `expected_target_state`
- emit `G1 Identify Gap` and `G2 Timing Gap` records when front-state expectations are violated
- project current front-state status into a narrow assessment summary field
- keep batch-runner, persisted artifact, and typed readback stable

This slice explicitly does not:

- create any new independent `M3` persistence owner
- redesign benchmark sample registry outside `expected_target_state`
- add lifecycle-event evaluation
- redesign hold/exit scoring
- touch `M5` closure or `M6`

## 2. Starting Point

Repository evidence before implementation:

- canonical `IdentifyState`, `TrackingState`, and `EntryState` contracts plus builders already exist in `decision_engine`
- benchmark transport already carries `m3_context` from fixture to assembler
- default fixture catalog does not inject those front states
- benchmark assembler does not compare front states against target-state expectations
- default validation seed config contains no `identify_state`, `tracking_state`, or `entry_state` expectations

So the correct narrow move is:

- build canonical front payloads in benchmark fixtures
- teach benchmark assembler to consume a small optional expectation contract
- update only evidence-backed positive seeds
- lock the change with focused benchmark tests

## 3. File Boundary

Production files:

- `neotrade3/benchmark/fixture_catalog.py`
- `neotrade3/benchmark/assembler.py`
- `neotrade3/benchmark/contracts.py`
- `config/benchmark/validation_seed_samples.json`

Conditional production file only if new constants are exported through the package surface:

- `neotrade3/benchmark/__init__.py`

Focused test files:

- `tests/unit/test_m4_benchmark_fixture_catalog.py`
- `tests/unit/test_m4_benchmark_seed.py`
- `tests/unit/test_m4_benchmark_batch_runner.py`
- `tests/unit/test_m4_benchmark_typed_readback.py`

Files intentionally not modified:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/decision_engine/projections.py`
- `neotrade3/benchmark/sample_registry.py`
- `neotrade3/governance/*`
- `neotrade3/orchestration/*`

## 4. Execution Steps

### M4FP-S1: Inject canonical M3 front payloads into default benchmark fixtures

Modify:

- `neotrade3/benchmark/fixture_catalog.py`

Implementation:

1. build a shared helper that derives:
   - `m1_constraints_ref`
   - `identify_state`
   - `tracking_state`
   - `entry_state`
   from the same reference `cycle` and formal M1 objects already used in the fixture catalog
2. attach those payloads to the fixture `m3_context`
3. keep current hold/exit-capable `m3_context` contract compatible by only adding new sibling keys

Implementation rule:

- use canonical `decision_engine.assembler` builders only
- do not handcraft benchmark-local payloads
- do not remove or rename existing `m3_context` keys

### M4FP-S2: Extend benchmark contracts with a narrow front summary projection

Modify:

- `neotrade3/benchmark/contracts.py`
- `neotrade3/benchmark/__init__.py` only if new exports are required

Implementation:

1. add `front_quality_risk_summary` to `AssessmentSummary`
2. wire it through:
   - dataclass definition
   - `to_payload()`
   - `from_dict()`
   - `build_assessment_summary(...)`
3. if tests import newly added constants such as `GAP_GROUP_TIMING`, export them through package surface

Implementation rule:

- keep the new summary field optional/default-empty
- preserve backward-compatible artifact reconstruction for existing persisted payloads that lack the new key

### M4FP-S3: Add front-state evaluation to benchmark assembler

Modify:

- `neotrade3/benchmark/assembler.py`

Implementation:

1. add a narrow extractor/helper for front-state actual payloads from `m3_context`
2. add optional expectation checks for:
   - `identify_state.allowed_status`
   - `tracking_state.allowed_status`
   - `tracking_state.allowed_maturity`
   - `entry_state.allowed_status`
   - `entry_state.allowed_decision`
   - `entry_state.actionable`
3. emit gap records with:
   - `G1 Identify Gap` for identify mismatches
   - `G2 Timing Gap` for tracking and entry mismatches
   - `L9 State-Drift` as the conservative label
4. build `front_quality_risk_summary` from actual front states plus grouped front-gap counts
5. keep existing M2 shadow checks, hold summary, interaction checks, and trace bundle intact

Implementation rule:

- no nested-path evaluator
- no benchmark-local front-state builder
- no inferred `Early-Entry` / `Late-Entry` labels

### M4FP-S4: Expand default validation seeds only where expectations are evidence-backed

Modify:

- `config/benchmark/validation_seed_samples.json`

Implementation:

1. add `identify_state`, `tracking_state`, and `entry_state` expectations to:
   - `b1_target_opportunity_seed`
   - `b3_boundary_complex_advancing_seed`
2. leave `b2_control_failure_seed` and `b4_local_global_guardrail_seed` unchanged on front expectations

Implementation rule:

- do not claim front expectations for `B2/B4`
- keep sample ids, fixture ids, bucket assignments, and existing M2 expectations unchanged

### M4FP-S5: Lock the slice with focused tests

Modify:

- `tests/unit/test_m4_benchmark_fixture_catalog.py`
- `tests/unit/test_m4_benchmark_seed.py`
- `tests/unit/test_m4_benchmark_batch_runner.py`
- `tests/unit/test_m4_benchmark_typed_readback.py`

Required coverage:

1. fixture catalog injects canonical `identify / tracking / entry` payloads
2. positive `B1/B3` seeds still pass with declared front expectations
3. crafted identify mismatch emits `G1 Identify Gap`
4. crafted tracking or entry mismatch emits `G2 Timing Gap`
5. `front_quality_risk_summary` exposes actual front states and grouped counts
6. default batch manifests keep stable aggregate grade/bucket behavior
7. typed readback round-trips the expanded summary contract

Testing rule:

- prefer targeted owner tests over widening into decision-engine runtime tests
- reuse existing benchmark carriers where possible

### M4FP-S6: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/benchmark/__init__.py neotrade3/benchmark/contracts.py neotrade3/benchmark/assembler.py neotrade3/benchmark/fixture_catalog.py tests/unit/test_m4_benchmark_fixture_catalog.py tests/unit/test_m4_benchmark_seed.py tests/unit/test_m4_benchmark_batch_runner.py tests/unit/test_m4_benchmark_typed_readback.py`
- `python3 -m pytest tests/unit/test_m4_benchmark_fixture_catalog.py tests/unit/test_m4_benchmark_seed.py tests/unit/test_m4_benchmark_batch_runner.py tests/unit/test_m4_benchmark_typed_readback.py`
- `git diff --check`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run inline assertions for:
  - fixture-injected front payload presence
  - front-gap classification
  - summary round-trip through `from_dict()`
  - batch-runner aggregate stability

## 5. Risks And Guardrails

- **Risk: benchmark invents a second M3 front schema**
  - Guardrail: fixture layer must call canonical `decision_engine` builders only
- **Risk: expectation language widens into a rule DSL**
  - Guardrail: only support direct optional keys under `identify_state`, `tracking_state`, and `entry_state`
- **Risk: false precision on negative samples**
  - Guardrail: keep `B2/B4` front expectations out of this slice
- **Risk: typed readback drift**
  - Guardrail: `front_quality_risk_summary` defaults empty and round-trips via `from_dict()`

## 6. Done Criteria

This slice is done only when all of the following are true:

- default benchmark fixtures inject canonical `identify / tracking / entry` payloads
- benchmark assembler evaluates optional front expectations without adding a DSL
- front mismatches are split into `G1 Identify Gap` and `G2 Timing Gap`
- `AssessmentSummary` exposes `front_quality_risk_summary`
- `B1/B3` default seeds declare front expectations and still pass
- focused tests pass
- batch artifacts still reconstruct through typed readback

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice reuses `M3` canonical front outputs and expands `M4` benchmark consumption only; it does not move ownership out of decision engine or into governance
- `G1-G6` target mapping:
  - this is the minimum `G1/G2` step that lets benchmark distinguish identify drift from timing drift in the default mainline
- new contract introduced:
  - optional front expectation keys in `expected_target_state`
  - `AssessmentSummary.front_quality_risk_summary`
- boundaries not touched:
  - no new M3 persistence
  - no lifecycle-event benchmarking
  - no `M5` closure
  - no `M6`
