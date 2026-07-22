Status: active
Owner: lowfreq / governance / worker / api
Scope: Implementation plan for the narrow `M5 candidate validation outcome trigger adoption baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Candidate Validation Outcome Trigger Adoption Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-validation-outcome-trigger-adoption-baseline-design.md`

## 1. Goal

This slice only promotes the existing `candidate validation outcome` runtime owner into
truthful external trigger surfaces.

This slice must:

- keep `run_governance_candidate_validation_outcome(...)` as the runtime owner
- add one governance CLI command that accepts explicit final validation payload input
- add one worker-owned on-demand trigger and worker CLI mode
- add one API-visible orchestration mode for the same trigger contract
- add focused tests proving CLI, worker/API, and HTTP round-trip parity

This slice explicitly does not:

- change candidate validation artifact or ledger schemas
- change reject or status-transition runtime semantics
- add scheduler registration
- add automatic `validation_id` selection
- add candidate-comparison logic
- update runbook or UI
- touch `M6`

## 2. File Boundary

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-validation-outcome-trigger-adoption-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-validation-outcome-trigger-adoption-baseline-plan.md`

Production files:

- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `apps/api/main.py`
- `apps/api/router.py`

Focused test files:

- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_bootstrap_skeleton.py`
- `tests/integration/test_http_smoke.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/contracts.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `tests/unit/test_m5_governance_candidate_validation_outcome.py`

## 3. Execution Steps

### M5CVT-S1: Extend governance CLI with explicit outcome input

Modify:

- `neotrade3/governance/cli.py`

Implementation:

1. import `run_governance_candidate_validation_outcome(...)`
2. add one subcommand:
   - `candidate-validation-outcome`
3. require:
   - `--source-run-id`
   - one JSON-file argument for the final `validation_result` payload
4. deserialize the JSON file into the existing `ValidationResult` contract shape
5. call the existing runtime owner
6. print one narrow JSON summary consistent with current governance CLI style

Implementation rules:

- do not explode `ValidationResult` into field-by-field CLI flags
- do not infer final outcome from `validation_id` alone
- keep `handoff`, `reject`, and `status-transition` commands unchanged

### M5CVT-S2: Add worker-owned on-demand trigger

Modify:

- `apps/worker/main.py`

Implementation:

1. import `run_governance_candidate_validation_outcome(...)`
2. add one worker method:
   - `run_governance_candidate_validation_outcome_on_demand(...)`
3. build an `OnDemandTaskRequest` with one explicit governance task using:
   - task id `governance.candidate_validation_outcome`
   - runtime entrypoint `neotrade3.governance.runtime:run_governance_candidate_validation_outcome`
   - `args_template` carrying:
     - `source_run_id`
     - `validation_result`
4. execute it through the existing on-demand orchestration carrier
5. preserve the existing stored snapshot envelope

Recommended minimum `TaskResult.details` projection:

- `source_run_id`
- `validation_id`
- `candidate_run_id`
- `outcome`

Implementation rules:

- mirror the current reject/status-transition on-demand pattern
- do not add scheduler config
- do not widen the worker snapshot schema beyond a narrow `details` projection

### M5CVT-S3: Extend worker CLI mode and payload parsing

Modify:

- `apps/worker/main.py`

Implementation:

1. extend `--mode` choices with:
   - `governance_candidate_validation_outcome`
2. add one new CLI argument for serialized `validation_result` input
3. keep existing `--source-run-id` validation
4. for the new mode, require both:
   - `--source-run-id`
   - the serialized `validation_result` payload input
5. route the mode to:
   - `run_governance_candidate_validation_outcome_on_demand(...)`

Implementation rules:

- reuse the existing parser/main structure
- do not change `governance_reject` or `governance_status_transition` argument
  semantics
- fail deterministically when the new payload input is missing or invalid JSON

### M5CVT-S4: Extend API service dispatch

Modify:

- `apps/api/main.py`

Implementation:

1. extend `orchestration_run_view(...)` to accept one additional governance mode:
   - `governance_candidate_validation_outcome`
2. route that mode to:
   - `self.worker_app.run_governance_candidate_validation_outcome_on_demand(...)`
3. pass through:
   - `source_run_id`
   - `validation_result`
4. keep stored orchestration ledger/artifact writing behavior unchanged

Implementation rules:

- keep `daily` on its current trading-day/lab path
- keep reject and status-transition routing unchanged
- do not create a generic non-daily catch-all branch

### M5CVT-S5: Extend API router validation

Modify:

- `apps/api/router.py`

Implementation:

1. extend valid `mode` values with:
   - `governance_candidate_validation_outcome`
2. require for the new mode:
   - non-empty `source_run_id`
   - object-valued `validation_result`
3. preserve current validation for:
   - `daily`
   - `governance_reject`
   - `governance_status_transition`
4. pass normalized values into `orchestration_run_view(...)`

Implementation rules:

- keep validation logic centralized in the router
- reuse existing API error style for invalid mode and missing required fields
- do not accept aliases or partial shorthand inputs

### M5CVT-S6: Lock focused CLI tests

Modify:

- `tests/unit/test_m5_governance_cli.py`

Required coverage:

1. CLI subcommand `candidate-validation-outcome` reaches
   `run_governance_candidate_validation_outcome(...)`
2. CLI reads one JSON-file payload and passes the canonical `ValidationResult` shape
3. CLI emits the expected narrow JSON projection containing at minimum:
   - `source_run_id`
   - `validation_id`
   - `candidate_run_id`
   - `outcome`
4. CLI rejects missing required payload input

Testing rules:

- follow the existing handoff/reject/status-transition CLI carrier style
- monkeypatch the runtime owner instead of re-testing persistence semantics

### M5CVT-S7: Lock focused worker/API unit tests

Modify:

- `tests/unit/test_bootstrap_skeleton.py`

Required coverage:

1. worker `--mode governance_candidate_validation_outcome` requires:
   - `--source-run-id`
   - the serialized `validation_result` payload input
2. worker on-demand trigger builds and stores one orchestration snapshot whose task id
   is:
   - `governance.candidate_validation_outcome`
3. API service dispatch uses
   `run_governance_candidate_validation_outcome_on_demand(...)`
4. router accepts `/api/orchestration/run` with:
   - `mode="governance_candidate_validation_outcome"`
   - `source_run_id`
   - `validation_result`
5. router rejects missing `source_run_id`
6. router rejects missing or non-object `validation_result`

Testing rules:

- mirror the current reject/status-transition carrier structure
- keep assertions focused on trigger ownership and stored orchestration payload shape

### M5CVT-S8: Lock focused HTTP smoke

Modify:

- `tests/integration/test_http_smoke.py`

Required coverage:

1. POST `/api/orchestration/run` with:
   - `mode="governance_candidate_validation_outcome"`
   - `source_run_id`
   - `validation_result`
2. GET orchestration detail returns stored run data for the new mode
3. GET orchestration download returns stored artifact data for the new mode
4. stored ledger/artifact preserve:
   - `mode == "governance_candidate_validation_outcome"`
   - `task_id == "governance.candidate_validation_outcome"`

Testing rules:

- reuse the existing HTTP smoke harness
- monkeypatch only the worker-owned candidate-validation trigger
- keep the test symmetric with current governance API smoke patterns

### M5CVT-S9: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/cli.py apps/worker/main.py apps/api/main.py apps/api/router.py tests/unit/test_m5_governance_cli.py tests/unit/test_bootstrap_skeleton.py tests/integration/test_http_smoke.py`
- `python3 -m pytest tests/unit/test_m5_governance_cli.py tests/unit/test_bootstrap_skeleton.py tests/integration/test_http_smoke.py -k "candidate_validation_outcome or governance_status_transition or governance_reject"`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: contract drift across CLI/worker/API**
  - Guardrail: every surface must carry the same normalized payload keys:
    - `source_run_id`
    - `validation_result`
- **Risk: shorthand inference sneaks in through `validation_id` only**
  - Guardrail: require the full final `ValidationResult` payload on every trigger path
- **Risk: widen into runtime/schema redesign**
  - Guardrail: no edits to `runtime.py`, `run_ledger.py`, or `artifact_writer.py`
- **Risk: widen into scheduler adoption**
  - Guardrail: no `daily_master_orchestrator.json` edits

## 5. Done Criteria

- governance CLI exposes `candidate-validation-outcome`
- worker exposes `governance_candidate_validation_outcome`
- API accepts and routes `mode="governance_candidate_validation_outcome"`
- focused CLI, worker/API unit, and HTTP smoke tests pass
- stored orchestration payload preserves truthful mode and task identity
- no runtime/schema/orchestrator-config diff appears in this slice

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays in trigger-surface ownership for `M5`
- `G1-G6` target mapping:
  - this is the minimum `G5` operability closure that makes final
    candidate-validation truth externally triggerable and auditable
- new contract introduced:
  - shared external trigger payload:
    - `source_run_id`
    - `validation_result`
  - API/worker mode:
    - `governance_candidate_validation_outcome`
- boundaries not touched:
  - no candidate-comparison engine
  - no automatic `validation_id` selection
  - no scheduler registration
  - no runbook/UI adoption
  - no `M6`
