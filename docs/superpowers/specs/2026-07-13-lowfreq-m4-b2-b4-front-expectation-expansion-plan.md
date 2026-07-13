Status: active
Owner: lowfreq / benchmark
Scope: Implementation plan for the narrow `B2/B4 front expectation expansion` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M4 B2/B4 Front Expectation Expansion Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m4-b2-b4-front-expectation-expansion-design.md`

## 1. Goal

This slice only promotes already-evidence-backed `B2/B4` front semantics into benchmark seed truth.

This slice must:

- add `tracking_state` expectations to `B2/B4`
- add `entry_state` expectations to `B2/B4`
- keep `identify_state` unchanged
- align focused test carriers with the linkage-aware front payloads already produced by canonical fixtures
- preserve existing pass/fail aggregate behavior for default benchmark batches

This slice explicitly does not:

- modify `decision_engine`
- redesign benchmark scoring
- add new expectation language
- update `B1/B3`
- touch `M5` closure or `M6`

## 2. Starting Point

Repository evidence before implementation:

- `B2/B4` still declare only `cycle_linkage_state` expectations in seed truth
- canonical front semantics now already produce blocked-continuation `tracking / entry` states
- default benchmark fixtures already emit those linkage-aware front payloads
- some focused test carriers still inline old non-linkage-aware `m3_context`

So the correct narrow move is:

- extend `B2/B4` seed truth to match current canonical front outputs
- update focused tests to consume that truth without changing benchmark owners

## 3. File Boundary

Production file:

- `config/benchmark/validation_seed_samples.json`

Focused test files:

- `tests/unit/test_m4_benchmark_sample_registry.py`
- `tests/unit/test_m4_benchmark_batch_runner.py`
- `tests/unit/test_m4_benchmark_seed.py`

Optional focused test file only if required by current drift:

- `tests/unit/test_m4_benchmark_fixture_catalog.py`

Files intentionally not modified:

- `neotrade3/decision_engine/*`
- `neotrade3/benchmark/assembler.py`
- `neotrade3/benchmark/contracts.py`
- `neotrade3/benchmark/fixture_catalog.py`
- `neotrade3/governance/*`
- `neotrade3/orchestration/*`

## 4. Execution Steps

### M4B24-S1: Expand B2/B4 seed truth with evidence-backed front expectations

Modify:

- `config/benchmark/validation_seed_samples.json`

Implementation:

1. add `tracking_state.allowed_status=["tracking"]` to `B2/B4`
2. add `tracking_state.allowed_maturity=["not_ready"]` to `B2/B4`
3. add `entry_state.allowed_status=["not_ready"]` to `B2/B4`
4. add `entry_state.allowed_decision=["wait"]` to `B2/B4`
5. add `entry_state.actionable=false` to `B2/B4`

Implementation rule:

- do not add `identify_state` expectations
- do not add `transition_reason` or `blocking_reasons`

### M4B24-S2: Align sample-registry tests with expanded seed truth

Modify:

- `tests/unit/test_m4_benchmark_sample_registry.py`

Implementation:

1. assert `B2/B4` now load front expectations from registry
2. keep existing registry metadata assertions intact

### M4B24-S3: Align batch-runner test fixtures with linkage-aware front payloads

Modify:

- `tests/unit/test_m4_benchmark_batch_runner.py`

Implementation:

1. update inline fixture provider so `B2/B4` carry linkage-aware `m3_context`
2. keep aggregate pass/fail expectations unchanged
3. add one focused assertion that blocked-continuation samples now expose `front_quality_risk_summary.status == "available"`

Implementation rule:

- reuse canonical front builders
- do not handcraft ad hoc front payloads

### M4B24-S4: Lock seed-level behavior with focused benchmark assertions

Modify:

- `tests/unit/test_m4_benchmark_seed.py`

Implementation:

1. assert `B2/B4` still fail under their prohibition target expectations
2. assert failure now remains consistent with front expectations present
3. if needed, add one direct assertion that blocked-continuation `entry_state` actual payload remains `not_ready / wait / False`

### M4B24-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile tests/unit/test_m4_benchmark_sample_registry.py tests/unit/test_m4_benchmark_batch_runner.py tests/unit/test_m4_benchmark_seed.py`
- `python3 -m pytest tests/unit/test_m4_benchmark_sample_registry.py tests/unit/test_m4_benchmark_batch_runner.py tests/unit/test_m4_benchmark_seed.py`
- `git diff --check`

## 5. Risks And Guardrails

- **Risk: encode unsupported identify rule**
  - Guardrail: `identify_state` stays untouched for `B2/B4`
- **Risk: stale inline test carriers mask real seed truth**
  - Guardrail: update inline `m3_context` to canonical linkage-aware payloads
- **Risk: widen scope into scoring redesign**
  - Guardrail: only seed truth plus focused test carriers

## 6. Done Criteria

This slice is done only when all of the following are true:

- `B2/B4` seed truth declares `tracking / entry` expectations
- focused tests pass
- default batch aggregates remain unchanged
- no decision-engine or benchmark owner file is modified

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in `M4` seed truth and test carriers only
- `G1-G6` target mapping:
  - this is the minimum `G2/G5` benchmark-truth completion step after canonical linkage-aware front semantics landed
- new contract introduced:
  - `B2/B4` benchmark front expectations for `tracking_state` and `entry_state`
- boundaries not touched:
  - no decision-engine rewrite
  - no benchmark rule redesign
  - no governance closure
  - no `M6`
