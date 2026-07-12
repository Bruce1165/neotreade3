Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow CLI success summary payload extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution CLI Summary Payload Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-cli-summary-payload-design.md`

## 1. Goal

This plan covers only the next narrow slice under `report-runner orchestration` after:

- `R2 stage progression contract`
- `R3 artifact path bundle contract`

This slice only handles:

- the final success summary payload that is printed at the end of the attribution report run
- one orchestration-side owner for that payload projection
- owner-focused tests for the success summary contract

The goal is to:

- move the visible success payload projection out of the script tail
- keep stdout emission in the script
- preserve the current success field set and path reuse exactly

This slice does not:

- rewrite `print(...)`
- rewrite `json.dumps(...)`
- rewrite failure output handling
- rewrite artifact writes
- rewrite status progression

## 2. Starting Point

Current repository evidence shows:

- the script still owns one inline success payload:
  - `status`
  - `report_id`
  - `output_dir`
  - `ranking_path`
  - `segments_path`
  - `attribution_path`
  - `report_path`
  - `aggregate`
- the script prints that payload through `print(json.dumps(...))`
- neighboring runners follow the same broad pattern of:
  - write artifacts
  - emit one final success JSON summary

So the correct narrow move is:

- extract only the success payload projection
- keep stdout transport in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_cli_summary.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_cli_summary.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-cli-summary-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-cli-summary-payload-plan.md`

## 4. Execution Steps

### R4-S1: Freeze the success summary contract

Freeze the current observable payload keys:

- `status`
- `report_id`
- `output_dir`
- `ranking_path`
- `segments_path`
- `attribution_path`
- `report_path`
- `aggregate`

Freeze the current visible success marker:

- `status -> "ok"`

Freeze current coercions:

- path-like values -> `str(...)`
- `report_id -> str(...)`
- `aggregate -> pass through`

Completion check:

- no key is added, removed, or renamed
- `"status": "ok"` remains unchanged

### R4-S2: Add the orchestration owner

Create:

- `neotrade3/orchestration/report_runner_cli_summary.py`

Public function:

- `build_lowfreq_report_success_summary(...) -> dict[str, Any]`

Implementation rules:

- project only the success payload
- do not print
- do not serialize JSON
- do not create files
- do not mutate `aggregate`

Completion check:

- the success payload has one dedicated owner outside the script

### R4-S3: Switch the script tail

In the script tail:

- replace the inline success payload dict with one call to `build_lowfreq_report_success_summary(...)`
- keep `print(json.dumps(...))` unchanged
- keep `ensure_ascii=False` unchanged
- keep `indent=2` unchanged
- keep `return 0` unchanged

Do not change:

- field names
- path sources
- aggregate source
- stdout shape

Completion check:

- only the payload projection leaves the script

### R4-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_cli_summary.py`

Minimum cases:

- projects the full current success payload with all expected keys
- preserves `"status": "ok"`
- stringifies all path-like inputs
- passes `aggregate` through by identity

Completion check:

- the contract is locked without a broad integration harness

### R4-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_cli_summary.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_cli_summary.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_cli_summary.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `build_lowfreq_report_success_summary(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### R4-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-cli-summary-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-cli-summary-payload-plan.md`
- `neotrade3/orchestration/report_runner_cli_summary.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_cli_summary.py`

Must exclude:

- changes to status owner
- changes to artifact path owner
- changes to artifact writes
- changes to failure output handling
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally widening into a generic stdout helper

Guard:

- keep the owner payload-only and leave `print(json.dumps(...))` in the script

Risk 2:

- accidentally simplifying or renaming success fields

Guard:

- freeze the current eight top-level fields in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the final success summary payload has one orchestration-side owner
- the script no longer owns the inline success payload dict
- stdout emission remains in the script
- the field set remains unchanged
- focused verification passes
- syntax verification passes
