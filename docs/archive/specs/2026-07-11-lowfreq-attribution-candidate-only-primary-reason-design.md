Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report candidate-only primary reason contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Candidate-Only Primary Reason Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the attribution not-picked primary reason extraction.

This slice freezes only the pure candidate-only primary-reason contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_candidate_only_primary_reason(...)`

The goal is to:

- move the pure candidate-only reason selection contract into one analysis owner
- keep report orchestration in the script
- preserve current returned strings exactly
- add direct owner-focused coverage for the contract

This design is not:

- a rewrite of `_analyze_topk(...)`
- a rewrite of candidate signal production
- a rewrite of candidate-tier semantics
- a rewrite of report row assembly

Project-phase note:

- domain: `top200 attribution report candidate-only primary reason`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- report-side selection from `daily_audits` to one candidate-only primary reason
- reuse of the existing analysis owner file
- owner-focused tests for empty and `soft_retained` behavior

Excluded:

- changes to audit stage generation
- changes to report output schema
- changes to engine/API contracts

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one inline pure selector:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L800-L808)
- the result is consumed as the `candidate_not_entry` branch reason:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L971-L974)
- there is already a nearby consumer assertion locking the visible soft-retained path:
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L254-L260)
- adjacent report reasoning contracts are already being consolidated into the shared analysis owner:
  - [attribution_reasoning.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py)

The problem is:

- the selector is still embedded inline in the report script
- the helper is pure and self-contained
- the helper belongs to consumer-side attribution reasoning, not producer ownership

## 4. Approach Options

### Option A: Move only the pure candidate-only selector into the existing analysis owner and keep report orchestration in the script (Recommended)

- extend `neotrade3/analysis/attribution_reasoning.py`
- move only the `daily_audits -> primary_reason` selection logic
- keep all report flow in the script

Pros:

- isolates a real contract kernel with minimal risk
- reuses the existing report reasoning owner
- preserves the script orchestration boundary

Cons:

- the script still keeps surrounding branch logic

### Option B: Extract a larger candidate attribution reasoning bundle

Pros:

- removes more inline script code

Cons:

- broadens into mixed report decisions beyond the proven narrow cut
- increases regression surface

### Option C: Move the selector into `decision_engine`

Pros:

- would place more helpers near lowfreq contracts

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

- `resolve_candidate_only_primary_reason(daily_audits: list[dict[str, Any]]) -> str`

Why keep it in the same file:

- it is adjacent to the other attribution reasoning helpers
- all current helpers are report-consumer contracts
- this avoids scattering tiny report contracts across multiple files

### 5.2 Script Boundary

The script should keep:

- branch selection that decides when the row is `candidate_not_entry`
- assignment of `primary_reason`
- assignment of `reason_bucket`

The script should no longer own:

- the candidate-hit selection and `soft_retained` wording rules inside `_candidate_only_primary_reason(...)`

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- keep only entries where `stage == "candidate_signal_selected"`
- if no candidate-hit exists -> `进入候选池但未进入正式建仓池`
- read `signal` only when it is a dict
- if `candidate_tier == "soft_retained"` -> `进入候选池但被软保留，未进入正式建仓池`
- otherwise -> `进入候选池但未进入正式建仓池`

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py`

Minimum owner cases:

- no candidate-hit fallback
- `soft_retained` mapping
- non-dict signal fallback

Keep and re-run the nearby consumer guard:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L254-L260)

## 6. Risks and Guardrails

Main risk:

- broadening into `_analyze_topk(...)` or other report orchestration

Guardrail:

- move only the pure selector

Secondary risk:

- drifting current visible wording

Guardrail:

- preserve strings exactly
- verify direct owner tests plus the consumer guard

## 7. Implementation Outline

Planned steps:

1. extend `neotrade3/analysis/attribution_reasoning.py`
2. move the selector there
3. switch the report script to import the new helper
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the candidate-only primary-reason contract has one analysis owner
- the report script no longer owns the selector inline
- returned strings stay unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
