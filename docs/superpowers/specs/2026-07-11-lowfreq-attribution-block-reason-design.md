Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report block-reason wording contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Block Reason Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the API execution block reason projection cleanup.

This slice freezes only the pure block-reason wording contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_audit_block_reason_text(...)`

The goal is to:

- move the pure report-side wording mapping into one shared owner
- keep `_extract_execution_reason(...)` orchestration inside the script
- preserve current Chinese wording exactly
- add direct owner-focused coverage for the wording contract

This design is not:

- a rewrite of `_extract_execution_reason(...)`
- a rewrite of report stage selection
- a rewrite of engine-side blocked reason normalization
- a rewrite of report chapter structure

Project-phase note:

- domain: `top200 attribution report block reason wording`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- report-side mapping from `blocked_reason` / `execution_block_reason` to Chinese explanation text
- one new owner module under `neotrade3/analysis/`
- owner-focused tests for the wording contract

Excluded:

- changes to engine or API normalization behavior
- changes to `_extract_execution_reason(...)` flow control
- changes to late-trade suffix wording
- changes to report output schema

## 3. Existing Context

Current repository evidence shows:

- the attribution report still owns one inline wording helper:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L688-L701)
- the surrounding orchestration is already separate and should stay in the script:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L704-L735)
- nearby consumer-grade tests already lock one visible path through `_extract_execution_reason(...)`:
  - [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L303-L347)
- the upstream blocked reason contract is already normalized elsewhere and should not be redefined here:
  - [buy_signal_audit_contract.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/buy_signal_audit_contract.py#L6-L32)
  - [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L16633-L16648)

The problem is:

- report wording is currently embedded inline in the script
- the helper is pure and self-contained
- the helper belongs to report-side reasoning, not engine ownership

## 4. Approach Options

### Option A: Extract only the pure report wording mapping into an analysis owner and keep `_extract_execution_reason(...)` in the script (Recommended)

- add one small owner module under `neotrade3/analysis/`
- move only the `blocked_reason` / `execution_block_reason` to Chinese text mapping
- keep block selection and late-trade suffix logic in the script

Pros:

- isolates a real contract kernel without broadening into report orchestration
- preserves current script ownership of sequencing and fallbacks
- keeps engine/API contracts untouched

Cons:

- the script still keeps orchestration code around the helper

### Option B: Extract the full `_extract_execution_reason(...)` logic

Pros:

- removes more inline script code

Cons:

- broadens into DB queries, top-date filtering, and late-trade composition
- increases regression surface without evidence that the full path is the next narrow cut

### Option C: Move the wording logic into `decision_engine`

Pros:

- would place more helpers near lowfreq contracts

Cons:

- report-specific Chinese explanation copy is not an engine rule kernel
- would blur the consumer boundary

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add a report-side owner:

- `neotrade3/analysis/attribution_reasoning.py`

Recommended function:

- `resolve_audit_block_reason_text(entry: dict[str, Any]) -> str`

Why this layer:

- the helper is a consumer-facing reasoning/projection function
- it does not define engine semantics
- it is currently consumed only by the top200 attribution report

### 5.2 Script Boundary

The script should keep:

- `_extract_execution_reason(...)`
- latest blocking audit selection
- late-trade suffix composition:
  - `"{reason}，见顶后才成交"`
  - `"信号存在但见顶后才成交"`

The script should no longer own:

- the direct mapping from block-reason buckets to Chinese explanation text

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- `blocked_reason=chase_entry_blocked` -> `信号存在但因追高型买点被硬禁`
- `blocked_reason=execution_signal_gate_blocked` -> `信号存在但因执行信号闸门被阻断`
- `execution_block_reason=entry_window_missed` -> `信号存在但执行窗口失效`
- `execution_block_reason=positions_full` -> `信号存在但同期仓位已满`
- `execution_block_reason=cash_insufficient` -> `信号存在但资金不足`
- otherwise -> `""`

Priority must remain unchanged:

- `blocked_reason` wording checks run before `execution_block_reason` wording checks

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_block_reason.py`

Minimum owner cases:

- maps `chase_entry_blocked`
- maps `execution_signal_gate_blocked`
- maps `entry_window_missed`
- maps `positions_full`
- maps `cash_insufficient`
- returns empty string for unknown reasons

Keep and re-run nearby consumer guard:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L303-L347)

## 6. Risks and Guardrails

Main risk:

- broadening this slice into full attribution reasoning orchestration

Guardrail:

- move only the pure wording helper

Secondary risk:

- drifting visible Chinese copy used in report outputs

Guardrail:

- preserve strings exactly
- verify direct owner tests plus existing consumer guard

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_reasoning.py`
2. move the wording helper there
3. switch the report script to import the new helper
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the report block-reason wording contract has one owner
- the script no longer owns the wording mapping inline
- report wording stays unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
