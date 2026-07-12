Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow execution fallback reason extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Execution Fallback Reason Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-fallback-reason-design.md`

## 1. Goal

This plan covers only the next narrow slice after the simple daily-audit payload extraction.

This slice only handles:

- the final fallback reason ordering inside `_extract_execution_reason(...)`
- one shared reasoning helper for that fallback ordering
- owner-focused tests for the fallback contract

The goal is to:

- move execution fallback reason selection out of the script
- preserve current reason texts, current precedence, and current data-access behavior exactly
- keep `attribution_reasoning.py` as the canonical owner of execution reason policy

This slice does not:

- extract the whole `_extract_execution_reason(...)` function
- move SQL reads or signal lookups
- change `resolve_execution_audit_primary_reason(...)`
- change late-trade suffix behavior

## 2. Starting Point

Current repository evidence shows:

- the audit-path execution reason already has an owner in `attribution_reasoning.py`
- the script still owns the non-audit fallback ordering
- canonical text for `positions_full` and `chase_entry_blocked` already exists in the reasoning owner

So the correct next slice is:

- add one pure fallback-ordering helper
- keep boolean derivation in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_execution_fallback_reason.py`
- `tests/unit/test_lowfreq_attribution_reasoning.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-fallback-reason-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-fallback-reason-plan.md`

## 4. Execution Steps

### EFR-S1: Freeze the fallback reason contract

Freeze the current fallback order as exactly:

1. all limit-up
2. positions full
3. chase blocked
4. generic fallback

Freeze the current returned texts:

- `"信号存在但连续涨停，无法成交"`
- `"信号存在但同期仓位已满"`
- `"信号存在但因追高型买点被硬禁"`
- `"信号存在但未形成实际成交，需复核执行窗口"`

Completion check:

- no text changes
- no order changes

### EFR-S2: Extend the reasoning owner

Add to:

- `neotrade3/analysis/attribution_reasoning.py`

Public function:

- `resolve_execution_fallback_reason(*, all_limit_up: bool, positions_full: bool, chase_blocked: bool) -> str`

Implementation rules:

- accept only already derived booleans
- resolve final fallback text only
- reuse canonical block-reason text mapping where possible

Completion check:

- fallback reason selection has one canonical owner outside the script

### EFR-S3: Switch the script fallback exit

In `_extract_execution_reason(...)`:

- keep deriving `all_limit_up`
- keep deriving `positions_full`
- keep deriving `chase_blocked`
- replace the remaining inline fallback returns with one call to `resolve_execution_fallback_reason(...)`

Do not change:

- audit-priority early return
- SQL access
- `execution_mode` semantics
- `engine._chase_entry_snapshot(...)` probing

Completion check:

- only the final fallback text selection leaves the script

### EFR-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_execution_fallback_reason.py`

Minimum cases:

- all-limit-up beats all other states
- positions-full uses canonical text
- chase-blocked uses canonical text
- generic fallback remains unchanged

Keep and rerun script-focused regression:

- `test_extract_execution_reason_skips_full_book_in_unbounded_mode`
- `test_extract_execution_reason_uses_buy_signal_audit_before_fallback`
- `test_extract_execution_reason_marks_late_buy_after_top`

Completion check:

- owner contract is directly locked
- script observable behavior stays unchanged on anchored cases

### EFR-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_reasoning.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_execution_fallback_reason.py tests/unit/test_lowfreq_attribution_reasoning.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_execution_fallback_reason.py tests/unit/test_lowfreq_attribution_reasoning.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against the new owner and the existing script-level anchored cases

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### EFR-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-fallback-reason-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-execution-fallback-reason-plan.md`
- `neotrade3/analysis/attribution_reasoning.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_execution_fallback_reason.py`

Must exclude:

- execution audit reason owner changes unrelated to fallback ordering
- daily-audit changes
- aggregate or row projection changes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally moving data-access logic together with reason selection

Guard:

- pass only booleans into the owner

Risk 2:

- accidentally changing existing reason precedence

Guard:

- lock exact order in owner-focused tests

## 6. Success Criteria

This slice is complete when:

- execution fallback ordering is owned in `attribution_reasoning.py`
- `_extract_execution_reason(...)` keeps the same data-access behavior
- current reason text and precedence remain unchanged
- focused verification passes
- syntax verification passes
