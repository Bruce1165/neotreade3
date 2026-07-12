Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report positions timeline contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Positions Timeline Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the attribution buy-signal-audit index extraction.

This slice freezes only the pure positions-timeline assembler that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_build_positions_timeline(...)`

The goal is to:

- move the pure `trades + trading_dates -> held-codes timeline` contract into one analysis owner
- keep `_extract_execution_reason(...)` and report orchestration in the script
- preserve the current holding-window semantics exactly
- add direct owner-focused coverage

This design is not:

- a rewrite of `_extract_execution_reason(...)`
- a rewrite of trade production
- a rewrite of report row assembly
- a rewrite of backtest execution semantics

Project-phase note:

- domain: `top200 attribution report positions timeline`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- default initialization for every provided trading date
- filtering invalid trades
- expanding held dates from `buy_date` forward
- stopping on `sell_date`
- grouping held codes into `date -> set[code]`
- owner-focused tests for holding-window semantics

Excluded:

- trading-date loading from DB
- execution reason wording
- changes to report output schema
- changes to engine/API contracts

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one self-contained positions timeline assembler:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
- the only visible consumer is full-book reasoning inside `_extract_execution_reason(...)`
- repository evidence does not show a dedicated direct test carrier for this helper itself

The problem is:

- this timeline kernel is still embedded in the report script
- the helper is pure and self-contained
- the helper belongs to report-consumer preparation, not producer ownership

## 4. Approach Options

### Option A: Move only the pure positions timeline assembler into a dedicated analysis owner and keep the script as a thin consumer (Recommended)

- add one small analysis module
- move only the timeline assembly logic
- keep full-book reasoning and report orchestration in the script

Pros:

- isolates a real contract kernel with minimal risk
- preserves current report flow exactly
- avoids broadening into execution reasoning

Cons:

- the script still keeps downstream consumer logic

### Option B: Merge this helper into the existing audit-index owner

Pros:

- fewer files

Cons:

- mixes distinct preparation contracts
- weakens discoverability

### Option C: Move a larger report-prep bundle together

Pros:

- removes more inline script code

Cons:

- broadens the slice beyond the proven narrow cut
- increases regression surface

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Create one dedicated report-side owner:

- `neotrade3/analysis/attribution_positions_timeline.py`

Recommended function:

- `build_positions_timeline(trades: list[dict[str, Any]], trading_dates: list[str]) -> dict[str, set[str]]`

Why create a new file:

- this helper is timeline assembly, not audit indexing or reason selection
- a dedicated file keeps the contract discoverable and avoids overloading other owners

### 5.2 Script Boundary

The script should keep:

- loading `trading_dates`
- deciding when to call the helper
- consuming the result for full-book reasoning

The script should no longer own:

- filtering invalid trades
- expanding the date window for each held code
- populating the per-date held-code sets

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- initialize every provided trading date with an empty `set`
- ignore trades with blank `code`
- ignore trades with blank `buy_date`
- ignore trades whose `buy_date` is not in the timeline keys
- for each trade, skip all `trading_dates < buy_date`
- if `sell_date` exists, stop before `d >= sell_date`
- otherwise keep the code held through the remaining trading dates

Important semantic note:

- `sell_date` is exclusive in the current contract

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_positions_timeline.py`

Minimum owner cases:

- fills all provided trading dates with default empty sets
- expands a holding window from `buy_date` until before `sell_date`
- ignores invalid trades and trades whose `buy_date` is outside the timeline

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

## 6. Risks and Guardrails

Main risk:

- silently drifting the inclusive/exclusive hold-window boundary

Guardrail:

- freeze the current `sell_date` exclusive rule exactly

Secondary risk:

- broadening into execution reasoning or DB date loading

Guardrail:

- move only the pure timeline assembler

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_positions_timeline.py`
2. move the timeline assembler there
3. switch the script helper to a thin wrapper
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the positions timeline contract has one analysis owner
- the report script no longer owns the timeline assembly logic inline
- grouped timeline output stays unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
