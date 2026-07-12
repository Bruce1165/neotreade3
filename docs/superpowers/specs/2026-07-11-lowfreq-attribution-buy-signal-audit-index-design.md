Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report buy-signal-audit index contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Buy-Signal-Audit Index Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the attribution signal snapshot extraction.

This slice freezes only the pure audit-index assembler that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `_build_buy_signal_audit_index(...)`

The goal is to:

- move the pure `entries -> code-index` contract into one analysis owner
- keep `_analyze_topk(...)` and `_extract_execution_reason(...)` orchestration in the script
- preserve current filtering and sorting rules exactly
- add direct owner-focused coverage for the index contract

This design is not:

- a rewrite of `_extract_execution_reason(...)`
- a rewrite of `_analyze_topk(...)`
- a rewrite of buy-signal-audit event production
- a rewrite of report row assembly

Project-phase note:

- domain: `top200 attribution report buy signal audit index`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- filtering out non-dict audit entries
- filtering out entries with blank `code`
- cloning retained entries
- grouping entries by `code`
- stable in-group sorting by `(date, event)`
- reuse of one dedicated analysis owner
- owner-focused tests for filtering and sorting behavior

Excluded:

- changes to execution reason wording
- changes to audit event schema
- changes to report output schema
- changes to engine/API contracts

## 3. Existing Context

Current repository evidence shows:

- the report script still owns one pure index assembler:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
- the result is consumed only as a preparatory map for execution reasoning:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
- there is no existing dedicated owner-focused carrier for this helper

The problem is:

- this grouping/sorting kernel is still embedded in the report script
- the helper is pure and self-contained
- the helper belongs to report-consumer audit assembly, not producer ownership

## 4. Approach Options

### Option A: Move only the pure audit-index assembler into a dedicated analysis owner and keep all report orchestration in the script (Recommended)

- add one small analysis module
- move only the `entries -> grouped/sorted index` logic
- keep the script as a thin consumer

Pros:

- isolates a real contract kernel with minimal risk
- preserves current report flow exactly
- avoids broadening into execution reasoning or row assembly

Cons:

- the script still keeps downstream orchestration

### Option B: Merge this helper into `attribution_reasoning.py`

Pros:

- fewer files

Cons:

- mixes index assembly with visible reason-selection helpers
- makes the owner file less coherent

### Option C: Move a larger report-prep bundle together

Pros:

- removes more inline script code

Cons:

- broadens the slice beyond the proven narrow cut
- increases regression surface

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Create one dedicated report-side owner:

- `neotrade3/analysis/attribution_audit_index.py`

Recommended function:

- `build_buy_signal_audit_index(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]`

Why create a new file:

- this helper is index assembly, not reason selection
- it is distinct from signal snapshot assembly
- a dedicated file keeps the contract discoverable and avoids overloading other owners

### 5.2 Script Boundary

The script should keep:

- deciding when to build the index from `summary["buy_signal_audit"]`
- passing the per-code list into `_extract_execution_reason(...)`
- all downstream reasoning and fallback logic

The script should no longer own:

- filtering invalid audit entries
- grouping audit entries by `code`
- sorting each code bucket by `(date, event)`

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- ignore non-dict entries
- read `code` via string normalization and ignore blank codes
- append a cloned `dict(entry)` into the grouped bucket
- sort each bucket by `(str(date), str(event))`
- return a plain dict mapping `code -> list[entry]`

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_audit_index.py`

Minimum owner cases:

- filters non-dict and blank-code entries
- sorts a single code bucket by `date` then `event`
- keeps buckets separated by `code`

Nearby consumer rerun:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

Note:

- repository evidence does not show an existing direct consumer assertion for the index helper itself, so this slice relies on new owner-focused tests plus a nearby report regression rerun

## 6. Risks and Guardrails

Main risk:

- broadening into execution reasoning or report orchestration

Guardrail:

- move only the pure index assembler

Secondary risk:

- silently drifting current in-bucket sort order

Guardrail:

- freeze `(date, event)` sorting exactly
- verify direct owner tests plus nearby report regression

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_audit_index.py`
2. move the assembler there
3. switch the script helper to a thin wrapper
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the buy-signal-audit index contract has one analysis owner
- the report script no longer owns the grouping/sorting logic inline
- grouped output stays unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
