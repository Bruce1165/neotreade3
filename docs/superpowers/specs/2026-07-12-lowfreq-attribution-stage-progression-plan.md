Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow R2 stage progression contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Stage Progression Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-report-runner-orchestration-design.md`

## 1. Goal

This plan covers only the first narrow slice under the new `report-runner orchestration` theme.

This slice only handles:

- the stage progression contract around `status.json`
- one orchestration-side owner for stage names and per-stage payload projection
- owner-focused tests for the stage protocol

The goal is to:

- move the visible stage payload assembly out of `main()`
- keep the script responsible for deciding when each stage is emitted
- preserve the current stage set, stage order, and stage payload fields exactly

This slice does not:

- rewrite artifact file writes
- rewrite sqlite access or engine calls
- rewrite final CLI summary output
- redesign `status.json` path or timestamp format
- generalize all orchestrator status contracts across the whole repository

## 2. Starting Point

Current repository evidence shows:

- the scorecard script still owns explicit stage writes through `_write_status(...)`
- the stage set is already finite and externally visible:
  - `initializing`
  - `ranking_ready`
  - `backtest_ready`
  - `analysis_ready`
  - `done`
- each stage already has a stable minimum payload:
  - [generate_lowfreq_top200_attribution_report.py:L879-L918](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L879-L918)
  - [generate_lowfreq_top200_attribution_report.py:L948-L956](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L948-L956)
- the repository already has a dedicated `neotrade3/orchestration/` domain for run-state models and ledgers:
  - [README.md](file:///Users/mac/NeoTrade3/neotrade3/orchestration/README.md)
  - [models.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/models.py)

So the correct next slice is:

- add one report-runner stage-status owner under `neotrade3/orchestration/`
- keep the script in charge of sequencing and timing

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_status.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_status.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-report-runner-orchestration-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-stage-progression-plan.md`

## 4. Execution Steps

### R2-S1: Freeze the stage progression contract

Freeze the stage names exactly:

- `initializing`
- `ranking_ready`
- `backtest_ready`
- `analysis_ready`
- `done`

Freeze the visible per-stage payload fields exactly:

- `initializing`
  - `year`
  - `limit`
  - `report_id`
- `ranking_ready`
  - `ranking_count`
- `backtest_ready`
  - `ranking_count`
  - `total_return_pct`
  - `total_trades`
- `analysis_ready`
  - `ranking_count`
  - `aggregate`
- `done`
  - `report_id`
  - `ranking_path`
  - `segments_path`
  - `attribution_path`
  - `report_path`

Freeze shared envelope behavior:

- `_write_status(...)` continues to add `updated_at`
- stage payload builders must not emit `updated_at` themselves

Completion check:

- no stage is renamed, removed, reordered, or merged
- no per-stage field is added, removed, or reworded

### R2-S2: Add the orchestration-side owner

Create:

- `neotrade3/orchestration/report_runner_status.py`

Recommended public surface:

- stage constants or enum for the five visible stages
- one builder per stage payload

Recommended builders:

- `build_initializing_report_status(...)`
- `build_ranking_ready_report_status(...)`
- `build_backtest_ready_report_status(...)`
- `build_analysis_ready_report_status(...)`
- `build_done_report_status(...)`

Implementation rules:

- perform only stage payload projection and coercion
- do not create timestamps
- do not write files
- do not decide stage ordering
- do not access sqlite or engine state directly

Completion check:

- the visible stage protocol has one dedicated owner outside the script

### R2-S3: Switch the script stage writes

In `generate_lowfreq_top200_attribution_report.py`:

- keep `_write_status(...)` as the file-writing boundary
- keep current stage emission order unchanged
- replace inline stage payload literals with calls to the new builders

Do not change:

- `_write_status(...)` signature
- `updated_at` formatting
- `status.json` location
- artifact write order
- any engine or sqlite call site

Completion check:

- only the stage payload assembly leaves `main()`

### R2-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_status.py`

Minimum cases:

- projects `initializing` payload with current coercions
- projects `ranking_ready` payload with current count field
- projects `backtest_ready` payload with current summary fields
- projects `analysis_ready` payload with current aggregate pass-through behavior
- projects `done` payload with current artifact path keys
- locks stage name constants or enum values

Completion check:

- the stage protocol is directly locked without broad script integration coverage

### R2-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_status.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_status.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_status.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against the stage builders

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### R2-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-report-runner-orchestration-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-stage-progression-plan.md`
- `neotrade3/orchestration/report_runner_status.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_status.py`

Must exclude:

- changes to artifact payload owners
- changes to markdown writer behavior
- changes to backtest payload owner
- changes to ranking / wave-segment payload owners
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- widening from stage payload extraction into a full `main()` refactor

Guard:

- keep sequencing, file writes, and runtime preparation in the script

Risk 2:

- mixing stage payload logic with artifact-path registration logic that belongs to `R3`

Guard:

- in this slice, `done` only freezes the currently visible payload keys
- broader artifact ordering remains explicitly out of scope

Risk 3:

- prematurely trying to share these stage semantics with the global daily orchestrator

Guard:

- keep the owner report-runner specific even though it lives under `neotrade3/orchestration/`

## 6. Success Criteria

This slice is complete when:

- the report-runner stage protocol has one orchestration-side owner
- `main()` no longer owns inline stage payload literals
- stage order and field set remain unchanged
- `_write_status(...)` remains the only file-writing boundary
- focused verification passes
- syntax verification passes
