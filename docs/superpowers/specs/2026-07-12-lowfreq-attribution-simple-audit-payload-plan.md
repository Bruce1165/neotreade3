Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow simple daily-audit envelope extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Simple Audit Payload Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-simple-audit-payload-design.md`

## 1. Goal

This plan covers only the next narrow slice after the daily signal-audit payload extraction.

This slice only handles:

- the repeated simple `date/stage/reason` envelopes inside `_audit_daily_reason(...)`
- one shared owner for those simple envelopes
- owner-focused tests for that shared envelope contract

The goal is to:

- move the remaining repeated simple envelope assembly out of the script
- preserve the current branch ordering, threshold math, and reason-string construction exactly
- keep the existing daily-audit owner as the single canonical home for audit payload projection

This slice does not:

- extract the whole `_audit_daily_reason(...)` function
- move threshold computation or any branch predicate
- rewrite dynamic reason strings
- change signal-hit payload builders or reasoning consumers

## 2. Starting Point

Current repository evidence shows:

- rich signal-hit payloads already live in `attribution_daily_audit_payload.py`
- the remaining inline returns in `_audit_daily_reason(...)` are all simple `date/stage/reason` envelopes
- several downstream consumers and tests depend on stable stage names and reason texts

So the correct next slice is:

- add one explicit simple-envelope builder
- keep every stage decision and every reason string at the call site

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_daily_audit_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_daily_simple_payload.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-simple-audit-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-simple-audit-payload-plan.md`

## 4. Execution Steps

### SAP-S1: Freeze the simple envelope contract

Freeze the repeated simple payload shape as exactly:

- `date`
- `stage`
- `reason`

Freeze current coercions:

- `date -> str(... or "")`
- `stage -> str(... or "")`
- `reason -> str(... or "")`

Completion check:

- no extra field is added
- no existing field is renamed or removed

### SAP-S2: Extend the daily-audit payload owner

Add to:

- `neotrade3/analysis/attribution_daily_audit_payload.py`

Public function:

- `build_simple_stage_audit(*, audit_date: str, stage: str, reason: str) -> dict[str, Any]`

Implementation rules:

- accept already computed `stage` and `reason`
- perform only the final envelope projection
- keep coercions minimal and explicit

Completion check:

- the repeated simple envelope has one canonical owner outside the script

### SAP-S3: Switch the simple script return sites

In `_audit_daily_reason(...)`, replace only the simple inline dict literals with `build_simple_stage_audit(...)`.

Simple stage set:

- `market_filtered`
- `sector_seed_miss`
- `sector_candidate_filtered`
- `score_below_threshold`
- `follower_filtered`
- `resonance_filtered`
- `sector_candidate_not_selected`
- `global_seed_miss`
- `global_candidate_filtered`
- `global_follower_filtered`
- `global_resonance_filtered`
- `global_wave_filtered`
- `global_score_filtered`
- `global_cap_filtered`

Do not change:

- any surrounding `if` condition
- any threshold math
- any dynamic reason formatting
- the existing signal-hit owner calls

Completion check:

- only simple envelope projection leaves the script

### SAP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_daily_simple_payload.py`

Minimum cases:

- simple envelope projects current `date/stage/reason` fields
- simple envelope preserves empty-string fallback coercions

Keep and rerun script-focused regression:

- `test_audit_daily_reason_marks_cross_sector_wave_filter_stage`

Completion check:

- the owner contract is directly locked
- at least one dynamic script branch proves unchanged observable behavior

### SAP-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_daily_audit_payload.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_daily_simple_payload.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_daily_simple_payload.py tests/unit/test_lowfreq_attribution_reasoning.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `build_simple_stage_audit(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### SAP-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-simple-audit-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-simple-audit-payload-plan.md`
- `neotrade3/analysis/attribution_daily_audit_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_daily_simple_payload.py`

Must exclude:

- reasoning changes
- aggregate-summary changes
- row projection changes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally moving branch logic together with the envelope

Guard:

- only replace returned dict literals, never the conditions above them

Risk 2:

- accidentally drifting stage texts or reason texts while deduplicating

Guard:

- keep all message construction at the call site
- test only the owner envelope contract plus one script-level observable branch

## 6. Success Criteria

This slice is complete when:

- the remaining simple daily-audit envelopes are owned in the shared analysis module
- `_audit_daily_reason(...)` keeps the same branch ordering and threshold logic
- stage names and reason texts remain unchanged
- focused verification passes
- syntax verification passes
