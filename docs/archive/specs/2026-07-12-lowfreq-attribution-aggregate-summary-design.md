Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report aggregate summary contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Aggregate Summary Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution signal pick summary extraction.

This slice freezes only the pure aggregate summary block that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the inline `report_rows + summary_counters -> aggregate` block inside `_analyze_topk(...)`

The goal is to:

- move the pure aggregate summary contract into one analysis owner
- keep report row assembly and markdown rendering in the script
- preserve the current aggregate field semantics exactly
- add direct owner-focused coverage

This design is not:

- a rewrite of report row assembly
- a rewrite of markdown report generation
- a rewrite of reason bucket semantics
- a rewrite of the `segment_failed` row fallback branch

Project-phase note:

- domain: `top200 attribution report aggregate summary`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- deriving `count`
- deriving `candidate_picked_count`
- deriving `entry_picked_count`
- deriving `picked_count`
- deriving `bought_count`
- deriving `held_to_top_count`
- copying `reason_buckets`
- owner-focused tests for the visible summary fields

Excluded:

- building `report_rows`
- incrementing `summary_counters`
- markdown formatting
- process-research derived summaries

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one self-contained inline aggregate summary block:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
- markdown report rendering directly consumes these aggregate fields:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
- nearby regression coverage already asserts part of the contract:
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

The problem is:

- this aggregate kernel is still embedded in the report script
- the block is pure and self-contained once `report_rows` and `summary_counters` exist
- the block belongs to report-consumer preparation, not orchestration

## 4. Approach Options

### Option A: Move only the pure aggregate summary assembler into a dedicated analysis owner and keep the script as a thin consumer (Recommended)

- add one small analysis module
- move only aggregate counting and reason-bucket copy logic
- keep row generation and markdown output in the script

Pros:

- isolates a real contract kernel with minimal risk
- preserves current report flow exactly
- avoids broadening into rendering or row assembly

Cons:

- the script still keeps upstream row production

### Option B: Merge this helper into `attribution_signal_pick_summary.py`

Pros:

- fewer files

Cons:

- mixes row-level signal summary with report-level aggregate reduction
- weakens discoverability

### Option C: Extract a larger report-finalization bundle

Pros:

- removes more inline code

Cons:

- broadens the slice into markdown/report shaping
- increases regression surface

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Create one dedicated report-side owner:

- `neotrade3/analysis/attribution_aggregate_summary.py`

Recommended function:

- `build_attribution_aggregate_summary(report_rows: list[dict[str, Any]], reason_buckets: dict[str, int]) -> dict[str, Any]`

Recommended output fields:

- `count`
- `candidate_picked_count`
- `entry_picked_count`
- `picked_count`
- `bought_count`
- `held_to_top_count`
- `reason_buckets`

Why create a new file:

- this helper is aggregate reduction, not row-level signal summary or reason selection
- a dedicated file keeps the contract discoverable and avoids overloading nearby owners

### 5.2 Script Boundary

The script should keep:

- building `report_rows`
- maintaining `summary_counters`
- returning `(segments, report_rows, aggregate)`
- rendering markdown from the aggregate output

The script should no longer own:

- counting aggregate picked / bought / held rows inline
- materializing `reason_buckets` inline

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- `count` equals `len(report_rows)`
- `candidate_picked_count` counts rows where `candidate_picked` is truthy
- `entry_picked_count` counts rows where `entry_picked` is truthy
- `picked_count` remains aligned with `entry_picked`, not the row's `picked` field
- `bought_count` counts rows where `bought` is truthy
- `held_to_top_count` counts rows where `held_to_top` is truthy
- `reason_buckets` is returned as a plain `dict`

Important semantic note:

- even though `picked_count` currently mirrors `entry_picked_count`, this slice must freeze the existing contract instead of reinterpreting it

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_aggregate_summary.py`

Minimum owner cases:

- computes all visible counts from report rows
- preserves the current `picked_count == entry_picked_count` contract
- materializes `reason_buckets` as a plain dict copy

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

## 6. Risks and Guardrails

Main risk:

- silently “fixing” `picked_count` semantics and changing current output

Guardrail:

- freeze the current field-to-source mapping exactly

Secondary risk:

- broadening into markdown or row assembly

Guardrail:

- move only the pure aggregate reduction block

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_aggregate_summary.py`
2. move the aggregate reduction logic there
3. switch the report script to consume the new owner
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the aggregate summary contract has one analysis owner
- the report script no longer owns the inline aggregate reduction block
- aggregate fields stay unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
