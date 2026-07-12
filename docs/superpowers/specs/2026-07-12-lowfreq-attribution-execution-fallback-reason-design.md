Status: active
Owner: lowfreq / analysis
Scope: Narrow extraction of execution fallback reason ordering from attribution report script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Execution Fallback Reason Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the simple daily-audit payload extraction.

This slice freezes only the remaining fallback reason ordering inside:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_extract_execution_reason(...)`

The goal is to:

- move the final fallback reason selection out of the script and into the existing reasoning owner
- keep `_extract_execution_reason(...)` responsible for data access and boolean derivation
- preserve current reason ordering and current Chinese reason text exactly
- continue shrinking the script toward a thin consumer without broadening into execution-state extraction

This design is not:

- a rewrite of `_extract_execution_reason(...)` as a whole
- a rewrite of the existing `resolve_execution_audit_primary_reason(...)`
- an extraction of SQL access, price fetching, or `engine._chase_entry_snapshot(...)`
- a rewrite of execution mode semantics

Project-phase note:

- domain: `top200 attribution execution fallback reason`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the fallback reason ordering after `resolve_execution_audit_primary_reason(...)` returns empty
- extending `attribution_reasoning.py` as the canonical owner of execution reason text selection
- switching the script to pass derived booleans into the new owner
- adding owner-focused tests for fallback ordering and canonical text reuse

Excluded:

- any change to how `buy_signal_audits` are read or filtered
- any change to how limit-up rows are fetched or interpreted
- any change to how positions-full is detected
- any change to how chase-entry blocked state is derived

## 3. Existing Context

Current repository evidence shows:

- `_extract_execution_reason(...)` already delegates the primary audit path to:
  - [resolve_execution_audit_primary_reason](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py#L25-L44)
- after that delegation, the script still owns a second-layer fallback reason ordering:
  - [generate_lowfreq_top200_attribution_report.py:L605-L675](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L605-L675)
- the reasoning owner already contains canonical reason text mapping for:
  - `blocked_reason == "chase_entry_blocked"`
  - `execution_block_reason == "positions_full"`
  - [resolve_audit_block_reason_text](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_reasoning.py#L9-L22)
- existing tests already anchor both the owner and the script observable behavior:
  - [test_lowfreq_attribution_block_reason.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_block_reason.py)
  - [test_lowfreq_attribution_execution_audit_reason.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_execution_audit_reason.py)
  - [test_lowfreq_attribution_reasoning.py:L265-L389](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L265-L389)

The current problem is:

- the script still contains the final text-selection policy for the non-audit fallback path
- two fallback strings already have canonical owner text upstream, but the script still returns them inline
- the observable ordering of fallback reasons is a reasoning concern, not a data-access concern

## 4. Approach Options

### Option A: Add one reasoning helper for execution fallback ordering and pass derived booleans into it (Recommended)

- keep all SQL, context lookup, and snapshot probing in the script
- move only the final fallback reason choice into `attribution_reasoning.py`

Pros:

- smallest slice that removes the remaining inline fallback reason policy
- fits the existing reasoning owner
- reuses canonical text mapping already present in `resolve_audit_block_reason_text(...)`

Cons:

- the script still computes `all_limit_up`, `positions_full`, and `chase_blocked`

### Option B: Extract the whole `_extract_execution_reason(...)` function

Pros:

- removes more script logic at once

Cons:

- too broad for one narrow slice
- mixes SQL access, context probing, engine calls, and reason selection

### Option C: Leave the fallback path inline

Pros:

- no new symbol

Cons:

- leaves reasoning policy split across script and owner
- duplicates canonical text sources for `positions_full` and `chase_entry_blocked`

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Extend the existing owner:

- `neotrade3/analysis/attribution_reasoning.py`

Recommended new public function:

- `resolve_execution_fallback_reason(*, all_limit_up: bool, positions_full: bool, chase_blocked: bool) -> str`

Why this file:

- the file already owns execution-related reason text resolution
- the remaining policy is a pure ordering decision over already derived booleans
- this keeps execution reason policy co-located instead of scattering it across the consumer script

### 5.2 Script Boundary

The script should keep:

- deriving `first_signal`
- fetching the first 3 daily-price rows
- deciding whether the early window is all limit-up
- deciding whether the book is full under bounded mode
- probing the chase-entry snapshot and deriving `chase_blocked`

The script should stop owning:

- the final fallback string ordering among:
  - all limit-up
  - positions full
  - chase blocked
  - generic fallback

### 5.3 Contract Freeze

The new helper must preserve this exact order:

1. `all_limit_up` -> `"信号存在但连续涨停，无法成交"`
2. `positions_full` -> `"信号存在但同期仓位已满"`
3. `chase_blocked` -> `"信号存在但因追高型买点被硬禁"`
4. otherwise -> `"信号存在但未形成实际成交，需复核执行窗口"`

Additional rule:

- the `positions_full` and `chase_blocked` texts should come from existing canonical mapping where possible

The helper must not:

- inspect SQL rows directly
- inspect signals directly
- append late-trade suffixes
- replace or broaden `resolve_execution_audit_primary_reason(...)`

### 5.4 Testing Strategy

Keep the existing script-focused tests:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

Add owner-focused tests in a new carrier:

- `tests/unit/test_lowfreq_attribution_execution_fallback_reason.py`

Minimum owner cases:

- all-limit-up has highest priority
- positions-full uses canonical text
- chase-blocked uses canonical text
- generic fallback remains unchanged

## 6. Risks and Guardrails

Main risk:

- accidentally moving data-access logic together with the reason ordering

Guardrail:

- derive only booleans in the script and pass them into the owner

Secondary risk:

- accidentally changing fallback ordering or text

Guardrail:

- lock exact ordering and exact returned strings in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `resolve_execution_fallback_reason(...)` to `attribution_reasoning.py`
2. switch `_extract_execution_reason(...)` to compute booleans and delegate final fallback text to the owner
3. add owner-focused tests
4. run focused verification and syntax checks

## 8. Success Criteria

This slice is complete when:

- execution fallback reason ordering is owned in `attribution_reasoning.py`
- `_extract_execution_reason(...)` keeps the same data-access behavior
- current reason text and precedence remain unchanged
- owner-focused tests pass
- syntax verification passes
