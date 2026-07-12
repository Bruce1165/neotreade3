Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution thin wrapper cleanup
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Thin Wrapper Cleanup Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-thin-wrapper-cleanup-design.md`

## 1. Goal

This plan covers only the next narrow consumer cleanup slice after the attribution report row projection extraction.

This slice only handles:

- removing the three script-local one-line forwarding wrappers
- switching the report script to direct reasoning owner consumption
- retargeting the nearby wrapper-focused assertion to the canonical owner

The goal is to:

- eliminate obsolete wrapper indirection from the report script
- preserve current reasoning semantics exactly
- continue shrinking the script toward thin-consumer ownership

This slice does not:

- change any reasoning rule or wording
- add a new owner
- change row projection
- change execution fallback behavior

## 2. Starting Point

Current repository evidence shows:

- the report script already imports the canonical reasoning owners
- the same script still defines three wrappers that only forward arguments unchanged
- the remaining consumer call sites use those wrappers directly
- dedicated owner-focused tests already cover the reasoning contracts, so only one nearby script-focused assertion still needs retargeting

So the correct next slice is:

- delete only the forwarding wrappers
- switch only their call sites
- keep every underlying reasoning contract untouched

## 3. Implementation Strategy

Production boundary:

- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_reasoning.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-thin-wrapper-cleanup-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-thin-wrapper-cleanup-plan.md`

## 4. Execution Steps

### ATW-S1: Freeze direct-owner mapping

Freeze the current source mapping:

- `_sell_reason_bucket(...)` -> `resolve_sell_reason_bucket(...)`
- `_not_picked_primary_reason(...)` -> `resolve_not_picked_primary_reason(...)`
- `_candidate_only_primary_reason(...)` -> `resolve_candidate_only_primary_reason(...)`

Completion check:

- no call-site argument list changes
- no fallback or coercion changes

### ATW-S2: Remove script-local forwarding wrappers

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- delete the three one-line wrapper definitions
- keep the existing imports from `attribution_reasoning.py`

Completion check:

- the script no longer defines the three wrapper names

### ATW-S3: Switch consumer call sites to canonical owners

In `_analyze_topk(...)`:

- replace `_sell_reason_bucket(latest_exit_reason)` with `resolve_sell_reason_bucket(latest_exit_reason)`
- replace `_candidate_only_primary_reason(daily_audits)` with `resolve_candidate_only_primary_reason(daily_audits)`
- replace `_not_picked_primary_reason(daily_audits)` with `resolve_not_picked_primary_reason(daily_audits)`

Do not change:

- execution reason extraction
- reason decision assembly
- summary counter behavior

Completion check:

- all three call sites use the canonical owners directly

### ATW-S4: Retarget nearby script-focused coverage

In `tests/unit/test_lowfreq_attribution_reasoning.py`:

- import `resolve_sell_reason_bucket` directly from `neotrade3.analysis.attribution_reasoning`
- keep the existing sell-reason bucket assertions, but point them at the canonical owner
- leave the rest of the script-focused tests unchanged

Completion check:

- no nearby test still depends on the removed wrapper surface

### ATW-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_reasoning.py neotrade3/analysis/attribution_reasoning.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_reasoning.py tests/unit/test_lowfreq_attribution_sell_reason_bucket.py tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py tests/unit/test_lowfreq_attribution_candidate_only_primary_reason.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions that call `resolve_sell_reason_bucket(...)` directly

Completion check:

- syntax validation passes
- focused reasoning verification passes with the best available runner in the current environment

### ATW-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-thin-wrapper-cleanup-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-thin-wrapper-cleanup-plan.md`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

Must exclude:

- unrelated report cleanup
- owner contract rewrites
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally turning consumer cleanup into reasoning logic edits

Guard:

- touch only wrapper definitions, their three call sites, and the one nearby test surface

Risk 2:

- removing a wrapper but forgetting downstream test references

Guard:

- search the repository for all three wrapper names before commit

## 6. Success Criteria

This slice is complete when:

- the report script no longer defines the three forwarding wrappers
- all three call sites consume canonical reasoning owners directly
- nearby focused coverage no longer relies on removed wrapper names
- focused verification passes
- syntax verification passes
