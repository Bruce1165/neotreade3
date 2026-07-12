Status: active
Owner: lowfreq / analysis
Scope: Narrow extraction of attribution ranking row payload from scorecard script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Ranking Payload Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the wave-segment extraction.

This slice freezes only the ranking row payload that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_load_top_ranking(...)`

The goal is to:

- move the visible ranking row contract into one analysis-side owner
- keep the script responsible for SQL and row ordering
- preserve the current ranking JSON row shape exactly
- add direct owner-focused coverage for the row payload

This design is not:

- a rewrite of `_a_share_universe_sql()`
- a rewrite of the ranking query
- a rewrite of ranking JSON file output
- a generic market screener ranking framework

Project-phase note:

- domain: `top200 attribution ranking payload`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the ranking row dict projection from `_load_top_ranking(...)`
- preserving current coercions and rounding
- preserving the current literal `price_basis`
- adding owner-focused tests for the payload builder

Excluded:

- changing the SQL text
- changing `ORDER BY annual_return_pct DESC, b.code ASC`
- changing `LIMIT ?`
- changing `ranking_path.write_text(...)`

## 3. Existing Context

Current repository evidence shows:

- the script still owns the canonical ranking row payload:
  - [generate_lowfreq_top200_attribution_report.py:L136-L196](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L136-L196)
- the output is externally visible through:
  - [generate_lowfreq_top200_attribution_report.py:L928-L933](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L928-L933)
- downstream code consumes the row fields directly:
  - [generate_lowfreq_top200_attribution_report.py:L704-L733](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L704-L733)
  - [generate_lowfreq_top200_attribution_report.py:L810-L815](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L810-L815)

The current problem is:

- the visible ranking payload is still embedded inside a query helper
- SQL access and payload projection remain mixed together
- there is no single owner for the ranking row contract

## 4. Approach Options

### Option A: Add one attribution-specific ranking row payload owner, and keep SQL plus ordering in the script (Recommended)

- move only row projection into one owner
- keep query text, execute, and enumerate ordering in the script

Pros:

- extracts the visible contract with minimal regression surface
- matches the current owner-per-contract extraction path
- avoids broadening into data-access changes

Cons:

- `_load_top_ranking(...)` still owns the sqlite query

### Option B: Move the entire `_load_top_ranking(...)` helper into analysis

Pros:

- larger script shrink

Cons:

- pulls query text and DB coupling into the new owner
- broadens the slice beyond contract extraction

### Option C: Keep the row payload inline

Pros:

- smallest movement

Cons:

- leaves the visible JSON contract in the script

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new analysis owner:

- `neotrade3/analysis/attribution_ranking_payload.py`

Recommended public function:

- `build_attribution_ranking_row(...) -> dict[str, Any]`

Why this file:

- the extracted concern is row projection for a report-side artifact
- a dedicated file keeps the ranking contract discoverable and avoids mixing it into row-projection or artifact-envelope owners

### 5.2 Contract Freeze

The owner must preserve the current visible row fields exactly:

- `rank`
- `code`
- `name`
- `sector`
- `first_trade_date`
- `last_trade_date`
- `first_close`
- `last_close`
- `annual_return_pct`
- `price_basis`

Current coercions and literals must stay unchanged:

- `rank=int(rank)`
- `code=str(code)`
- `name=str(name or "")`
- `sector=str(sector or "")`
- `first_trade_date=str(first_trade_date)`
- `last_trade_date=str(last_trade_date)`
- `first_close=round(float(first_close), 4)`
- `last_close=round(float(last_close), 4)`
- `annual_return_pct=round(float(annual_return_pct), 2)`
- `price_basis="未复权收盘价"`

The owner must not:

- execute SQL
- sort rows
- assign ranks automatically

### 5.3 Script Boundary

The script should keep:

- the ranking SQL
- the database call
- `enumerate(rows, start=1)`

The script should stop owning:

- the literal dict projection for each ranking row

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_ranking_payload.py`

Minimum owner cases:

- projects the current row payload with current coercions
- keeps empty-string fallback for `name` and `sector`
- preserves 4-decimal price rounding and 2-decimal return rounding

## 6. Risks and Guardrails

Main risk:

- silently changing `price_basis` or rounding semantics

Guardrail:

- lock all visible fields and rounding behavior in owner-focused tests

Secondary risk:

- broadening the slice into SQL extraction

Guardrail:

- keep query text, execute, and rank ordering in the script

## 7. Implementation Outline

Planned steps:

1. add `attribution_ranking_payload.py`
2. implement `build_attribution_ranking_row(...)`
3. switch `_load_top_ranking(...)` row assembly to the owner
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the ranking row contract has one analysis-side owner
- the script no longer owns the inline row dict projection
- SQL and ordering remain in the script
- ranking JSON row shape remains unchanged
- owner-focused tests pass
- syntax verification passes
