Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow M3 position contract snapshot extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Position Contract Snapshot Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-position-contract-snapshot-design.md`

## 1. Goal

This plan covers only the next narrow `position contract snapshot` slice after the `rotation candidate` owner extraction.

This slice only handles:

- hold/exit position contract shaping
- hold-state and attribution bucket assignment
- owner-focused coverage for the position contract contract

The goal is to:

- move the dense position contract kernel into one shared owner
- keep runtime snapshot lookup unchanged in the engine
- preserve current API/workbench observable fields exactly

This slice does not:

- rewrite `check_sell_signal_v2(...)`
- rewrite `_market_exit_snapshot(...)`
- rewrite `_sector_exit_snapshot(...)`
- rewrite `_trend_exhaustion_snapshot(...)`
- rewrite API portfolio assembly

## 2. Starting Point

Current repository evidence shows:

- `_position_contract_snapshot(...)` still owns a dense inline contract-shaping kernel in:
  - `lowfreq_engine_v16_advanced.py`
- runtime collaborators are already separate from the final payload shaping:
  - `_get_price(...)`
  - `_market_exit_snapshot(...)`
  - `_sector_exit_snapshot(...)`
  - `_trend_exhaustion_snapshot(...)`
- API portfolio construction directly consumes the returned fields
- nearby sell logic tests already anchor observable behavior

So the correct next slice is:

- extract only the final contract-shaping kernel
- keep runtime collaborator calls in the engine facade

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/position_contract_snapshot.py`

Move the pure contract-shaping rule there:

- `build_position_contract_snapshot(...)`

Keep the engine method as a thin facade:

- `_position_contract_snapshot(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py`

## 4. Execution Steps

### PCS-S1: Freeze file boundary and observable contract

Freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/position_contract_snapshot.py`
- `tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py`

Freeze the observable contract:

- evidence list behavior remains unchanged
- warning flag behavior remains unchanged
- latest transition date selection remains unchanged
- hold-state ladder remains unchanged
- hold attribution bucket values remain unchanged
- exit attribution bucket values remain unchanged
- `not_exit_reasons` copy remains unchanged
- API field names remain unchanged

Completion check:

- no runtime snapshot or API orchestration changes are part of this slice

### PCS-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/position_contract_snapshot.py`

Move the final contract-shaping logic into:

- `build_position_contract_snapshot(...)`

Implementation rules:

- accept normalized scalar values, snapshot dicts, and a plain sell payload
- do not read config directly inside the owner
- do not fetch price or runtime snapshots inside the owner
- do not mutate `trade`
- do not emit events

Completion check:

- the hold/exit position contract can be understood independently from engine runtime collaborators

### PCS-S3: Switch engine helper to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helper
- keep current price lookup in the engine
- keep market/sector/trend snapshot lookup in the engine
- normalize `SellSignal` into a plain dict in the engine
- replace the dense inline contract shaping with owner delegation

Do not change:

- `check_sell_signal_v2(...)`
- `_market_exit_snapshot(...)`
- `_sector_exit_snapshot(...)`
- `_trend_exhaustion_snapshot(...)`

Completion check:

- the engine keeps `_position_contract_snapshot(...)` but no longer owns the dense contract body inline

### PCS-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py`

Minimum owner cases:

- partial weakness stays in hold-side `noise_watch`
- grace hold maps to `hold_grace`
- trend exhausted exit maps to `trend_exhaustion_exit`
- unknown exit reason falls back to `exit_other`
- latest transition picks the latest non-empty date

Completion check:

- the position contract kernel has direct focused coverage

### PCS-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/position_contract_snapshot.py tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py`

Completion check:

- owner tests pass
- nearby sell logic guard passes
- syntax validation passes

### PCS-S6: Narrow commit

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/position_contract_snapshot.py`
- `tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py`

Must exclude:

- API files
- runtime snapshot helpers
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into API or runtime snapshot ownership

Guard:

- keep price and snapshot collection in the engine facade

Risk 2:

- silently drifting bucket labels or field names used by workbench

Guard:

- preserve field names and bucket strings exactly
- verify direct owner contract plus nearby consumer tests

## 6. Success Criteria

This slice is complete when:

- the position contract kernel has one shared owner
- the dense inline contract shaping no longer lives in the engine
- API-observed field names and values remain unchanged
- owner-focused tests pass
- nearby sell logic tests pass
- syntax verification passes
