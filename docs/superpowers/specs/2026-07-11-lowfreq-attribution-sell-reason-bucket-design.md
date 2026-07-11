Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report sell-reason bucket contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Sell Reason Bucket Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the attribution block-reason wording extraction.

This slice freezes only the pure sell-reason bucket contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_sell_reason_bucket(...)`

The goal is to:

- move the pure sell-reason bucket mapping into one analysis owner
- keep report orchestration in the script
- preserve current bucket strings exactly
- add direct owner-focused coverage for the bucket contract

This design is not:

- a rewrite of report chapter logic
- a rewrite of sell signal generation
- a rewrite of `_extract_execution_reason(...)`
- a rewrite of report wording or copy

Project-phase note:

- domain: `top200 attribution report sell reason bucket`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- report-side mapping from raw sell reason text to bucket strings
- reuse of the existing analysis owner file
- owner-focused tests for the bucket contract

Excluded:

- changes to engine-side sell reason production
- changes to report wording text
- changes to late-trade reasoning
- changes to report output schema

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one inline bucket helper:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L790-L800)
- the bucket is already consumed as a pure contract inside report orchestration:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L956-L962)
- nearby consumer tests already lock the observable mapping:
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L26-L32)
- the analysis owner created in the previous slice already hosts adjacent report reasoning helpers:
  - [attribution_reasoning.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py)

The problem is:

- the bucket contract is still embedded inline in the report script
- the helper is pure and self-contained
- the helper belongs to consumer-side attribution reasoning, not engine ownership

## 4. Approach Options

### Option A: Move only the pure sell-reason bucket mapping into the existing analysis owner and keep report orchestration in the script (Recommended)

- extend `neotrade3/analysis/attribution_reasoning.py`
- move only the raw sell-reason text to bucket mapping
- keep all report orchestration and reason selection in the script

Pros:

- isolates a real contract kernel with minimal blast radius
- reuses the report reasoning owner introduced in the previous slice
- preserves current orchestration boundary

Cons:

- the script still keeps surrounding orchestration

### Option B: Extract a larger attribution reasoning bundle from the script

Pros:

- removes more inline script code

Cons:

- broadens into mixed concerns beyond the proven narrow cut
- increases regression surface without new evidence

### Option C: Move the bucket helper into `decision_engine`

Pros:

- would place more lowfreq helpers near engine contracts

Cons:

- raw Chinese sell reason text interpretation is a report consumer concern
- would blur producer/consumer ownership

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Extend the existing report-side owner:

- `neotrade3/analysis/attribution_reasoning.py`

Recommended function:

- `resolve_sell_reason_bucket(sell_reason: str) -> str`

Why keep it in the same file:

- it is adjacent to `resolve_audit_block_reason_text(...)`
- both functions are report-consumer reasoning/projection helpers
- this avoids scattering tiny report contracts across multiple files

### 5.2 Script Boundary

The script should keep:

- selection of `latest_exit_reason`
- orchestration that chooses `primary_reason`
- assignment of `reason_bucket`

The script should no longer own:

- the direct raw-text-to-bucket mapping rules

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- `reason.startswith("回测结束平仓") -> "回测结束平仓"`
- `"板块见顶确认" in reason -> "sector_top_confirmed"`
- `"见顶确认" in reason or "见顶：" in reason -> "market_top_confirmed"`
- `"跌破买入价止损" in reason or "硬证伪退出" in reason -> "thesis_invalidated"`
- otherwise -> `"other"`

Priority order must remain unchanged:

1. backtest closeout prefix
2. sector top confirmation
3. market top confirmation
4. thesis invalidation
5. fallback `other`

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_sell_reason_bucket.py`

Minimum owner cases:

- backtest closeout prefix
- sector top confirmation
- market top confirmation
- thesis invalidation
- unknown fallback

Keep and re-run nearby consumer guard:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L26-L32)

## 6. Risks and Guardrails

Main risk:

- broadening into full report reasoning orchestration

Guardrail:

- move only the pure bucket helper

Secondary risk:

- drifting canonical bucket strings used downstream

Guardrail:

- preserve strings exactly
- verify direct owner tests plus the consumer guard

## 7. Implementation Outline

Planned steps:

1. extend `neotrade3/analysis/attribution_reasoning.py`
2. move the bucket helper there
3. switch the report script to import the new helper
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the sell-reason bucket contract has one analysis owner
- the report script no longer owns the mapping inline
- bucket strings stay unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
