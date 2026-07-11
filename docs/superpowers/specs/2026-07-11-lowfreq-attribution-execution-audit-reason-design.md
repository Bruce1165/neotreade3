Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report execution-audit primary reason contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Execution Audit Reason Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the attribution candidate-only primary reason extraction.

This slice freezes only the pure execution-audit precedence contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L698-L729)
  - `_extract_execution_reason(...)` pre-check block

The goal is to:

- move the pure buy-signal-audit explanation precedence into one analysis owner
- keep SQL and engine fallback logic in the report script
- preserve current returned strings exactly
- add direct owner-focused coverage for the contract

This design is not:

- a rewrite of `_extract_execution_reason(...)`
- a rewrite of the later SQL-based execution fallback
- a rewrite of `_analyze_topk(...)`
- a rewrite of engine execution semantics

Project-phase note:

- domain: `top200 attribution report execution audit reason`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- selection of the latest pre-top `block` audit entry
- translation of that audit into visible Chinese reason text
- late-trade suffix composition and late-trade fallback text
- reuse of the existing analysis owner file
- owner-focused tests for priority and fallback behavior

Excluded:

- SQL reads for recent price bars
- full-book checks
- chase-entry snapshot probing
- changes to report output schema
- changes to engine/API contracts

## 3. Existing Context

Current repository evidence shows:

- `_extract_execution_reason(...)` starts with a pure list-based precedence block before any SQL/engine fallback:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L714-L729)
- the visible wording for audit block reasons is already owned by the shared analysis helper:
  - [attribution_reasoning.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py#L9-L22)
- there are already nearby consumer tests locking this precedence behavior:
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L303-L347)
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L350-L387)

The problem is:

- the pre-check precedence contract is still embedded inline in the script
- that block is pure report-consumer reasoning over already-produced audit rows and trades
- the later half of `_extract_execution_reason(...)` is not equally narrow because it mixes SQL and engine probes

## 4. Approach Options

### Option A: Move only the pre-fallback execution-audit precedence into the existing analysis owner and keep SQL/engine fallback in the script (Recommended)

- extend `neotrade3/analysis/attribution_reasoning.py`
- move only the list-based audit/trade explanation contract
- keep the script responsible for DB and engine fallback

Pros:

- isolates a real contract kernel with minimal risk
- reuses the existing report reasoning owner
- avoids dragging IO/orchestration into the owner

Cons:

- `_extract_execution_reason(...)` remains partially inline

### Option B: Move the whole `_extract_execution_reason(...)` function into the analysis owner

Pros:

- removes more inline script code

Cons:

- broadens the slice into SQL and engine calls
- increases regression surface
- weakens the current report-orchestration boundary

### Option C: Leave the logic inline and only add more tests

Pros:

- zero production movement

Cons:

- preserves duplicate consumer reasoning inside the script
- misses the established owner-consolidation direction

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Extend the existing report-side owner:

- `neotrade3/analysis/attribution_reasoning.py`

Recommended function:

- `resolve_execution_audit_primary_reason(...) -> str`

Recommended inputs:

- `buy_signal_audits: list[dict[str, Any]]`
- `code_trades: list[dict[str, Any]]`
- `segment_top_date: str`

Why keep it in the same file:

- it is adjacent to the other attribution reasoning helpers
- it composes existing `resolve_audit_block_reason_text(...)`
- it remains consumer-side reasoning, not producer ownership

### 5.2 Script Boundary

The script should keep:

- deciding when the row is in the `picked_not_bought` branch
- later SQL-driven limit-up/full-book/chase-entry fallback
- final assignment of `primary_reason`

The script should no longer own:

- filtering buy-signal-audit rows to the pre-top window
- choosing the latest `block` audit
- composing the `，见顶后才成交` suffix
- emitting the plain late-trade fallback text

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- only consider audit rows whose `date <= segment_top_date` when `segment_top_date` is present
- only consider audit rows whose `action_type == "block"`
- choose the latest blocking audit by `date`
- translate that audit through `resolve_audit_block_reason_text(...)`
- if a reason exists and there are late trades, append `，见顶后才成交`
- if no mapped reason exists but there are late trades, return `信号存在但见顶后才成交`
- if neither branch matches, return an empty string and let the script continue to fallback logic

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_execution_audit_reason.py`

Minimum owner cases:

- mapped block reason wins and appends late-trade suffix
- plain late-trade fallback survives without mapped audit reason
- returns empty string when neither audit reason nor late trade exists

Keep and re-run nearby consumer guards:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L303-L347)
- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L350-L387)

## 6. Risks and Guardrails

Main risk:

- broadening into SQL/engine fallback and turning a narrow consumer contract into a mixed orchestration slice

Guardrail:

- move only the pre-fallback list-based reasoning block

Secondary risk:

- drifting current visible wording or suffix rules

Guardrail:

- preserve strings exactly
- verify direct owner tests plus existing consumer guards

## 7. Implementation Outline

Planned steps:

1. extend `neotrade3/analysis/attribution_reasoning.py`
2. move the execution-audit precedence block there
3. switch `_extract_execution_reason(...)` to call the owner first
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the execution-audit precedence contract has one analysis owner
- `_extract_execution_reason(...)` no longer owns that pre-fallback block inline
- returned strings stay unchanged
- owner-focused tests pass
- nearby consumer guards pass
- syntax verification passes
