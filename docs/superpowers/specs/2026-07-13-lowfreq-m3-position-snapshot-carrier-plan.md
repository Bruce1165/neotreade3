Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow `M3 position snapshot production carrier` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Position Snapshot Production Carrier Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m3-position-snapshot-carrier-design.md`

## 1. Goal

This plan implements the next truthful `M3 backhalf` slice after the persisted `M5` truth switch.

Repository evidence collected during plan preparation shows:

- `HoldState` / `ExitState` and `build_m3_hold_exit_bridge(...)` already exist
- but `build_lowfreq_formal_front_payload(...)` cannot rebuild `position_contract_snapshot(...)`
  - because it only receives buy-side candidate inputs plus formal `M1/M2/M3 front-half` data
- `position_contract_snapshot(...)` is currently produced only inside `lowfreq_engine_v16_advanced.py`
- that snapshot is not yet carried into a stable production output surface

So this slice does **not** pretend to wire backhalf into buy-side `formal_front`.

This slice only does one truthful move:

- carry the already-ownerized `position_contract_snapshot` into the lowfreq production result tree
- make that carrier stable enough for later:
  - `M3` formal bridge mainline wiring
  - `M4` richer hold/exit evaluation
  - semantic audit of hold/exit runtime truth

This slice does not include:

- `decision_lifecycle_log`
- `local_exit_semantics` / `global_thesis_end_semantics`
- `formal_front` backhalf generation
- API/workbench rendering changes
- `M4/M5/M6` changes

## 2. Starting Point

Current repository evidence:

- `lowfreq_engine_v16_advanced.py::_position_contract_snapshot(...)` builds the canonical runtime snapshot
- the snapshot already contains:
  - `hold_state`
  - `not_exit_reasons`
  - `warning_flags`
  - `exit_ready`
  - `exit_scope`
  - `exit_reason_type`
  - `exit_evidence_bundle`
  - layer-contract fields such as `current_stage / decision / next_action / last_transition`
- the snapshot is currently used internally, but a code search shows no stable production result carrier for it

Therefore the correct narrow move is:

- expose `position_contract_snapshot` through a production result carrier that already belongs to the lowfreq engine output
- avoid recomputing or translating semantics anywhere else in this slice

## 3. File Boundary

Production files:

- `lowfreq_engine_v16_advanced.py`

Focused test files:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- one additional focused carrier test only if the existing sell-logic test file becomes too noisy

Documentation files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m3-production-hold-exit-wiring-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m3-position-snapshot-carrier-plan.md`

Files intentionally not modified:

- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/decision_engine/projections.py`
- `neotrade3/decision_engine/hold_exit_bridge.py`
- `neotrade3/benchmark/*`
- `neotrade3/governance/*`

## 4. Execution Steps

### M3SNAP-S1: Find the stable production result carrier

In `lowfreq_engine_v16_advanced.py`:

- identify the narrowest existing result surface that already carries trade-level or daily execution truth
- choose one place where `position_contract_snapshot` can be attached without changing sell decisions

Implementation rule:

- do not invent a new top-level report subsystem in this slice
- reuse an existing engine result payload or audit/event carrier

Completion check:

- the chosen carrier is already part of the engine output path, not a debug-only local variable

### M3SNAP-S2: Attach `position_contract_snapshot` without rewriting semantics

In `lowfreq_engine_v16_advanced.py`:

- write the output of `_position_contract_snapshot(...)` into the selected production carrier

Implementation rules:

- call the existing `_position_contract_snapshot(...)` exactly once per needed runtime path
- carry the snapshot as-is or with only shallow copying for safety
- do not rename or reinterpret existing snapshot fields
- do not rebuild any hold/exit logic outside the existing owner

Completion check:

- engine output now includes one stable `position_contract_snapshot` carrier with the canonical runtime shape

### M3SNAP-S3: Lock the carrier contract with focused tests

Preferred test carrier:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Required assertions:

1. the production carrier includes `position_contract_snapshot`
2. the carried snapshot preserves:
   - `hold_state`
   - `exit_ready`
   - `exit_scope`
   - `exit_reason_type`
   - `current_stage`
   - `decision`
   - `next_action`
   - `last_transition`
3. the snapshot carrier matches the output of the canonical owner
4. existing sell-side behavior remains unchanged

Testing rule:

- do not widen into `build_m3_hold_exit_bridge(...)` tests here
- do not widen into `formal_front` tests in this slice

Completion check:

- production carrier semantics are locked independently from future bridge/mainline wiring

### M3SNAP-S4: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile lowfreq_engine_v16_advanced.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run inline assertions that:
  - construct the relevant engine test case
  - confirm the production output now carries `position_contract_snapshot`
  - confirm key fields match the canonical owner output

Additional boundary check:

- `git diff --check`

## 5. Risks And Guardrails

- **Risk: fake backhalf mainline**
  - Guardrail: this slice only exposes the canonical snapshot carrier; it does not claim formal-front backhalf completion
- **Risk: semantic duplication**
  - Guardrail: reuse `_position_contract_snapshot(...)` only; do not re-derive fields
- **Risk: widening into API/report**
  - Guardrail: limit the change to one existing engine production carrier

## 6. Done Criteria

This slice is done only when all of the following are true:

- one stable production result carrier now includes `position_contract_snapshot`
- the carried snapshot matches canonical owner semantics
- sell-side behavior is unchanged
- focused tests and minimum verification pass

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M3`, making existing backhalf runtime truth externally carriable
- `G1-G6` target mapping:
  - this is a `G4` truth-exposure step before later `M3 -> M4/M5` typed wiring
- new contract introduced:
  - engine production output carries `position_contract_snapshot`
- boundaries not touched:
  - no `decision_lifecycle_log`
  - no exit semantic expansion
  - no `formal_front` backhalf generation
  - no `M4/M5/M6`
