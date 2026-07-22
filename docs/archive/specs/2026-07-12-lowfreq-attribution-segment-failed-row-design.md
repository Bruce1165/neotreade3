Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report segment-failed row projection extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Segment Failed Row Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution thin-wrapper cleanup.

This slice freezes only the remaining inline failure-row payload inside:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the `segment.get("status") != "ok"` branch inside `_analyze_topk(...)`

The goal is to:

- move the last inline report-row fallback payload into the report-row owner
- keep the current failure-row field set and visible semantics unchanged
- keep aggregate summary behavior unchanged
- continue shrinking the script toward a pure orchestrator

This design is not:

- a rewrite of `_compute_wave_segment(...)`
- a rewrite of aggregate summary rules
- a rewrite of the successful row projection contract
- a rewrite of markdown rendering

Project-phase note:

- domain: `top200 attribution report segment-failed row projection`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the failure-row payload from the script into the report-row owner
- preserving the current failure-row field set and defaults exactly
- adding owner-focused tests for the failed-segment row projection

Excluded:

- any change to segment detection rules
- any change to successful row payloads
- any change to `summary_counters["segment_failed"] += 1`
- any change to aggregate counting behavior

## 3. Existing Context

Current repository evidence shows:

- the successful report row is already owned by:
  - [attribution_report_row.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_report_row.py)
- the script still keeps one inline fallback row when `segment.get("status") != "ok"`:
  - [generate_lowfreq_top200_attribution_report.py:L739-L755](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L739-L755)
- this fallback row is still a pure payload projection:
  - it uses only prepared values from `item`, `code`, `name`, and `segment`
  - it does not touch DB, engine, ctx, or later orchestration steps
- aggregate summary only depends on boolean flags already present in the fallback row:
  - [attribution_aggregate_summary.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_aggregate_summary.py)

The current inline failure-row payload is:

- `rank`
- `code`
- `name`
- `annual_return_pct`
- `segment_status`
- `candidate_picked: False`
- `entry_picked: False`
- `picked: False`
- `bought: False`
- `held_to_top: False`
- `primary_reason: "主升段识别失败"`

The problem is:

- successful rows already have a dedicated owner, but failed rows do not
- the script still owns one visible row payload contract inline
- row ownership is therefore not fully centralized

## 4. Approach Options

### Option A: Add one failed-row builder to the existing report-row owner and switch the script to consume it directly (Recommended)

- keep `attribution_report_row.py` as the single row-projection home
- add one dedicated helper for the failed-segment fallback row
- keep the script responsible only for detecting the failed branch and incrementing counters

Pros:

- keeps all row payload contracts in one owner
- preserves the current field set exactly
- smallest possible change with clear ownership

Cons:

- adds one more helper function to the report-row owner

### Option B: Leave the failure row inline because it is short

Pros:

- no new test changes

Cons:

- leaves row ownership split between owner and script
- keeps the last visible row payload contract inline

### Option C: Merge failed and successful rows into one polymorphic builder

Pros:

- one public entry point

Cons:

- broadens the slice into a larger API redesign
- risks reinterpreting the successful-row contract

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Keep the canonical row owner in:

- [attribution_report_row.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_report_row.py)

Add one failed-row builder there, for example:

- `build_attribution_segment_failed_row(...) -> dict[str, Any]`

Recommended inputs:

- `rank`
- `code`
- `name`
- `annual_return_pct`
- `segment_status`

Recommended output fields:

- `rank`
- `code`
- `name`
- `annual_return_pct`
- `segment_status`
- `candidate_picked`
- `entry_picked`
- `picked`
- `bought`
- `held_to_top`
- `primary_reason`

Why the same file:

- both successful and failed rows are report-side projection contracts
- a shared owner keeps row shape ownership centralized and discoverable

### 5.2 Script Boundary

The script should keep:

- detecting `segment.get("status") != "ok"`
- incrementing `summary_counters["segment_failed"] += 1`
- continuing the loop immediately after appending the fallback row

The script should stop owning:

- the inline failed-segment fallback row dictionary

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- `rank` continues to come from `item["rank"]`
- `code` continues to come from `code`
- `name` continues to come from `name`
- `annual_return_pct` continues to come from `item["annual_return_pct"]`
- `segment_status` continues to be `str(segment.get("status") or "unknown")`
- `candidate_picked` remains `False`
- `entry_picked` remains `False`
- `picked` remains `False`
- `bought` remains `False`
- `held_to_top` remains `False`
- `primary_reason` remains `"主升段识别失败"`

Important semantic note:

- this slice must not add `reason_bucket`, `sector`, or any other fields to the failed row just for symmetry

### 5.4 Testing Strategy

Extend the owner-focused carrier:

- [test_lowfreq_attribution_report_row.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_report_row.py)

Minimum owner cases:

- projects the failed-segment row with the current field set and coercions
- keeps the current `"unknown"` fallback for empty segment status

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

## 6. Risks and Guardrails

Main risk:

- silently making the failed row look more like the successful row by adding fields that do not exist today

Guardrail:

- freeze the exact current field set and defaults from the inline branch

Secondary risk:

- broadening into segment computation or aggregate logic

Guardrail:

- touch only the row owner, the branch append site, and owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add a failed-row builder to `attribution_report_row.py`
2. switch the script branch to call it
3. add owner-focused tests for the failed row contract
4. run focused verification

## 8. Success Criteria

This slice is complete when:

- the failed-segment row payload has one owner in `attribution_report_row.py`
- the script no longer owns the inline failed-row dictionary
- the failed-row field set remains unchanged
- owner-focused tests pass
- syntax verification passes
