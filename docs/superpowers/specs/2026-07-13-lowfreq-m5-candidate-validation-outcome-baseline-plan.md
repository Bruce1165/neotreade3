Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 candidate validation outcome baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Candidate Validation Outcome Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-validation-outcome-baseline-design.md`

## 1. Goal

This slice only introduces the minimum formal owner for final candidate-validation
truth between:

- pending `governance_handoff`
- downstream `reject_execution`
- downstream `status_transition`

This slice must:

- persist one final `ValidationResult` independently from `governance_handoff`
- keep handoff as the immutable pending baseline
- expose typed readback keyed by `validation_id`
- switch downstream governance runtime to consume final validation truth from the new
  owner instead of patched handoff payloads

This slice explicitly does not:

- add candidate-comparison logic
- add scheduled orchestrator adoption
- add auto `validation_id` selection
- add CLI / worker / API triggers
- add promotion approval
- touch `M6`

## 2. File Boundary

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-validation-outcome-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-validation-outcome-baseline-plan.md`

Production files:

- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/__init__.py`

Focused test files:

- `tests/unit/test_m5_governance_candidate_validation_outcome.py`
- `tests/unit/test_m5_governance_reject_execution.py`
- `tests/unit/test_m5_governance_status_transition.py`

Files intentionally not modified:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `apps/api/*`
- `neotrade3/orchestration/*`
- `config/orchestrator/daily_master_orchestrator.json`

## 3. Execution Steps

### M5CVO-S1: Add candidate-validation artifact writer

Modify:

- `neotrade3/governance/artifact_writer.py`

Implementation:

1. add one narrow artifact metadata record for candidate-validation outcomes
2. add one writer for:
   - `var/artifacts/governance_candidate_validations/<validation_id>/governance_candidate_validation.json`
3. artifact payload must include:
   - `validation_id`
   - `source_run_id`
   - `baseline_run_id`
   - `candidate_run_id`
   - `validation_result`
   - `written_at`

Implementation rules:

- `validation_result` must be stored as the authoritative final typed payload
- reject or status-transition fields must not appear in this earlier-stage artifact
- do not read or rewrite `governance_handoff` from this writer

### M5CVO-S2: Add ledger and readback helpers

Modify:

- `neotrade3/governance/run_ledger.py`

Implementation:

1. add one `GovernanceCandidateValidationRecord`
2. add read/materialize helpers for:
   - `var/ledgers/governance_candidate_validations/<validation_id>/governance_candidate_validation_run.json`
3. add artifact readback helpers parallel to existing reject/status-transition readers

Ledger payload must include:

- `validation_id`
- `source_run_id`
- `status`
- `written_at`
- `artifact_path`
- `ledger_path`
- `baseline_run_id`
- `candidate_run_id`
- `outcome`

Implementation rules:

- keep the new record keyed by `validation_id`
- do not widen handoff, reject, or status-transition ledger schemas
- typed readback should return `None` when files are absent, matching existing style

### M5CVO-S3: Add runtime owner for final validation outcome

Modify:

- `neotrade3/governance/runtime.py`

Implementation:

1. add one runtime entrypoint for materializing candidate-validation outcome
2. runtime flow:
   - normalize `source_run_id`
   - normalize and validate final `ValidationResult`
   - require a persisted handoff bundle for `source_run_id`
   - require that the target `validation_id` exists in the handoff baseline
   - require final outcome semantics:
     - not `awaiting_candidate_validation`
     - non-empty `candidate_run_id`
   - materialize independent candidate-validation artifact and ledger

Implementation rules:

- this runtime validates storage truth; it does not compute the outcome
- fail if the handoff bundle is missing
- fail if the target `validation_id` is absent from the baseline bundle
- fail if a caller tries to persist a pending validation payload as a final outcome

### M5CVO-S4: Switch downstream runtime consumers

Modify:

- `neotrade3/governance/runtime.py`

Implementation:

1. update `run_governance_reject_execution(...)` to resolve final validation truth from
   candidate-validation outcome storage instead of `handoff.validation_results`
2. update `run_governance_status_transition(...)` to resolve final validation truth from
   candidate-validation outcome storage instead of `handoff.validation_results`
3. keep blocker/attention lookup sourced from the handoff bundle

Implementation rules:

- handoff remains the owner of baseline blocker/attention structure
- candidate-validation outcome becomes the owner of final validation semantics
- status transition must still require reject proof from `governance_rejections`
- do not patch `governance_handoff` during any downstream runtime path

### M5CVO-S5: Export the new owner surface

Modify:

- `neotrade3/governance/__init__.py`

Implementation:

1. export the new candidate-validation ledger record and runtime entrypoint if they
   belong on the package surface
2. keep export changes minimal and aligned with current `M5` style

Implementation rule:

- do not create a new top-level package or namespace for this slice

### M5CVO-S6: Add focused tests for the new owner

Create:

- `tests/unit/test_m5_governance_candidate_validation_outcome.py`

Test carrier pattern:

- materialize a real governance handoff under a temp project root
- build one final `ValidationResult` with the same `validation_id`
- materialize candidate-validation outcome through the new runtime owner
- assert independent artifact and ledger behavior

Required coverage:

1. final rejected outcome writes independent artifact and ledger
2. final passed outcome writes independent artifact and ledger
3. dry-run writes nothing
4. missing handoff bundle fails deterministically
5. missing baseline `validation_id` fails deterministically
6. pending outcome is rejected as invalid final outcome input

Testing rules:

- do not widen into worker / CLI / API surfaces
- do not fabricate candidate-comparison logic

### M5CVO-S7: Rebase downstream tests onto the new owner

Modify:

- `tests/unit/test_m5_governance_reject_execution.py`
- `tests/unit/test_m5_governance_status_transition.py`

Implementation:

1. remove manual handoff artifact mutation used only to append final validation payloads
2. seed downstream tests through the new candidate-validation outcome owner
3. preserve the original assertions for reject/status-transition runtime outputs

Required coverage outcome:

- reject execution still materializes independent reject artifacts
- status transition still materializes independent effective-state artifacts
- neither test file depends on in-place `governance_handoff` rewrites anymore

### M5CVO-S8: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/artifact_writer.py neotrade3/governance/run_ledger.py neotrade3/governance/runtime.py neotrade3/governance/__init__.py tests/unit/test_m5_governance_candidate_validation_outcome.py tests/unit/test_m5_governance_reject_execution.py tests/unit/test_m5_governance_status_transition.py`
- `python3 -m pytest tests/unit/test_m5_governance_candidate_validation_outcome.py tests/unit/test_m5_governance_reject_execution.py tests/unit/test_m5_governance_status_transition.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: continue relying on handoff mutation implicitly**
  - Guardrail: downstream test seeding must go through the new owner
- **Risk: collapse candidate validation into reject execution**
  - Guardrail: candidate-validation artifact/ledger must not include reject decision data
- **Risk: accept pending validation as final outcome**
  - Guardrail: runtime rejects `awaiting_candidate_validation` and empty `candidate_run_id`
- **Risk: widen into scheduler adoption prematurely**
  - Guardrail: keep all changes inside `governance` plus three focused test files

## 5. Done Criteria

- independent candidate-validation artifact exists
- independent candidate-validation ledger exists
- typed readback exists
- runtime owner exists
- reject and status-transition runtime consume the new final validation truth source
- focused tests pass without patching `governance_handoff` in place
- no `worker/API/orchestrator/M6` file changes appear in the diff

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely inside `M5` and fills the missing owner between pending
    handoff truth and downstream governance actions
- `G1-G6` target mapping:
  - this is the minimum `G5` step that replaces test scaffolding with a formal upstream
    truth source for later governance execution
- new runtime contract introduced:
  - independent candidate-validation artifact and ledger keyed by `validation_id`
  - final validation-outcome readback consumed by reject/status-transition runtime
- boundaries not touched:
  - no candidate-comparison engine
  - no auto scheduler adoption
  - no worker / CLI / API trigger
  - no promotion approval
  - no `M6`
