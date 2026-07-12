Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow run context extraction under report-runner orchestration
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Run Context Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-run-context-design.md`

## 1. Goal

This plan covers only the next narrow slice under `report-runner orchestration` after:

- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

This slice only handles:

- the pre-run `top_label / report_id / output_dir` projection
- one orchestration-side owner for that run-context projection
- owner-focused tests for the run-context contract

The goal is to:

- move the visible startup projection out of the script
- keep directory creation and later orchestration in the script
- preserve the current `report_id` fallback shape and `output_dir` resolution exactly

This slice does not:

- rewrite `output_dir.mkdir(...)`
- rewrite `_write_status(...)`
- rewrite sqlite lifecycle
- rewrite backtest preparation
- rewrite engine preparation
- rewrite artifact writes

## 2. Starting Point

Current repository evidence shows:

- the script still owns one inline startup block with:
  - `top_label`
  - `report_id`
  - `output_dir`
- that block feeds:
  - initial status writes
  - artifact path projection
  - `done` status
  - final CLI summary
- neighboring runners reuse the same broad startup pattern, but the narrow contract here is still only the projection, not the side effects

So the correct narrow move is:

- extract only the run-context projection
- keep `mkdir(...)` and the rest of `main()` in place

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_run_context.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_run_context.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-run-context-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-run-context-plan.md`

## 4. Execution Steps

### R1-S1: Freeze the run-context contract

Freeze the current projected fields:

- `top_label`
- `report_id`
- `output_dir`

Freeze the current rules:

- `top_label -> f"top{int(limit)}"`
- `report_id -> str(report_id or f"{top_label}_{int(year)}_{timestamp}")`
- `output_dir -> project_root / "var/artifacts" / f"lowfreq_{top_label}_attribution" / report_id`

Completion check:

- no field is added, removed, or renamed
- the fallback `report_id` shape remains unchanged
- the `output_dir` path root remains unchanged

### R1-S2: Add the orchestration owner

Create:

- `neotrade3/orchestration/report_runner_run_context.py`

Public function:

- `build_lowfreq_report_run_context(...) -> dict[str, Any]`

Implementation rules:

- project only the run context
- do not create directories
- do not write status
- do not open sqlite connections
- do not prepare the engine
- do not write artifacts

Completion check:

- the startup projection has one dedicated owner outside the script

### R1-S3: Switch the script startup block

In the script startup block:

- replace the inline `top_label / report_id / output_dir` projection with one call to `build_lowfreq_report_run_context(...)`
- keep `output_dir.mkdir(parents=True, exist_ok=True)` unchanged
- keep `_write_status(...)` unchanged
- keep `service = BootstrapApiService(...)` unchanged

Do not change:

- timestamp formatting
- `status.json` write location
- later artifact path builder inputs
- final CLI summary inputs

Completion check:

- only the startup projection leaves the script

### R1-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_run_context.py`

Minimum cases:

- projects the full current run context with explicit inputs
- preserves fallback `report_id` shape with an injected timestamp
- preserves explicit `report_id` override without rewriting it
- preserves `output_dir` resolution under `project_root / "var/artifacts"`
- coerces `year` and `limit` with the current `int(...)` behavior

Completion check:

- the contract is locked without a broad integration harness

### R1-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_run_context.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_run_context.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_run_context.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `build_lowfreq_report_run_context(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### R1-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-run-context-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-run-context-plan.md`
- `neotrade3/orchestration/report_runner_run_context.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_run_context.py`

Must exclude:

- changes to stage progression owner
- changes to artifact path owner
- changes to CLI summary owner
- changes to sqlite lifecycle
- changes to artifact writes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally widening into a startup-side-effect helper

Guard:

- keep the owner projection-only and leave `mkdir(...)`, `_write_status(...)`, and service/sqlite orchestration in the script

Risk 2:

- accidentally changing fallback naming while trying to normalize `report_id`

Guard:

- freeze the fallback format and lock it with an injected timestamp in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the run-context projection has one orchestration-side owner
- the script no longer owns the inline startup projection
- directory creation remains in the script
- the fallback `report_id` shape remains unchanged
- `output_dir` resolution remains unchanged
- focused verification passes
- syntax verification passes
