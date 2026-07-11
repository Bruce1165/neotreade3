Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow API execution block reason projection cleanup
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq API Execution Block Reason Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-api-execution-block-reason-design.md`

## 1. Goal

This plan covers only the next narrow API projection slice after the `buy signal audit contract` extraction.

This slice only handles:

- API reuse of the canonical shared `execution_block_reason` normalization for the proven common alias subset
- API-local supplements for proven API-only aliases
- API-focused tests for normalization and blocked execution contract output

The goal is to:

- remove the real duplication in `apps/api/main.py`
- preserve current API projection behavior exactly
- keep API-only semantics local

This slice does not:

- rewrite the shared owner
- rewrite `_lowfreq_execution_contract_from_intent(...)`
- rewrite action field or funnel-stage mapping
- rewrite execution lifecycle behavior

## 2. Starting Point

Current repository evidence shows:

- the canonical normalization already lives in `neotrade3/decision_engine/buy_signal_audit_contract.py`
- the API still duplicates part of that contract in `_lowfreq_normalize_execution_block_reason(...)`
- API also owns local-only aliases such as `signal_expired`, `already_holding`, `position_missing`, `no_shares`, and `abandoned`

So the correct next slice is:

- reuse the shared owner only for the proven common subset
- keep API-only aliases in `apps/api/main.py`

## 3. Implementation Strategy

Production boundary:

- `apps/api/main.py`

Test boundary:

- `tests/unit/test_lowfreq_api_execution_block_reason.py`

Shared dependency boundary:

- reuse `normalize_execution_block_reason(...)` from `neotrade3/decision_engine/buy_signal_audit_contract.py`
- do not change the shared owner in this slice

## 4. Execution Steps

### AEBR-S1: Freeze the alias boundary

Freeze the shared alias subset to:

- `no_slots`
- `reserved_due_to_full_book`
- `no_cash`
- `reservation_expired`
- `pending_conflict_older_intent_wins`

Freeze the API-local supplement to:

- `signal_expired -> entry_window_missed`
- `no_open_price -> execution_rule_blocked`
- `no_price -> execution_rule_blocked`
- `invalid_code -> execution_rule_blocked`
- `already_holding -> execution_rule_blocked`
- `position_missing -> execution_rule_blocked`
- `no_shares -> execution_rule_blocked`
- `abandoned -> execution_rule_blocked`

Completion check:

- no extra raw reasons are newly delegated to the shared owner

### AEBR-S2: Turn the API helper into a thin projection shim

In `apps/api/main.py`:

- import `normalize_execution_block_reason(...)`
- keep `_lowfreq_normalize_execution_block_reason(...)`
- delegate only the frozen shared alias subset
- keep the API-local supplement inline
- preserve passthrough behavior for unknown reasons

Do not change:

- `_lowfreq_execution_contract_from_intent(...)` field ownership
- intent lifecycle branches
- API response structure

Completion check:

- the API helper no longer restates the shared subset inline

### AEBR-S3: Add API-focused contract tests

Create:

- `tests/unit/test_lowfreq_api_execution_block_reason.py`

Minimum cases:

- shared aliases normalize to the same canonical buckets
- API-local aliases normalize to the same buckets as before
- unknown reason passes through unchanged
- `_lowfreq_execution_contract_from_intent(...)` still emits the blocked contract for an API-local failure

Completion check:

- the projection contract has direct focused coverage

### AEBR-S4: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_api_execution_block_reason.py`
- `python3 -m py_compile apps/api/main.py tests/unit/test_lowfreq_api_execution_block_reason.py`

Completion check:

- API-focused tests pass
- syntax validation passes

### AEBR-S5: Narrow commit

For the implementation commit, stage only:

- `apps/api/main.py`
- `tests/unit/test_lowfreq_api_execution_block_reason.py`

Must exclude:

- shared owner files
- report files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidental behavior broadening through over-delegation to the shared owner

Guard:

- delegate only the frozen common subset

Risk 2:

- silently changing blocked intent payloads consumed by the API

Guard:

- keep `_lowfreq_execution_contract_from_intent(...)` intact
- verify the final emitted contract in focused tests

## 6. Success Criteria

This slice is complete when:

- API reuses the shared normalization for the proven common subset
- API-only aliases remain local
- API emitted `execution_block_reason` strings remain unchanged
- API-focused tests pass
- syntax verification passes
