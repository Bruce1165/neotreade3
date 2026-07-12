Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report signal pick summary contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Signal Pick Summary Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution trade window extraction.

This slice freezes only the pure signal-pick summarization block that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the inline `daily_audits -> candidate_dates / entry_dates / first dates / counts / picked flags` block inside `_analyze_topk(...)`

The goal is to:

- move the pure `daily_audits -> signal pick summary` contract into one analysis owner
- keep `_audit_daily_reason(...)` orchestration in the script
- preserve current stage-to-date mapping semantics exactly
- add direct owner-focused coverage

This design is not:

- a rewrite of `_audit_daily_reason(...)`
- a rewrite of report row assembly
- a rewrite of execution-reason fallback
- a rewrite of reason-bucket branching

Project-phase note:

- domain: `top200 attribution report signal pick summary`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- scanning `daily_audits`
- collecting `candidate_dates`
- collecting `entry_dates`
- deriving `candidate_picked`
- deriving `entry_picked`
- deriving `picked`
- deriving `first_candidate_date`
- deriving `candidate_signal_count_in_segment`
- deriving `first_entry_date`
- deriving `first_signal_date`
- deriving `entry_signal_count_in_segment`
- deriving `signal_count_in_segment`
- owner-focused tests for the visible summary fields

Excluded:

- generating `daily_audits`
- converting `segment_dates` to `date`
- reason wording
- aggregate rollups across report rows

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one self-contained inline signal-pick summary block:
  - classify `candidate_signal_selected` and `entry_signal_selected`
  - append corresponding dates
  - derive first dates and counts
  - reuse `entry_dates` for execution-reason fallback
- report row fields and aggregate counters already consume this summary contract:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

The problem is:

- this signal-pick kernel is still embedded in the report loop
- the block is pure and self-contained once `daily_audits` exists
- the block belongs to report-consumer preparation, not daily audit orchestration

## 4. Approach Options

### Option A: Move only the pure signal-pick summarizer into a dedicated analysis owner and keep the script as a thin consumer (Recommended)

- add one small analysis module
- move only the stage-to-date classification and derived summary fields
- keep `_audit_daily_reason(...)` invocation in the script

Pros:

- isolates a real contract kernel with minimal risk
- preserves the current daily audit loop
- avoids broadening into audit generation or report branching

Cons:

- the script still keeps the upstream `daily_audits` build loop

### Option B: Merge this helper into `attribution_reasoning.py`

Pros:

- fewer files

Cons:

- mixes reason wording with structural signal summary mapping
- weakens discoverability

### Option C: Extract the whole daily audit loop together

Pros:

- removes more inline code

Cons:

- broadens the slice into engine/context orchestration
- increases regression surface

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Create one dedicated report-side owner:

- `neotrade3/analysis/attribution_signal_pick_summary.py`

Recommended function:

- `build_attribution_signal_pick_summary(daily_audits: list[dict[str, Any]]) -> dict[str, Any]`

Recommended output fields:

- `candidate_dates`
- `entry_dates`
- `candidate_picked`
- `entry_picked`
- `picked`
- `first_candidate_date`
- `candidate_signal_count_in_segment`
- `first_entry_date`
- `first_signal_date`
- `entry_signal_count_in_segment`
- `signal_count_in_segment`

Why create a new file:

- this helper is summary projection, not reason selection
- a dedicated file keeps the contract discoverable and avoids overloading existing owners

### 5.2 Script Boundary

The script should keep:

- building `daily_audits`
- deciding when to call the helper
- passing `entry_dates` into `_extract_execution_reason(...)`
- branching on `entry_dates` / `candidate_dates`
- assembling final report rows and aggregate counters

The script should no longer own:

- scanning `daily_audits` to append dates inline
- deriving the picked flags inline
- deriving the first-date and count fields inline

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- append a date to `candidate_dates` when `stage` is `candidate_signal_selected` or `entry_signal_selected`
- append a date to `entry_dates` only when `stage` is `entry_signal_selected`
- keep date order exactly as `daily_audits` iteration order
- derive `candidate_picked` from whether `candidate_dates` is non-empty
- derive `entry_picked` and `picked` from whether `entry_dates` is non-empty
- derive `first_candidate_date` from the first candidate date
- derive `first_entry_date` and `first_signal_date` from the first entry date
- derive candidate and entry counts from the lengths of the corresponding date lists
- keep `signal_count_in_segment` equal to entry count

Important semantic note:

- this slice should not infer or repair missing `date` values; it should preserve current append behavior based on the existing entries

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_signal_pick_summary.py`

Minimum owner cases:

- maps candidate-only stages into candidate summary fields
- maps entry stages into both candidate and entry summary fields
- keeps iteration order and empty defaults when no stage matches

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

## 6. Risks and Guardrails

Main risk:

- silently drifting the current stage mapping or first-date semantics

Guardrail:

- freeze the exact current append conditions and derived-field aliases

Secondary risk:

- broadening into `_audit_daily_reason(...)` orchestration

Guardrail:

- move only the pure `daily_audits -> summary` projection

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_signal_pick_summary.py`
2. move the signal-pick summary projection there
3. switch the report script to consume the new owner
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the signal-pick summary contract has one analysis owner
- the report script no longer owns the inline summary mapping block
- `candidate_dates` / `entry_dates` semantics stay unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
