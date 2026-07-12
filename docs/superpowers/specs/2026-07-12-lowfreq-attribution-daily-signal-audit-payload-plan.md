Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow daily signal-audit payload extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Daily Signal-Audit Payload Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-daily-signal-audit-payload-design.md`

## 1. Goal

This plan covers only the next narrow slice after the segment-failed row extraction.

This slice only handles:

- the `entry_signal_selected` daily-audit payload
- the `candidate_signal_selected` daily-audit payload
- owner-focused tests for those two payload builders

The goal is to:

- move the densest nested `stage/reason/signal` assembly out of `_audit_daily_reason(...)`
- preserve the current branch ordering and decision flow exactly
- create a dedicated owner for later daily-audit payload extractions without broadening now

This slice does not:

- extract the whole `_audit_daily_reason(...)` function
- move the simpler one-line stage returns
- change any market / sector / global filtering rule
- re-normalize raw signal snapshots

## 2. Starting Point

Current repository evidence shows:

- `_audit_daily_reason(...)` owns both decision flow and payload shaping
- only the `entry_signal_selected` and `candidate_signal_selected` branches carry nested `signal` payloads
- existing tests already anchor the observable shape of those branches
- upstream signal snapshot normalization already happens before these branches are evaluated

So the correct next slice is:

- extract only the two signal-hit payload builders
- keep all branch ordering and threshold logic in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_daily_audit_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_daily_audit_payload.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-daily-signal-audit-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-daily-signal-audit-payload-plan.md`

## 4. Execution Steps

### ADP-S1: Freeze observable payload contracts

Freeze the current entry-signal payload contract:

- `date`
- `stage`
- `reason`
- `signal.buy_score`
- `signal.role`
- `signal.wave_phase`
- `signal.candidate_tier`
- `signal.reasons`

Freeze the current candidate-signal payload contract:

- `date`
- `stage`
- `reason`
- `signal.buy_score`
- `signal.role`
- `signal.wave_phase`
- `signal.candidate_tier`
- `signal.entry_ready`
- `signal.reasons`

Completion check:

- no field is added, removed, or renamed
- coercions remain unchanged

### ADP-S2: Add a dedicated daily-audit payload owner

Create:

- `neotrade3/analysis/attribution_daily_audit_payload.py`

Public functions:

- `build_entry_signal_selected_audit(...)`
- `build_candidate_signal_selected_audit(...)`

Implementation rules:

- accept already selected `sig`
- shape only the current event envelope plus nested signal payload
- keep all current coercions

Completion check:

- both signal-hit payloads have one canonical owner outside the script

### ADP-S3: Switch the two script return sites to owner calls

In `_audit_daily_reason(...)`:

- replace the inline `entry_signal_selected` dict with `build_entry_signal_selected_audit(...)`
- replace the inline `candidate_signal_selected` dict with `build_candidate_signal_selected_audit(...)`

Do not change:

- `market_filter_state(...)` branch
- branch ordering
- signal lookup order
- sector/global filter logic

Completion check:

- only the two rich payload returns disappear from the script

### ADP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_daily_audit_payload.py`

Minimum cases:

- entry payload projects current field set and coercions
- candidate payload projects current field set and coercions
- candidate payload preserves `entry_ready`
- candidate payload preserves `candidate_tier`

Completion check:

- nested signal payload contract is directly locked outside the script

### ADP-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_daily_audit_payload.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_daily_audit_payload.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_daily_audit_payload.py tests/unit/test_lowfreq_attribution_reasoning.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against the new owner functions

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### ADP-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-daily-signal-audit-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-daily-signal-audit-payload-plan.md`
- `neotrade3/analysis/attribution_daily_audit_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_daily_audit_payload.py`

Must exclude:

- extraction of simpler stage returns
- reasoning changes
- aggregate or row projection changes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally extracting decision logic together with payload assembly

Guard:

- only replace the two returned dicts, not any surrounding `if` condition

Risk 2:

- silently drifting the nested `signal` field shape

Guard:

- lock exact field sets and coercions in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the two signal-hit payloads are owned in a dedicated analysis module
- `_audit_daily_reason(...)` keeps the same branch ordering
- nested `signal` fields remain unchanged
- focused verification passes
- syntax verification passes
