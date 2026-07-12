Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report primary reason decision extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Primary Reason Decision Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-primary-reason-decision-design.md`

## 1. Goal

This plan covers only the next narrow report-prep slice after the attribution aggregate summary extraction.

This slice only handles:

- the pure primary reason priority selector used inline in `_analyze_topk(...)`
- reuse of one dedicated reasoning owner
- direct owner-focused tests plus a nearby report regression rerun

The goal is to:

- remove the inline primary reason branch from the script
- keep upstream component reason computation stable
- preserve current branch priority semantics exactly

This slice does not:

- rewrite `_extract_execution_reason(...)`
- rewrite sell reason bucket mapping
- rewrite candidate-only or not-picked owners
- rewrite row schema

## 2. Starting Point

Current repository evidence shows:

- the script still owns the final cross-branch decision between held-to-top, bought-not-held, picked-not-bought, candidate-not-entry, and not-picked
- upstream component reason helpers already exist
- the execution reason path remains mixed and should stay outside this slice

So the correct next slice is:

- extract only the final primary reason selector
- keep all upstream component reason computation in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_primary_reason_decision.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### APR-S1: Freeze observable decision contract

Freeze the visible behavior:

- `bought and held_to_top` wins first
- `bought` wins next and uses `latest_exit_reason or fallback`
- `entry_picked` wins next and always maps to `picked_not_bought`
- `candidate_picked` wins next and always maps to `candidate_not_entry`
- the final fallback is `not_picked`

Completion check:

- no new interpretation or fallback behavior is added in this slice

### APR-S2: Add the reasoning owner

Extend `neotrade3/analysis/attribution_reasoning.py` with:

- `resolve_primary_reason_decision(...) -> dict[str, str]`

Implementation rules:

- use only the passed booleans and precomputed component reasons
- do not call DB, engine, or context methods
- do not compute execution or sell bucket internals

Completion check:

- the decision contract is independently understandable from the report script

### APR-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- compute `execution_primary_reason`, `candidate_only_primary_reason`, `not_picked_primary_reason`, and `sell_reason_bucket` first
- replace the inline branch with one `resolve_primary_reason_decision(...)` call

Do not change:

- `_extract_execution_reason(...)`
- `_sell_reason_bucket(...)`
- `_candidate_only_primary_reason(...)`
- `_not_picked_primary_reason(...)`
- row schema

Completion check:

- the script no longer owns the inline priority selector

### APR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_primary_reason_decision.py`

Minimum owner cases:

- held-to-top branch wins
- bought-not-held branch keeps fallback text and sell bucket
- entry branch beats candidate branch
- candidate branch beats not-picked branch

Completion check:

- the owner contract has direct focused coverage

### APR-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_primary_reason_decision.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_reasoning.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_primary_reason_decision.py`

Completion check:

- owner tests pass
- nearby report regression passes
- syntax validation passes

### APR-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-primary-reason-decision-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-primary-reason-decision-plan.md`
- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_primary_reason_decision.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into execution fallback internals

Guard:

- keep execution reason precomputed in the script and only pass the result in

Risk 2:

- changing the current branch priority order

Guard:

- freeze the exact order with owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the primary reason decision contract has one reasoning owner
- the report script no longer owns the inline branch
- branch priority remains unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
