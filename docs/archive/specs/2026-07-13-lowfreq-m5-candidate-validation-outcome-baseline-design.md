Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 candidate validation outcome baseline` slice after governance status transition API/docs closure
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Candidate Validation Outcome Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows that the next truthful `M5 governance` gap is not
scheduled orchestrator adoption for `reject_execution` or `status_transition`.

The hard blocker is earlier:

- current `governance_handoff` only materializes pending validation truth
- current `reject_execution` only accepts a final rejected validation result
- current `status_transition` additionally requires persisted reject proof

So the narrow next problem is:

- how to formalize one post-handoff candidate-validation outcome owner
- how to persist final validation outcomes without mutating the handoff baseline
- how to give later governance steps a real upstream truth source instead of
  test-only artifact patching

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `post-handoff candidate-validation outcome baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- define one independent persistence/readback owner for final candidate-validation outcomes
- keep `governance_handoff` as the immutable pending baseline
- teach later governance runtime to consume the new final-validation truth instead of
  relying on handoff mutation
- establish the minimum contract needed for future scheduled adoption work

Excluded:

- no scheduled orchestrator registration
- no `daily_master_orchestrator.json` task additions
- no auto `validation_id` selection logic yet
- no benchmark-side candidate comparison engine
- no approval / promotion path
- no `M6`

## 3. Existing Evidence

### 3.1 Handoff Only Produces Pending Validation Results

Current repository evidence in:

- [handoff.py](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py#L198-L292)
- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L283-L298)
- [test_m5_governance_handoff_adapter.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_handoff_adapter.py#L186-L283)
- [2026-07-13-lowfreq-m5-governance-closure-baseline-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-closure-baseline-design.md#L196-L220)

shows that:

- `build_governance_handoff_from_assessment(...)` creates one validation result per
  experiment request
- the generated payload is intentionally pending:
  - `candidate_run_id = ""`
  - `outcome = "awaiting_candidate_validation"`
- batch handoff may contain multiple validation results in deterministic order

So the persisted handoff bundle is not a final validation-outcome source.

### 3.2 Reject Execution Requires Final Rejected Validation Truth

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L318-L334)
- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L190-L228)
- [test_m5_governance_reject_execution.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_reject_execution.py#L154-L187)

shows that:

- `build_reject_decision_record_from_validation_result(...)` raises unless
  `validation_result.outcome == "rejected"`
- `run_governance_reject_execution(...)` looks up the selected validation result and
  then builds the reject decision from it
- repository tests prove non-rejected outcomes are rejected by design

So `reject_execution` cannot truthfully chain from the current handoff baseline.

### 3.3 Status Transition Has An Additional Upstream Proof Requirement

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L231-L283)
- [test_m5_governance_status_transition.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_status_transition.py#L163-L178)

shows that:

- `run_governance_status_transition(...)` still requires:
  - `source_run_id`
  - `validation_id`
  - persisted reject proof for the same `validation_id`

So status transition is at least one step downstream from final validation outcome.

### 3.4 Current Runtime Closure Depends On Test-Only Handoff Mutation

Current repository evidence in:

- [test_m5_governance_reject_execution.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_reject_execution.py#L31-L64)
- [test_m5_governance_status_transition.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_status_transition.py#L40-L89)

shows that current reject/status-transition tests become runnable only by manually:

- reading the persisted handoff artifact
- appending a final rejected validation payload
- writing the handoff artifact back to disk

This is test scaffolding, not a formal runtime owner.

### 3.5 Scheduled Adoption Is Blocked Even Before `validation_id` Selection

Current repository evidence in:

- [daily_master_orchestrator.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/daily_master_orchestrator.py#L132-L184)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L397-L425)
- [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json#L116-L133)

shows that:

- orchestrator dynamic args can only read top-level `TaskResult.details[detail_key]`
- governance handoff task details expose counts and `source_run_id`, but no selected
  `validation_id`
- more importantly, the handoff owner still exposes only pending validation semantics

So the next missing owner is not a config registration and not just a scalar selector.
The missing owner is final candidate-validation truth.

## 4. Approach Options

### Option A: Mutate The Existing Handoff Bundle In Place

- replace or append the pending `ValidationResult` inside
  `var/artifacts/governance_handoffs/<source_run_id>/governance_handoff_bundle.json`

Pros:

- smallest raw code change

Cons:

- breaks the current meaning of handoff as the immutable post-`M4` pending baseline
- mixes lifecycle stages into one namespace
- makes later audits unable to distinguish baseline truth from post-handoff decisions
- conflicts with the already-established isolation style used by reject execution and
  status transition

### Option B: Add An Independent Candidate-Validation Outcome Namespace (Recommended)

- persist final validation outcomes under a new independent namespace keyed by
  `validation_id`
- keep handoff unchanged as the pending baseline
- add readback helpers so downstream governance runtime can resolve:
  - baseline blocker / attention state from handoff
  - final validation outcome from the new namespace
- postpone scheduler work until this truth source exists

Pros:

- preserves baseline immutability
- aligns with the existing reject/status-transition isolation pattern
- gives later runtime and scheduler work one explicit upstream truth source
- keeps lifecycle stages auditable

Cons:

- requires one more persistence/readback owner before scheduler adoption
- reject runtime must stop assuming final validation truth lives inside handoff

### Option C: Skip Outcome Persistence And Add Selector Logic First

- keep current handoff as-is
- add config or orchestrator logic that picks one validation id

Pros:

- appears to move scheduled adoption forward

Cons:

- still selects only pending validations
- does not satisfy reject runtime preconditions
- produces a scheduler path that cannot execute truthfully

Decision:

- choose Option B

## 5. Design

### 5.1 New Owner: Final Candidate-Validation Outcome

Add one formal governance owner for final candidate-validation outcomes.

Minimum responsibilities:

- accept one final `ValidationResult` with non-pending outcome
- persist it independently from handoff
- expose typed readback keyed by `validation_id`
- retain `source_run_id` association for downstream governance steps

This slice does not define how candidate comparison is computed.
It only formalizes how an already-determined final outcome is stored and consumed.

### 5.2 Persistence Strategy

Use a new namespace parallel to existing later-stage governance namespaces.

Recommended artifact and ledger roots:

- `var/artifacts/governance_candidate_validations/<validation_id>/governance_candidate_validation.json`
- `var/ledgers/governance_candidate_validations/<validation_id>/governance_candidate_validation_run.json`

Minimum payload fields should include:

- `validation_id`
- `source_run_id`
- one final `validation_result`
- `status`
- `written_at`
- `artifact_path`
- `ledger_path`

Design rule:

- do not rewrite `governance_handoff`
- do not reuse `governance_rejections` for this earlier lifecycle step

### 5.3 Runtime Consumption Shift

After this owner exists, downstream runtime should resolve inputs as follows:

- `reject_execution`
  - baseline structural context from handoff
  - final validation outcome from candidate-validation outcome storage
- `status_transition`
  - baseline structural context from handoff
  - final validation outcome from candidate-validation outcome storage
  - reject proof from `governance_rejections`

This keeps each stage consuming only the truth it actually owns.

### 5.4 Scheduler Implication

This slice intentionally stops before scheduler/config work.

But it creates the first truthful foundation for later adoption because a future
scheduler-facing task can project top-level details such as:

- `source_run_id`
- `validation_id`
- `validation_outcome`

without pretending those facts came from the handoff baseline.

## 6. Acceptance Criteria

- repository has one formal owner for final candidate-validation outcome persistence
- handoff remains the pending baseline and is not rewritten
- later governance runtime no longer depends on test-only handoff patching to obtain a
  final rejected validation result
- the next scheduler discussion can start from a real upstream truth source rather than
  a fabricated selector

## 7. Risks And Guardrails

### 7.1 Baseline Drift Risk

Risk:

- a quick implementation may choose to patch handoff in place

Guardrail:

- freeze handoff as the pending post-`M4` baseline
- require a dedicated namespace for final validation outcomes

### 7.2 Lifecycle Collapse Risk

Risk:

- reject execution and candidate validation get merged into one owner

Guardrail:

- keep candidate validation outcome as an upstream stage
- keep reject execution as a separate downstream governance action

### 7.3 Premature Scheduler Pressure

Risk:

- implementation widens into orchestrator config changes immediately

Guardrail:

- no scheduled task registration in this slice
- no `validation_id` auto-selection in this slice

## 8. Verification

Design-phase verification:

- re-read current handoff, reject runtime, and status-transition runtime owners
- confirm repository evidence for:
  - pending handoff validation semantics
  - reject-only final outcome requirement
  - status-transition reject-proof requirement
- confirm current tests still rely on manual handoff mutation for final rejected outcomes

## 9. Dual-axis Audit

- M5 归属：本切片补的是治理闭环中 handoff 与 reject/status_transition 之间缺失的
  `candidate validation outcome` 正式 owner
- G5 归属：让后续治理动作消费真实上游事实，而不是测试脚手架或伪造调度选择
- 新增 contract：独立的 final candidate-validation outcome persistence/readback
  contract，后续可成为 scheduler-facing projection 的真值输入
- 未触碰边界：`daily` orchestrator config、auto `validation_id` selection、
  benchmark candidate-comparison engine、promotion approval、`M6`
