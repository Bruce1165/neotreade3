Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report block-reason wording extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Block Reason Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-block-reason-design.md`

## 1. Goal

This plan covers only the next narrow report reasoning slice after the API execution block reason cleanup.

This slice only handles:

- the pure block-reason wording mapping used by the top200 attribution report
- one analysis owner for that wording contract
- direct owner-focused tests and one nearby consumer guard rerun

The goal is to:

- remove the inline wording mapping from the script
- keep `_extract_execution_reason(...)` orchestration stable
- preserve visible Chinese copy exactly

This slice does not:

- rewrite report orchestration
- rewrite engine/API normalization
- rewrite late-trade suffix handling

## 2. Starting Point

Current repository evidence shows:

- `_audit_block_reason_text(...)` is still inline in the script
- `_extract_execution_reason(...)` consumes that helper but otherwise owns filtering, fallback, and suffix assembly
- existing tests already cover one consumer path through `_extract_execution_reason(...)`

So the correct next slice is:

- extract only the wording mapping
- keep orchestration in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_block_reason.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### ABR-S1: Freeze observable wording contract

Freeze the current visible strings:

- `chase_entry_blocked -> 信号存在但因追高型买点被硬禁`
- `execution_signal_gate_blocked -> 信号存在但因执行信号闸门被阻断`
- `entry_window_missed -> 信号存在但执行窗口失效`
- `positions_full -> 信号存在但同期仓位已满`
- `cash_insufficient -> 信号存在但资金不足`
- unknown -> `""`

Freeze the priority order:

- `blocked_reason` checks run before `execution_block_reason` checks

Completion check:

- no orchestration or suffix logic is included in this slice

### ABR-S2: Implement the analysis owner

Create:

- `neotrade3/analysis/attribution_reasoning.py`

Add:

- `resolve_audit_block_reason_text(...)`

Implementation rules:

- accept a raw audit entry dictionary
- normalize only local string reads
- do not query DB
- do not compose late-trade suffix
- do not alter report schema

Completion check:

- the wording contract can be understood independently from script orchestration

### ABR-S3: Switch the script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import the new helper
- delete inline wording mapping
- delegate `_audit_block_reason_text(...)` to the new owner, or replace the call site with the new owner directly

Do not change:

- `_extract_execution_reason(...)` flow
- latest blocking-audit selection
- late-trade suffix composition

Completion check:

- the script no longer owns the wording mapping inline

### ABR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_block_reason.py`

Minimum owner cases:

- `chase_entry_blocked`
- `execution_signal_gate_blocked`
- `entry_window_missed`
- `positions_full`
- `cash_insufficient`
- unknown fallback

Completion check:

- the wording contract has direct focused coverage

### ABR-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_block_reason.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_reasoning.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_block_reason.py`

Completion check:

- owner tests pass
- nearby consumer guard passes
- syntax validation passes

### ABR-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_block_reason.py`

Must exclude:

- engine/API files
- unrelated script/report changes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally pulling `_extract_execution_reason(...)` into the new owner

Guard:

- move only the wording mapping

Risk 2:

- changing visible report text or rule priority

Guard:

- freeze strings exactly
- verify owner tests plus consumer guard

## 6. Success Criteria

This slice is complete when:

- the block-reason wording contract has one analysis owner
- the report script no longer owns the mapping inline
- visible wording remains unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
