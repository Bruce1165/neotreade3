Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report aggregate summary extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Aggregate Summary Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-aggregate-summary-design.md`

## 1. Goal

This plan covers only the next narrow report-prep slice after the attribution signal pick summary extraction.

This slice only handles:

- the pure `report_rows + summary_counters -> aggregate` contract used inline in `_analyze_topk(...)`
- reuse of one dedicated analysis owner
- direct owner-focused tests plus a nearby report regression rerun

The goal is to:

- remove the inline aggregate reduction block from the script
- keep report row generation and markdown rendering stable
- preserve current aggregate field semantics exactly

This slice does not:

- rewrite `report_rows`
- rewrite markdown report generation
- rewrite reason bucket semantics
- rewrite the `segment_failed` row branch

## 2. Starting Point

Current repository evidence shows:

- the script still computes aggregate count fields inline from `report_rows`
- the script still materializes `reason_buckets` inline from `summary_counters`
- markdown output and nearby tests consume this aggregate contract
- repository evidence does not show a dedicated owner test for this reduction itself

So the correct next slice is:

- extract only the aggregate summary reducer
- keep row production and downstream rendering in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_aggregate_summary.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_aggregate_summary.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### AAS-S1: Freeze observable aggregate contract

Freeze the visible behavior:

- `count` equals `len(report_rows)`
- `candidate_picked_count` counts truthy `candidate_picked`
- `entry_picked_count` counts truthy `entry_picked`
- `picked_count` still counts truthy `entry_picked`
- `bought_count` counts truthy `bought`
- `held_to_top_count` counts truthy `held_to_top`
- `reason_buckets` is a plain dict copy

Completion check:

- no semantic cleanup or field reinterpretation is added in this slice

### AAS-S2: Add the analysis owner

Create `neotrade3/analysis/attribution_aggregate_summary.py` with:

- `build_attribution_aggregate_summary(report_rows: list[dict[str, Any]], reason_buckets: dict[str, int]) -> dict[str, Any]`

Implementation rules:

- use plain Python data structures
- keep only aggregate counting and dict materialization logic
- do not call DB, engine, or markdown helpers

Completion check:

- the contract is independently understandable from the report script

### AAS-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `build_attribution_aggregate_summary(...)`
- replace the inline aggregate block with one owner call

Do not change:

- `summary_counters` updates inside the loop
- row schema
- markdown rendering usage of `aggregate`

Completion check:

- the script no longer owns the inline aggregate reduction block

### AAS-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_aggregate_summary.py`

Minimum owner cases:

- computes visible counts from report rows
- keeps `picked_count` aligned with `entry_picked`
- materializes `reason_buckets` as a plain dict copy

Completion check:

- the owner contract has direct focused coverage

### AAS-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_aggregate_summary.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_aggregate_summary.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_aggregate_summary.py`

Completion check:

- owner tests pass
- nearby report regression passes
- syntax validation passes

### AAS-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-aggregate-summary-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-aggregate-summary-plan.md`
- `neotrade3/analysis/attribution_aggregate_summary.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_aggregate_summary.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally changing `picked_count` semantics

Guard:

- freeze the current mapping to `entry_picked` exactly

Risk 2:

- broadening into markdown rendering or row assembly

Guard:

- move only the pure aggregate reduction block

## 6. Success Criteria

This slice is complete when:

- the aggregate summary contract has one analysis owner
- the report script no longer owns the inline aggregate block
- aggregate fields remain unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
