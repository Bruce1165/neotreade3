Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution segment-failed row projection extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Segment Failed Row Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-segment-failed-row-design.md`

## 1. Goal

This plan covers only the next narrow report-row cleanup slice after the attribution thin-wrapper cleanup.

This slice only handles:

- the failed-segment fallback row currently built inline in `_analyze_topk(...)`
- reuse of the existing report-row owner for that fallback payload
- owner-focused tests plus minimum nearby regression verification

The goal is to:

- remove the last inline failed-row payload from the script
- keep the current failure-row field set and defaults unchanged
- centralize successful and failed report-row projection under one owner file

This slice does not:

- rewrite `_compute_wave_segment(...)`
- rewrite aggregate summary logic
- rewrite successful row projection behavior
- rewrite markdown rendering

## 2. Starting Point

Current repository evidence shows:

- successful row projection already lives in `neotrade3/analysis/attribution_report_row.py`
- the script still builds the failed-segment fallback row inline
- that branch uses only already prepared values and therefore fits the same report-row projection ownership
- aggregate summary only reads boolean flags already present in the failed row, so behavior should remain stable if the payload stays unchanged

So the correct next slice is:

- add only one failed-row builder to the existing row owner
- switch only the failed branch append site
- add only owner-focused failed-row coverage

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_report_row.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_report_row.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-segment-failed-row-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-segment-failed-row-plan.md`

## 4. Execution Steps

### ASF-S1: Freeze failed-row observable contract

Freeze the current failed-row payload:

- `rank`
- `code`
- `name`
- `annual_return_pct`
- `segment_status`
- `candidate_picked: False`
- `entry_picked: False`
- `picked: False`
- `bought: False`
- `held_to_top: False`
- `primary_reason: "主升段识别失败"`

Completion check:

- no field is added, removed, or renamed
- no default value changes

### ASF-S2: Add failed-row builder to the report-row owner

In `neotrade3/analysis/attribution_report_row.py`:

- add `build_attribution_segment_failed_row(...) -> dict[str, Any]`

Implementation rules:

- use only prepared scalar inputs
- keep coercions aligned with the current inline branch
- keep the field set exactly as frozen in `ASF-S1`

Completion check:

- failed-row projection has one dedicated owner in the report-row module

### ASF-S3: Switch the script to a thin consumer for the failed branch

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- replace the inline failed-row dictionary with one `build_attribution_segment_failed_row(...)` call
- keep `summary_counters["segment_failed"] += 1` in the script
- keep the `continue` boundary unchanged

Do not change:

- `segment.get("status") != "ok"` branch condition
- segment computation
- aggregate summary call

Completion check:

- the script no longer owns the failed-row inline dictionary

### ASF-S4: Add owner-focused failed-row tests

In `tests/unit/test_lowfreq_attribution_report_row.py`:

- add one test that asserts the full failed-row payload and coercions
- add one test that asserts `segment_status` keeps the `"unknown"` fallback

Completion check:

- failed-row contract has direct focused coverage

### ASF-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_report_row.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_report_row.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_report_row.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions that call `build_attribution_segment_failed_row(...)` directly

Completion check:

- syntax validation passes
- failed-row focused verification passes with the best available runner in the current environment

### ASF-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-segment-failed-row-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-segment-failed-row-plan.md`
- `neotrade3/analysis/attribution_report_row.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_report_row.py`

Must exclude:

- unrelated report cleanup
- reasoning changes
- aggregate summary rewrites
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- silently adding symmetry fields such as `reason_bucket` or `sector` that do not exist in the current failed row

Guard:

- copy the exact field set from the current inline branch and nothing more

Risk 2:

- broadening into segment or aggregate behavior changes

Guard:

- touch only the row owner, the failed-branch append site, and owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the failed-segment row payload has one owner in `attribution_report_row.py`
- the script no longer owns the inline failed-row dictionary
- the failed-row field set remains unchanged
- owner-focused tests pass
- syntax verification passes
