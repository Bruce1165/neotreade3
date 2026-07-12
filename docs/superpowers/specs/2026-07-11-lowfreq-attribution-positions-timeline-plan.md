Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report positions timeline extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Positions Timeline Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-positions-timeline-design.md`

## 1. Goal

This plan covers only the next narrow report-prep slice after the attribution buy-signal-audit index extraction.

This slice only handles:

- the pure `trades + trading_dates -> held-codes timeline` contract used by `_build_positions_timeline(...)`
- reuse of one dedicated analysis owner
- direct owner-focused tests plus a nearby report regression rerun

The goal is to:

- remove the inline timeline helper from the script
- keep report orchestration stable
- preserve holding-window semantics exactly

This slice does not:

- rewrite execution reasoning
- rewrite trade production
- rewrite DB trading-date loading

## 2. Starting Point

Current repository evidence shows:

- `_build_positions_timeline(...)` is still inline in the report script
- the helper is pure and only prepares full-book consumer input
- repository evidence does not show a dedicated existing owner test for this helper

So the correct next slice is:

- extract only the timeline assembler
- keep the script as a thin consumer around it

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_positions_timeline.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_positions_timeline.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### APT-S1: Freeze observable timeline contract

Freeze the visible behavior:

- every provided trading date is initialized in the output
- invalid trades are ignored
- holdings begin on `buy_date`
- holdings end before `sell_date`
- missing `sell_date` keeps the code active through remaining trading dates

Completion check:

- no execution reasoning or DB loading is included in this slice

### APT-S2: Add the analysis owner

Create `neotrade3/analysis/attribution_positions_timeline.py` with:

- `build_positions_timeline(trades: list[dict[str, Any]], trading_dates: list[str]) -> dict[str, set[str]]`

Implementation rules:

- use plain Python data structures
- initialize from the provided `trading_dates`
- keep only local filtering and window expansion logic
- do not call DB or engine methods

Completion check:

- the contract is independently understandable from the report script

### APT-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `build_positions_timeline(...)`
- replace the inline helper body with a single delegation call

Do not change:

- trading-date loading
- the call site inside `_analyze_topk(...)`
- downstream full-book reasoning

Completion check:

- the script no longer owns the timeline assembly logic inline

### APT-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_positions_timeline.py`

Minimum owner cases:

- keeps default empty sets for all trading dates
- expands a hold window from `buy_date` until before `sell_date`
- ignores invalid trades and out-of-range `buy_date`

Completion check:

- the owner contract has direct focused coverage

### APT-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_positions_timeline.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_positions_timeline.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_positions_timeline.py`

Completion check:

- owner tests pass
- nearby report regression passes
- syntax validation passes

### APT-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_positions_timeline.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_positions_timeline.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally drifting the `sell_date` exclusive boundary

Guard:

- freeze the current `d >= sell_date` stop rule exactly

Risk 2:

- broadening into execution reasoning or trading-date loading

Guard:

- move only the pure timeline assembler

## 6. Success Criteria

This slice is complete when:

- the positions timeline contract has one analysis owner
- the report script no longer owns the timeline assembly logic inline
- grouped timeline output remains unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
