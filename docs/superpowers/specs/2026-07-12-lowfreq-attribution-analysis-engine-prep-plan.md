Status: active
Owner: lowfreq / scripts
Scope: Implementation plan for the narrow analysis engine preparation extraction under report-runner orchestration
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Analysis Engine Prep Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-analysis-engine-prep-design.md`

## 1. Goal

This plan covers only the next narrow slice under `report-runner orchestration` after:

- `R1 run context contract`
- `R1 backtest payload source contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

This slice only handles:

- the current analysis-stage engine source
- one orchestration-side owner for the optional `MAX_POSITIONS` override
- owner-focused tests for the engine preparation contract

The goal is to:

- move the current analysis-stage engine prep block out of the script
- preserve the current `service._lowfreq_engine_v16()` source exactly
- preserve the current `MAX_POSITIONS` override behavior exactly
- keep `_analyze_topk(...)`, sqlite lifecycle, backtest source loading, and artifact writes in the script

This slice does not:

- rewrite `_analyze_topk(...)`
- rewrite backtest payload loading
- rewrite stage progression writes
- rewrite artifact writes
- rewrite final CLI summary emission

## 2. Starting Point

Current repository evidence shows:

- the script still owns one inline analysis-stage engine preparation block
- that block only does two visible things:
  - source the engine from `service._lowfreq_engine_v16()`
  - apply `MAX_POSITIONS = int(max_positions_override)` when provided
- `_analyze_topk(...)` consumes only the prepared engine object
- the remaining artifact sequence is still broader and more action-heavy than this prep block

So the correct narrow move is:

- extract only the engine preparation block
- keep `_analyze_topk(...)` and later orchestration in place

## 3. Implementation Strategy

Production boundary:

- `neotrade3/orchestration/report_runner_analysis_engine.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_report_runner_analysis_engine.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-analysis-engine-prep-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-analysis-engine-prep-plan.md`

## 4. Execution Steps

### R1E-S1: Freeze the engine-prep contract

Freeze the current inputs:

- `service`
- `max_positions_override`

Freeze the current behavior:

- acquire `engine = service._lowfreq_engine_v16()`
- when `max_positions_override is not None`, apply `engine.MAX_POSITIONS = int(max_positions_override)`
- return the engine object

Completion check:

- no input is added, removed, or renamed
- no extra override is introduced

### R1E-S2: Add the orchestration owner

Create:

- `neotrade3/orchestration/report_runner_analysis_engine.py`

Public function:

- `prepare_lowfreq_report_analysis_engine(...)`

Implementation rules:

- own only the current engine source plus `MAX_POSITIONS` override
- do not call `_analyze_topk(...)`
- do not load backtest payload
- do not open sqlite connections
- do not write status
- do not write artifacts

Completion check:

- the analysis-stage engine prep has one dedicated owner outside the script

### R1E-S3: Switch the script call site

In the script:

- replace the inline `service._lowfreq_engine_v16()` block with one call to `prepare_lowfreq_report_analysis_engine(...)`
- keep `_analyze_topk(...)` invocation unchanged
- keep `execution_one_price_limit_only` forwarding unchanged

Do not change:

- `backtest_payload` loading
- `summary` extraction for `backtest_ready`
- sqlite lifecycle
- artifact path and write ordering

Completion check:

- only the engine-prep block leaves the script

### R1E-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_report_runner_analysis_engine.py`

Minimum cases:

- returns the exact engine instance from `service._lowfreq_engine_v16()` without overriding `MAX_POSITIONS`
- applies `MAX_POSITIONS = int(max_positions_override)` when provided
- preserves service call count at one per invocation

Test style:

- use a fake service and fake engine
- do not use sqlite or broad script integration

Completion check:

- the engine-prep contract is locked without widening to runner integration

### R1E-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/orchestration/report_runner_analysis_engine.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_report_runner_analysis_engine.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_report_runner_analysis_engine.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `prepare_lowfreq_report_analysis_engine(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### R1E-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-analysis-engine-prep-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-analysis-engine-prep-plan.md`
- `neotrade3/orchestration/report_runner_analysis_engine.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_report_runner_analysis_engine.py`

Must exclude:

- changes to backtest source owner
- changes to stage progression owner
- changes to artifact path owner
- changes to CLI summary owner
- changes to sqlite lifecycle
- changes to `_analyze_topk(...)`
- changes to artifact writes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally widening into `_analyze_topk(...)` or the remaining `R3` write block

Guard:

- keep the owner limited to engine source plus `MAX_POSITIONS` override only

Risk 2:

- accidentally reusing backtest-path override behavior on the analysis-stage path

Guard:

- freeze only the currently visible analysis-stage prep behavior and lock it with owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the analysis-stage engine prep has one orchestration-side owner
- the script no longer owns the inline prep block
- engine source and `MAX_POSITIONS` override behavior remain unchanged
- `_analyze_topk(...)` remains untouched
- focused verification passes
- syntax verification passes
