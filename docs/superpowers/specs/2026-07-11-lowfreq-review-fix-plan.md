# Lowfreq Review-Fix Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-review-fix-design.md`

## 1. Goal

This plan covers one narrow `review-fix` slice after the recent lowfreq checkpoint review.

This slice handles only the four approved review findings:

- correct the misleading elite soft-flag rejection wording
- add consumer regression proving non-elite signals do not enter reservation under full-book conditions
- add consumer regression proving `trade_block_reason` maps `min_amount` and `participation_rate` into `trade_blocks`
- add consumer regression proving system-exit watch expiry can be followed by same-day restart

The goal is to:

- preserve current runtime behavior
- restrict production movement to one wording-only fix
- lock the missing buy-side and sell-side consumer behaviors with focused tests
- avoid any new ownerization topic or runtime-shell refactor

This slice does not:

- refactor `lowfreq_engine_v16_advanced.py`
- change `plan_system_exit_application(...)`
- change `resolve_trade_block_reason(...)`
- add a new shared owner
- touch unrelated workspace changes

## 2. Starting Point

Current repository evidence shows:

- `elite_execution_candidate.py` rejects any non-empty `soft_flags`, but the detail wording overstates that those flags are specifically `soft-retained`
- current reservation-path tests prove elite reservation positive flows, but not non-elite negative flows
- current owner tests prove `min_amount` and `participation_rate` can be returned, but consumer mapping is not locked end-to-end
- current sell-side tests do not lock the combined path where an existing watch expires and then restarts on the same day

Relevant evidence files:

- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

So the correct next slice is:

- one semantic-copy correction in the elite owner
- plus missing consumer regressions only

## 3. Implementation Strategy

Production file boundary:

- `neotrade3/decision_engine/elite_execution_candidate.py`

Consumer regression file boundary:

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

No-change evidence-only files:

- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`

Implementation principle:

- fix wording where repository evidence shows semantic drift
- add tests where repository evidence shows missing behavioral locks
- do not broaden into another refactor

## 4. Execution Steps

### RF-S1: Freeze file boundary and observable contract

Before implementation, freeze the target file set to:

- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Freeze the observable behavior to preserve:

- any non-empty `soft_flags` still make elite reservation ineligible
- `blocked_reason` remains `elite_execution_candidate_rejected`
- role and score threshold logic remain unchanged
- elite positive reservation behavior remains unchanged
- `trade_block_reason` buy-side mapping remains `limit_up -> buy_limit_up`, `min_amount -> buy_min_amount`, `participation_rate -> buy_participation_rate`
- system-exit expiry does not force an unintended sell when a same-day restart path should occur

Completion check:

- no additional production files are needed
- no new owner contract is introduced

### RF-S2: Correct elite soft-flag detail wording

In `neotrade3/decision_engine/elite_execution_candidate.py`:

- replace the current soft-flag detail text with wording that correctly covers any non-empty `soft_flags`

Implementation rules:

- do not change the `eligible` boolean logic
- do not change the `blocked_reason`
- do not change score thresholds
- do not change reason ordering

Completion check:

- the wording no longer falsely implies every soft flag is specifically `soft-retained`

### RF-S3: Add reservation negative consumer regression

In `tests/unit/test_lowfreq_engine_v16_signal_convergence.py` add one focused full-book reservation negative path covering:

- follower signal
- soft-flagged leader
- unknown-wave leader below the elite unknown-wave threshold

Test rules:

- keep reservation enabled
- keep the book full so the reservation path is exercised if eligible
- assert that these signals do not produce `reservation_created`
- assert that these signals do not increment `buy_reserved_due_to_full_book`
- assert that they do not execute trades through reservation release

Completion check:

- non-elite reservation rejection is locked at consumer level

### RF-S4: Add trade-block mapping consumer regressions

In `tests/unit/test_lowfreq_engine_v16_signal_convergence.py` add focused buy-side cases for:

- `min_amount`
- `participation_rate`

Test rules:

- drive the real `run_backtest()` path
- configure `_get_bar(...)` and execution constraints so each case isolates a single block reason
- assert the blocked trade is not executed
- assert `trade_blocks["buy_min_amount"]` increments only for the first case
- assert `trade_blocks["buy_participation_rate"]` increments only for the second case

Completion check:

- the already-existing buy-side mapping in the engine is covered end-to-end

### RF-S5: Add system-exit expiry-plus-restart consumer regression

In `tests/unit/test_lowfreq_engine_v16_sell_logic.py` add one focused case covering:

- an existing watch that expires on the current day
- a same-day passing snapshot
- immediate restart of the watch with fresh `observe/start/expire/hits/last_reason/last_hit`

Test rules:

- assert the prior watch does not survive as stale state
- assert the restarted watch writes the new values
- assert no premature sell signal is emitted

Completion check:

- the combined expiry-plus-restart path is locked at consumer level

### RF-S6: Minimum verification

Run at minimum:

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/elite_execution_candidate.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Optional guard if needed during debugging:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Completion check:

- syntax validation passes
- buy-side consumer regressions pass
- sell-side consumer regressions pass

### RF-S7: Narrow commit

For the plan commit, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-review-fix-plan.md`

For the implementation commit, stage only:

- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_application.py`
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- the elite wording fix accidentally changes business semantics

Guard:

- edit only the human-readable soft-flag detail string

Risk 2:

- reservation negative regression accidentally asserts implementation trivia instead of behavior

Guard:

- assert only on runtime outputs such as trades, `trade_blocks`, and audit events

Risk 3:

- the trade-block mapping cases collide with other block reasons and become ambiguous

Guard:

- isolate each case with explicit bar data and execution settings

Risk 4:

- the system-exit combined test expands into owner or engine refactor

Guard:

- treat it as a consumer regression only
- change production code only if a real failure proves existing behavior drift

## 6. Success Criteria

This slice is complete when:

- elite soft-flag wording is semantically correct
- non-elite full-book signals are proven not to enter reservation
- `min_amount` and `participation_rate` are proven to map into buy-side `trade_blocks`
- system-exit expiry plus same-day restart is proven by consumer regression
- no new ownerization topic or unrelated refactor is introduced

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-review-fix-plan.md`

It must exclude:

- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- any other workspace changes
