Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 reject decision nucleus` slice after typed handoff readback baseline
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Decision Nucleus Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- `ValidationResult` already supports `outcome="rejected"`
- `GovernanceDecisionRecord` already supports `decision="reject"`
- `M5` runtime still only has one decision-specific helper:
  - `build_block_decision_record_from_promotion_blocker(...)`
- the just-finished typed readback baseline now lets later runtime slices consume persisted governance truth through typed owners

So the next narrow problem is:

- how to freeze one canonical builder that turns a final rejected validation result into a formal reject decision record

This slice is not yet:

- reject runtime execution
- artifact overwrite/update
- promotion approval
- blocker/attention status transition

Project-phase note:

- domain: `M5 governance decision builder nucleus`
- change type: `object-owner nucleus`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add one builder:
  - `build_reject_decision_record_from_validation_result(...)`
- export that builder from `neotrade3.governance`
- add focused contract/builder tests

Excluded:

- no runtime entrypoint
- no handoff materialization
- no artifact rewrite
- no blocker or attention state transitions
- no promotion approval
- no `M6`

## 3. Existing Evidence

Current repository evidence in:

- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L203-L315)
- [test_m5_governance_contract_nucleus.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_contract_nucleus.py#L168-L284)

shows that:

- a rejected validation result is already a valid formal object
- a reject decision record is already a valid formal object
- but there is no shared helper that defines the canonical mapping between the two

That means future reject runtime would otherwise choose its own private:

- `decision_id`
- `subject_type`
- `subject_id`
- `rationale`
- `approver`
- `status`
- `evidence_refs`

This is the true missing nucleus.

## 4. Approach Options

### Option A: Build Reject Decisions Inline In Runtime

Pros:

- fewer files changed now

Cons:

- pushes canonical mapping into a later consumer
- repeats the same mistake the block helper already avoids

### Option B: Add One Canonical Reject Builder First (Recommended)

Pros:

- keeps runtime thin in the next slice
- freezes the mapping at the ownership layer
- matches the existing `block` builder pattern

Cons:

- does not yet make reject runtime executable

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

Production files:

- `neotrade3/governance/assembler.py`
- `neotrade3/governance/__init__.py`

Focused test file:

- `tests/unit/test_m5_governance_contract_nucleus.py`

No other files should change.

### 5.2 Canonical Mapping Freeze

Input:

- one final `ValidationResult`

Required input rule:

- `validation_result.outcome` must equal `"rejected"`

Output:

- one `GovernanceDecisionRecord`

Canonical mapping:

- `decision_id` = `"{validation_id}:decision"`
- `subject_type` = `"validation_result"`
- `subject_id` = `validation_id`
- `decision` = `"reject"`
- `decision_scope` = `"promotion"`
- `rationale` = `"validation outcome rejected"`
- `approver` = `"system_governance"`
- `status` = `"recorded"`
- `evidence_refs` = `validation_result.evidence_refs`

Guardrail:

- if the input validation result is not rejected, the builder must raise `ValueError`

### 5.3 Why Subject Anchors To Validation Result

This slice should anchor the reject decision to `validation_result`, not to:

- `experiment_request`
- `promotion_blocker`
- `change_request`

Reason:

- reject is a final governance decision derived from validation outcome
- `ValidationResult` is the narrowest formal proof object for that outcome
- this keeps reject execution tied to the final comparison result rather than an earlier planning object

## 6. Testing Strategy

Focused tests should lock:

1. rejected validation result builds one reject decision record
2. the mapping fields above stay stable
3. non-rejected outcomes are rejected by the builder

Do not test:

- runtime materialization
- artifact updates
- approval flows

## 7. Acceptance Criteria

- `build_reject_decision_record_from_validation_result(...)` exists
- the builder is exported from `neotrade3.governance`
- focused contract/builder tests pass
- no runtime/materialization file changes are made

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` builder ownership
- `G1-G6` target mapping:
  - this is the minimum `G2` reject-decision owner freeze before runtime materialization
- new contract introduced:
  - canonical `ValidationResult -> reject GovernanceDecisionRecord` builder
- boundaries not touched:
  - no runtime execution
  - no artifact mutation
  - no promotion approval
  - no `M6`
