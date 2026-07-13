Status: active
Owner: lowfreq / governance / worker / api
Scope: Narrow `M5 candidate validation outcome trigger adoption baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Candidate Validation Outcome Trigger Adoption Baseline Design

Date: 2026-07-13

## 1. Goal

This slice continues the current `M5 governance` mainline after:

- candidate validation outcome persistence/runtime baseline
- reject execution runtime consumption switch
- status transition runtime consumption switch

Current repository evidence now shows:

- `run_governance_candidate_validation_outcome(...)` already exists as the runtime owner
- downstream `reject_execution` and `status_transition` already consume persisted
  candidate-validation truth
- `candidate validation outcome` is still not triggerable from the external ownership
  surfaces:
  - governance CLI
  - worker on-demand mode
  - `/api/orchestration/run`
- `daily` orchestrator registration is not the current blocker because:
  - `args_template` already supports top-level detail propagation
  - governance daily registration already exists for handoff
  - auto `validation_id` selection is still intentionally out of scope

So the next narrow problem is not:

- another orchestrator config change
- scheduler-facing projection work
- runtime semantics redesign

It is:

- how to expose one truthful external trigger for persisted final
  candidate-validation outcomes
- how to do so with one shared input contract instead of three drifting parameter
  shapes
- how to close CLI, worker, and API parity without widening into scheduling

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `post-outcome trigger adoption baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- define one shared trigger input contract for candidate validation outcome
- add one governance CLI trigger that feeds the shared runtime owner
- add one worker-owned on-demand trigger for candidate validation outcome
- add one API-visible orchestration mode that routes to the new worker trigger
- add focused unit and HTTP-level tests for the new trigger path

Excluded:

- no change to candidate validation persistence or ledger schema
- no change to reject/status-transition runtime semantics
- no scheduled orchestrator registration
- no automatic `validation_id` selection
- no benchmark-side candidate comparison logic
- no runbook or UI adoption in this slice
- no `M6`

## 3. Existing Evidence

### 3.1 Runtime Owner Already Exists

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L232-L277)
- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L668-L722)
- [artifact_writer.py](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L148-L195)
- [test_m5_governance_candidate_validation_outcome.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_candidate_validation_outcome.py#L18-L226)

shows that:

- `run_governance_candidate_validation_outcome(...)` already materializes persisted
  final outcomes
- the owner writes a dedicated artifact and ledger namespace
- the runtime already enforces the key truth constraints:
  - handoff baseline must exist
  - `validation_id` must belong to the persisted handoff
  - outcome must not remain pending
  - `candidate_run_id` must be non-empty

So this slice must not redesign persistence or runtime semantics.

### 3.2 Downstream Governance Already Depends On The Persisted Outcome

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L89-L102)
- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L280-L389)

shows that:

- `reject_execution` resolves final validation truth from candidate-validation
  storage
- `status_transition` also resolves final validation truth from the same storage

So candidate validation outcome is already a real upstream owner, not a future-only
concept.

### 3.3 CLI Still Has No Candidate Validation Outcome Surface

Current repository evidence in:

- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L10-L14)
- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L21-L95)
- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L98-L169)
- [test_m5_governance_cli.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_cli.py#L93-L163)

shows that:

- governance CLI only exposes:
  - `handoff`
  - `reject`
  - `status-transition`
- there is no command that reaches
  `run_governance_candidate_validation_outcome(...)`

So the first missing external trigger surface is CLI parity.

### 3.4 Worker Still Has No Candidate Validation Outcome On-Demand Trigger

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L21-L25)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L311-L435)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L638-L782)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L962-L991)

shows that:

- worker only imports governance runtime owners for:
  - handoff
  - reject
  - status transition
- worker CLI modes only include:
  - `daily`
  - `governance_reject`
  - `governance_status_transition`
- there is no worker-owned on-demand entry for candidate validation outcome

So the second missing surface is worker parity.

### 3.5 API Still Has No Candidate Validation Outcome Mode

Current repository evidence in:

- [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2555-L2649)
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1325-L1377)
- [test_http_smoke.py](file:///Users/mac/NeoTrade3/tests/integration/test_http_smoke.py#L223-L431)

shows that:

- `/api/orchestration/run` only accepts:
  - `daily`
  - `governance_reject`
  - `governance_status_transition`
- API dispatch only routes governance special modes to reject or status transition
- HTTP smoke only covers those existing governance modes

So the third missing surface is API parity.

### 3.6 Orchestrator Is Not The Current Missing Owner

Current repository evidence in:

- [daily_master_orchestrator.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/daily_master_orchestrator.py#L126-L184)
- [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json#L99-L133)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L327-L425)

shows that:

- governance daily registration already exists for handoff
- `args_template` already supports top-level detail propagation from dependency
  results
- governance worker result `details` already carry narrow projected scalars

So the next missing owner is not another scheduler capability slice.
The current blocker is the absent external trigger surface for the already-existing
runtime owner.

## 4. Approach Options

### Option A: Add One Shared Trigger Contract And Thin Surface Wiring (Recommended)

- define one external input contract shaped as:
  - `source_run_id`
  - `validation_result`
- keep `validation_result` aligned with the existing `ValidationResult` payload shape
- add thin trigger surfaces in:
  - governance CLI
  - worker on-demand mode
  - API orchestration mode

Pros:

- keeps all external surfaces aligned to one truthful payload shape
- avoids re-specifying every `ValidationResult` field as separate flags or query params
- preserves runtime ownership in `run_governance_candidate_validation_outcome(...)`
- closes the obvious parity gap without widening into scheduler work

Cons:

- requires touching four ownership surfaces in one slice:
  - CLI
  - worker
  - API service
  - API router

### Option B: Add Only One Surface First

- expose candidate validation outcome from just one of:
  - CLI
  - worker
  - API

Pros:

- smaller raw diff

Cons:

- guarantees contract drift because the remaining surfaces will later re-invent
  payload shape
- does not close the already-visible parity gap
- creates partial operability with no shared ownership rule

### Option C: Skip Trigger Adoption And Move Directly To Scheduler Projection

- defer external trigger work
- continue with scheduled registration or selector projection first

Pros:

- appears to move automation forward

Cons:

- widens beyond the current blocker
- still leaves no truthful external way to materialize final candidate-validation
  truth
- mixes manual-operability closure with later automatic-selection concerns

Decision:

- choose Option A

## 5. Boundary Decisions

Frozen decisions for this slice:

- external mode name:
  - `governance_candidate_validation_outcome`
- shared trigger payload shape:
  - `source_run_id`
  - `validation_result`
- `validation_result` must remain an explicit structured payload, not inferred from
  `validation_id`
- runtime owner remains:
  - `run_governance_candidate_validation_outcome(...)`
- worker owner remains a thin on-demand trigger
- API owner remains a thin router/service dispatch layer

This slice must not:

- add inferred lookup from `validation_id` to a not-yet-defined candidate-comparison
  source
- add a second persistence path for candidate validation outcome
- mutate handoff, reject, or status-transition artifact meanings
- add daily config entries or scheduled tasks

## 6. Design

### 6.1 Shared Input Contract

The external trigger contract should be normalized to:

- `source_run_id: str`
- `validation_result: dict`

Design rule:

- `validation_result` must match the existing `ValidationResult` payload contract
  already consumed by the runtime owner
- thin surface owners may parse or deserialize this payload, but they must not invent
  alternate field names or partial shorthand inputs

Why this is correct:

- the runtime already expects a full `ValidationResult` object
- the final outcome semantics live in the payload itself, not in `validation_id`
  alone
- a structured payload keeps future extensions localized to the canonical contract

### 6.2 CLI Surface

Primary owner:

- `neotrade3/governance/cli.py`

Recommended extension:

- add one command:
  - `candidate-validation-outcome`
- require:
  - `--source-run-id`
  - one serialized `validation_result` input

Recommended CLI carrier:

- accept one JSON file path for `validation_result`

Reason:

- avoids exploding the CLI into many field-level flags
- keeps the CLI aligned with the canonical payload contract
- minimizes ambiguity around nested `ValidationResult` structure

This slice should not add convenience aliases or partial-field reconstruction.

### 6.3 Worker Surface

Primary owner:

- `apps/worker/main.py`

Recommended extension:

- add one thin worker method:
  - `run_governance_candidate_validation_outcome_on_demand(...)`
- add one worker CLI mode:
  - `governance_candidate_validation_outcome`

Behavior:

- deserialize the provided `validation_result` payload into `ValidationResult`
- call `run_governance_candidate_validation_outcome(...)`
- return a narrow `TaskResult.details` projection sufficient for stored run audit

Recommended minimum `details` fields:

- `source_run_id`
- `validation_id`
- `candidate_run_id`
- `outcome`

This mirrors the existing governance trigger style without changing runtime semantics.

### 6.4 API Surface

Primary owners:

- `apps/api/router.py`
- `apps/api/main.py`

Recommended extension:

- allow `/api/orchestration/run` mode:
  - `governance_candidate_validation_outcome`
- require request body fields:
  - `source_run_id`
  - `validation_result`
- dispatch to:
  - `BootstrapWorkerApp.run_governance_candidate_validation_outcome_on_demand(...)`

Design rule:

- API request validation stays centralized in the router
- API service remains a thin dispatcher and stored-run persistence owner
- API response envelope stays unchanged; only the invoked mode and task id differ

### 6.5 Testing Strategy Ownership

Focused production owners:

- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `apps/api/router.py`
- `apps/api/main.py`

Focused test owners:

- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_bootstrap_skeleton.py`
- `tests/integration/test_http_smoke.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `config/orchestrator/daily_master_orchestrator.json`

## 7. Acceptance Criteria

- one shared external input contract exists for candidate validation outcome trigger
- governance CLI can trigger candidate validation outcome materialization
- worker exposes one on-demand candidate validation outcome trigger
- `/api/orchestration/run` accepts and routes
  `mode="governance_candidate_validation_outcome"`
- stored orchestration run payload preserves the truthful mode and task identity
- focused tests cover CLI, worker/API unit behavior, and one HTTP smoke round-trip
- no scheduler config is changed

## 8. Risks And Guardrails

### 8.1 Contract Drift Risk

Risk:

- each surface may introduce its own field names or partial payload shape

Guardrail:

- freeze the shared trigger contract as:
  - `source_run_id`
  - `validation_result`
- require surface owners to translate into the canonical `ValidationResult` contract
  only once

### 8.2 Shorthand Inference Risk

Risk:

- implementation may try to trigger the runtime from just `validation_id`

Guardrail:

- disallow lookup-based inference in this slice
- require the final `validation_result` payload to be passed explicitly

### 8.3 Scope Creep Risk

Risk:

- implementation may widen into orchestrator registration, runbook changes, or
  selector semantics

Guardrail:

- no `daily_master_orchestrator.json` edits
- no docs/runbook edits
- no auto `validation_id` selection logic

## 9. Verification

Design-phase verification:

- re-read runtime, CLI, worker, API, and orchestrator owners
- confirm:
  - runtime owner already exists
  - CLI/worker/API trigger surfaces are absent
  - orchestrator capability is not the current blocker
- confirm the proposed trigger contract does not require runtime semantic change

## 10. Dual-axis Audit

- M5 归属：本切片补的是 `candidate validation outcome` 从内部 owner 到外部
  trigger surface 的正式接线，不涉及新的治理语义
- G5 归属：本切片让 final candidate-validation truth 具备可操作、可审计、
  可回放的触发面，而不是只存在内部 runtime 与测试载体中
- 新增 contract：一个共享 external trigger payload contract
  (`source_run_id + validation_result`) 以及对齐该 contract 的 CLI/worker/API
  薄接线
- 未触碰边界：scheduler 注册、`validation_id` 自动选择、candidate-comparison
  owner、runbook/UI adoption、`M6`
