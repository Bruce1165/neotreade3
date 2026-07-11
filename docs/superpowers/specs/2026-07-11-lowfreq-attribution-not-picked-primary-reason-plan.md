Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report not-picked primary reason extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Not-Picked Primary Reason Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-not-picked-primary-reason-design.md`

## 1. Goal

This plan covers only the next narrow report reasoning slice after the attribution sell-reason bucket extraction.

This slice only handles:

- the pure not-picked primary-reason selector used by the top200 attribution report
- reuse of the existing analysis owner for report reasoning helpers
- direct owner-focused tests for priority and fallback behavior

The goal is to:

- remove the inline selector from the script
- keep report orchestration stable
- preserve returned strings exactly

This slice does not:

- rewrite report flow
- rewrite `_candidate_only_primary_reason(...)`
- rewrite audit stage production

## 2. Starting Point

Current repository evidence shows:

- `_not_picked_primary_reason(...)` is still inline in the report script
- the helper is consumed as a pure selector for the `not_picked` branch
- there is no direct test carrier yet, so this slice needs one new owner-focused test file

So the correct next slice is:

- extract only the selector
- keep all surrounding report flow in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py`

## 4. Execution Steps

### ANPR-S1: Freeze observable selector contract

Freeze the fallback text:

- empty or no-reason result -> `主升段内从未进入候选池`

Freeze the stage-priority map exactly as it exists today.

Freeze the selection algorithm:

1. compute `max_priority`
2. keep only entries at that priority
3. if that filtered set is empty, fall back to the full list
4. count non-empty `reason` values
5. return the most common reason
6. if none exist, return the fallback text

Completion check:

- no surrounding report branching or row assembly is included in this slice

### ANPR-S2: Extend the analysis owner

In `neotrade3/analysis/attribution_reasoning.py` add:

- `resolve_not_picked_primary_reason(...)`

Implementation rules:

- accept only `daily_audits`
- normalize only local `stage` and `reason` string reads
- do not query DB
- do not compose report rows
- do not alter report schema

Completion check:

- the selector contract can be understood independently from the report script

### ANPR-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `resolve_not_picked_primary_reason(...)`
- delete inline selector logic
- delegate `_not_picked_primary_reason(...)` to the owner

Do not change:

- branch selection between `candidate_not_entry` and `not_picked`
- row fields or bucket assignments

Completion check:

- the script no longer owns the selector inline

### ANPR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py`

Minimum owner cases:

- empty-list fallback
- higher-priority stage overrides lower-priority stage
- most-common reason wins within the preferred priority bucket
- no non-empty reasons fallback

Completion check:

- the selector contract has direct focused coverage

### ANPR-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py`
- `python3 -m py_compile neotrade3/analysis/attribution_reasoning.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py`

Completion check:

- owner tests pass
- syntax validation passes

### ANPR-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally pulling broader report reasoning into the owner

Guard:

- move only the pure selector

Risk 2:

- silently drifting the stage-priority map or fallback text

Guard:

- freeze the map and string exactly
- verify focused owner tests

## 6. Success Criteria

This slice is complete when:

- the not-picked primary-reason contract has one analysis owner
- the report script no longer owns the selector inline
- returned strings remain unchanged
- owner-focused tests pass
- syntax verification passes
