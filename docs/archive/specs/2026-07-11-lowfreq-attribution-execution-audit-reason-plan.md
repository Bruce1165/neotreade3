Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report execution-audit primary reason extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Execution Audit Reason Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-execution-audit-reason-design.md`

## 1. Goal

This plan covers only the next narrow report reasoning slice after the attribution candidate-only primary reason extraction.

This slice only handles:

- the pre-fallback execution-audit precedence contract used by `_extract_execution_reason(...)`
- reuse of the existing analysis owner for report reasoning helpers
- direct owner-focused tests plus nearby consumer guard reruns

The goal is to:

- remove the inline pre-fallback reasoning block from the script
- keep SQL and engine fallback logic stable
- preserve returned strings exactly

This slice does not:

- rewrite the whole `_extract_execution_reason(...)`
- rewrite SQL-based execution fallback
- rewrite report row assembly

## 2. Starting Point

Current repository evidence shows:

- `_extract_execution_reason(...)` begins with a pure list-based audit/trade reasoning block before any DB probing
- the visible wording for block reasons is already centralized in `resolve_audit_block_reason_text(...)`
- existing consumer tests already lock the precedence and late-trade wording

So the correct next slice is:

- extract only the audit/trade precedence block
- keep later fallback heuristics in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_execution_audit_reason.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### AEAR-S1: Freeze observable contract

Freeze the visible behavior:

- mapped blocking audit reason wins
- late trades append `，见顶后才成交` when a mapped blocking reason exists
- late trades alone return `信号存在但见顶后才成交`
- no mapped audit reason and no late trade return an empty string

Freeze the selection algorithm:

1. if `segment_top_date` exists, keep only audits with `date <= segment_top_date`
2. keep only rows where `action_type == "block"`
3. choose the latest blocking row by `date`
4. translate that row through `resolve_audit_block_reason_text(...)`
5. apply the late-trade suffix or fallback text exactly as today

Completion check:

- no SQL or engine behavior is included in this slice

### AEAR-S2: Extend the analysis owner

In `neotrade3/analysis/attribution_reasoning.py` add:

- `resolve_execution_audit_primary_reason(...)`

Implementation rules:

- accept only `buy_signal_audits`, `code_trades`, and `segment_top_date`
- reuse `resolve_audit_block_reason_text(...)`
- normalize only local `date` / `action_type` / `buy_date` reads
- do not query DB
- do not call engine methods
- do not compose report rows

Completion check:

- the contract can be understood independently from the script fallback

### AEAR-S3: Switch the report script to a thinner consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `resolve_execution_audit_primary_reason(...)`
- replace the inline pre-fallback block in `_extract_execution_reason(...)`
- keep the rest of the function unchanged

Do not change:

- the SQL queries
- limit-up/full-book/chase-entry checks
- branch selection for `picked_not_bought`

Completion check:

- `_extract_execution_reason(...)` only delegates the pre-fallback contract

### AEAR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_execution_audit_reason.py`

Minimum owner cases:

- mapped blocking audit plus late-trade suffix
- late-trade fallback without mapped audit reason
- empty-string fallback without usable audit reason or late trade

Completion check:

- the contract has direct focused coverage

### AEAR-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_execution_audit_reason.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_reasoning.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_execution_audit_reason.py`

Completion check:

- owner tests pass
- nearby consumer guards pass
- syntax validation passes

### AEAR-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_execution_audit_reason.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally pulling SQL/engine fallback into the owner

Guard:

- move only the pre-fallback list-based reasoning block

Risk 2:

- silently drifting visible wording or suffix rules

Guard:

- freeze strings exactly
- verify focused owner tests plus existing consumer guards

## 6. Success Criteria

This slice is complete when:

- the execution-audit precedence contract has one analysis owner
- the report script no longer owns that block inline
- returned strings remain unchanged
- owner-focused tests pass
- nearby consumer guards pass
- syntax verification passes
