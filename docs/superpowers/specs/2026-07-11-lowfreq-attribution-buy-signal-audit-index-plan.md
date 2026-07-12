Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report buy-signal-audit index extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Buy-Signal-Audit Index Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-buy-signal-audit-index-design.md`

## 1. Goal

This plan covers only the next narrow report-prep slice after the attribution signal snapshot extraction.

This slice only handles:

- the pure `entries -> grouped/sorted audit index` contract used by `_build_buy_signal_audit_index(...)`
- reuse of one dedicated analysis owner
- direct owner-focused tests plus a nearby report regression rerun

The goal is to:

- remove the inline grouping/sorting helper from the script
- keep report orchestration stable
- preserve grouped output exactly

This slice does not:

- rewrite execution reasoning
- rewrite `_analyze_topk(...)`
- rewrite buy-signal-audit event production

## 2. Starting Point

Current repository evidence shows:

- `_build_buy_signal_audit_index(...)` is still inline in the report script
- the helper is pure and only prepares per-code audit lists
- repository evidence does not show a dedicated existing owner test for this helper

So the correct next slice is:

- extract only the index assembler
- keep the script as a thin consumer around it

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_audit_index.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_audit_index.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

## 4. Execution Steps

### ABAI-S1: Freeze observable index contract

Freeze the visible behavior:

- non-dict entries are ignored
- blank-code entries are ignored
- retained entries are cloned before storage
- buckets are keyed by normalized `code`
- each bucket is sorted by `(date, event)`

Completion check:

- no execution reasoning or report row logic is included in this slice

### ABAI-S2: Add the analysis owner

Create `neotrade3/analysis/attribution_audit_index.py` with:

- `build_buy_signal_audit_index(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]`

Implementation rules:

- keep only local filtering/grouping/sorting logic
- use plain Python data structures
- do not call DB or engine methods
- do not compose report rows

Completion check:

- the contract is independently understandable from the report script

### ABAI-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `build_buy_signal_audit_index(...)`
- replace the inline helper body with a single delegation call

Do not change:

- the call site inside `_analyze_topk(...)`
- downstream `_extract_execution_reason(...)` behavior

Completion check:

- the script no longer owns the grouping/sorting logic inline

### ABAI-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_audit_index.py`

Minimum owner cases:

- filters invalid entries and blank codes
- sorts a single code bucket by `date` then `event`
- keeps buckets separated by code

Completion check:

- the owner contract has direct focused coverage

### ABAI-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_audit_index.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `python3 -m py_compile neotrade3/analysis/attribution_audit_index.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_audit_index.py`

Completion check:

- owner tests pass
- nearby report regression passes
- syntax validation passes

### ABAI-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_audit_index.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_audit_index.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into execution reasoning

Guard:

- move only the index assembler

Risk 2:

- silently drifting the in-bucket ordering contract

Guard:

- freeze `(date, event)` sorting exactly
- verify owner-focused tests plus nearby report regression

## 6. Success Criteria

This slice is complete when:

- the buy-signal-audit index contract has one analysis owner
- the report script no longer owns the grouping/sorting logic inline
- grouped output remains unchanged
- owner-focused tests pass
- nearby report regression passes
- syntax verification passes
