# Lowfreq System Exit State Machine Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-state-machine-design.md`

## 1. Goal

This plan covers only the next narrow `system exit state machine` slice after the `thesis invalidation snapshot` extraction.

This slice only handles:

- watch expiry / start / review / confirm transition interpretation
- grace downgrade versus final confirmation branch interpretation
- owner-focused coverage for the transition contract

The goal is to:

- move the real transition kernel into one shared owner
- keep `trade` mutation unchanged in the engine
- keep sell and grace audit-event flow unchanged in the engine
- preserve current confirmation thresholds, review semantics, and final sell details exactly
- add direct focused coverage for the transition policy

This slice does not:

- rewrite `check_sell_signal_v2()`
- rewrite `_system_exit_attr_names(...)`
- rewrite `_reset_system_exit_state(...)`
- rewrite `_reset_all_system_exit_states(...)`
- rewrite `_record_system_exit_audit_event(...)`
- rewrite `_record_system_exit_grace_audit_event(...)`
- rewrite `_system_exit_expire_date(...)`
- rewrite market/sector exit snapshots
- rewrite `system_exit_grace` eligibility policy

## 2. Starting Point

Current repository evidence shows:

- hard invalidation, trend exhaustion, market/sector snapshots, and grace eligibility are already ownerized
- the remaining dense sell-side kernel is `_apply_system_exit_state(...)`
- current sell-logic regressions already cover:
  - first-hit observe
  - second-hit review
  - confirm sell
  - expiry reset
  - leader extra hits
  - grace downgrade
  - one-time grace usage
  - stop-loss preemption after prior downgrade

Relevant current engine helper:

- `_apply_system_exit_state(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

So the correct next slice is:

- extract only the pure state-machine transition kernel
- keep attr writes, audit side effects, and final `SellSignal` construction in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/system_exit_state_machine.py`

Move the pure transition helper there:

- `evaluate_system_exit_transition(...)`

Keep the engine method as a thin facade:

- `_apply_system_exit_state(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_state_machine.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

## 4. Execution Steps

### SESM-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_state_machine.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_state_machine.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Freeze the observable contract:

- market scope still uses market window and confirm-hit settings
- sector scope still uses sector window and confirm-hit settings
- leader hold still adds `LEADER_CONFIRM_EXTRA_HITS`
- watch still expires only when `elapsed > window`
- invalid snapshots still do not start or advance state
- the first valid hit still starts `observe`
- the second valid hit still enters `review`
- same-day repeated hits still do not increment hit count twice
- confirmation still requires `hit_count >= confirm_hits`
- grace downgrade still wins over final confirmation when eligible
- prior grace usage still emits the later `system_exit_downgraded_then_confirmed` branch
- confirmed details still replace `"确认候选"` with `"确认"`
- market confirmation still maps to `exit_scope = "portfolio"`
- sector confirmation still maps to `exit_scope = "sector_only"`

Completion check:

- no `trade` writes, audit side effects, or sibling-scope resets are part of this slice

### SESM-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/system_exit_state_machine.py`

Move the pure transition body into:

- `evaluate_system_exit_transition(...)`

Implementation rules:

- accept explicit already-derived inputs rather than the engine instance or `trade`
- do not compute trading-day differences inside the owner
- do not compute expire dates inside the owner
- do not write to `trade`
- do not emit events
- do not construct `SellSignal`

Completion check:

- the transition policy can be understood independently from engine-side mutation and audit flow

### SESM-S3: Switch `_apply_system_exit_state(...)` to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- replace the real transition body of `_apply_system_exit_state(...)`

Do not change:

- `_system_exit_attr_names(...)`
- `_reset_system_exit_state(...)`
- `_reset_all_system_exit_states(...)`
- `_record_system_exit_audit_event(...)`
- `_record_system_exit_grace_audit_event(...)`
- `_system_exit_expire_date(...)`
- `check_sell_signal_v2()`

Completion check:

- the engine keeps the same helper name but no longer owns the real transition rule body inline

### SESM-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_system_exit_state_machine.py`

Minimum owner cases:

- non-passing snapshot returns a no-op transition
- expired watch emits the expiry transition before current processing
- first valid hit starts watch with `observe`
- second distinct-day hit enters `review`
- same-day repeat hit does not increment hit count
- confirm threshold produces a confirmation transition
- grace-eligible confirmation returns a downgrade transition
- previously used grace returns the follow-up confirmation flag
- market confirmation returns `portfolio`
- sector confirmation returns `sector_only`

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Completion check:

- the transition policy has direct focused coverage
- current sell-side consumer tests still pass unchanged

### SESM-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_system_exit_state_machine.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/system_exit_state_machine.py tests/unit/test_lowfreq_engine_v16_system_exit_state_machine.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### SESM-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-state-machine-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-state-machine-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_state_machine.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_state_machine.py`

Must exclude:

- other sell-side helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into mutable `trade` writes or audit emission

Guard:

- keep the owner limited to intent-level transition output only

Risk 2:

- drifting hit-count and same-day repeat semantics

Guard:

- preserve repeated-day gating exactly and test it directly in the owner carrier

Risk 3:

- changing final confirmed details or scope mapping

Guard:

- preserve the `"确认候选" -> "确认"` replacement and current scope mapping exactly

## 6. Success Criteria

This slice is complete when:

- the system-exit transition kernel has one shared owner
- the real transition rule body no longer lives inline in the engine
- `trade` mutation, audit emission, and outer sell-chain orchestration remain unchanged
- owner-focused state-machine tests pass
- current sell-side consumer regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-state-machine-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_state_machine.py`
- `tests/unit/*`
- any other workspace changes
