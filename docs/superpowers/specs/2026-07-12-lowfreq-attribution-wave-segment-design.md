Status: active
Owner: lowfreq / analysis
Scope: Narrow extraction of attribution wave-segment contract from scorecard script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Wave Segment Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the attribution artifact-payload extraction.

This slice freezes only the wave-segment contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_compute_wave_segment(...)`

The goal is to:

- move the wave-segment result contract into one analysis-side owner
- keep the script responsible for SQL reads and orchestration
- preserve the current three status outcomes exactly:
  - `missing_2025_prices`
  - `insufficient_history`
  - `ok`
- add direct owner-focused coverage for the segment result builder

This design is not:

- a rewrite of `_analyze_topk(...)`
- a rewrite of report-row projection
- a rewrite of daily audit reasoning
- a generic price-series analytics framework

Project-phase note:

- domain: `top200 attribution wave segment`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the wave-segment result payload builder from `_compute_wave_segment(...)`
- preserving the current failure statuses and success payload fields
- preserving the current segment-basis text and rounding semantics
- adding owner-focused tests for the segment result contract

Excluded:

- changing SQL queries against `daily_prices`
- changing `_load_price_series(...)`
- changing how `_analyze_topk(...)` computes `min_start` / `max_top`
- changing how failed segments become `build_attribution_segment_failed_row(...)`
- changing `segment_return_pct` consumption in row projection

## 3. Existing Context

Current repository evidence shows:

- the scorecard script still owns one dense segment-analysis helper:
  - [generate_lowfreq_top200_attribution_report.py:L218-L270](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L218-L270)
- the helper currently owns both:
  - status selection
  - success payload assembly
- downstream consumers already treat the returned object as a visible contract:
  - [generate_lowfreq_top200_attribution_report.py:L704-L708](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L704-L708)
  - [generate_lowfreq_top200_attribution_report.py:L725-L733](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L725-L733)
  - [generate_lowfreq_top200_attribution_report.py:L810-L818](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L810-L818)
- nearby tests already prove the contract matters downstream:
  - [test_lowfreq_attribution_report_row.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_report_row.py)
  - [test_lowfreq_attribution_reasoning.py:L195-L228](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L195-L228)

The current problem is:

- the script still owns the canonical shape of the segment result
- failure-state payloads and success-state payloads are mixed into a data-access helper
- there is no single analysis owner for the segment contract itself

## 4. Approach Options

### Option A: Add one attribution-specific wave-segment contract owner, and keep SQL plus row selection in the script (Recommended)

- move only payload projection and status-specific result assembly into one owner
- keep `rows_2025` query, `top_row` selection, window loading, and `start_row` selection in the script

Pros:

- extracts the real visible contract without widening into data-access changes
- matches the current owner-per-contract refactor path
- preserves the script as the source of orchestration and repository reads

Cons:

- `_compute_wave_segment(...)` still performs data selection work in the script

### Option B: Move the entire `_compute_wave_segment(...)` helper into analysis

Pros:

- larger reduction in script size

Cons:

- pulls sqlite reads and `_load_price_series(...)` coupling into the new owner
- broadens the slice beyond the current contract extraction objective

### Option C: Keep the function inline and only add comments

Pros:

- smallest code movement

Cons:

- leaves the canonical segment contract in the script
- gives no reusable owner value

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new analysis owner:

- `neotrade3/analysis/attribution_wave_segment.py`

Recommended public functions:

- `build_missing_wave_segment(...) -> dict[str, Any]`
- `build_insufficient_history_wave_segment(...) -> dict[str, Any]`
- `build_ok_wave_segment(...) -> dict[str, Any]`

Why this file:

- the extracted concern is the wave-segment result contract, not SQL access
- a dedicated file keeps success and failure payloads discoverable and prevents overloading row-projection owners

### 5.2 Contract Freeze

The owner must preserve the current visible payloads exactly.

Failure payload 1:

- `status="missing_2025_prices"`
- `code=str(code)`

Failure payload 2:

- `status="insufficient_history"`
- `code=str(code)`
- `top_date=top_date.isoformat()`
- `top_close=round(top_close, 4)`

Success payload:

- `status="ok"`
- `code=str(code)`
- `segment_window_trading_days=int(lookback_trading_days)`
- `start_date=str(start_row["trade_date"])`
- `start_close=round(start_close, 4)`
- `top_date=top_date.isoformat()`
- `top_close=round(top_close, 4)`
- `segment_return_pct=round(float(segment_return), 2)`
- `segment_basis="见顶日前180交易日窗口内最低收盘价 -> 2025年最高收盘价"`

The owner must not:

- query sqlite
- load price windows
- decide which row is `top_row` or `start_row`
- mutate row dictionaries

### 5.3 Script Boundary

The script should keep:

- loading `rows_2025`
- selecting `top_row`
- calling `_load_price_series(...)`
- selecting `start_row`
- computing `segment_return`

The script should stop owning:

- the literal success and failure payload assembly

This keeps the slice narrow: contract leaves the script, orchestration stays in place.

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_wave_segment.py`

Minimum owner cases:

- projects the current `missing_2025_prices` payload
- projects the current `insufficient_history` payload with rounding
- projects the current `ok` payload with current coercions, rounding, and basis text

Nearby consumer rerun:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - syntax verification only; this slice does not need a broad integration harness

## 6. Risks and Guardrails

Main risk:

- silently changing `segment_basis` text or the rounding of `top_close/start_close/segment_return_pct`

Guardrail:

- lock all visible payload fields and rounding rules in owner-focused tests

Secondary risk:

- broadening the slice into data-access extraction

Guardrail:

- keep SQL, row selection, and window loading in the script

## 7. Implementation Outline

Planned steps:

1. add `attribution_wave_segment.py`
2. implement the three payload builders
3. switch `_compute_wave_segment(...)` to call those builders
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the wave-segment result contract has one analysis-side owner
- the script no longer owns the literal success and failure payloads
- SQL and window orchestration remain in the script
- downstream payload shape remains unchanged
- owner-focused tests pass
- syntax verification passes
