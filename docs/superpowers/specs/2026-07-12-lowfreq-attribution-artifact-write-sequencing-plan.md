Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow artifact write sequencing extraction under report-runner orchestration
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Artifact Write Sequencing Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-write-sequencing-design.md`

## 1. Goal

This plan covers only the next narrow slice under `report-runner orchestration` after:

- `R1 run context contract`
- `R1 backtest payload source contract`
- `R1 analysis engine prep contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

This slice only handles:

- the remaining artifact write ordering
- one orchestration-side owner for the ordered side effects
- owner-focused tests for the sequencing contract

The goal is to:

- move the current inline artifact write sequence out of the script
- preserve the current write order exactly
- preserve JSON formatting and trailing newline behavior exactly
- preserve attribution artifact `generated_at` forwarding exactly
- keep artifact path projection, payload projection, markdown content building, done-status payload projection, and CLI success summary in their current owners

This slice does not:

- rewrite artifact path projection
- rewrite artifact payload semantics
- rewrite markdown report content
- rewrite final CLI success summary emission
- rewrite any analysis or sqlite lifecycle

## 2. Starting Point

Current repository evidence shows:

- the script tail already delegates path projection
- the script tail already delegates attribution payload projection
- the script tail already delegates markdown content building
- the script tail already delegates done-status payload projection
- what remains inline is the ordered side-effect sequence tying those owners together

So the correct narrow move is:

- extract only the artifact write sequencing block
- keep the surrounding analysis and CLI summary in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_artifact_writes.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_artifact_writes.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-write-sequencing-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-write-sequencing-plan.md`

## 4. Execution Steps

### R3W-S1: Freeze the sequencing contract

Freeze the current inputs:

- `output_dir`
- `report_id`
- `year`
- `limit`
- `ranking_path`
- `segments_path`
- `attribution_path`
- `report_path`
- `ranking`
- `segments`
- `aggregate`
- `attribution_rows`
- `backtest_payload`
- `generated_at`

Freeze the current ordered behavior:

1. write ranking JSON
2. write wave-segment JSON
3. build and write attribution artifact JSON
4. write markdown report
5. write final `done` status

Freeze the current formatting:

- JSON uses `ensure_ascii=False`
- JSON uses `indent=2`
- JSON artifacts append trailing `"\n"`
- markdown write keeps direct UTF-8 text write

Completion check:

- no input is added, removed, or renamed
- no order or formatting drift is introduced

### R3W-S2: Add the orchestration owner

Create:

- `neotrade3/orchestration/report_runner_artifact_writes.py`

Public function:

- `write_lowfreq_report_artifacts(...) -> None`

Implementation rules:

- own only the current ordered artifact side effects
- reuse `build_attribution_artifact_payload(...)`
- reuse `build_attribution_markdown_report(...)`
- reuse `build_done_report_status(...)`
- reproduce current status-file write semantics directly inside the owner
- do not rebuild artifact paths
- do not print the final success summary

Completion check:

- the artifact tail has one dedicated owner outside the script

### R3W-S3: Switch the script call site

In the script:

- replace the inline tail block with one call to `write_lowfreq_report_artifacts(...)`
- keep artifact path resolution where it is
- keep `generated_at` creation where it is
- keep final CLI summary emission where it is

Do not change:

- analysis execution
- artifact path resolution
- final summary print block

Completion check:

- only the artifact write sequence leaves the script

### R3W-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_artifact_writes.py`

Minimum cases:

- writes ranking and segment JSON with current formatting and trailing newline
- writes attribution artifact using forwarded `generated_at`
- writes markdown report output
- writes final `status.json` with current `done` payload shape
- preserves current write ordering across the five side effects

Test style:

- use temporary paths
- use lightweight payloads
- avoid broad script integration

Completion check:

- the sequencing contract is locked without widening to the whole runner

### R3W-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_artifact_writes.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_artifact_writes.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_artifact_writes.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `write_lowfreq_report_artifacts(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### R3W-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-write-sequencing-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-write-sequencing-plan.md`
- `neotrade3/orchestration/report_runner_artifact_writes.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_artifact_writes.py`

Must exclude:

- changes to path owner
- changes to backtest source owner
- changes to analysis engine prep owner
- changes to status payload owner
- changes to CLI summary owner
- changes to analysis execution
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally widening into surrounding analysis flow or final CLI summary flow

Guard:

- keep the owner limited to the current tail block after artifact paths are resolved and before final summary print

Risk 2:

- accidentally changing file formatting or side-effect order

Guard:

- lock formatting, newline behavior, `generated_at` forwarding, and write order in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the artifact write sequence has one orchestration-side owner
- the script no longer owns the inline artifact tail
- write order and formatting remain unchanged
- done-status registration remains unchanged
- focused verification passes
- syntax verification passes
