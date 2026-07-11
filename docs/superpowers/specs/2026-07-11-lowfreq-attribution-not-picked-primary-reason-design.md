Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report not-picked primary reason contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Not-Picked Primary Reason Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the attribution sell-reason bucket extraction.

This slice freezes only the pure not-picked primary-reason contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_not_picked_primary_reason(...)`

The goal is to:

- move the pure not-picked reason selection contract into one analysis owner
- keep report orchestration in the script
- preserve current returned strings exactly
- add direct owner-focused coverage for the contract

This design is not:

- a rewrite of `_audit_daily_reason(...)`
- a rewrite of `_candidate_only_primary_reason(...)`
- a rewrite of report row assembly
- a rewrite of buy-signal audit production

Project-phase note:

- domain: `top200 attribution report not-picked primary reason`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- report-side selection from `daily_audits` to one primary not-picked reason
- reuse of the existing analysis owner file
- owner-focused tests for priority, empty, and no-reason fallback behavior

Excluded:

- changes to audit stage generation
- changes to candidate-only wording
- changes to report output schema
- changes to engine/API contracts

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one inline pure selector:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L795-L823)
- the result is consumed only as one branch of report-side reason selection:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L973-L976)
- adjacent consumer-side contracts are already being consolidated into the shared analysis owner:
  - [attribution_reasoning.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py)

The problem is:

- the selector is still embedded inline in the report script
- the helper is pure and self-contained
- the helper belongs to consumer-side attribution reasoning, not producer ownership

## 4. Approach Options

### Option A: Move only the pure not-picked selector into the existing analysis owner and keep report orchestration in the script (Recommended)

- extend `neotrade3/analysis/attribution_reasoning.py`
- move only the `daily_audits -> primary_reason` selection logic
- keep all report flow in the script

Pros:

- isolates a real contract kernel with minimal risk
- reuses the report reasoning owner introduced by the previous slices
- preserves the script’s orchestration boundary

Cons:

- the script still keeps surrounding branch logic

### Option B: Extract a larger daily-attribution reasoning bundle

Pros:

- removes more inline script code

Cons:

- broadens into mixed report decisions not yet proven as the next narrow cut
- increases regression surface

### Option C: Move the selector into `decision_engine`

Pros:

- would place more lowfreq helpers near engine contracts

Cons:

- this helper interprets report-consumer audit rows, not engine rule kernels
- would blur producer/consumer ownership

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Extend the existing report-side owner:

- `neotrade3/analysis/attribution_reasoning.py`

Recommended function:

- `resolve_not_picked_primary_reason(daily_audits: list[dict[str, Any]]) -> str`

Why keep it in the same file:

- it is adjacent to the other attribution reasoning helpers
- all three helpers are report-consumer contracts
- this avoids scattering tiny report contracts across multiple files

### 5.2 Script Boundary

The script should keep:

- branch selection that decides when the row is `candidate_not_entry` versus `not_picked`
- assignment of `primary_reason`
- assignment of `reason_bucket`

The script should no longer own:

- the stage-priority and reason-frequency selection rules inside `_not_picked_primary_reason(...)`

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- if `daily_audits` is empty -> `主升段内从未进入候选池`
- compute `max_priority` using the current stage-to-priority map
- keep only entries at `max_priority`
- if no preferred entries remain, fall back to the original list
- pick the most common non-empty `reason`
- if there is no non-empty reason -> `主升段内从未进入候选池`

Priority map must remain unchanged:

- `market_filtered -> 1`
- `market_candidate_filtered -> 2`
- `sector_filtered -> 2`
- `sector_candidate_filtered -> 3`
- `global_candidate_filtered -> 3`
- `score_below_threshold -> 4`
- `follower_filtered -> 4`
- `resonance_filtered -> 4`
- `global_follower_filtered -> 4`
- `global_resonance_filtered -> 4`
- `global_wave_filtered -> 4`
- `global_score_filtered -> 4`
- `global_cap_filtered -> 5`
- `sector_candidate_not_selected -> 5`
- `candidate_signal_selected -> 6`
- `entry_signal_selected -> 7`

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py`

Minimum owner cases:

- empty list fallback
- highest-priority stage wins over lower-priority reasons
- most-common reason wins inside the preferred priority bucket
- all-empty reasons fallback

## 6. Risks and Guardrails

Main risk:

- broadening into `_audit_daily_reason(...)` or other report orchestration

Guardrail:

- move only the pure selector

Secondary risk:

- drifting current fallback text or stage priorities

Guardrail:

- preserve strings and map entries exactly
- verify direct owner tests

## 7. Implementation Outline

Planned steps:

1. extend `neotrade3/analysis/attribution_reasoning.py`
2. move the selector there
3. switch the report script to import the new helper
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the not-picked primary-reason contract has one analysis owner
- the report script no longer owns the selector inline
- returned strings stay unchanged
- owner-focused tests pass
- syntax verification passes
