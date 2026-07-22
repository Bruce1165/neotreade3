Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow shared `status.json` write adapter extraction under report-runner orchestration
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Status Write Adapter Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-status-write-adapter-design.md`

## 1. Goal

This plan covers only the next narrow slice under `report-runner orchestration` after:

- `R1 run context contract`
- `R1 backtest payload source contract`
- `R1 analysis engine prep contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R3 artifact write sequencing contract`
- `R4 CLI success summary payload contract`

This slice only handles:

- the shared `status.json` file-write adapter
- one orchestration-side owner for status emission side effects
- owner-focused tests for the frozen write semantics

The goal is to:

- remove duplicated `status.json` write logic from the script and artifact-write owner
- preserve timestamp generation, write target, JSON formatting, and trailing newline exactly
- keep stage payload projection and final CLI summary projection in their current owners
- let staged runner writes and final `done` registration consume the same writer

This slice does not:

- rewrite stage payload builders
- rewrite artifact write sequencing
- rewrite final CLI summary emission
- rewrite analysis, sqlite lifecycle, or run context setup

## 2. Starting Point

Current repository evidence shows:

- stage payload builders are already ownerized in `neotrade3/orchestration/report_runner_status.py`
- final CLI summary payload is already ownerized in `neotrade3/orchestration/report_runner_cli_summary.py`
- the script still owns `_write_status(...)` and uses it for four staged writes
- `neotrade3/orchestration/report_runner_artifact_writes.py` owns a second private `_write_status_file(...)` for the final `done` write

So the correct narrow move is:

- extract only the shared file-write adapter semantics
- keep payload meaning and stage ordering where they currently live

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_status_writer.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `neotrade3/orchestration/report_runner_artifact_writes.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_status_writer.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-status-write-adapter-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-status-write-adapter-plan.md`

## 4. Execution Steps

### SWA-S1: Freeze the shared write contract

Freeze the current observable semantics:

- write file path remains `(output_dir / "status.json")`
- payload always includes:
  - `stage`
  - `updated_at`
- forwarded extra fields are merged into the payload after defaults
- serialization remains:
  - `json.dumps(payload, ensure_ascii=False, indent=2) + "\n"`
- write encoding remains:
  - `utf-8`

Freeze current call classes:

1. staged runner status writes from `main()`
2. final `done` status registration from artifact sequencing

Completion check:

- no stage field is renamed
- no timestamp or formatting drift is introduced

### SWA-S2: Add the orchestration owner

Create:

- `neotrade3/orchestration/report_runner_status_writer.py`

Public function:

- `write_lowfreq_report_status(...) -> None`

Implementation rules:

- own only the current `status.json` side effect
- generate `updated_at` with the current UTC format
- accept `output_dir`, `stage`, and arbitrary forwarded payload fields
- do not decide stage payload shape
- do not emit CLI output
- do not absorb artifact sequencing logic

Completion check:

- there is one dedicated orchestration owner for status-file writes

### SWA-S3: Switch current consumers

In the script:

- replace staged `_write_status(...)` calls with `write_lowfreq_report_status(...)`
- remove the private `_write_status(...)` helper

In the artifact-write owner:

- replace `_write_status_file(...)` usage with the shared writer
- remove the private `_write_status_file(...)` helper and its now-unused imports

Do not change:

- any `build_*_report_status(...)` payload builder
- stage emission order
- artifact write order
- final CLI summary print block

Completion check:

- both current consumers call the same writer
- duplicated private status writers no longer exist

### SWA-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_status_writer.py`

Minimum cases:

- writes `status.json` with current JSON formatting and trailing newline
- preserves forwarded payload fields for staged status data
- preserves `done`-style forwarding shape
- emits non-empty `updated_at` in the current UTC textual format

Test style:

- use temporary directories
- use direct owner calls
- avoid broad script integration

Completion check:

- the shared write contract is locked without widening to full runner integration

### SWA-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_status_writer.py neotrade3/orchestration/report_runner_artifact_writes.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_status_writer.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_status_writer.py tests/unit/test_lowfreq_report_runner_artifact_writes.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `write_lowfreq_report_status(...)`
- run `.venv/bin/python` inline assertions to confirm `write_lowfreq_report_artifacts(...)` still writes final `done` status through the shared writer

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### SWA-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-status-write-adapter-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-status-write-adapter-plan.md`
- `neotrade3/orchestration/report_runner_status_writer.py`
- `neotrade3/orchestration/report_runner_artifact_writes.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_status_writer.py`
- `tests/unit/test_lowfreq_report_runner_artifact_writes.py`

Must exclude:

- changes to stage payload builders
- changes to artifact path owner
- changes to CLI summary owner
- changes to analysis execution
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally widening into stage-semantics rewrites or artifact sequencing rewrites

Guard:

- keep the new owner limited to shared file-write semantics
- keep payload builders and sequencing decisions in existing owners

Risk 2:

- accidentally changing timestamp shape, write target, or JSON formatting

Guard:

- lock target path, newline behavior, forwarded fields, and `updated_at` presence in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- there is one shared orchestration owner for `status.json` writes
- the script no longer defines `_write_status(...)`
- `report_runner_artifact_writes.py` no longer defines its private status writer
- current stage payloads and final `done` payload remain unchanged
- focused verification passes
- syntax verification passes
