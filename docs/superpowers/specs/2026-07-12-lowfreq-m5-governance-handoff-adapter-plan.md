Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance handoff adapter` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Handoff Adapter Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-handoff-adapter-design.md`

## 1. Goal

This plan implements only the next narrow `M5` slice after the contract nucleus:

- one formal `M4 -> M5` pure projection owner
- one stable governance handoff bundle
- one focused test carrier that locks assessment-level and batch-level projection

This slice explicitly does not include:

- artifact writing
- ledger/readback
- CLI
- API
- worker/orchestrator registration
- `M6` delivery consumption

## 2. Starting Point

Repository evidence before this slice:

- `M4` already emits formal assessment and batch objects:
  - `BenchmarkAssessmentResult`
  - `BenchmarkBatchRunResult`
- `M5` already has:
  - governance contract objects
  - `B4 local-global guardrail` diagnosis builder
  - diagnosis-derived `ChangeRequest / ExperimentRequest / PromotionBlocker` builders
- there is still no production owner that converts `M4` outputs into a stable `M5` handoff surface

So the implementation strategy is:

- reuse existing `M4` formal outputs
- reuse existing `M5` builders
- add one thin pure projector
- do not modify `M4` producers or widen into runtime/storage semantics

## 3. File Boundary

Production files:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/__init__.py`

Test file:

- `tests/unit/test_m5_governance_handoff_adapter.py`

Documentation files:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-handoff-adapter-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-handoff-adapter-plan.md`

Files explicitly not in scope:

- `neotrade3/benchmark/*`
- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- any governance artifact or ledger module

## 4. Execution Steps

### M5H-S1: Add the handoff bundle contract

Create `neotrade3/governance/handoff.py`.

Add one stable bundle object, recommended as:

- `GovernanceHandoffBundle`

Minimum fields:

- `source_run_id`
- `source_layer`
- `diagnostics`
- `change_requests`
- `experiment_requests`
- `promotion_blockers`
- `projected_assessment_count`
- `projected_issue_count`

Implementation rules:

- use immutable dataclass
- provide `to_payload()`
- use defensive copy semantics for list outputs
- store canonical `M5` objects, not raw `M4` payloads

Completion check:

- downstream code can read one stable in-memory governance bundle without rerunning projector internals

### M5H-S2: Add assessment-level projection

In `neotrade3/governance/handoff.py`, add:

- `build_governance_handoff_from_assessment(...)`

Input:

- `BenchmarkAssessmentResult`

Execution rules:

1. if `trace_bundle` is missing, return an empty bundle
2. inspect `interaction_guardrail_breaches`
3. select only the already-supported `C_GUARD_LOCAL_GLOBAL_END` path
4. call existing builders:
   - `build_b4_local_global_guardrail_diagnostic(...)`
   - `build_change_request_from_diagnostic(...)`
   - `build_experiment_request_from_change_request(...)`
   - `build_promotion_blocker_from_diagnostic(...)`
5. return a bundle with exactly one projected path for each supported assessment

Zero-projection rule:

- non-matching assessments must return an empty bundle
- empty bundle is a valid business outcome, not an error

Completion check:

- one real `B4` failing assessment can be projected into the full minimal governance chain

### M5H-S3: Add batch-level projection

In `neotrade3/governance/handoff.py`, add:

- `build_governance_handoff_from_batch_run(...)`

Input:

- `BenchmarkBatchRunResult`

Execution rules:

1. iterate `results` in original order
2. project each result through `build_governance_handoff_from_assessment(...)`
3. concatenate projected objects in deterministic order
4. set:
   - `source_run_id = batch_result.run_id`
   - `source_layer = "M4"`
   - `projected_assessment_count = len(batch_result.results)`
   - `projected_issue_count = total projected diagnostics`

Implementation guard:

- do not introduce deduplication or merge heuristics beyond deterministic concatenation
- do not inspect raw fixture or manifest inputs

Completion check:

- a real batch result can become one stable aggregated governance bundle

### M5H-S4: Export the package surface

Update `neotrade3/governance/__init__.py`.

Export:

- `GovernanceHandoffBundle`
- `build_governance_handoff_from_assessment(...)`
- `build_governance_handoff_from_batch_run(...)`

Completion check:

- tests and future consumers can import the handoff owner from package root

### M5H-S5: Add focused tests

Create `tests/unit/test_m5_governance_handoff_adapter.py`.

Test groups:

1. assessment projection test
   - reuse real `B4` failing assessment
   - assert exactly one:
     - `DiagnosticChain`
     - `ChangeRequest`
     - `ExperimentRequest`
     - `PromotionBlocker`
   - assert `source_run_id` and summary counts are stable
2. zero-projection assessment test
   - build a real assessment without matching `B4` local-global breach
   - assert all projected lists are empty
   - assert no exception is raised
3. batch projection test
   - compose a batch with both matching and non-matching assessments
   - assert deterministic ordering
   - assert aggregate counts and payload shape
4. defensive payload copy test
   - mutate returned payload lists
   - assert underlying bundle state remains unchanged

Testing rule:

- do not restate `M4` benchmark logic
- test only the new handoff contract and projection boundary

Completion check:

- `M5` handoff behavior is locked independently of runtime/storage concerns

### M5H-S6: Verify

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/governance/handoff.py neotrade3/governance/__init__.py tests/unit/test_m5_governance_handoff_adapter.py`
- `.venv/bin/python -m pytest tests/unit/test_m5_governance_handoff_adapter.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - one `B4` failing assessment
  - one non-matching assessment
  - one synthetic batch result assembled from those real assessment objects

Completion check:

- syntax passes
- best-available focused verification passes

### M5H-S7: Commit Narrowly

Stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-handoff-adapter-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-handoff-adapter-plan.md`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/__init__.py`
- `tests/unit/test_m5_governance_handoff_adapter.py`

Exclude:

- `neotrade3/benchmark/*`
- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- widening the handoff slice into storage or delivery semantics

Guard:

- forbid file IO
- forbid ledger/artifact logic
- keep all outputs in-memory only

Risk 2:

- overfitting the new owner to raw `M4` payload shapes rather than canonical `M5` objects

Guard:

- store only `M5` formal objects in the bundle
- keep `M4` evidence consumption confined to projector inputs

Risk 3:

- treating non-matching assessments as errors and making batch projection brittle

Guard:

- freeze zero-projection as a valid outcome
- reserve exceptions for malformed inputs only

Risk 4:

- silently widening beyond the proven `B4` path

Guard:

- hard-freeze supported projection to `C_GUARD_LOCAL_GLOBAL_END`
- keep other buckets and guardrails out of this slice

## 6. Success Criteria

This slice is complete when:

- `neotrade3/governance/handoff.py` exists as a real production owner
- a real `BenchmarkAssessmentResult` can be projected into a stable governance bundle
- a real `BenchmarkBatchRunResult` can be projected into a stable aggregated governance bundle
- non-matching assessments yield zero projection without runtime failure
- focused verification passes
