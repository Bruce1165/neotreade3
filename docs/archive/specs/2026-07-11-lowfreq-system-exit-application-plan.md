# Lowfreq System Exit Application Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-application-design.md`

## 1. Goal

This plan covers only the next narrow `system exit application` slice after the `trade block reason` extraction.

This slice only handles:

- expire/start/review/grace/confirm application-plan interpretation
- owner-focused coverage for the application-plan contract

The goal is to:

- move the real application-plan shell into one shared owner
- keep transition evaluation unchanged in the engine
- keep `trade` mutation unchanged in the engine
- keep sell and grace audit-event emission unchanged in the engine
- keep final `SellSignal` construction unchanged in the engine
- preserve current branch ordering and application semantics exactly

This slice does not:

- rewrite `evaluate_system_exit_transition(...)`
- rewrite `_eligible_for_system_exit_grace(...)`
- rewrite `_system_exit_attr_names(...)`
- rewrite `_reset_system_exit_state(...)`
- rewrite `_reset_all_system_exit_states(...)`
- rewrite `_record_system_exit_audit_event(...)`
- rewrite `_record_system_exit_grace_audit_event(...)`
- rewrite `check_sell_signal_v2()`

## 2. Starting Point

Current repository evidence shows:

- the transition kernel is already ownerized in `system_exit_state_machine.py`
- `_apply_system_exit_state(...)` still owns the remaining dense application shell
- this helper is active on both market and sector sell paths
- current sell-side regressions already cover its main behaviors

Relevant current engine helper:

- `_apply_system_exit_state(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

So the correct next slice is:

- extract only the pure application-plan layer
- keep transition evaluation, mutation, audit, and final sell construction in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/system_exit_application.py`

Move the pure plan helper there:

- `plan_system_exit_application(...)`

Keep the engine method as a thinner facade:

- `_apply_system_exit_state(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

## 4. Execution Steps

### SEA-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_application.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Freeze the observable contract:

- expired watch still emits the expire action before current-day processing
- non-passing snapshot still returns `None` after optional expiry handling
- first valid hit still starts watch and writes `observe/start/expire/hits/last_reason/last_hit`
- passing non-start path still updates `last_reason`
- increment path still updates `hits` and `last_hit`
- review path still emits the review intent
- grace path still resets all scopes and returns no sell signal
- prior-grace follow-up path still emits the grace-follow-up event intent
- final confirmation still resets only current scope and yields the current sell payload contract

Completion check:

- no actual mutation, reset execution, audit emission, or `SellSignal` construction is part of this slice

### SEA-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/system_exit_application.py`

Move the pure application-plan body into:

- `plan_system_exit_application(...)`

Implementation rules:

- accept already-derived transition payloads and scalar inputs
- do not resolve attr names inside the owner
- do not call transition evaluation inside the owner
- do not write to `trade`
- do not emit events
- do not instantiate `SellSignal`

Completion check:

- the application plan can be understood independently from engine-side mutation and audit flow

### SEA-S3: Switch `_apply_system_exit_state(...)` to a thinner facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- keep transition evaluation where it is
- replace the dense application branch body with owner planning plus engine side effects

Do not change:

- `_eligible_for_system_exit_grace(...)`
- `_record_system_exit_audit_event(...)`
- `_record_system_exit_grace_audit_event(...)`
- `_reset_system_exit_state(...)`
- `_reset_all_system_exit_states(...)`
- `check_sell_signal_v2()`

Completion check:

- the engine keeps the same helper name but no longer owns the dense application-plan mapping inline

### SEA-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

Minimum owner cases:

- expired non-passing transition returns expire intent only
- start-watch transition returns the expected start/update plan
- review transition returns increment plus review intent
- grace transition returns grace fields plus reset-all intent
- confirm-after-grace transition returns follow-up grace event plus sell payload
- plain confirm returns final sell payload and current-scope reset intent

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Completion check:

- the application shell has direct focused coverage
- current sell-side consumer tests still pass unchanged

### SEA-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_system_exit_application.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/system_exit_application.py tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### SEA-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-application-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-application-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_application.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

Must exclude:

- other sell-side helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into real mutation or audit emission

Guard:

- keep the owner limited to pure application planning only

Risk 2:

- drifting action ordering between expiry, start, review, grace, and final confirmation

Guard:

- preserve the current branch ordering exactly and test representative action shapes directly

Risk 3:

- leaking engine-only attr/write concerns into the owner

Guard:

- keep the owner output semantic and attr-name-agnostic

## 6. Success Criteria

This slice is complete when:

- the remaining application-plan shell has one shared owner
- `_apply_system_exit_state(...)` no longer owns the dense branch mapping inline
- mutation, audit, and final sell construction remain unchanged in the engine
- owner-focused application-plan tests pass
- current sell-side consumer regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-application-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_application.py`
- `tests/unit/*`
- any other workspace changes
