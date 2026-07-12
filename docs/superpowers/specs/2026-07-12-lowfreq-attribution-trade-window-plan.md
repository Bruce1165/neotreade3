Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report trade window extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Trade Window Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-trade-window-design.md`

## 1. Goal

This plan covers only the next narrow report-prep slice after the attribution positions timeline extraction.

This slice only handles:

- the pure `trades + segment window -> trade summary` contract used inline in `_analyze_topk(...)`
- reuse of one dedicated analysis owner
- direct owner-focused tests plus a nearby report regression rerun

The goal is to:

- remove the inline trade-window summary block from the script
- keep report orchestration stable
- preserve trade ordering and overlap semantics exactly

This slice does not:

- rewrite trade grouping by code
- rewrite `_extract_execution_reason(...)`
- rewrite sell-reason mapping
- rewrite report row assembly

## 2. Starting Point

Current repository evidence shows:

- the script still sorts `code_trades`, filters `relevant_trades`, and derives several summary fields inline
- the same sorted `code_trades` is consumed later by `_extract_execution_reason(...)`
- repository evidence does not show a dedicated owner test for this summarizer itself

So the correct next slice is:

- extract only the per-code trade-window summarizer
- keep grouping and downstream branching in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_trade_window.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_trade_window.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### ATW-S1: Freeze observable trade-window contract

Freeze the visible behavior:

- trades are sorted by `(buy_date, sell_date)`
- relevant trades satisfy `buy_date <= segment_top_date`
- relevant trades also satisfy blank `sell_date` or `sell_date >= segment_start_date`
- `bought` reflects whether relevant trades exist
- `held_to_top` reflects whether any relevant trade spans the top date
- first-window fields come from the first relevant trade after sorting
- `latest_exit_reason` comes from the relevant trade with the max `sell_date`

Completion check:

- no new validation or cleanup semantics are added in this slice

### ATW-S2: Add the analysis owner

Create `neotrade3/analysis/attribution_trade_window.py` with:

- `build_attribution_trade_window(trades: list[dict[str, Any]], *, segment_start_date: str, segment_top_date: str) -> dict[str, Any]`

Implementation rules:

- use plain Python data structures
- sort locally inside the owner
- keep only overlap filtering and summary derivation logic
- do not call DB or engine methods

Completion check:

- the contract is independently understandable from the report script

### ATW-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `build_attribution_trade_window(...)`
- replace the inline sort/filter/summary block with a single owner call and field reads

Do not change:

- `trades_by_code` construction
- `_extract_execution_reason(...)` inputs other than reading `code_trades` from the new owner result
- downstream report branching and row schema

Completion check:

- the script no longer owns the inline trade-window summary block

### ATW-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_trade_window.py`

Minimum owner cases:

- sorts trades before deriving first-window fields
- keeps only trades overlapping the segment window
- derives `held_to_top` and `latest_exit_reason` from the current contract
- returns empty defaults when no relevant trade exists

Completion check:

- the owner contract has direct focused coverage

### ATW-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_trade_window.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_trade_window.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_trade_window.py`

Completion check:

- owner tests pass
- nearby report regression passes
- syntax validation passes

### ATW-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-trade-window-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-trade-window-plan.md`
- `neotrade3/analysis/attribution_trade_window.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_trade_window.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally drifting the current overlap filter or first-trade ordering

Guard:

- freeze the current `(buy_date, sell_date)` sort and overlap conditions exactly

Risk 2:

- broadening into execution fallback or report-row assembly

Guard:

- move only the per-code trade-window summarizer

## 6. Success Criteria

This slice is complete when:

- the trade-window contract has one analysis owner
- the report script no longer owns the inline trade summary block
- `relevant_trades` ordering remains unchanged
- derived fields remain unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
