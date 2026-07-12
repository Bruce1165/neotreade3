Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report thin wrapper cleanup
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Thin Wrapper Cleanup Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution report row projection extraction.

This slice freezes only the three one-line wrapper helpers that still live in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_sell_reason_bucket(...)`
  - `_not_picked_primary_reason(...)`
  - `_candidate_only_primary_reason(...)`

The goal is to:

- remove script-local forwarding wrappers that add no business logic
- make the report script consume the existing reasoning owners directly
- keep all observable reason texts and reason buckets unchanged
- keep the script moving toward a thin consumer

This design is not:

- a rewrite of `resolve_sell_reason_bucket(...)`
- a rewrite of `resolve_not_picked_primary_reason(...)`
- a rewrite of `resolve_candidate_only_primary_reason(...)`
- a rewrite of `_extract_execution_reason(...)`
- a rewrite of `_analyze_topk(...)` orchestration

Project-phase note:

- domain: `top200 attribution report thin wrapper cleanup`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- deleting the three script-local forwarding wrappers
- switching the script call sites to direct owner consumption
- adjusting focused tests so they assert the canonical owner surface instead of the removed wrappers

Excluded:

- any change to reasoning priority or wording
- any change to report row payload
- any change to execution fallback behavior
- any extraction of new owner modules

## 3. Existing Context

Current repository evidence shows:

- the report script imports the canonical owners already:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L26-L32)
- the same script still keeps three local wrappers that only forward arguments unchanged:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L693-L702)
- the three call sites use only those wrappers and add no extra shaping:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L805-L824)
- canonical owner-focused tests already exist for each reasoning contract:
  - [test_lowfreq_attribution_sell_reason_bucket.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_sell_reason_bucket.py)
  - [test_lowfreq_attribution_not_picked_primary_reason.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py)
  - [test_lowfreq_attribution_candidate_only_primary_reason.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py)

The problem is:

- the script still exposes obsolete indirection after the owners have already been extracted
- one nearby focused test still validates the wrapper surface instead of the canonical reasoning owner
- this keeps thin-consumer cleanup unfinished even though the real contract has already moved

## 4. Approach Options

### Option A: Remove only the three forwarding wrappers and switch consumers/tests to the existing owners (Recommended)

- keep all existing owners unchanged
- update the script to call the reasoning owners directly
- update the wrapper-focused test assertion to the owner surface

Pros:

- smallest possible cleanup with direct evidence
- no contract movement and almost no regression surface
- removes dead indirection from the consumer

Cons:

- only a small amount of code is removed

### Option B: Keep the wrappers for script readability

Pros:

- no test churn

Cons:

- preserves duplicate names and extra indirection
- weakens the meaning of the extracted owner surface

### Option C: Collapse more reasoning and execution helpers in the same slice

Pros:

- removes more lines at once

Cons:

- broadens beyond thin-wrapper cleanup
- mixes consumer cleanup with live business logic

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

No new owner is needed.

The canonical reasoning surface remains:

- `resolve_sell_reason_bucket(...)`
- `resolve_not_picked_primary_reason(...)`
- `resolve_candidate_only_primary_reason(...)`

All three already live in:

- [attribution_reasoning.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py)

The report script should consume those functions directly.

### 5.2 Script Boundary

The script should keep:

- reasoning owner imports
- orchestration order inside `_analyze_topk(...)`
- existing local helper ownership for `_audit_daily_reason(...)`, `_extract_execution_reason(...)`, and unrelated orchestration helpers

The script should stop owning:

- `_sell_reason_bucket(...)`
- `_not_picked_primary_reason(...)`
- `_candidate_only_primary_reason(...)`

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- `sell_reason_bucket` continues to come from `resolve_sell_reason_bucket(latest_exit_reason)`
- `candidate_only_primary_reason` continues to come from `resolve_candidate_only_primary_reason(daily_audits)`
- `not_picked_primary_reason` continues to come from `resolve_not_picked_primary_reason(daily_audits)`
- no wording changes
- no priority changes
- no fallback changes

### 5.4 Testing Strategy

Focused coverage should remain on the canonical reasoning owners.

Update nearby script-focused coverage only where it still points at removed wrappers:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

Minimum check:

- the sell-reason bucket contract assertion should call `resolve_sell_reason_bucket(...)` directly
- the rest of the script-focused tests continue to exercise `_audit_daily_reason(...)`, `_extract_execution_reason(...)`, and `_analyze_topk(...)`

## 6. Risks and Guardrails

Main risk:

- accidentally broadening the cleanup into reasoning behavior changes

Guardrail:

- delete only the forwarding wrappers and replace only their call sites

Secondary risk:

- dropping meaningful script-focused coverage when removing the wrapper assertion

Guardrail:

- retarget the existing assertion to the canonical owner rather than deleting the test intent

## 7. Implementation Outline

Planned steps:

1. remove the three forwarding wrappers from the report script
2. switch the three local call sites to direct reasoning owner calls
3. retarget the wrapper-focused test assertion to the canonical owner import
4. run focused verification and syntax checks

## 8. Success Criteria

This slice is complete when:

- the report script no longer defines the three forwarding wrappers
- all three call sites use the canonical reasoning owners directly
- canonical reasoning behavior remains unchanged
- focused verification passes
- syntax verification passes
