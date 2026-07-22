Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report trade window contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Trade Window Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution positions timeline extraction.

This slice freezes only the pure trade-window summarization block that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the inline `code_trades -> relevant_trades / bought / held_to_top / first dates / latest_exit_reason` block inside `_analyze_topk(...)`

The goal is to:

- move the pure `trades + segment window -> trade summary` contract into one analysis owner
- keep `_extract_execution_reason(...)` and report orchestration in the script
- preserve current relevant-trade filtering and ordering semantics exactly
- add direct owner-focused coverage

This design is not:

- a rewrite of backtest trade production
- a rewrite of `_extract_execution_reason(...)`
- a rewrite of sell-reason bucket mapping
- a rewrite of report row assembly

Project-phase note:

- domain: `top200 attribution report trade window`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- sorting one code's trade list by `(buy_date, sell_date)`
- filtering `relevant_trades` by the current segment window
- deriving `bought`
- deriving `held_to_top`
- deriving `first_buy_date`
- deriving `first_sell_date`
- deriving `latest_exit_reason`
- owner-focused tests for the visible summary fields

Excluded:

- grouping all trades by code
- DB reads
- report row field naming outside this trade summary
- execution-reason wording or fallback logic

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one self-contained inline trade summary block:
  - sort `trades_by_code.get(code, [])`
  - filter `relevant_trades` by `start_key` and `top_key`
  - derive `bought`, `held_to_top`, `first_buy_date`, `first_sell_date`, `latest_exit_reason`
- the same sorted `code_trades` is then reused by `_extract_execution_reason(...)`
- process-research/report consumers already rely on these derived fields being stable:
  - [test_lowfreq_process_research_buy_progress_label.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_process_research_buy_progress_label.py)

The problem is:

- this trade-window kernel is still embedded in the report loop
- the block is pure and self-contained
- the block belongs to report-consumer preparation, not producer ownership

## 4. Approach Options

### Option A: Move only the pure trade-window summarizer into a dedicated analysis owner and keep the script as a thin consumer (Recommended)

- add one small analysis module
- move only sorting, window filtering, and summary derivation
- keep grouping by code, report branching, and execution reasoning in the script

Pros:

- isolates a real contract kernel with minimal risk
- preserves the report loop shape
- avoids broadening into trade grouping or execution heuristics

Cons:

- the script still keeps upstream grouping and downstream consumer logic

### Option B: Merge this helper into `attribution_positions_timeline.py`

Pros:

- fewer files

Cons:

- mixes timeline expansion with trade-window summarization
- weakens discoverability

### Option C: Extract a larger report-row assembler bundle

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

- `neotrade3/analysis/attribution_trade_window.py`

Recommended function:

- `build_attribution_trade_window(trades: list[dict[str, Any]], *, segment_start_date: str, segment_top_date: str) -> dict[str, Any]`

Recommended output fields:

- `code_trades`
- `relevant_trades`
- `bought`
- `held_to_top`
- `first_buy_date`
- `first_sell_date`
- `latest_exit_reason`

Why create a new file:

- this helper is trade-window summarization, not positions timeline or reason wording
- a dedicated file keeps the contract discoverable and avoids overloading other owners

### 5.2 Script Boundary

The script should keep:

- building `trades_by_code`
- deciding when to call the helper
- passing `code_trades` into `_extract_execution_reason(...)`
- deriving final `primary_reason` / `reason_bucket`
- assembling final report rows

The script should no longer own:

- sorting one code's trades inline
- filtering `relevant_trades` inline
- deriving the window summary fields inline

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- sort trades by `(buy_date, sell_date)` before any derived-field access
- keep only trades where `buy_date <= segment_top_date`
- keep only trades where `sell_date` is blank or `sell_date >= segment_start_date`
- derive `bought` from whether `relevant_trades` is non-empty
- derive `held_to_top` from whether any relevant trade spans `segment_top_date`
- derive `first_buy_date` and `first_sell_date` from the first relevant trade after sorting
- derive `latest_exit_reason` from the relevant trade with the max `sell_date`

Important semantic note:

- this slice should not add new validation filters that the inline block does not currently perform

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_trade_window.py`

Minimum owner cases:

- sorts the input trades before deriving first-window fields
- keeps only trades overlapping the current segment window
- derives `held_to_top` and `latest_exit_reason` from the current overlap contract
- returns default empty fields when no relevant trade exists

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

## 6. Risks and Guardrails

Main risk:

- silently drifting the current overlap filter or first-trade ordering semantics

Guardrail:

- freeze the current sort key and overlap condition exactly

Secondary risk:

- broadening into code-level trade grouping or execution fallback logic

Guardrail:

- move only the pure per-code trade-window summarizer

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_trade_window.py`
2. move the trade-window summarizer there
3. switch the report script to consume the new owner
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the trade-window contract has one analysis owner
- the report script no longer owns the inline trade-window summary block
- `relevant_trades` ordering and summary fields stay unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
