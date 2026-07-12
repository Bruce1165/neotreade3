Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance contract nucleus` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Contract Nucleus Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-contract-nucleus-design.md`

## 1. Goal

This plan implements only the first real `M5` code nucleus:

- formal governance contracts
- pure builders
- one real `B4 interaction guardrail` diagnosis path

This slice explicitly does not include:

- CLI
- API
- worker
- persistence
- state machine runtime

## 2. Starting Point

Repository evidence before this slice:

- `M5` has a frozen design document, but no code package
- `M4` already provides formal upstream objects:
  - `GapRecord`
  - `TraceBundle`
  - `InteractionGuardrailBreach`
- `B4_interaction_guardrail` already emits:
  - `L8 Local-Global-Misread`
  - `C_GUARD_LOCAL_GLOBAL_END`

So the implementation strategy is:

- reuse `M4`
- add `M5`
- do not modify upstream `M4` producers

## 3. File Boundary

Production files:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/__init__.py`

Test file:

- `tests/unit/test_m5_governance_contract_nucleus.py`

Documentation files:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-contract-nucleus-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-contract-nucleus-plan.md`

## 4. Execution Steps

### M5N-S1: Add contract objects

Create `neotrade3/governance/contracts.py`.

Add constants:

- `DIAGNOSTIC_CHAIN_OBJECT_TYPE`
- `CHANGE_REQUEST_OBJECT_TYPE`
- `EXPERIMENT_REQUEST_OBJECT_TYPE`
- `VALIDATION_RESULT_OBJECT_TYPE`
- `PROMOTION_BLOCKER_OBJECT_TYPE`
- `GOVERNANCE_DECISION_RECORD_OBJECT_TYPE`
- `M5_OBJECT_VERSION`

Add root-layer constants:

- `A1 Data Root`
- `A2 Recognition Root`
- `A3 Translation Root`
- `A4 Interaction Root`
- `A5 Governance Root`

Add dataclasses:

- `DiagnosticChain`
- `ChangeRequest`
- `ExperimentRequest`
- `ValidationResult`
- `PromotionBlocker`
- `GovernanceDecisionRecord`

Each object must provide:

- immutable dataclass
- `to_payload()`
- defensive copy behavior for mappings/lists

Completion check:

- each object has a stable payload shape and object metadata

### M5N-S2: Add pure builders

Create `neotrade3/governance/assembler.py`.

Add:

- generic builders for all contract objects
- one diagnosis builder:
  - `build_b4_local_global_guardrail_diagnostic(...)`
- thin derived builders:
  - `build_change_request_from_diagnostic(...)`
  - `build_experiment_request_from_change_request(...)`
  - `build_promotion_blocker_from_diagnostic(...)`

Implementation rules:

- validate required text ids
- do not accept empty identifiers
- consume only formal `M4` objects or mappings derived from them
- keep policy deterministic and minimal

`B4` diagnosis builder should:

1. locate `C_GUARD_LOCAL_GLOBAL_END`
2. locate related `L8 Local-Global-Misread` gap(s)
3. emit `DiagnosticChain`
4. set:
   - `primary_root_layer = A4 Interaction Root`
   - `recommended_path = P4 协同语义修正路径`
   - `interaction_layers = ["M2", "M3", "M4"]`

Completion check:

- the diagnosis path is pure and attached to real benchmark evidence

### M5N-S3: Export the package surface

Create `neotrade3/governance/__init__.py`.

Export:

- all object constants
- all root-layer constants
- all dataclasses
- all builders

Completion check:

- tests can import the governance nucleus from package root

### M5N-S4: Add focused tests

Create `tests/unit/test_m5_governance_contract_nucleus.py`.

Test groups:

1. payload contract tests
   - object type
   - object version
   - copy behavior for lists/mappings
2. validation tests
   - empty ids/text should fail
3. real `B4` diagnosis test
   - reuse `build_benchmark_assessment_from_m2_shadow(...)`
   - produce a failing `B4` assessment
   - build `DiagnosticChain`
   - assert root layer, path, gap refs, breach refs
4. governance-action projection tests
   - `DiagnosticChain -> ChangeRequest`
   - `DiagnosticChain -> PromotionBlocker`

Testing rule:

- do not restate all `M4` behavior
- test only the new `M5` contract and projection logic

Completion check:

- the governance nucleus is locked independently of runtime entrypoints

### M5N-S5: Verify

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/governance/contracts.py neotrade3/governance/assembler.py neotrade3/governance/__init__.py tests/unit/test_m5_governance_contract_nucleus.py`
- `.venv/bin/python -m pytest tests/unit/test_m5_governance_contract_nucleus.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - a `B4` failing benchmark assessment
  - `build_b4_local_global_guardrail_diagnostic(...)`
  - `build_change_request_from_diagnostic(...)`
  - `build_promotion_blocker_from_diagnostic(...)`

Completion check:

- syntax passes
- best-available verification passes

### M5N-S6: Commit Narrowly

Stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-contract-nucleus-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-contract-nucleus-plan.md`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/__init__.py`
- `tests/unit/test_m5_governance_contract_nucleus.py`

Exclude:

- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- `neotrade3/benchmark/*`
- unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- pulling in runtime concerns before the object layer is stable

Guard:

- keep every builder pure
- no file writes
- no CLI

Risk 2:

- overfitting the contract to one `B4` scenario

Guard:

- keep generic object builders
- only the diagnosis adapter is `B4`-specific

Risk 3:

- creating fields that the frozen design does not support

Guard:

- derive field names from the design doc wherever possible
- keep additional fields to evidence-tracking minimum only

## 6. Success Criteria

This slice is complete when:

- `neotrade3/governance/` exists
- the `M5` contract nucleus has stable payloads
- a real `B4` breach can become a formal `DiagnosticChain`
- that diagnosis can become a `ChangeRequest` and `PromotionBlocker`
- focused verification passes
