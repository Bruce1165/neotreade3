Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report signal pick summary extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Signal Pick Summary Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-signal-pick-summary-design.md`

## 1. Goal

This plan covers only the next narrow report-prep slice after the attribution trade window extraction.

This slice only handles:

- the pure `daily_audits -> signal pick summary` contract used inline in `_analyze_topk(...)`
- reuse of one dedicated analysis owner
- direct owner-focused tests plus a nearby report regression rerun

The goal is to:

- remove the inline signal-pick summary block from the script
- keep daily audit orchestration stable
- preserve current stage mapping and date ordering exactly

This slice does not:

- rewrite `_audit_daily_reason(...)`
- rewrite reason branching
- rewrite report aggregate rollups
- rewrite row assembly beyond reading owner outputs

## 2. Starting Point

Current repository evidence shows:

- the script still scans `daily_audits` inline to build `candidate_dates` and `entry_dates`
- the script derives first-date and count fields inline from those lists
- `entry_dates` is later consumed by `_extract_execution_reason(...)`
- repository evidence does not show a dedicated owner test for this summarizer itself

So the correct next slice is:

- extract only the `daily_audits -> signal pick summary` projection
- keep the daily audit loop and downstream branching in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_signal_pick_summary.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_signal_pick_summary.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### ASP-S1: Freeze observable signal-pick contract

Freeze the visible behavior:

- `candidate_signal_selected` contributes to `candidate_dates`
- `entry_signal_selected` contributes to both `candidate_dates` and `entry_dates`
- date order follows `daily_audits` iteration order
- candidate and entry picked flags come from list emptiness
- first-date aliases and count fields come from those same lists

Completion check:

- no new normalization or repair semantics are added in this slice

### ASP-S2: Add the analysis owner

Create `neotrade3/analysis/attribution_signal_pick_summary.py` with:

- `build_attribution_signal_pick_summary(daily_audits: list[dict[str, Any]]) -> dict[str, Any]`

Implementation rules:

- use plain Python data structures
- scan the provided `daily_audits` once
- keep only stage-to-date classification and summary derivation logic
- do not call DB, engine, or context methods

Completion check:

- the contract is independently understandable from the report script

### ASP-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `build_attribution_signal_pick_summary(...)`
- replace the inline append and summary derivation block with one owner call and field reads

Do not change:

- `_audit_daily_reason(...)` invocation
- `_extract_execution_reason(...)` inputs other than reading `entry_dates` from the new owner output
- downstream row schema or aggregate counter logic

Completion check:

- the script no longer owns the inline signal-pick summary block

### ASP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_signal_pick_summary.py`

Minimum owner cases:

- candidate-only stage yields candidate summary but no entry summary
- entry stage yields both candidate and entry summary
- unmatched stages keep empty defaults

Completion check:

- the owner contract has direct focused coverage

### ASP-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_signal_pick_summary.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_signal_pick_summary.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_signal_pick_summary.py`

Completion check:

- owner tests pass
- nearby report regression passes
- syntax validation passes

### ASP-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-signal-pick-summary-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-signal-pick-summary-plan.md`
- `neotrade3/analysis/attribution_signal_pick_summary.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_signal_pick_summary.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally drifting the current stage-to-date mapping or alias fields

Guard:

- freeze the current append conditions and alias relationships exactly

Risk 2:

- broadening into daily audit generation

Guard:

- move only the pure projection from existing `daily_audits`

## 6. Success Criteria

This slice is complete when:

- the signal-pick summary contract has one analysis owner
- the report script no longer owns the inline summary mapping block
- `candidate_dates` / `entry_dates` ordering remains unchanged
- derived flags and count fields remain unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
