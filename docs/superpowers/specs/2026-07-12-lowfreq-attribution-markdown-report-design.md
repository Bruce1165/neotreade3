Status: active
Owner: lowfreq / analysis
Scope: Narrow extraction of attribution report Markdown formatter from scorecard script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Markdown Report Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the execution limit-window extraction.

This slice freezes only the pure Markdown text assembly that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_write_markdown_report(...)`

The goal is to:

- move the Markdown line-assembly contract into one analysis-side formatter owner
- keep the script responsible for file paths and `write_text(...)`
- preserve the current section order, copy, sample selection, and visible text semantics exactly
- add direct formatter-focused coverage for the assembled text

This design is not:

- a rewrite of attribution aggregation
- a rewrite of row projection
- a general reporting framework for all lowfreq scripts
- a change to any report wording, limits, or filtering rules

Project-phase note:

- domain: `top200 attribution markdown report`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the `lines.append(...)` Markdown assembly logic from `_write_markdown_report(...)`
- preserving the current title, section order, bullet text, blank-line layout, and top-20 sample truncation
- keeping `Counter(...)` and early-exit sample selection with the formatter if they remain part of text assembly
- adding formatter-focused tests for the rendered Markdown string

Excluded:

- changing `report_path`
- changing `output_path.write_text(...)`
- changing `aggregate`, `ranking`, `attribution_rows`, or `backtest_payload` payload shapes
- sharing a formatter with `generate_lowfreq_top200_process_research_report.py`
- introducing HTML, templates, or a generic report DSL

## 3. Existing Context

Current repository evidence shows:

- the attribution scorecard script still owns one self-contained Markdown formatter:
  - [generate_lowfreq_top200_attribution_report.py:L841-L902](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L841-L902)
- the block is pure once `ranking`, `aggregate`, `attribution_rows`, and `backtest_payload` are already prepared
- the script still computes:
  - `top_reasons = Counter(...)`
  - `early_exits = [...]`
  - all section lines and bullets
- another lowfreq report script also has its own inline Markdown writer:
  - [generate_lowfreq_top200_process_research_report.py:L656-L718](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_process_research_report.py#L656-L718)
- there is no existing shared report formatter owner under `neotrade3/analysis/`

The current problem is:

- the visible report text contract is still embedded in the consumer script
- section rendering and file IO still live in the same function
- there is no single owner for the attribution report Markdown payload

## 4. Approach Options

### Option A: Add an attribution-specific Markdown formatter owner that returns the final text, and keep file writing in the script (Recommended)

- add one dedicated analysis module for the scorecard Markdown formatter
- move line assembly, section ordering, and section-local sample selection into that owner
- keep `report_path` selection and `write_text(...)` in the script

Pros:

- isolates a real pure-output contract with minimal regression surface
- keeps the script as a thin file-output consumer
- matches the current owner-per-contract extraction path

Cons:

- another lowfreq script still keeps its own Markdown formatter inline

### Option B: Keep formatting in the script and only wrap `write_text(...)`

Pros:

- smallest code movement

Cons:

- does not remove the visible Markdown contract from the script
- produces a thin wrapper with no owner value

### Option C: Build a shared generic Markdown report framework for attribution and process-research together

Pros:

- fewer report-specific formatter functions in the long run

Cons:

- broadens scope beyond the current evidence
- the two reports have different payload shapes and section semantics
- increases abstraction risk during bootstrap

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new analysis owner:

- `neotrade3/analysis/attribution_markdown_report.py`

Recommended public function:

- `build_attribution_markdown_report(...) -> str`

Why this file:

- the contract is report-side text projection, not reasoning, aggregation, or row assembly
- a dedicated file keeps the formatter discoverable and prevents overloading nearby owners
- keeping it attribution-specific avoids fabricating a cross-report abstraction without evidence

### 5.2 Contract Freeze

The formatter must preserve the current observable output contract:

- same title line:
  - `# Lowfreq Model {year} Top{limit} Scorecard Report`
- same section order:
  - `口径说明`
  - `总体摘要`
  - `原因分布`
  - `典型候选未转建仓样本`
  - `典型未进候选样本`
  - `典型提前离场样本`
- same blank-line spacing produced by the current `lines` list
- same summary bullet wording and field interpolation
- same `Counter(...).most_common()` ordering for reason distribution
- same top-20 truncation for each sample section

The formatter must return:

- one UTF-8 compatible Markdown string ending with a trailing newline

The formatter must not:

- write files
- create directories
- mutate the input payloads
- normalize or reinterpret upstream business fields

### 5.3 Boundary Placement

The new formatter owner should own:

- section-local derivations used only for Markdown rendering:
  - `top_reasons`
  - `early_exits`
  - the filtered top-20 sample lists for each section
- the final Markdown line assembly

The script should keep:

- deciding `report_path`
- calling `build_attribution_markdown_report(...)`
- writing the returned string through `output_path.write_text(...)`

This placement keeps the owner pure while preventing the script from retaining projection logic.

### 5.4 Input Surface

The formatter should accept the same prepared inputs already present at the script boundary:

- `year: int`
- `limit: int`
- `ranking: list[dict[str, Any]]`
- `aggregate: dict[str, Any]`
- `attribution_rows: list[dict[str, Any]]`
- `backtest_payload: dict[str, Any]`

Why keep this input surface:

- it avoids widening the slice into upstream precomputation refactors
- it preserves the current script call site almost one-for-one
- it lets the formatter own only presentation-side derivations

### 5.5 Testing Strategy

Add one formatter-focused carrier:

- `tests/unit/test_lowfreq_attribution_markdown_report.py`

Minimum owner cases:

- renders the current headline and required section headers
- renders the current summary bullets from `aggregate` and optional backtest summary
- renders reason-distribution bullets using the current `reason_bucket` counts
- truncates the three sample sections to at most 20 entries
- returns a string that ends with `\n`

Nearby consumer rerun:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - syntax verification only; no new broad integration harness is required for this slice

## 6. Risks and Guardrails

Main risk:

- silently changing visible report wording or section ordering while moving the formatter

Guardrail:

- freeze the current section sequence and literal bullet copy in formatter-focused tests

Secondary risk:

- over-abstracting toward a shared report framework without consumer evidence

Guardrail:

- keep the owner attribution-specific and accept the current prepared payloads directly

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_markdown_report.py`
2. implement `build_attribution_markdown_report(...) -> str`
3. switch `_write_markdown_report(...)` to call the new owner and keep only `write_text(...)`
4. add formatter-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the scorecard Markdown contract has one analysis-side owner
- the script no longer owns the inline `lines.append(...)` assembly
- file output stays in the script
- visible report wording and section order stay unchanged
- formatter-focused tests pass
- syntax verification passes
