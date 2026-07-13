Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance closure baseline` slice for pending validation and decision-record runtime closure
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Closure Baseline Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M5 governance contract nucleus`
- `M5 governance handoff runtime baseline`
- `M4 -> M5 persisted benchmark consumption`
- `M4 state-level front benchmark truth expansion`

Current repository evidence shows:

- `ValidationResult` and `GovernanceDecisionRecord` already exist as formal contracts
- pure builders for both objects already exist
- but the current governance runtime closure still stops at:
  - `diagnostics`
  - `change_requests`
  - `experiment_requests`
  - `promotion_blockers`
- therefore these two formal closure objects are still outside:
  - handoff bundle
  - artifact payload
  - ledger payload
  - CLI surfaced counts

So the narrow problem is not:

- how to redesign governance contracts
- how to build a real baseline-vs-candidate experiment executor
- how to automate promotion approval
- how to change orchestrator chaining

It is:

- how to let governance runtime produce truthful pending `ValidationResult` envelopes
- how to let governance runtime produce truthful blocker-based `GovernanceDecisionRecord` objects
- how to persist and surface both through the existing closure chain

Project-phase note:

- domain: `M5 governance closure baseline`
- change type: `pending closure runtime`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- extend `GovernanceHandoffBundle` with:
  - `validation_results`
  - `decision_records`
- project one pending `ValidationResult` per `ExperimentRequest`
- project one `GovernanceDecisionRecord` per active `PromotionBlocker`
- persist both object lists in governance artifact payloads
- surface both count fields in governance run ledger and CLI output
- add focused tests for handoff, ledger, and CLI

Excluded:

- no real candidate-run comparison engine
- no automated promotion approval path
- no `AttentionItem`
- no orchestrator contract change
- no `M6`

## 3. Existing Evidence

### 3.1 Contracts Already Exist

Current repository evidence in:

- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L161-L248)

shows that:

- `ValidationResult`
- `GovernanceDecisionRecord`

already exist as formal objects.

### 3.2 Pure Builders Already Exist

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L165-L235)

shows that pure builders already exist for both objects.

So the current gap is not contract definition.

### 3.3 Runtime Closure Still Stops Before Them

Current repository evidence in:

- [handoff.py](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py#L34-L146)
- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L17-L130)
- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L53-L72)

shows that runtime closure still only handles:

- diagnostics
- change_requests
- experiment_requests
- promotion_blockers

### 3.4 Real Comparison Logic Does Not Exist Yet

Current repository evidence in:

- [2026-07-12-lowfreq-m5-governance-contract-nucleus-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-contract-nucleus-design.md#L250-L270)

explicitly freezes:

- `ValidationResult` is part of the standard governance chain
- but this stage does not yet automate comparison logic

This means the next truthful runtime closure must be pending, not fake-final.

## 4. Approach Options

### Option A: Keep Validation And Decision Objects Outside Runtime

Pros:

- zero code change

Cons:

- formal governance chain remains incomplete
- runtime artifact and ledger continue to omit approved contracts

### Option B: Add Pending Closure Objects To Runtime (Recommended)

Pros:

- completes the currently approved governance chain
- stays truthful by marking validation as pending
- avoids inventing a fake candidate comparison engine
- keeps file boundary narrow

Cons:

- requires one controlled relaxation in `build_validation_result(...)`
- requires bundle/ledger/CLI count expansion

### Option C: Build Real Candidate Comparison Runtime First

Pros:

- more complete

Cons:

- too wide for the current missing piece
- requires candidate run production, compare logic, and promotion policy in one slice

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

This slice closes the runtime chain around already-existing governance objects.

Primary owners:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`

Supporting contract/builder owner only where strictly needed:

- `neotrade3/governance/assembler.py`

Files intentionally not modified in this slice:

- `neotrade3/governance/runtime.py`
- `neotrade3/orchestration/*`
- `neotrade3/benchmark/*`
- `M6`

### 5.2 Pending ValidationResult Freeze

This slice defines one truthful pending closure envelope:

- one `ValidationResult` is created for each `ExperimentRequest`
- it anchors the current source benchmark run as `baseline_run_id`
- it explicitly records that no candidate run has been provided yet

Concrete fields:

- `validation_id = "{experiment_id}:validation"`
- `experiment_id = experiment_request.experiment_id`
- `baseline_run_id = source_run_id`
- `candidate_run_id = ""`
- `outcome = "awaiting_candidate_validation"`
- `cleared_guardrail_codes = []`
- `remaining_guardrail_codes = experiment_request.guardrail_codes`
- `introduced_risk_count = 0`
- `evidence_refs = experiment_request.evidence_refs`

Design rule:

- `candidate_run_id=""` is allowed only for the pending outcome above
- this slice must not fabricate a fake candidate run id
- this slice must not claim cleared guardrails or comparison success

### 5.3 GovernanceDecisionRecord Freeze

This slice defines one formal block decision per active `PromotionBlocker`:

- `decision_id = "{blocker_id}:decision"`
- `subject_type = "promotion_blocker"`
- `subject_id = blocker.blocker_id`
- `decision = "block"`
- `decision_scope = "promotion"`
- `rationale = blocker.reason`
- `approver = "system_governance"`
- `status = "recorded"`
- `evidence_refs = blocker.evidence_refs`

Reason:

- the blocker already exists as the formal gate object
- the runtime closure still lacks the corresponding decision trail object
- a system-recorded block decision is truthful at this stage because promotion is not being approved here

### 5.4 Bundle And Persistence Freeze

`GovernanceHandoffBundle` should gain:

- `validation_results`
- `decision_records`

Artifact payload should include both lists.

Ledger payload should gain:

- `validation_result_count`
- `decision_record_count`

CLI output should surface the same two count fields.

### 5.5 Builder Constraint Freeze

`build_validation_result(...)` currently requires non-empty `candidate_run_id`.

This slice should relax that only for:

- `outcome == "awaiting_candidate_validation"`

Behavior:

- if outcome is pending, empty `candidate_run_id` is allowed
- for all other outcomes, `candidate_run_id` remains required

Design rule:

- do not weaken the builder more broadly than needed

## 6. Testing Strategy

Focused tests should lock:

1. handoff adapter now projects:
   - one `validation_result`
   - one `decision_record`
   for the failing `B4` governance chain
2. clean handoff still projects zero closure objects
3. governance ledger persists:
   - `validation_result_count`
   - `decision_record_count`
4. governance CLI surfaces the new counts consistently with ledger and artifact
5. builder logic allows empty `candidate_run_id` only for the pending outcome

Testing rule:

- do not widen into real candidate comparison
- do not widen into promotion approval runtime

## 7. Risks And Guardrails

### 7.1 Fake Comparison Risk

The main risk is fabricating a candidate run id or pretending validation already happened.

Guardrail:

- pending validation uses `candidate_run_id=""`
- outcome is explicitly `awaiting_candidate_validation`

### 7.2 Over-Broad Builder Relaxation Risk

Another risk is weakening `build_validation_result(...)` so much that malformed final results slip through.

Guardrail:

- empty `candidate_run_id` is permitted only for the pending outcome

### 7.3 Decision Scope Drift Risk

Another risk is writing a decision record that implies approval authority this slice does not own.

Guardrail:

- use only `decision="block"`
- use only `decision_scope="promotion"`
- use `approver="system_governance"` and `status="recorded"`

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- failing governance handoff bundles include pending `validation_results`
- failing governance handoff bundles include blocker-based `decision_records`
- governance artifact payload persists both lists
- governance ledger and CLI surface both counts
- no fake candidate run id is introduced
- focused tests pass

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- real baseline-vs-candidate comparison runtime
- promotion approval / reject execution
- attention-item runtime
- governance orchestrator expansion
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely within `M5` runtime closure and persistence; it does not change benchmark or delivery ownership
- `G1-G6` target mapping:
  - this is the minimum `G5` closure step that turns already-approved governance contracts into persisted runtime truth
- new contract introduced:
  - pending `ValidationResult` outcome `awaiting_candidate_validation`
  - blocker-based `GovernanceDecisionRecord` with `block/promotion/recorded`
- boundaries not touched:
  - no candidate comparison engine
  - no promotion approval automation
  - no `M6`
