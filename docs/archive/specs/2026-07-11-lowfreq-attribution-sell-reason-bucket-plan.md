Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report sell-reason bucket extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Sell Reason Bucket Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-sell-reason-bucket-design.md`

## 1. Goal

This plan covers only the next narrow report reasoning slice after the attribution block-reason wording extraction.

This slice only handles:

- the pure sell-reason bucket mapping used by the top200 attribution report
- reuse of the existing analysis owner for report reasoning helpers
- direct owner-focused tests plus the nearby consumer guard rerun

The goal is to:

- remove the inline sell-reason bucket mapping from the script
- keep report orchestration stable
- preserve bucket strings exactly

This slice does not:

- rewrite report reasoning flow
- rewrite engine sell reason production
- rewrite wording text

## 2. Starting Point

Current repository evidence shows:

- `_sell_reason_bucket(...)` is still inline in the report script
- the helper is consumed as a pure contract when `primary_reason` is derived from `latest_exit_reason`
- a focused consumer guard already exists in `test_lowfreq_attribution_reasoning.py`

So the correct next slice is:

- extract only the bucket mapping
- keep orchestration in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_sell_reason_bucket.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### ASRB-S1: Freeze observable bucket contract

Freeze the current bucket outputs:

- `回测结束平仓* -> 回测结束平仓`
- `板块见顶确认* -> sector_top_confirmed`
- `*见顶确认* / *见顶：* -> market_top_confirmed`
- `*跌破买入价止损* / *硬证伪退出* -> thesis_invalidated`
- unknown -> `other`

Freeze the priority order:

1. backtest closeout prefix
2. sector top confirmation
3. market top confirmation
4. thesis invalidation
5. fallback `other`

Completion check:

- no report flow control or wording text changes are included in this slice

### ASRB-S2: Extend the analysis owner

In `neotrade3/analysis/attribution_reasoning.py` add:

- `resolve_sell_reason_bucket(...)`

Implementation rules:

- accept only raw sell reason text
- normalize the local string input
- do not query DB
- do not compose report text
- do not alter report schema

Completion check:

- the bucket contract can be understood independently from the report script

### ASRB-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `resolve_sell_reason_bucket(...)`
- delete inline bucket mapping
- delegate `_sell_reason_bucket(...)` to the owner, or replace the call site directly

Do not change:

- `primary_reason` selection
- `latest_exit_reason` selection
- any report output fields

Completion check:

- the script no longer owns the bucket mapping inline

### ASRB-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_sell_reason_bucket.py`

Minimum owner cases:

- backtest closeout prefix
- sector top confirmation
- market top confirmation
- thesis invalidation
- unknown fallback

Completion check:

- the bucket contract has direct focused coverage

### ASRB-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_sell_reason_bucket.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_reasoning.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_sell_reason_bucket.py`

Completion check:

- owner tests pass
- nearby consumer guard passes
- syntax validation passes

### ASRB-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_sell_reason_bucket.py`

Must exclude:

- engine/API files
- unrelated report changes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into report orchestration

Guard:

- move only the pure bucket helper

Risk 2:

- silently drifting canonical bucket values

Guard:

- freeze strings exactly
- verify owner tests plus consumer guard

## 6. Success Criteria

This slice is complete when:

- the sell-reason bucket contract has one analysis owner
- the report script no longer owns the mapping inline
- bucket strings remain unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
