Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow attribution backtest payload extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Backtest Payload Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-payload-design.md`

## 1. Goal

This plan covers only the next narrow slice after the ranking payload extraction.

This slice only handles:

- the backtest payload envelope returned by `_load_backtest_payload(...)`
- one analysis owner for that attribution-report payload contract
- owner-focused tests for the payload shape

The goal is to:

- move the visible backtest payload contract out of the script helper
- keep the script responsible for file/engine orchestration
- preserve the current `_meta/summary/trade_blocks/config_snapshot/coverage_gaps/trades` shape exactly

This slice does not:

- rewrite `run_backtest(...)`
- rewrite the `--backtest-json` read path
- rewrite `status.json`
- migrate `run_lowfreq_top200_capacity_experiment.py`
- change downstream attribution aggregation logic

## 2. Starting Point

Current repository evidence shows:

- the scorecard script still owns one inline backtest payload envelope
- that envelope feeds visible downstream fields:
  - `summary`
  - `trade_blocks`
  - `config_snapshot`
  - `coverage_gaps`
  - `trades`
- no existing analysis owner currently freezes this attribution-report payload shape

So the correct next slice is:

- add one attribution-specific backtest-payload owner
- keep file/engine orchestration in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_backtest_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_backtest_payload.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-payload-plan.md`

## 4. Execution Steps

### ABP-S1: Freeze the payload envelope contract

Freeze the current observable payload as:

- top-level keys:
  - `_meta`
  - `summary`
  - `trade_blocks`
  - `config_snapshot`
  - `coverage_gaps`
  - `trades`
- `_meta` fields:
  - `status="ok"`
  - `requested_by`
  - `model="lowfreq_engine_v16_advanced"`
  - `generated_at`

Freeze current coercions and fallbacks:

- `requested_by -> str(... or "")`
- `generated_at -> str(... or "")`
- `summary -> summary if dict else {}`
- `trade_blocks/config_snapshot/coverage_gaps -> derived from summary if dict else {}`
- `trades -> trades if list else []`

Completion check:

- no payload key is added, removed, or renamed

### ABP-S2: Add the analysis owner

Create:

- `neotrade3/analysis/attribution_backtest_payload.py`

Public function:

- `build_attribution_backtest_payload(*, requested_by: str, generated_at: str, summary: Any, trades: Any) -> dict[str, Any]`

Implementation rules:

- perform only the payload projection
- keep `summary` and `trades` as prepared inputs
- reuse `summary` child dicts directly when present
- do not read files
- do not create timestamps
- do not run backtests

Completion check:

- the payload envelope has one dedicated owner outside the script

### ABP-S3: Switch the script helper

Inside `_load_backtest_payload(...)`:

- keep the `backtest_json` fast path unchanged
- keep engine acquisition and override handling unchanged
- keep `run_backtest(...)` unchanged
- keep local `trades` / `summary` preparation unchanged
- replace the inline payload literal with one call to `build_attribution_backtest_payload(...)`

Do not change:

- helper signature
- control flow
- status progression
- downstream report logic

Completion check:

- only the payload envelope leaves the script helper

### ABP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_backtest_payload.py`

Minimum cases:

- projects the current payload keys and `_meta`
- preserves summary-derived child dict references
- falls back to `{}` / `[]` for invalid inputs
- keeps empty-string fallbacks for `requested_by` and `generated_at`

Completion check:

- the payload contract is directly locked without broad integration scaffolding

### ABP-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_backtest_payload.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_backtest_payload.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_backtest_payload.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `build_attribution_backtest_payload(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### ABP-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-backtest-payload-plan.md`
- `neotrade3/analysis/attribution_backtest_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_backtest_payload.py`

Must exclude:

- changes to `run_lowfreq_top200_capacity_experiment.py`
- changes to `status.json` writes
- changes to report artifact writers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally turning the new owner into an execution helper

Guard:

- keep the owner payload-only and require prepared inputs

Risk 2:

- accidentally copying or reshaping `summary` child dicts

Guard:

- lock child-reference behavior in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- the attribution-report backtest payload has one analysis-side owner
- `_load_backtest_payload(...)` no longer owns the inline payload literal
- file/engine orchestration remains in the script
- payload shape remains unchanged
- focused verification passes
- syntax verification passes
