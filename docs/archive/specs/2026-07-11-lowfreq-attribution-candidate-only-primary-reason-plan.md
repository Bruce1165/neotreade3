Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report candidate-only primary reason extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Candidate-Only Primary Reason Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-candidate-only-primary-reason-design.md`

## 1. Goal

This plan covers only the next narrow report reasoning slice after the attribution not-picked primary reason extraction.

This slice only handles:

- the pure candidate-only primary-reason selector used by the top200 attribution report
- reuse of the existing analysis owner for report reasoning helpers
- direct owner-focused tests plus the nearby consumer guard rerun

The goal is to:

- remove the inline selector from the script
- keep report orchestration stable
- preserve returned strings exactly

This slice does not:

- rewrite report flow
- rewrite candidate-tier production
- rewrite report row assembly

## 2. Starting Point

Current repository evidence shows:

- `_candidate_only_primary_reason(...)` is still inline in the report script
- the helper is consumed as the `candidate_not_entry` branch reason
- there is already a nearby consumer guard for the visible `soft_retained` path

So the correct next slice is:

- extract only the selector
- keep all surrounding report flow in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### ACOPR-S1: Freeze observable selector contract

Freeze the visible strings:

- no candidate-hit -> `进入候选池但未进入正式建仓池`
- `candidate_tier == "soft_retained"` -> `进入候选池但被软保留，未进入正式建仓池`
- otherwise -> `进入候选池但未进入正式建仓池`

Freeze the selection algorithm:

1. keep only entries where `stage == "candidate_signal_selected"`
2. if none exist, return the default fallback text
3. use the first candidate hit
4. read `signal` only when it is a dict
5. branch only on `candidate_tier == "soft_retained"`

Completion check:

- no surrounding report branching or row assembly is included in this slice

### ACOPR-S2: Extend the analysis owner

In `neotrade3/analysis/attribution_reasoning.py` add:

- `resolve_candidate_only_primary_reason(...)`

Implementation rules:

- accept only `daily_audits`
- normalize only local `stage` / `signal` / `candidate_tier` reads
- do not query DB
- do not compose report rows
- do not alter report schema

Completion check:

- the selector contract can be understood independently from the report script

### ACOPR-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `resolve_candidate_only_primary_reason(...)`
- delete inline selector logic
- delegate `_candidate_only_primary_reason(...)` to the owner

Do not change:

- branch selection for `candidate_not_entry`
- row fields or bucket assignments

Completion check:

- the script no longer owns the selector inline

### ACOPR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py`

Minimum owner cases:

- no candidate-hit fallback
- `soft_retained` mapping
- non-dict signal fallback

Completion check:

- the selector contract has direct focused coverage

### ACOPR-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_reasoning.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py`

Completion check:

- owner tests pass
- nearby consumer guard passes
- syntax validation passes

### ACOPR-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py`

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

- silently drifting the visible wording

Guard:

- freeze strings exactly
- verify focused owner tests plus the consumer guard

## 6. Success Criteria

This slice is complete when:

- the candidate-only primary-reason contract has one analysis owner
- the report script no longer owns the selector inline
- returned strings remain unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
