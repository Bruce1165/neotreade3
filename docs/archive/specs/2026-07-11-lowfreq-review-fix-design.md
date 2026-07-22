# Lowfreq Review-Fix Design

Date: 2026-07-11

## 1. Goal

This design covers one narrow `review-fix` slice after the recent lowfreq checkpoint review.

This slice only fixes the four issues already confirmed by repository evidence:

- the `elite_execution_candidate` soft-flag rejection detail is semantically misleading
- there is no consumer regression proving non-elite signals do not enter reservation under full-book conditions
- there is no consumer regression proving `trade_block_reason` maps `min_amount` and `participation_rate` into `trade_blocks`
- there is no combined consumer regression for `system exit` watch expiry followed by same-day restart

The goal is to:

- preserve all currently intended runtime behavior
- tighten one misleading detail string in `elite_execution_candidate`
- add missing consumer regressions around reservation, trade-block mapping, and system-exit restart behavior
- avoid introducing any new ownerization topic
- avoid broadening into unrelated cleanup

This design is not:

- a new extraction slice
- a rewrite of `run_backtest()`
- a rewrite of `_apply_system_exit_state(...)`
- a rewrite of `plan_system_exit_application(...)`
- a rewrite of `resolve_trade_block_reason(...)`
- a broad review of all recent lowfreq slices

Project-phase note:

- domain: `lowfreq review-fix`
- change type: `migration follow-up / audit fix`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- one wording-only production fix in:
  - [elite_execution_candidate.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/elite_execution_candidate.py)
- consumer regression coverage in:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
- focused verification for the touched production/test files

Excluded:

- any new shared owner module
- any refactor of `lowfreq_engine_v16_advanced.py`
- any contract change for `system_exit_application.py`
- any cleanup beyond the four reviewed findings
- any unrelated workspace changes

## 3. Existing Evidence

### 3.1 Elite soft-flag wording mismatch

Current owner code in:

- [elite_execution_candidate.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/elite_execution_candidate.py#L39-L44)

uses:

- `存在 soft-retained 标记，不进入 elite execution 资格`

when any non-empty `soft_flags` are present.

Repository evidence shows the actual flag set is wider than `soft-retained`, including:

- `structure_soft_fail`
- `focus_soft_fail`
- `wave_uncertain`
- `history_short`

Evidence:

- [test_lowfreq_engine_v16_signal_convergence.py:L949-L1028](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L949-L1028)
- [test_lowfreq_engine_v16_signal_convergence.py:L1032-L1077](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L1032-L1077)

So the behavior is acceptable, but the wording is narrower than the real contract.

### 3.2 Missing non-elite reservation negative coverage

Current reservation-path regressions prove:

- elite signals can be reserved and later released
- elite signals can expire when the slot never opens

Evidence:

- [test_lowfreq_engine_v16_signal_convergence.py:L584-L816](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L584-L816)

But there is no consumer regression proving that non-elite signals under full-book conditions are blocked instead of entering reservation.

### 3.3 Missing `trade_block_reason -> trade_blocks` consumer coverage

Owner-level tests already prove `resolve_trade_block_reason(...)` can return:

- `min_amount`
- `participation_rate`

Evidence:

- [test_lowfreq_engine_v16_trade_block_reason.py:L74-L122](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_trade_block_reason.py#L74-L122)

Engine consumption code maps those reasons into `trade_blocks`:

- [lowfreq_engine_v16_advanced.py:L3725-L3729](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3725-L3729)
- [lowfreq_engine_v16_advanced.py:L3521-L3524](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3521-L3524)

But current consumer regression only locks the `limit_up` mapping path.

### 3.4 Missing system-exit expiry-plus-restart coverage

Current owner tests for `plan_system_exit_application(...)` cover:

- expire-only
- start-watch
- review/update
- grace
- confirm-after-grace
- plain confirm

Evidence:

- [test_lowfreq_engine_v16_system_exit_application.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_system_exit_application.py)

Current sell-side tests cover grace behavior and confirmation flow, but there is no combined consumer path proving:

- an existing watch first expires
- a same-day passing snapshot immediately starts a new watch

Evidence:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)

## 4. Approach Options

### Option A: Fix only the four reviewed findings (Recommended)

- adjust the elite soft-flag detail wording
- add one non-elite reservation negative regression
- add `trade_block_reason` consumer regressions for `min_amount` and `participation_rate`
- add one sell-side regression for expiry plus same-day restart

Pros:

- exactly matches the approved review boundary
- preserves atomicity
- keeps production movement minimal

Cons:

- leaves the minor `system_exit_application` contract drift for a later slice

### Option B: Include the minor `system_exit_application` contract drift now

Pros:

- resolves all currently known review notes at once

Cons:

- broadens beyond the approved four-issue boundary
- mixes behavior-locking work with a separate contract-shape cleanup

### Option C: Add tests only and leave the elite wording unchanged

Pros:

- smallest production diff

Cons:

- knowingly preserves misleading wording in a recently extracted owner

Decision:

- choose Option A

## 5. Design

### 5.1 Production Boundary

Only one production file should change:

- [elite_execution_candidate.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/elite_execution_candidate.py)

Allowed change:

- replace the current soft-flag rejection detail with wording that matches any non-empty `soft_flags`

Required behavior preservation:

- any non-empty `soft_flags` still make `eligible` false
- `blocked_reason` stays `elite_execution_candidate_rejected`
- score thresholds and role checks stay unchanged
- reason ordering stays unchanged relative to the existing function

This is a semantic-copy correction only, not a policy change.

### 5.2 Reservation Negative Regression

Add one focused consumer regression in:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

The test should prove that under `full book + reservation enabled` conditions, non-elite signals do not create a reservation.

Minimum negative cases:

- follower signal rejected by elite reservation eligibility
- soft-flagged leader rejected by elite reservation eligibility
- unknown-wave leader below the elite unknown-wave threshold rejected by elite reservation eligibility

Observable contract to freeze:

- `reservation_created` does not appear for those signals
- `buy_reserved_due_to_full_book` does not increment for those signals
- the signal remains blocked by the ordinary full-book path rather than entering reservation

The exact assertion surface should come from current runtime outputs rather than new instrumentation.

### 5.3 Trade-Block Mapping Regression

Add consumer-level coverage in:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

Minimum cases:

- a buy candidate blocked by `min_amount`
- a buy candidate blocked by `participation_rate`

Observable contract to freeze:

- `trade_blocks["buy_min_amount"]` increments only for the `min_amount` path
- `trade_blocks["buy_participation_rate"]` increments only for the `participation_rate` path
- the blocked trade is not executed

This locks the consumer wiring already present in:

- [lowfreq_engine_v16_advanced.py:L3725-L3729](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3725-L3729)

### 5.4 System-Exit Combined Regression

Add one sell-side consumer regression in:

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)

The test should cover one combined path:

- an existing watch is expired by current-day state
- the same evaluation pass receives a passing snapshot
- a new watch starts immediately on that same day

Observable contract to freeze:

- the previous watch does not survive after expiry
- the restarted watch writes the new `observe/start/expire/hits/last_reason/last_hit` values
- the path does not emit an early sell just because the prior watch expired

This is a consumer regression only. No owner contract change is required in this slice.

### 5.5 File Boundary

Expected touched files:

- `docs/superpowers/specs/2026-07-11-lowfreq-review-fix-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-review-fix-plan.md`
- `neotrade3/decision_engine/elite_execution_candidate.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Expected untouched files:

- `neotrade3/decision_engine/system_exit_application.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_application.py`
- `tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

Those files already provide evidence and do not need direct edits for this slice.

## 6. Risks and Guardrails

Risk 1:

- accidentally turning the elite wording fix into a policy change

Guardrail:

- only adjust the human-readable detail string
- keep all boolean eligibility logic and thresholds unchanged

Risk 2:

- overfitting the reservation negative regression to internal implementation details

Guardrail:

- assert on current public test outputs such as `trade_blocks`, `buy_signal_audit`, and executed trades
- do not assert on new internal locals

Risk 3:

- broadening the sell-side combined regression into a new `system_exit_application` refactor

Guardrail:

- add coverage only
- leave owner and engine contracts unchanged unless a real failing regression proves otherwise

Risk 4:

- mixing unrelated workspace changes into the commit

Guardrail:

- stage only the design doc for the spec commit
- keep the implementation commit limited to the production/test files above

## 7. Testing Strategy

Focused verification should include:

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/elite_execution_candidate.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py`

If needed, retain the already relevant owner guard:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_trade_block_reason.py`

The purpose is:

- syntax safety for touched Python files
- consumer-level regression proof for buy/execution wiring
- consumer-level regression proof for sell/system-exit restart wiring

## 8. Success Criteria

This slice is complete when:

- the elite soft-flag rejection detail no longer mislabels all soft flags as `soft-retained`
- full-book non-elite signals are proven not to enter reservation by consumer regression
- `min_amount` and `participation_rate` are proven to map into `trade_blocks` by consumer regression
- system-exit expiry plus same-day restart is proven by consumer regression
- no new ownerization topic is introduced
