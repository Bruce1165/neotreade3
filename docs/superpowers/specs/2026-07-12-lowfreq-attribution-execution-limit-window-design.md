Status: active
Owner: lowfreq / analysis
Scope: Narrow extraction of execution limit-up window detection from attribution report script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Execution Limit Window Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the execution fallback reason extraction.

This slice freezes only the `all_limit_up` window detection inside:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_extract_execution_reason(...)`

The goal is to:

- move the first-signal three-bar limit-up window detection out of the script
- reuse the existing `trade_block_reason` buy-side limit-up semantics instead of re-implementing one-price-board checks inline
- keep `_extract_execution_reason(...)` responsible for SQL access and fallback ordering
- preserve the current `LIMIT 3` window semantics and the current `execution_one_price_limit_only` behavior exactly

This design is not:

- a rewrite of `_extract_execution_reason(...)` as a whole
- a rewrite of `resolve_trade_block_reason(...)`
- an extraction of positions-full detection
- an extraction of chase-entry probing

Project-phase note:

- domain: `top200 attribution execution limit window`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the `rows -> all_limit_up` window predicate
- reusing `resolve_trade_block_reason(...)` for the buy-side limit-up / one-price-board contract
- switching `_extract_execution_reason(...)` to pass normalized bar payloads into that owner
- adding owner-focused tests for the limit-window predicate

Excluded:

- any change to the SQL query:
  - `ORDER BY trade_date ASC LIMIT 3`
- any change to `limit_up_pct`
- any change to `positions_full`
- any change to `chase_blocked`
- any change to fallback reason ordering

## 3. Existing Context

Current repository evidence shows:

- `_extract_execution_reason(...)` still contains an inline three-bar loop that derives `all_limit_up`:
  - [generate_lowfreq_top200_attribution_report.py:L618-L646](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L618-L646)
- that loop re-implements the same buy-side limit-up / one-price-board semantics already owned by:
  - [resolve_trade_block_reason](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/trade_block_reason.py#L6-L63)
- the trade-block owner already has focused tests anchoring:
  - limit-up buy block
  - one-price-only behavior
  - non-one-price pass-through
  - [test_lowfreq_engine_v16_trade_block_reason.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_trade_block_reason.py)
- current script tests anchor `_extract_execution_reason(...)` behavior but do not directly own the limit-window predicate:
  - [test_lowfreq_attribution_reasoning.py:L265-L389](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L265-L389)

The current problem is:

- the script still owns a local reimplementation of an already canonical trade-block rule
- the repeated one-price-board math does not belong in the consumer script
- the remaining logic is a pure window predicate over already fetched bars, which fits an M3 consumer-side owner

## 4. Approach Options

### Option A: Add an attribution-side execution-window helper that consumes normalized bars and delegates per-bar blocking to `resolve_trade_block_reason(...)` (Recommended)

- keep SQL access in the script
- move only the three-bar limit-window predicate into a shared owner

Pros:

- smallest slice that removes the last inline one-price-board loop
- explicitly reuses canonical trade-block semantics
- keeps attribution-specific `LIMIT 3` window policy outside the decision engine

Cons:

- the script still normalizes SQL tuples into bars

### Option B: Call `resolve_trade_block_reason(...)` inline from the script loop

Pros:

- no new owner file

Cons:

- still leaves the three-bar window contract inline in the script
- does not create a direct owner-focused test carrier for the window predicate

### Option C: Extend `trade_block_reason.py` to own the whole three-bar window policy

Pros:

- concentrates more execution gating logic in the decision owner

Cons:

- broadens M2 responsibility with an attribution-report consumer policy
- `LIMIT 3` is not a trade-execution universal rule; it is specific to this attribution explanation path

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add a new analysis owner:

- `neotrade3/analysis/attribution_execution_limit_window.py`

Recommended public function:

- `is_execution_limit_up_window(*, bars: list[dict[str, Any]], limit_up_pct: float, one_price_only: bool) -> bool`

Why a new file:

- `attribution_trade_window.py` owns trade overlap and exit-window projection, not entry-bar block detection
- this new predicate is still attribution-consumer policy, but it is distinct from text reasoning and distinct from trade overlap projection
- a dedicated file keeps the contract small and self-contained

### 5.2 Contract Freeze

The helper must preserve the current observable rule:

- return `False` for empty `bars`
- return `True` only when every bar in the provided window is buy-side `limit_up` blocked
- respect `one_price_only`
- respect `limit_up_pct`

The helper must not:

- read SQL rows directly
- inspect `positions_timeline`
- inspect `buy_signal_audits`
- inspect `chase_entry_snapshot`

### 5.3 Reuse Rule

Per bar, the helper should normalize to the `resolve_trade_block_reason(...)` input contract and call it with:

- `side="buy"`
- `block_on_limit_up=True`
- `block_on_limit_down=False`
- `only_one_price_limit=<current execution_one_price_limit_only>`
- unrelated constraints neutralized:
  - `trade_value=0.0`
  - `min_amount_cny=0.0`
  - `max_participation_rate=1.0`

Then treat only:

- `reason == "limit_up"`

as a positive hit for that bar.

### 5.4 Script Boundary

The script should keep:

- fetching the first three rows from `daily_prices`
- mapping SQL tuples into normalized bar dictionaries
- deciding that the fetched window begins at `first_signal`

The script should stop owning:

- the per-bar one-price-board and limit-up math
- the aggregate `all_limit_up` fold over the fetched window

### 5.5 Testing Strategy

Keep the existing script-focused tests:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

Add owner-focused tests in:

- `tests/unit/test_lowfreq_attribution_execution_limit_window.py`

Minimum owner cases:

- empty bars return `False`
- all bars limit-up => `True`
- one non-limit-up bar => `False`
- one-price-only rejects non-one-price limit-up bars

## 6. Risks and Guardrails

Main risk:

- accidentally dragging liquidity or participation-rate rules into the attribution helper

Guardrail:

- neutralize unrelated trade-block parameters and assert only on `reason == "limit_up"`

Secondary risk:

- accidentally changing the current “all bars must match” fold semantics

Guardrail:

- lock exact `all(...)` style behavior in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `attribution_execution_limit_window.py`
2. implement `is_execution_limit_up_window(...)` by delegating per-bar checks to `resolve_trade_block_reason(...)`
3. switch `_extract_execution_reason(...)` to normalize SQL rows and call the new owner
4. add owner-focused tests
5. run focused verification and syntax checks

## 8. Success Criteria

This slice is complete when:

- the script no longer owns one-price-board / limit-up math for the three-bar window
- the new helper reuses canonical trade-block semantics
- `_extract_execution_reason(...)` keeps the same SQL window and fallback flow
- owner-focused tests pass
- syntax verification passes
