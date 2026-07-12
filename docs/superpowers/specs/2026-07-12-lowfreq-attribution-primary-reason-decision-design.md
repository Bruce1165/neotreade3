Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report primary reason decision contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Primary Reason Decision Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution aggregate summary extraction.

This slice freezes only the pure priority selector that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the inline `bought / held_to_top / entry_picked / candidate_picked -> primary_reason + reason_bucket` branch inside `_analyze_topk(...)`

The goal is to:

- move the pure primary-reason decision contract into one analysis owner
- keep execution reason calculation and upstream projections in the script
- preserve the current branch priority semantics exactly
- add direct owner-focused coverage

This design is not:

- a rewrite of `_extract_execution_reason(...)`
- a rewrite of sell reason bucket mapping
- a rewrite of candidate-only or not-picked reason owners
- a rewrite of report row assembly

Project-phase note:

- domain: `top200 attribution report primary reason decision`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- deciding between held-to-top, bought-not-held, picked-not-bought, candidate-not-entry, not-picked
- deriving `primary_reason`
- deriving `reason_bucket`
- owner-focused tests for the visible decision result

Excluded:

- computing `execution_primary_reason`
- computing `candidate_only_primary_reason`
- computing `not_picked_primary_reason`
- computing `sell_reason_bucket`
- building `daily_audits`, `entry_dates`, or trade window fields

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one self-contained priority branch:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
- upstream pure helpers already exist for component reasons:
  - [attribution_reasoning.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py)
- execution fallback remains the highest-risk mixed block and should stay outside this slice

The problem is:

- the final reason decision is still embedded in the report loop
- the branch itself is pure once component reasons and booleans are already known
- the branch belongs to report-consumer reasoning, not orchestration

## 4. Approach Options

### Option A: Move only the pure priority selector into `attribution_reasoning.py` and keep upstream reason computation in the script (Recommended)

- add one more reasoning owner function
- compute `execution_primary_reason` / `candidate_only_primary_reason` / `not_picked_primary_reason` in the script first
- pass those results into the selector

Pros:

- isolates a real contract kernel with minimal risk
- avoids touching execution fallback internals
- keeps current helper family coherent

Cons:

- the script still computes component reasons before the final selection

### Option B: Extract the whole bought / picked / candidate / not-picked chain together

Pros:

- removes more inline script code

Cons:

- broadens into execution reason calculation and upstream dependencies
- increases regression surface

### Option C: Extract only the bought branch

Pros:

- even smaller cut

Cons:

- lower value
- leaves the real cross-branch priority contract inline

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Extend:

- `neotrade3/analysis/attribution_reasoning.py`

Recommended function:

- `resolve_primary_reason_decision(...) -> dict[str, str]`

Recommended inputs:

- `bought`
- `held_to_top`
- `entry_picked`
- `candidate_picked`
- `latest_exit_reason`
- `sell_reason_bucket`
- `execution_primary_reason`
- `candidate_only_primary_reason`
- `not_picked_primary_reason`

Recommended output fields:

- `primary_reason`
- `reason_bucket`

Why keep it in `attribution_reasoning.py`:

- this helper is pure reason selection
- it belongs with existing reason wording and bucket-mapping owners

### 5.2 Script Boundary

The script should keep:

- computing `execution_primary_reason`
- computing `candidate_only_primary_reason`
- computing `not_picked_primary_reason`
- computing `sell_reason_bucket`
- passing all prepared values into the new selector

The script should no longer own:

- the inline priority branch itself

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- if `bought and held_to_top`, return:
  - `primary_reason = "实际持仓延续到市场事实见顶"`
  - `reason_bucket = "held_to_top"`
- else if `bought`, return:
  - `primary_reason = latest_exit_reason or "已买入但未持有到见顶"`
  - `reason_bucket = sell_reason_bucket`
- else if `entry_picked`, return:
  - `primary_reason = execution_primary_reason`
  - `reason_bucket = "picked_not_bought"`
- else if `candidate_picked`, return:
  - `primary_reason = candidate_only_primary_reason`
  - `reason_bucket = "candidate_not_entry"`
- else return:
  - `primary_reason = not_picked_primary_reason`
  - `reason_bucket = "not_picked"`

Important semantic note:

- this slice must not reinterpret empty `execution_primary_reason` or `latest_exit_reason`; it only freezes the current branch priority contract

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_primary_reason_decision.py`

Minimum owner cases:

- held-to-top branch wins over all lower branches
- bought-not-held branch keeps fallback text and passed sell bucket
- entry-pick branch beats candidate branch
- candidate branch beats not-picked branch

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into execution fallback logic

Guardrail:

- pass precomputed component reasons into the selector instead of computing them inside

Secondary risk:

- drifting the current branch priority order

Guardrail:

- lock the exact existing branch order in focused tests

## 7. Implementation Outline

Planned steps:

1. extend `attribution_reasoning.py` with the new selector
2. switch the report script to compute component reasons first and call the selector
3. add owner-focused tests
4. run focused verification

## 8. Success Criteria

This slice is complete when:

- the primary reason decision contract has one reasoning owner
- the report script no longer owns the inline priority branch
- branch priority stays unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
