Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report row projection contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Row Projection Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution primary reason decision extraction.

This slice freezes only the pure row projection block that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the inline `prepared segment + signal summary + trade window + reason decision -> report row` block inside `_analyze_topk(...)`

The goal is to:

- move the pure report-row projection contract into one analysis owner
- keep upstream audit collection, trade-window computation, and reason selection in the script
- preserve the current row payload fields and visible semantics exactly
- add direct owner-focused coverage

This design is not:

- a rewrite of `_extract_execution_reason(...)`
- a rewrite of trade-window assembly
- a rewrite of reason bucket selection
- a rewrite of markdown rendering or aggregate summary

Project-phase note:

- domain: `top200 attribution report row projection`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- projecting one final attribution row from prepared inputs
- preserving current field names, field set, type coercions, and pass-through payloads
- owner-focused tests for the visible row payload

Excluded:

- building `daily_audits`
- computing `signal_pick_summary`
- computing `trade_window`
- computing `primary_reason` or `reason_bucket`
- rendering markdown
- building aggregate summary

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one self-contained row assembly block:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L839-L866)
- upstream owners already exist for signal pick summary, trade window, aggregate summary, and reasoning:
  - [attribution_signal_pick_summary.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_signal_pick_summary.py)
  - [attribution_trade_window.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_trade_window.py)
  - [attribution_aggregate_summary.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_aggregate_summary.py)
  - [attribution_reasoning.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py)
- the remaining inline row block is pure once all inputs have already been prepared

The problem is:

- the final report-row shape is still embedded in the main loop
- the block mixes visible payload contract with orchestration flow
- downstream consumers have no single owner for the row payload shape

## 4. Approach Options

### Option A: Move only the pure row projection into a dedicated analysis owner and keep the script as a thin consumer (Recommended)

- add one dedicated analysis module for report-row projection
- pass only prepared scalar values and already-built payload fragments into the owner
- keep data fetching, daily audit generation, and reason computation in the script

Pros:

- isolates a real contract kernel with minimal risk
- preserves the current report flow exactly
- continues the existing owner-per-contract extraction path

Cons:

- the script still owns upstream preparation work

### Option B: Merge row projection into `attribution_aggregate_summary.py`

Pros:

- fewer files

Cons:

- mixes row-level projection with final aggregate reduction
- weakens ownership clarity

### Option C: Extract a larger report-finalization bundle

Pros:

- removes more inline code at once

Cons:

- broadens into aggregate and markdown concerns
- increases regression surface

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Create one dedicated report-side owner:

- `neotrade3/analysis/attribution_report_row.py`

Recommended function:

- `build_attribution_report_row(...) -> dict[str, Any]`

Recommended input groups:

- rank and instrument identity
- segment fields
- signal pick summary fields
- trade window fields
- final `primary_reason` and `reason_bucket`
- pass-through collections for `daily_audits` and `relevant_trades`

Recommended output fields:

- `rank`
- `code`
- `name`
- `sector`
- `annual_return_pct`
- `segment_start_date`
- `segment_top_date`
- `segment_return_pct`
- `candidate_picked`
- `entry_picked`
- `picked`
- `first_candidate_date`
- `candidate_signal_count_in_segment`
- `first_entry_date`
- `first_signal_date`
- `entry_signal_count_in_segment`
- `signal_count_in_segment`
- `bought`
- `first_buy_date`
- `first_sell_date`
- `held_to_top`
- `primary_reason`
- `reason_bucket`
- `daily_audits`
- `relevant_trades`

Why create a new file:

- this helper is report-row projection, not reasoning, signal summarization, or aggregate reduction
- a dedicated file keeps the row payload contract discoverable and avoids overloading nearby owners

### 5.2 Script Boundary

The script should keep:

- building `daily_audits`
- building `signal_pick_summary`
- building `trade_window`
- computing `primary_reason`
- computing `reason_bucket`
- incrementing `summary_counters`

The script should no longer own:

- the final inline row dictionary projection

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- the output field set stays unchanged
- field names stay unchanged
- numeric fields continue to coerce through `int(...)` or `float(...)` where the current script does so
- string fields continue to coerce through `str(... or "")` where the current script does so
- boolean fields continue to coerce through `bool(...)` where the current script does so
- `picked` remains sourced from `signal_pick_summary["picked"]`
- `daily_audits` remains the original prepared list
- `relevant_trades` remains the original prepared list

Important semantic note:

- this slice must not reinterpret or trim any payload field even if some fields appear redundant with nearby values

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_report_row.py`

Minimum owner cases:

- projects one full row with the current field set and type coercions
- preserves `picked` independently from `entry_picked`
- passes through `daily_audits` and `relevant_trades` unchanged

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

## 6. Risks and Guardrails

Main risk:

- silently cleaning or reinterpreting row payload fields during extraction

Guardrail:

- freeze the current field set and field-to-source mapping exactly

Secondary risk:

- broadening into upstream audit, execution, or markdown responsibilities

Guardrail:

- pass only already-prepared values into the row owner

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_report_row.py`
2. move the inline row projection logic there
3. switch the report script to call the new owner
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the report row projection contract has one analysis owner
- the report script no longer owns the inline row dictionary block
- row payload fields stay unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
