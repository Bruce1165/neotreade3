# Lowfreq System Exit Snapshots Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-snapshots-design.md`

## 1. Goal

This plan covers only the next narrow `system exit snapshots` slice after the `system_exit_grace eligibility policy` extraction.

This slice only handles:

- market exit snapshot interpretation
- sector exit snapshot interpretation
- owner-focused coverage for the snapshot contract

The goal is to:

- move the real market/sector snapshot rule body into one shared owner
- keep upstream data acquisition unchanged in the engine
- keep sell-state mutation and audit-event flow unchanged in the engine
- preserve current threshold, evidence, and `details` semantics exactly
- add direct focused coverage for the snapshot policy

This slice does not:

- rewrite `check_sell_signal_v2()`
- rewrite `_apply_system_exit_state(...)`
- rewrite `_position_contract_snapshot(...)`
- rewrite `_market_top_snapshot(...)`
- rewrite `_market_drawdown_snapshot(...)`
- rewrite `detect_sector_cooldown(...)`

## 2. Starting Point

Current repository evidence shows:

- the buy side is now largely orchestration shell after recent owner extractions
- the next dense and reusable engine-owned kernel is the sell-side market/sector snapshot policy
- existing sell tests already pin the observable behavior of both snapshots
- the engine helpers are consumed both by the sell confirm chain and the hold/exit contract snapshot

Relevant current engine helpers:

- `_market_exit_snapshot(...)`
- `_sector_exit_snapshot(...)`

Current consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

So the correct next slice is:

- extract only the pure snapshot interpretation kernel
- keep upstream sourcing and downstream state transitions in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/system_exit_snapshots.py`

Move the pure snapshot helpers there:

- `build_market_exit_snapshot(...)`
- `build_sector_exit_snapshot(...)`

Keep the engine methods as thin facades:

- `_market_exit_snapshot(...)`
- `_sector_exit_snapshot(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_system_exit_snapshots.py`

Keep existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

## 4. Execution Steps

### SESP-S1: Freeze file boundary and behavior contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_snapshots.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_snapshots.py`

Keep consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Freeze the observable contract:

- market label still falls back from `top_snapshot` to `drawdown_snapshot` to `"市场"`
- market key still falls back from facade input to resolved proxy key
- `price_trend_weak` still means `break_ma20 or ma20_weak`
- `breadth_weak` still means `breadth_ratio < 0.40`
- `drawdown_weak` still means `drawdown_pct <= MARKET_EXIT_MIN_DRAWDOWN_PCT`
- market `condition_pass` still requires trend weak plus breadth weak, with at least two pieces of evidence
- drawdown weakness remains observation-only evidence
- sector `follower_weak` still means `follower_weakness > 0.6`
- sector `trend_deteriorating` still means `trend_state in {"diverging", "falling"}`
- sector `leader_rollover` still means `leader_strength < 0.55 or leader_avg < 8.0`
- sector `condition_pass` still requires both `trend_deteriorating` and `follower_weak`
- cooldown and leader-rollover remain observation-only evidence
- both helpers still return `None` only when no evidence exists
- the exact `details` strings remain unchanged

Completion check:

- no upstream sourcing or sell-state mutation behavior is part of this slice

### SESP-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/system_exit_snapshots.py`

Move the pure interpretation body into:

- `build_market_exit_snapshot(...)`
- `build_sector_exit_snapshot(...)`

Implementation rules:

- accept explicit already-fetched inputs rather than the engine instance
- do not resolve market proxy inside the owner
- do not call data sources inside the owner
- do not write to `trade`
- do not emit events

Completion check:

- the snapshot policy can be understood independently from the sell-state machine

### SESP-S3: Switch engine helpers to thin facades

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helpers
- replace the real bodies of:
  - `_market_exit_snapshot(...)`
  - `_sector_exit_snapshot(...)`

Do not change:

- `_apply_system_exit_state(...)`
- `check_sell_signal_v2()`
- `_position_contract_snapshot(...)`
- `_market_top_snapshot(...)`
- `_market_drawdown_snapshot(...)`
- `detect_sector_cooldown(...)`

Completion check:

- the engine keeps the same helper names but no longer owns the real snapshot rule body inline

### SESP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_system_exit_snapshots.py`

Minimum owner cases:

- market snapshot confirms with trend weak plus breadth weak even when drawdown is not weak
- market snapshot keeps large drawdown as observation-only evidence
- market snapshot does not confirm on drawdown-only weakness
- market snapshot returns `None` when no evidence exists
- sector snapshot confirms only when both trend deterioration and follower weakness are present
- sector snapshot keeps cooldown plus leader rollover as observation-only evidence
- sector snapshot returns `None` when sector is blank
- sector snapshot returns `None` when cooldown info is missing

Keep and re-run:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

Completion check:

- the snapshot policy has direct focused coverage
- current sell-side consumer tests still pass unchanged

### SESP-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_system_exit_snapshots.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/system_exit_snapshots.py tests/unit/test_lowfreq_engine_v16_system_exit_snapshots.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### SESP-S6: Narrow commit

Before committing, stage only:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-snapshots-design.md`
- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-snapshots-plan.md`

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_snapshots.py`
- `tests/unit/test_lowfreq_engine_v16_system_exit_snapshots.py`

Must exclude:

- other sell-side helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into market/sector data acquisition

Guard:

- keep the owner limited to interpreting already-fetched inputs

Risk 2:

- drifting the current confirmation thresholds or `details` copy

Guard:

- preserve the current rule expressions and string templates exactly

Risk 3:

- changing the current return-null boundary

Guard:

- keep `None` tied only to complete absence of evidence

## 6. Success Criteria

This slice is complete when:

- market and sector exit snapshots have one shared owner
- the real snapshot rule body no longer lives inline in the engine
- upstream sourcing and downstream state mutation remain unchanged
- owner-focused snapshot tests pass
- current sell-side consumer regressions still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-system-exit-snapshots-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/system_exit_snapshots.py`
- `tests/unit/*`
- any other workspace changes
