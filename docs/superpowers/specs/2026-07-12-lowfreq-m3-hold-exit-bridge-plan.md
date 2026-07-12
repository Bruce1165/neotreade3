Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow `M3 hold/exit formal bridge -> M4` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M3 Hold/Exit Formal Bridge Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m3-hold-exit-bridge-design.md`

## 1. Goal

This plan covers only the first six-layer back-half acceleration slice after the closure audit.

This slice only handles:

- formal `M3` hold and exit contract objects
- one canonical bridge from `position_snapshot` to stable `m3_context`
- the first minimal `M4` consumption of that bridge for:
  - `trace_bundle.m3_context`
  - `hold_quality_risk_summary`

The goal is to:

- stop `M3` from ending at `identify / tracking / entry`
- reuse the already-ownerized `position_contract_snapshot(...)` semantics instead of rebuilding sell logic
- let `M4` consume a stable hold/exit bridge without widening into full hold/exit gap taxonomy

This slice does not:

- rewrite sell logic, trend-exhaustion logic, or thesis-invalidation logic
- rewrite `build_position_contract_snapshot(...)`
- add `DecisionLifecycleLog`
- add new `M4` gap groups
- touch `M5` governance or `M6` delivery code

## 2. Starting Point

Current repository evidence shows:

- `neotrade3/decision_engine/contracts.py` only defines:
  - `IdentifyState`
  - `TrackingState`
  - `EntryState`
- `neotrade3/decision_engine/position_contract_snapshot.py` already owns the hold/exit runtime contract surface
- `neotrade3/benchmark/assembler.py` forwards `m3_context` unchanged
- `neotrade3/benchmark/assembler.py` still hard-codes:
  - `hold_quality_risk_summary={"status": "not_in_scope"}`

So the correct narrow move is:

- formalize the existing snapshot semantics
- bridge them into `m3_context`
- let `M4` read only the minimal bridge interpretation

## 3. Implementation Strategy

Production boundary:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/hold_exit_bridge.py`
- `neotrade3/decision_engine/__init__.py`
- `neotrade3/benchmark/assembler.py`

Test boundary:

- `tests/unit/test_m2_m3_contract_skeleton.py`
- `tests/unit/test_m3_hold_exit_bridge.py`
- `tests/unit/test_m4_benchmark_seed.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-m3-hold-exit-bridge-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m3-hold-exit-bridge-plan.md`

## 4. Execution Steps

### HEB-S1: Extend formal M3 contracts

In `neotrade3/decision_engine/contracts.py`:

- add `HOLD_STATE_OBJECT_TYPE`
- add `EXIT_STATE_OBJECT_TYPE`
- add `HoldState`
- add `ExitState`

Freeze minimum field sets:

- `HoldState`
  - `stock_code`
  - `trade_date`
  - `status`
  - `hold_state`
  - `warning_flags`
  - `not_exit_reasons`
  - `evidence_ref`
  - `m2_cycle_ref`
  - `m1_constraints_ref`
- `ExitState`
  - `stock_code`
  - `trade_date`
  - `status`
  - `exit_ready`
  - `exit_scope`
  - `exit_reason_type`
  - `exit_attribution_bucket`
  - `evidence_ref`
  - `m2_cycle_ref`
  - `m1_constraints_ref`

Completion check:

- both new objects support `to_payload()`
- field copying behavior matches existing `IdentifyState / TrackingState / EntryState` patterns

### HEB-S2: Add M3 builders and exports

In `neotrade3/decision_engine/assembler.py`:

- add `build_hold_state(...)`
- add `build_exit_state(...)`

Requirements:

- follow existing `_require_text`, `_copy_mapping`, `_copy_text_list` conventions
- avoid adding runtime dependencies
- accept optional `m2_cycle_ref` and `m1_constraints_ref`

In `neotrade3/decision_engine/__init__.py`:

- export the new constants, dataclasses, and builder functions

Completion check:

- downstream tests can import the new public symbols from `neotrade3.decision_engine`

### HEB-S3: Add the bridge owner

Create:

- `neotrade3/decision_engine/hold_exit_bridge.py`

Public function:

- `build_m3_hold_exit_bridge(...) -> dict[str, Any]`

Implementation rules:

- consume only the already-shaped `position_snapshot`
- when `exit_ready` is false:
  - build `HoldState`
  - leave `exit_state` empty
- when `exit_ready` is true:
  - build `ExitState`
  - leave `hold_state` empty
- include:
  - `bridge_version`
  - `source_contract`
  - `position_status`
  - `hold_quality_signal`
- do not mutate current snapshot semantics

Completion check:

- one canonical bridge exists from snapshot payload to `m3_context`

### HEB-S4: Add minimal M4 consumption

In `neotrade3/benchmark/assembler.py`:

- add a small internal helper for hold-quality summary projection from `m3_context`
- replace `{"status": "not_in_scope"}` with the new helper result
- keep `trace_bundle.m3_context` as the forwarded bridge payload

Summary rules:

- no `m3_context`:
  - `status = "missing_m3_hold_exit_bridge"`
- `exit_state` present:
  - `status = "exit_ready"`
  - `risk_level = "high"`
- watch-like hold states:
  - `status = "watch"`
  - `risk_level = "watch"`
- `holding`:
  - `status = "holding"`
  - `risk_level = "low"`

Do not add:

- new gap records
- new gap groups
- new interaction breaches

Completion check:

- `M4` gains minimal hold-quality visibility without changing its main gap framework

### HEB-S5: Add focused tests

Update or add:

- `tests/unit/test_m2_m3_contract_skeleton.py`
  - lock `HoldState` and `ExitState` payloads
- `tests/unit/test_m3_hold_exit_bridge.py`
  - lock hold-branch bridge payload
  - lock exit-branch bridge payload
- `tests/unit/test_m4_benchmark_seed.py`
  - assert `hold_quality_risk_summary` reflects:
    - missing bridge
    - watch-style hold
    - exit-ready bridge

Test style:

- use direct owner calls
- reuse current small reference fixtures and snapshot payloads
- keep scope on contract and bridge meaning, not engine integration

Completion check:

- bridge behavior is locked independently from the engine runtime path

### HEB-S6: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/decision_engine/contracts.py neotrade3/decision_engine/assembler.py neotrade3/decision_engine/hold_exit_bridge.py neotrade3/decision_engine/__init__.py neotrade3/benchmark/assembler.py tests/unit/test_m2_m3_contract_skeleton.py tests/unit/test_m3_hold_exit_bridge.py tests/unit/test_m4_benchmark_seed.py`
- `.venv/bin/python -m pytest tests/unit/test_m2_m3_contract_skeleton.py tests/unit/test_m3_hold_exit_bridge.py tests/unit/test_m4_benchmark_seed.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - `build_hold_state(...)`
  - `build_exit_state(...)`
  - `build_m3_hold_exit_bridge(...)`
  - `build_benchmark_assessment_from_m2_shadow(...)`

Completion check:

- syntax validation passes
- focused verification passes with the best available runner in the environment

### HEB-S7: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m3-hold-exit-bridge-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m3-hold-exit-bridge-plan.md`
- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/hold_exit_bridge.py`
- `neotrade3/decision_engine/__init__.py`
- `neotrade3/benchmark/assembler.py`
- `tests/unit/test_m2_m3_contract_skeleton.py`
- `tests/unit/test_m3_hold_exit_bridge.py`
- `tests/unit/test_m4_benchmark_seed.py`

Must exclude:

- changes to `position_contract_snapshot.py`
- changes to lowfreq engine runtime orchestration
- changes to fixture catalog, sample registry, manifest, batch runner
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally rebuilding hold/exit semantics instead of translating the existing snapshot owner

Guard:

- use `position_snapshot` as the bridge source of truth
- keep sell-flow logic out of the bridge module

Risk 2:

- widening `M4` into a premature hold/exit gap framework

Guard:

- restrict `M4` changes to summary projection only
- do not create new gap labels or groups in this slice

Risk 3:

- introducing import drift by extending `decision_engine` exports

Guard:

- update focused skeleton tests to import through public package exports

## 6. Success Criteria

This slice is complete when:

- `M3` has formal `HoldState` and `ExitState`
- the repository has one bridge helper from `position_snapshot` to `m3_context`
- `M4 trace_bundle.m3_context` can carry the bridge payload
- `M4 hold_quality_risk_summary` is no longer a placeholder
- focused verification passes
- syntax verification passes
