Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow attribution ranking row payload extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Ranking Payload Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-ranking-payload-design.md`

## 1. Goal

This plan covers only the next narrow slice after the wave-segment extraction.

This slice only handles:

- the ranking row payload inside `_load_top_ranking(...)`
- one analysis owner for that row projection contract
- owner-focused tests for the row payload

The goal is to:

- move the visible ranking row contract out of the scorecard script
- keep SQL text, execute, and rank ordering in the script
- preserve the current ranking row shape and rounding exactly

This slice does not:

- rewrite the ranking SQL
- rewrite ranking JSON file output
- move sqlite access into analysis
- change how rows are sorted or limited

## 2. Starting Point

Current repository evidence shows:

- the script still owns the canonical ranking row dict projection
- that row shape is externally visible through `top{limit}_{year}_ranking.json`
- downstream consumers already depend on the row fields

So the correct next slice is:

- add one attribution-specific ranking row payload owner
- keep the sqlite query and enumerate ordering in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_ranking_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_ranking_payload.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-ranking-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-ranking-payload-plan.md`

## 4. Execution Steps

### ARP-S1: Freeze the ranking row contract

Freeze the current row fields exactly:

- `rank`
- `code`
- `name`
- `sector`
- `first_trade_date`
- `last_trade_date`
- `first_close`
- `last_close`
- `annual_return_pct`
- `price_basis`

Freeze current coercions and literals:

- `rank=int(rank)`
- `code=str(code)`
- `name=str(name or "")`
- `sector=str(sector or "")`
- `first_trade_date=str(first_trade_date)`
- `last_trade_date=str(last_trade_date)`
- `first_close=round(float(first_close), 4)`
- `last_close=round(float(last_close), 4)`
- `annual_return_pct=round(float(annual_return_pct), 2)`
- `price_basis="未复权收盘价"`

Completion check:

- no key is added, removed, renamed, or reworded

### ARP-S2: Add the analysis owner

Create:

- `neotrade3/analysis/attribution_ranking_payload.py`

Public function:

- `build_attribution_ranking_row(...) -> dict[str, Any]`

Implementation rules:

- perform only row projection and coercion
- do not execute SQL
- do not assign ranking order automatically

Completion check:

- the visible ranking row contract has one dedicated owner outside the script

### ARP-S3: Switch `_load_top_ranking(...)`

In `_load_top_ranking(...)`:

- keep the SQL text unchanged
- keep `conn.execute(...)` unchanged
- keep `enumerate(rows, start=1)` unchanged
- replace the inline row dict projection with one owner call

Do not change:

- sort order
- limit
- return type

Completion check:

- only the literal row payload assembly leaves the script

### ARP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_ranking_payload.py`

Minimum cases:

- projects the current row payload with current coercions
- keeps empty-string fallback for `name` and `sector`
- preserves 4-decimal price rounding and 2-decimal return rounding

Completion check:

- the ranking row contract is directly locked without broad integration coverage

### ARP-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_ranking_payload.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_ranking_payload.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_ranking_payload.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against the owner function

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### ARP-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-ranking-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-ranking-payload-plan.md`
- `neotrade3/analysis/attribution_ranking_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_ranking_payload.py`

Must exclude:

- changes to the ranking SQL
- changes to wave-segment owner
- changes to markdown or artifact payload owners
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally changing `price_basis` or rounding behavior

Guard:

- lock all visible fields and rounding behavior in owner-focused tests

Risk 2:

- widening into query extraction

Guard:

- keep sqlite access and ordering in the script

## 6. Success Criteria

This slice is complete when:

- the ranking row contract has one analysis-side owner
- the script no longer owns the inline row dict projection
- SQL and ordering remain in the script
- ranking JSON row shape remains unchanged
- focused verification passes
- syntax verification passes
