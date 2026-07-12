Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow backtest payload source extraction under report-runner orchestration
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Backtest Source Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-source-design.md`

## 1. Goal

This plan covers only the next narrow slice under `report-runner orchestration` after:

- `R1 run context contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

This slice only handles:

- the current backtest payload source decision
- one orchestration-side owner for the file-override and engine-fallback branches
- owner-focused tests for the source contract

The goal is to:

- move the current `_load_backtest_payload(...)` helper out of the script
- preserve the current two-branch sourcing behavior exactly
- preserve the current engine override knobs and payload normalization exactly
- keep sqlite lifecycle, stage progression, analysis engine preparation, and artifact writes in the script

This slice does not:

- rewrite sqlite open / close behavior
- rewrite analysis-stage `engine = service._lowfreq_engine_v16()`
- rewrite `build_attribution_backtest_payload(...)`
- rewrite artifact writes
- rewrite final CLI summary emission

## 2. Starting Point

Current repository evidence shows:

- the script still owns one dedicated helper for backtest payload sourcing
- that helper already has two visible branches:
  - file override via `backtest_json`
  - engine fallback via `service._lowfreq_engine_v16()`
- downstream analysis consumes only the resulting `backtest_payload`
- the backtest payload envelope already has its own M3 owner

So the correct narrow move is:

- extract only the sourcing helper
- keep the later analysis engine bootstrap in `main()`
- avoid widening into sqlite lifecycle or artifact sequencing

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_backtest_source.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_backtest_source.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-source-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-source-plan.md`

## 4. Execution Steps

### R1B-S1: Freeze the source contract

Freeze the current inputs:

- `service`
- `backtest_json`
- `start_date`
- `end_date`
- `initial_capital`
- `max_positions_override`
- `execution_one_price_limit_only`
- `generated_at`

Freeze the current file branch:

- when `backtest_json` exists, return `json.loads(backtest_json.read_text(...))`

Freeze the current engine branch:

- acquire `engine = service._lowfreq_engine_v16()`
- apply `MAX_POSITIONS = int(max_positions_override)` when provided
- apply `EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = True` when requested
- call `run_backtest(..., include_trades=True)`
- split `metrics` into `summary` and `trades`
- remove `summary["trades"]`
- delegate to `build_attribution_backtest_payload(...)`

Completion check:

- no input is added, removed, or renamed
- both branches preserve current observable behavior

### R1B-S2: Add the orchestration owner

Create:

- `neotrade3/orchestration/report_runner_backtest_source.py`

Public function:

- `load_lowfreq_report_backtest_payload(...) -> dict[str, Any]`

Implementation rules:

- own only the current source decision and normalization
- do not open sqlite connections
- do not write status
- do not create output directories
- do not write artifacts
- do not acquire the later analysis-stage engine

Completion check:

- the backtest source helper has one dedicated owner outside the script

### R1B-S3: Switch the script call site

In the script:

- replace `_load_backtest_payload(...)` consumption with `load_lowfreq_report_backtest_payload(...)`
- pass through the current arguments unchanged
- inject the current UTC timestamp string through `generated_at`
- remove the inline helper from the script

Do not change:

- backtest date parsing
- `initial_capital` source
- later `build_backtest_ready_report_status(...)` consumption
- later analysis-stage `engine = service._lowfreq_engine_v16()`

Completion check:

- only the backtest source helper leaves the script

### R1B-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_backtest_source.py`

Minimum cases:

- returns file JSON unchanged when `backtest_json` exists
- applies `MAX_POSITIONS`, `EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT`, and `include_trades=True` on the engine path
- removes `trades` from `summary` before building the attribution payload
- preserves `requested_by="script"` and forwards `generated_at`
- tolerates non-dict metrics by falling back to empty `summary` and empty `trades`

Test style:

- use fake service and fake engine
- do not use sqlite or broad script integration

Completion check:

- the source contract is locked without widening to runner integration

### R1B-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_backtest_source.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_backtest_source.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_backtest_source.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `load_lowfreq_report_backtest_payload(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### R1B-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-source-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-source-plan.md`
- `neotrade3/orchestration/report_runner_backtest_source.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_backtest_source.py`

Must exclude:

- changes to run context owner
- changes to stage progression owner
- changes to artifact path owner
- changes to CLI summary owner
- changes to sqlite lifecycle
- changes to analysis-stage engine preparation
- changes to artifact writes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally widening into the whole remaining `R1` bootstrap chain

Guard:

- keep the owner limited to `_load_backtest_payload(...)` semantics and leave sqlite plus later engine prep in the script

Risk 2:

- accidentally changing payload semantics between the file branch and engine branch

Guard:

- lock both branches directly in owner-focused tests and preserve delegation to `build_attribution_backtest_payload(...)`

## 6. Success Criteria

This slice is complete when:

- the backtest payload source has one orchestration-side owner
- the script no longer owns `_load_backtest_payload(...)`
- file override and engine fallback behavior remain unchanged
- the M3 payload envelope remains reused, not duplicated
- focused verification passes
- syntax verification passes
