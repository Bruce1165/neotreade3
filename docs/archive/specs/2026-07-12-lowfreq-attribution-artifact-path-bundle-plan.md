Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow report-runner artifact path bundle extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Artifact Path Bundle Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-path-bundle-design.md`

## 1. Goal

This plan covers only the next narrow slice under the `report-runner orchestration` theme after `R2 stage progression`.

This slice only handles:

- the four artifact path projections in the scorecard script tail
- one orchestration-side owner for that path bundle contract
- owner-focused tests for the path naming and key set

The goal is to:

- move the visible artifact path bundle out of `main()`
- keep the script responsible for artifact write order, serialization, and side effects
- preserve the current four filenames and consumer reuse points exactly

This slice does not:

- rewrite artifact writes
- rewrite `json.dumps(...)`
- rewrite `_write_markdown_report(...)`
- rewrite `done` status emission
- rewrite final CLI summary output

## 2. Starting Point

Current repository evidence shows:

- the scorecard script still owns one inline four-path bundle:
  - `ranking_path`
  - `segments_path`
  - `attribution_path`
  - `report_path`
- that bundle is reused by three downstream orchestration surfaces:
  - artifact writes
  - `done` status
  - final CLI summary
- no existing orchestration owner currently freezes this path contract

So the correct next slice is:

- add one report-runner artifact-path owner
- keep all file writes and ordering in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_artifact_paths.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_artifact_paths.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-path-bundle-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-path-bundle-plan.md`

## 4. Execution Steps

### R3-S1: Freeze the artifact path bundle contract

Freeze the current observable payload as:

- top-level keys:
  - `ranking_path`
  - `segments_path`
  - `attribution_path`
  - `report_path`

Freeze the current file naming rules:

- `ranking_path -> output_dir / f"top{int(limit)}_{year}_ranking.json"`
- `segments_path -> output_dir / f"top{int(limit)}_{year}_wave_segments.json"`
- `attribution_path -> output_dir / f"top{int(limit)}_{year}_model_attribution.json"`
- `report_path -> output_dir / "report.md"`

Freeze current coercions:

- `year -> int(...)`
- `limit -> int(...)`
- each output path -> `str(...)`

Completion check:

- no key is added, removed, or renamed
- no file basename changes

### R3-S2: Add the orchestration owner

Create:

- `neotrade3/orchestration/report_runner_artifact_paths.py`

Public function:

- `build_lowfreq_report_artifact_paths(*, output_dir: Path, year: int, limit: int) -> dict[str, str]`

Implementation rules:

- perform only the path projection
- do not create directories
- do not write files
- do not serialize JSON
- do not emit status or CLI summary payloads

Completion check:

- the artifact path bundle has one dedicated owner outside the script

### R3-S3: Switch the script tail

In the scorecard script tail:

- replace the inline four-path projection with one call to `build_lowfreq_report_artifact_paths(...)`
- keep current write order unchanged
- keep current `generated_at` creation unchanged
- keep current `done` status builder consumption unchanged
- keep current final CLI summary payload unchanged

Do not change:

- artifact write order
- JSON formatting
- Markdown writer usage
- `done` status field names
- final CLI summary field names

Completion check:

- only the path projection leaves the script

### R3-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_artifact_paths.py`

Minimum cases:

- projects the current four path keys from `output_dir/year/limit`
- preserves the current `top{limit}_{year}_...` naming contract
- coerces `year` and `limit` with current `int(...)` behavior
- keeps `report.md` as the fixed Markdown artifact name

Completion check:

- the path contract is directly locked without a broad integration harness

### R3-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_artifact_paths.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_artifact_paths.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_artifact_paths.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `build_lowfreq_report_artifact_paths(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### R3-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-path-bundle-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-path-bundle-plan.md`
- `neotrade3/orchestration/report_runner_artifact_paths.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_artifact_paths.py`

Must exclude:

- changes to `report_runner_status.py`
- changes to artifact payload owners
- changes to Markdown writer behavior
- changes to final CLI summary shape
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally widening into a full artifact writer helper

Guard:

- keep the owner payload-only and forbid file writes or serialization

Risk 2:

- accidentally changing one or more visible filenames while centralizing the bundle

Guard:

- lock the four exact basenames in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the artifact path bundle has one orchestration-side owner
- the script no longer owns the inline four-path projection
- writes and serialization remain in the script
- file naming remains unchanged
- focused verification passes
- syntax verification passes
