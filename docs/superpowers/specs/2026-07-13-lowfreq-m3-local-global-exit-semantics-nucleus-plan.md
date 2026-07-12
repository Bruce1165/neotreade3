Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow `M3 local/global exit semantics nucleus` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Local/Global Exit Semantics Nucleus Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m3-local-global-exit-semantics-nucleus-design.md`

## 1. Goal

This plan implements the next truthful `M3 backhalf` slice after the already-landed:

- `M3 hold/exit formal bridge`
- `M3 position snapshot production carrier`

This slice must:

- add explicit `local_exit_semantics` and `global_thesis_end_semantics` to the canonical `position_contract_snapshot` exit path
- extend formal `ExitState` so those semantics become first-class payload fields
- extend the existing `build_m3_hold_exit_bridge(...)` path so the new semantics survive formal translation
- lock the new owner and bridge contract with focused tests

This slice explicitly does not include:

- `decision_lifecycle_log`
- hold-side local/global taxonomy
- `formal_front` rewiring
- `M4` benchmark consumer changes
- `M5` governance consumer changes
- `M6`

## 2. Starting Point

Repository evidence before implementation:

- `neotrade3/decision_engine/position_contract_snapshot.py` already emits the canonical exit-ready shape:
  - `exit_ready`
  - `exit_scope`
  - `exit_reason_type`
  - `exit_attribution_bucket`
- the same owner currently emits no explicit local/global semantic fields
- `neotrade3/decision_engine/contracts.py::ExitState` already formalizes exit payloads, but only with:
  - `exit_ready`
  - `exit_scope`
  - `exit_reason_type`
  - `exit_attribution_bucket`
- `neotrade3/decision_engine/assembler.py::build_exit_state(...)` mirrors that same incomplete formal shape
- `neotrade3/decision_engine/hold_exit_bridge.py` already maps exit-ready snapshots into `ExitState`, but does not pass local/global semantics through
- existing focused tests already anchor:
  - bridge translation in `tests/unit/test_m3_hold_exit_bridge.py`
  - runtime owner output in `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

So the implementation strategy is:

- change the canonical exit snapshot owner first
- then align the formal `ExitState` contract and builder with the new owner fields
- then update the bridge to remain a thin pass-through
- then lock the new contract in the two existing focused test carriers

## 3. File Boundary

Production files:

- `neotrade3/decision_engine/position_contract_snapshot.py`
- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/hold_exit_bridge.py`

Focused test files:

- `tests/unit/test_m3_hold_exit_bridge.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Files intentionally not modified:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/benchmark/*`
- `neotrade3/governance/*`
- `PROJECT_STATUS.md`

## 4. Execution Steps

### M3SEM-S1: Extend the canonical snapshot owner

Modify:

- `neotrade3/decision_engine/position_contract_snapshot.py`

Implementation:

1. extend the exit-ready payload to include:
   - `local_exit_semantics`
   - `global_thesis_end_semantics`
2. for any `sell_payload`-driven exit, set:
   - `local_exit_semantics = "local_end_only"`
   - `global_thesis_end_semantics = "needs_global_confirmation"`
3. for non-exit snapshots, keep both fields as empty strings to match the current exit-only-field style

Implementation rule:

- do not emit `possible_global_end`
- do not emit `global_end_only`
- do not invent any hold-side semantics in this slice

Completion check:

- every exit-ready snapshot now contains explicit local/global semantics
- no stronger global-thesis claim appears without new upstream proof

### M3SEM-S2: Extend formal `ExitState` and its builder

Modify:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`

Implementation:

1. add `local_exit_semantics` and `global_thesis_end_semantics` to `ExitState`
2. include the two fields in `ExitState.to_payload()`
3. extend `build_exit_state(...)` so callers must pass both values explicitly
4. keep `HoldState` unchanged

Implementation rule:

- the two fields must be first-class formal payload members
- do not hide them inside `evidence_ref`

Completion check:

- the formal `ExitState` contract fully mirrors the new owner shape for local/global exit semantics

### M3SEM-S3: Extend the bridge as a thin pass-through

Modify:

- `neotrade3/decision_engine/hold_exit_bridge.py`

Implementation:

1. read the new semantic fields from the exit-ready snapshot
2. pass them directly into `build_exit_state(...)`
3. keep hold-side bridge behavior unchanged
4. keep `position_status` and `hold_quality_signal` logic unchanged

Implementation rule:

- bridge must not infer stronger semantics
- bridge must not reinterpret `m2_cycle_ref`
- bridge remains a translator, not a semantic owner

Completion check:

- exit-ready bridge payload preserves the two new fields verbatim from the snapshot owner

### M3SEM-S4: Lock the contract with focused tests

Modify:

- `tests/unit/test_m3_hold_exit_bridge.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Required assertions:

1. `build_m3_hold_exit_bridge(...)` includes:
   - `local_exit_semantics`
   - `global_thesis_end_semantics`
2. `trend_exhausted` runtime snapshots emit:
   - `local_end_only`
   - `needs_global_confirmation`
3. `market_top_confirmed` runtime snapshots also emit:
   - `local_end_only`
   - `needs_global_confirmation`
4. hold-side bridge behavior remains unchanged
5. no test asserts richer values such as:
   - `possible_global_end`
   - `global_end_only`

Testing rule:

- do not widen into lifecycle logging
- do not widen into `formal_front`
- do not widen into `M4/M5/M6`

Completion check:

- the new semantics are locked independently in both owner-facing and bridge-facing carriers

### M3SEM-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/decision_engine/position_contract_snapshot.py neotrade3/decision_engine/contracts.py neotrade3/decision_engine/assembler.py neotrade3/decision_engine/hold_exit_bridge.py tests/unit/test_m3_hold_exit_bridge.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `.venv/bin/python -m pytest tests/unit/test_m3_hold_exit_bridge.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run one inline assertion script that:
  - builds one exit-ready bridge payload
  - confirms the two new fields survive `ExitState.to_payload()`
  - confirms `trend_exhausted` emits the conservative pair
  - confirms `market_top_confirmed` emits the same conservative pair

Additional boundary check:

- `git diff --check`

## 5. Risks And Guardrails

- **Risk: false global-thesis claim**
  - Guardrail: emit only `needs_global_confirmation` in this slice
- **Risk: semantic duplication**
  - Guardrail: owner decides the values, bridge only passes them through
- **Risk: hidden contract**
  - Guardrail: add the fields to formal `ExitState`, not only `evidence_ref`
- **Risk: scope expansion**
  - Guardrail: leave `HoldState`, lifecycle, benchmark, governance, and delivery untouched

## 6. Done Criteria

This slice is done only when all of the following are true:

- exit-ready `position_contract_snapshot` payloads contain explicit local/global semantic fields
- the emitted values stay inside the conservative repository-supported pair
- `ExitState` carries the same two fields as first-class payload members
- `build_m3_hold_exit_bridge(...)` preserves the fields without reinterpretation
- focused tests and minimum verification pass

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - implementation belongs to `M3`, completing the backhalf exit semantic owner and formal bridge surface
- `G1-G6` target mapping:
  - this is a `G4` semantic truth-completion step that reduces later `M4/M5` local/global misread risk
- new contract introduced:
  - `position_contract_snapshot.local_exit_semantics`
  - `position_contract_snapshot.global_thesis_end_semantics`
  - `ExitState.local_exit_semantics`
  - `ExitState.global_thesis_end_semantics`
- boundaries not touched:
  - no `decision_lifecycle_log`
  - no hold-side taxonomy
  - no `formal_front`
  - no `M4/M5/M6`
