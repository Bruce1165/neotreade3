Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance contract nucleus` slice for the six-layer back-half landing
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Contract Nucleus Design

Date: 2026-07-12

## 1. Goal

This slice starts `M5 minimal governance` with the smallest code-bearing nucleus that is still attached to real upstream evidence.

Current repository evidence shows:

- `M5` detailed design is frozen, but no production code package exists yet for governance objects or governance builders.
- `M4` already emits the exact formal upstream evidence that `M5` needs:
  - `gap_record`
  - `trace_bundle`
  - `interaction_guardrail_breach`
- the strongest already-runnable `M4 -> M5` proof path is `B4_interaction_guardrail`, where `local_end_vs_global_end` misread is projected into a formal high-severity interaction breach.

So the smallest safe next step is not:

- a full governance CLI
- a governance state machine
- orchestrator registration
- auto experiment execution

It is:

- freeze formal `M5` contract objects
- add pure in-memory builders
- prove one real diagnosis path from `M4 B4 guardrail` into `M5` governance objects

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `skeleton -> formal contract nucleus`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add a new package: `neotrade3/governance/`
- add formal `M5` contract objects:
  - `DiagnosticChain`
  - `ChangeRequest`
  - `ExperimentRequest`
  - `ValidationResult`
  - `PromotionBlocker`
  - `GovernanceDecisionRecord`
- add pure builders for those objects
- add one `B4 local-global guardrail` diagnosis builder that consumes existing `M4` formal objects only
- add focused tests for contract payloads and the `B4 -> diagnostic/change/blocker` path

Excluded:

- no CLI
- no worker/orchestrator registration
- no API routes
- no governance persistence
- no human approval workflow
- no multi-path root-cause engine
- no direct mutation of `M2/M3/M4`

## 3. Existing Evidence

### 3.1 M5 Is Designed But Not Implemented

The design already freezes the governance path:

- [2026-07-07-m5-evolution-controller-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m5-evolution-controller-design.md)

Critical evidence:

- `M4` is the formal gap-input layer for `M5`
- `diagnostic_chain` is the problem-truth object
- `Change Request` is the governance-action object
- `Promotion Blocker` is a first-class governance object
- the standard loop must be:
  - `Gap / Diagnostic -> Change Request -> Experiment Request -> Validation Result -> Promotion Decision / Reject Decision`

### 3.2 M4 Already Emits Real Inputs

Current upstream objects already exist in code:

- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py)
- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py)

Relevant formal objects:

- `GapRecord`
- `TraceBundle`
- `InteractionGuardrailBreach`

The `B4_interaction_guardrail` sample already emits:

- `gap_label = L8 Local-Global-Misread`
- `guardrail_code = C_GUARD_LOCAL_GLOBAL_END`
- `severity = high`

This makes `B4` the best first governance seed because it is already formal, deterministic, and risk-oriented.

### 3.3 Learning Is Not M5

`LearningLoopPipeline` and `EvolutionReportGenerator` currently remain suggestion/report tooling, not formal governance control.

Therefore this slice must not reuse those modules as if they were already the `M5` owner.

## 4. Design Decision

### Option A: Start With Governance Contract Nucleus (Recommended)

- create `neotrade3/governance/contracts.py`
- create `neotrade3/governance/assembler.py`
- create `neotrade3/governance/__init__.py`
- add one real `B4` diagnosis builder

Pros:

- smallest code slice that makes `M5` real
- directly consumes formal `M4` evidence
- creates a stable base for later CLI, persistence, and governance state machine
- avoids wide runtime changes

Cons:

- does not yet provide a runnable governance entrypoint

### Option B: Start With Governance CLI

Pros:

- runnable sooner

Cons:

- would force contract choices and runtime shape at the same time
- widens into persistence and operational behavior before the object layer is frozen

### Option C: Start With Full State Machine

Pros:

- closer to end-state workflow

Cons:

- too wide for the first M5 slice
- depends on approval/persistence surfaces that do not exist yet

Decision:

- choose Option A

## 5. Contract Design

### 5.1 Root-Layer Vocabulary

This slice freezes only the design-approved root-layer names already documented by `M5`:

- `A1 Data Root`
- `A2 Recognition Root`
- `A3 Translation Root`
- `A4 Interaction Root`
- `A5 Governance Root`

For the `B4 local-global misread` path, the primary root layer is:

- `A4 Interaction Root`

Reason:

- the defect is not raw data corruption
- not pure `M2` state definition in isolation
- not pure `M3` behavior translation in isolation
- it is the cross-layer semantic misread already formalized as an interaction guardrail breach

### 5.2 Formal Objects Included In This Slice

#### `DiagnosticChain`

Purpose:

- formal problem-truth object for one governance issue

Minimum fields:

- `diagnostic_id`
- `symbol`
- `trade_date`
- `sample_bucket`
- `primary_root_layer`
- `secondary_layers`
- `interaction_layers`
- `problem_statement`
- `suspected_root_cause`
- `recommended_path`
- `source_gap_ids`
- `source_breach_ids`
- `evidence_refs`
- `trace_id`
- `benchmark_run_id`

#### `ChangeRequest`

Purpose:

- formal governance action proposal derived from a diagnosis

Minimum fields:

- `cr_id`
- `diagnostic_id`
- `target_layer`
- `source_gap_ids`
- `problem_statement`
- `suspected_root_cause`
- `expected_improvement`
- `risk_scope`
- `priority`
- `requires_human_approval`
- `status`
- `evidence_refs`

#### `ExperimentRequest`

Purpose:

- formal pre-promotion experiment envelope

Minimum fields:

- `experiment_id`
- `cr_id`
- `target_layer`
- `hypothesis`
- `expected_improvement`
- `guardrail_codes`
- `comparison_scope`
- `status`
- `evidence_refs`

#### `ValidationResult`

Purpose:

- formal result object for baseline vs candidate validation

Minimum fields:

- `validation_id`
- `experiment_id`
- `baseline_run_id`
- `candidate_run_id`
- `outcome`
- `cleared_guardrail_codes`
- `remaining_guardrail_codes`
- `introduced_risk_count`
- `evidence_refs`

Note:

- `ValidationResult` is included now because the `M5` design already freezes it inside the standard governance chain, even if this slice does not yet automate comparison logic.

#### `PromotionBlocker`

Purpose:

- formal gate object preventing promotion while risk remains active

Minimum fields:

- `blocker_id`
- `diagnostic_id`
- `blocker_code`
- `severity`
- `reason`
- `required_clearance`
- `active`
- `evidence_refs`

#### `GovernanceDecisionRecord`

Purpose:

- formal decision trail for approve/reject/block/close outcomes

Minimum fields:

- `decision_id`
- `subject_type`
- `subject_id`
- `decision`
- `decision_scope`
- `rationale`
- `approver`
- `status`
- `evidence_refs`

### 5.3 B4-Specific Builder

This slice adds one real diagnosis builder:

- `build_b4_local_global_guardrail_diagnostic(...)`

Inputs:

- `gap_records`
- `trace_bundle`
- `interaction_guardrail_breaches`

Behavior:

- select the `C_GUARD_LOCAL_GLOBAL_END` breach
- bind the related `L8 Local-Global-Misread` interaction gap(s)
- produce one `DiagnosticChain` with:
  - `primary_root_layer = A4 Interaction Root`
  - `recommended_path = P4 协同语义修正路径`
  - `interaction_layers = ["M2", "M3", "M4"]`

Why `M2/M3/M4`:

- `M2` owns the local/global semantic source
- `M3` is the downstream translator that can mis-handle the meaning
- `M4` is the validation layer that formally observed and surfaced the breach

This function remains pure:

- no files
- no network
- no orchestration

### 5.4 Governance Object Builders Derived From Diagnosis

This slice also provides thin builders that turn a diagnosis into the minimal governance action chain:

- `build_change_request_from_diagnostic(...)`
- `build_experiment_request_from_change_request(...)`
- `build_promotion_blocker_from_diagnostic(...)`

For the first `B4` path:

- `ChangeRequest.target_layer = "M2-M3"`
- `requires_human_approval = True`
- `PromotionBlocker.active = True` while the guardrail breach exists

These builders are intentionally policy-light and deterministic.

## 6. Export Boundary

Expose the contract types, constants, and builders via:

- `neotrade3/governance/__init__.py`

No package-root side effects.

## 7. Testing Strategy

Add one focused unit test file:

- `tests/unit/test_m5_governance_contract_nucleus.py`

Tests should lock:

1. object payloads and `object_type`
2. validation that key ids/text inputs cannot be empty
3. `B4` failing assessment -> `DiagnosticChain`
4. `DiagnosticChain` -> `ChangeRequest`
5. `DiagnosticChain` -> `PromotionBlocker`

The `B4` test must reuse real `M4` assessment output rather than fake dictionaries where practical.

## 8. Risks And Guardrails

Risk 1:

- inventing too much governance semantics before runtime consumers exist

Guardrail:

- keep only the minimum fields already demanded by the design doc
- avoid persistence/state-machine fields beyond the nucleus

Risk 2:

- letting this slice become a hidden adapter/CLI slice

Guardrail:

- forbid file IO and runtime entrypoints in this slice

Risk 3:

- overclaiming that `M5` is now implemented

Guardrail:

- claim only:
  - formal `M5` object nucleus exists
  - one real `B4` diagnosis path exists
- do not claim:
  - governance runtime
  - governance queue
  - promotion workflow

## 9. Success Criteria

This slice is complete when:

- `neotrade3/governance/` exists as a real code package
- formal `M5` nucleus objects exist with stable payload shape
- `B4` interaction guardrail evidence can be turned into a formal `DiagnosticChain`
- that diagnosis can produce a formal `ChangeRequest` and `PromotionBlocker`
- focused tests lock the behavior

## 10. Dual-Axis Audit Target

Architecture:

- primary layer: `M5`
- upstream dependency consumed but not modified: `M4`

Goal mapping:

- `G5`: convert formal `M4` deviation evidence into formal governance objects
- not yet `G6`: no delivery/UI/runtime projection is claimed here

Not claimed in this slice:

- no orchestrator integration
- no automated experiment execution
- no promotion automation
- no `M6` governance view
