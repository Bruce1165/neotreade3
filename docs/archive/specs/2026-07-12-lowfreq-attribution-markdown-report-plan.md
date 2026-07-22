Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow attribution Markdown formatter extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Markdown Report Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-markdown-report-design.md`

## 1. Goal

This plan covers only the next narrow slice after the execution limit-window extraction.

This slice only handles:

- the pure Markdown line assembly inside `_write_markdown_report(...)`
- one analysis owner for that Markdown formatter contract
- formatter-focused tests for the rendered text

The goal is to:

- move the visible report text contract out of the scorecard script
- keep the script responsible for `report_path` and `write_text(...)`
- preserve current section order, bullet wording, sample filters, and top-20 truncation exactly

This slice does not:

- redesign the report
- change report wording
- generalize formatting across multiple report scripts
- change upstream aggregation or row payload logic

## 2. Starting Point

Current repository evidence shows:

- the attribution scorecard script still owns one self-contained Markdown writer
- the Markdown block is pure after prepared inputs arrive at `_write_markdown_report(...)`
- no existing owner under `neotrade3/analysis/` currently owns the attribution Markdown payload

So the correct next slice is:

- add one attribution-specific formatter owner that returns `str`
- keep file output in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_markdown_report.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Reference-only evidence:

- `scripts/generate_lowfreq_top200_process_research_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_markdown_report.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-markdown-report-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-markdown-report-plan.md`

## 4. Execution Steps

### AMR-S1: Freeze the Markdown output contract

Freeze the current observable Markdown behavior as:

- same headline line
- same six section headers and section order
- same blank-line layout
- same summary bullet copy and interpolation
- same reason distribution ordering via `Counter(...).most_common()`
- same top-20 truncation for each sample section
- same trailing newline

Completion check:

- no visible copy drift is introduced
- no section is added, removed, or reordered

### AMR-S2: Add the attribution formatter owner

Create:

- `neotrade3/analysis/attribution_markdown_report.py`

Public function:

- `build_attribution_markdown_report(*, year: int, limit: int, ranking: list[dict[str, Any]], aggregate: dict[str, Any], attribution_rows: list[dict[str, Any]], backtest_payload: dict[str, Any]) -> str`

Implementation rules:

- accept already prepared inputs only
- compute formatter-local derivations inside the owner:
  - `top_reasons`
  - `early_exits`
  - section-local filtered sample lists
- assemble and return the final Markdown string
- do not write files or mutate inputs

Completion check:

- the visible Markdown contract has one dedicated owner outside the script

### AMR-S3: Switch the scorecard script consumer

In `_write_markdown_report(...)`:

- keep the function as the file-output boundary
- replace inline `lines.append(...)` assembly with one call to `build_attribution_markdown_report(...)`
- keep `output_path.write_text(..., encoding="utf-8")`

Do not change:

- `report_path`
- encoding
- any upstream payload building
- any section wording

Completion check:

- the script stops owning Markdown projection logic
- the script remains the file writer

### AMR-S4: Add formatter-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_markdown_report.py`

Minimum cases:

- renders the current headline and required section headers
- renders summary bullets with and without backtest summary payload
- renders reason-distribution counts from `reason_bucket`
- truncates each sample section to at most 20 rendered bullets
- returns a string ending with `\n`

Completion check:

- the formatter contract is directly locked without relying on broad script integration

### AMR-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_markdown_report.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_markdown_report.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_markdown_report.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `build_attribution_markdown_report(...)`

Completion check:

- syntax validation passes
- formatter-focused verification passes with the best available runner in the current environment

### AMR-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-markdown-report-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-markdown-report-plan.md`
- `neotrade3/analysis/attribution_markdown_report.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_markdown_report.py`

Must exclude:

- changes to `generate_lowfreq_top200_process_research_report.py`
- changes to aggregation owners
- changes to reasoning owners
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally rewriting visible Markdown text while moving the formatter

Guard:

- assert key headings, bullet copy, and sample truncation directly in formatter-focused tests

Risk 2:

- broadening this slice into a cross-report formatting framework

Guard:

- keep the owner attribution-specific and accept the current prepared payloads directly

## 6. Success Criteria

This slice is complete when:

- the scorecard Markdown formatter has one analysis-side owner
- the script no longer owns the inline line-assembly block
- file output remains in the script
- visible report wording and section order remain unchanged
- focused verification passes
- syntax verification passes
