# Lowfreq System Exit Grace Eligibility Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-grace-eligibility-design.md`

## 1. Goal

This plan covers only the next narrow `system_exit_grace eligibility policy` slice after the `formal-front build bridge` extraction.

This slice only handles:

- buy-progress-label fallback resolution for grace eligibility
- profit-keep ratio calculation
- scope-aware grace-threshold selection
- leader-hold candidate gating
- the final boolean grace-eligibility predicate

The goal is to:

- move the real grace-eligibility rule body into one shared owner
- keep sell-state mutation and audit-event flow unchanged in the engine
- preserve current market/sector threshold semantics exactly
- preserve current label fallback semantics exactly
- add owner-focused coverage for the policy contract

This slice does not:

- rewrite `check_sell_signal_v2()`
- rewrite `_apply_system_exit_state(...)`
- rewrite `_record_system_exit_grace_audit_event(...)`
- rewrite `_system_exit_expire_date(...)`
- rewrite market/sector snapshots

## 2. Starting Point

Current repository evidence shows:

- `generate_buy_signals()` is now largely orchestration shell
- the next dense engine-owned kernel sits in the sell path inside `system_exit_grace`
- current sell-logic regressions already cover the behavior of this rule set

Relevant current engine helpers:

- `_resolve_buy_progress_label(...)`
- `_profit_keep_ratio(...)`
- `_system_exit_grace_thresholds(...)`
- `_is_leader_hold_candidate(...)`
- `_eligible_for_system_exit_grace(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`

So the correct next slice is:

- extract only the pure policy kernel
- keep state writes and audit side effects in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/system_exit_grace.py`

Move the pure rule helpers there:

- `resolve_buy_progress_label(...)`
- `profit_keep_ratio(...)`
- `system_exit_grace_thresholds(...)`
- `is_leader_hold_candidate(...)`
- `is_eligible_for_system_exit_grace(...)`

Keep the engine methods as thin facades:

- `_resolve_buy_progress_label(...)`
- `_profit_keep_ratio(...)`
- `_system_exit_grace_thresholds(...)`
- `_is_leader_hold_candidate(...)`
- `_eligible_for_system_exit_grace(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_grace_policy.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`

## 4. Execution Steps

### SEGP-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_grace.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_grace_policy.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`

Freeze the observable contract:

- explicit `buy_progress_label` still wins over wave fallback
- `1浪 -> 前置布局`
- `3浪 -> 早窗`
- otherwise `其它`
- profit-keep ratio still returns `0.0` when `peak_return_pct <= 0`
- market scope still uses market settings and the max with legacy `SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT`
- sector scope still uses sector settings directly
- market scope still requires leader-hold eligibility
- sector scope still requires role in `{"龙头", "中军"}`
- accepted labels still limited to `{"早窗", "前置布局"}`
- positive-return gating still respects `SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN`

Completion check:

- no sell-state mutation or audit-event behavior is part of this slice

### SEGP-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/system_exit_grace.py`

Move the pure policy body into:

- `resolve_buy_progress_label(...)`
- `profit_keep_ratio(...)`
- `system_exit_grace_thresholds(...)`
- `is_leader_hold_candidate(...)`
- `is_eligible_for_system_exit_grace(...)`

Implementation rules:

- accept explicit scalar inputs rather than the engine instance
- do not write to `trade`
- do not emit events
- do not compute expiry dates

Completion check:

- the grace-eligibility policy can be understood independently from the sell-state machine

### SEGP-S3: Switch engine helpers to thin facades

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helpers
- replace the real bodies of:
  - `_resolve_buy_progress_label(...)`
  - `_profit_keep_ratio(...)`
  - `_system_exit_grace_thresholds(...)`
  - `_is_leader_hold_candidate(...)`
  - `_eligible_for_system_exit_grace(...)`

Do not change:

- `_apply_system_exit_state(...)`
- `check_sell_signal_v2()`
- market/sector snapshots
- grace audit-event emission
- grace-date/scope/reason writes

Completion check:

- the engine keeps the same helper names but no longer owns the real rule body inline

### SEGP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_system_exit_grace_policy.py`

Minimum owner cases:

- explicit label overrides wave fallback
- `1浪` maps to `前置布局`
- `3浪` maps to `早窗`
- profit-keep ratio returns `0.0` for non-positive peak return
- sector thresholds return the sector tuple
- market thresholds return the market tuple
- market grace eligibility accepts a valid leader case
- grace eligibility rejects a non-early label
- grace eligibility rejects insufficient profit-keep ratio
- sector grace eligibility rejects excessive hold days

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`

Completion check:

- the policy has direct focused coverage
- current sell-side consumer tests still pass unchanged

### SEGP-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_system_exit_grace_policy.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py tests/unit/test_lowfreq_intent_conflicts.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/system_exit_grace.py tests/unit/test_lowfreq_engine_v16_system_exit_grace_policy.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### SEGP-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_grace.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_grace_policy.py`

Must exclude:

- `apps/api/main.py`
- market/sector snapshot helpers
- sell-state mutation helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into sell-state mutation or event recording

Guard:

- keep extraction limited to pure policy helpers only

Risk 2:

- drifting current threshold precedence for market grace

Guard:

- preserve the current `max(market_setting, legacy_min_peak_setting)` rule explicitly in the owner

Risk 3:

- mixing sector-role and market-leader gating

Guard:

- preserve the current scope split exactly

## 6. Success Criteria

This slice is complete when:

- `system_exit_grace` eligibility rules have one shared owner
- the real rule body no longer lives inline in the engine
- trade mutation and audit-event flow remain unchanged
- owner-focused policy tests pass
- current sell-side grace regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-grace-eligibility-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_grace.py`
- `tests/unit/*`
- any other workspace changes
