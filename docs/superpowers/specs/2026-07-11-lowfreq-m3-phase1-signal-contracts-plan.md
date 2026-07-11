# Lowfreq M3 Phase1 Signal Contracts Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-phase1-signal-contracts-design.md`

## 1. Goal

This plan covers only the next narrow `M3 phase1 signal contracts` slice after the `cross-sector wave policy` extraction.

This slice only handles:

- the inline `candidate_tier` resolution in `lowfreq_engine_v16_advanced.py`
- the inline tracking snapshot builder in `lowfreq_engine_v16_advanced.py`
- the inline phase1 signal decorator in `lowfreq_engine_v16_advanced.py`

The goal is to:

- move the real `M3 discovery -> tracking -> entry` phase1 contract body into one shared owner module
- keep the engine methods as thin facades
- preserve the current `candidate_tier`, `tracking_*`, `candidate_contract`, `tracking_contract`, and `entry_contract` semantics exactly
- preserve the current `wave1_tracking_only` soft-retain rule exactly
- add owner-focused coverage for the phase1 contract semantics

This slice does not:

- rewrite `generate_buy_signals()`
- move `_layer_contract_payload()`
- rewrite hold / exit contract assembly
- rewrite `apps/api/main.py`
- rewrite tracking runtime event recording

## 2. Starting Point

Current repository evidence shows:

- `_candidate_tier_from_signal(...)`, `_tracking_snapshot_from_signal(...)`, and `_decorate_signal_with_phase1_contracts(...)` still own the real M3 phase1 semantic body inside the engine
- `_layer_contract_payload()` is broader than this slice and is still used by hold/exit/API consumers
- direct regression anchors already exist in:
  - `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
  - `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
  - `tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`

So the correct next slice is:

- extract only the phase1 semantic kernel
- keep the generic builder and broader consumers unchanged

## 3. Implementation Strategy

Use one dedicated shared owner under `decision_engine`:

- add a new owner module:
  - `neotrade3/decision_engine/phase1_signal_contracts.py`
- move the real phase1 semantic logic into:
  - `candidate_tier_from_signal(...)`
  - `tracking_snapshot_from_signal(...)`
  - `decorate_signal_with_phase1_contracts(...)`
- keep `_layer_contract_payload()` in `lowfreq_engine_v16_advanced.py`
- inject the engine builder into the shared owner where needed
- keep these engine methods as thin facades:
  - `_candidate_tier_from_signal(...)`
  - `_tracking_snapshot_from_signal(...)`
  - `_decorate_signal_with_phase1_contracts(...)`
- add one new owner-focused carrier:
  - `tests/unit/test_lowfreq_engine_v16_phase1_signal_contracts.py`

Keep the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`

## 4. Execution Steps

### M3-P1C-S1: Freeze file boundary and semantic contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/phase1_signal_contracts.py`
- `tests/unit/test_lowfreq_engine_v16_phase1_signal_contracts.py`

Keep these consumer guards:

- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`

Freeze the observable contract:

- any non-empty `soft_flags` still produce `candidate_tier == "soft_retained"`
- otherwise `candidate_tier == "execution_eligible"`
- `entry_ready` still defaults to `candidate_tier != "soft_retained"` when not explicitly provided
- `tracking_state` still defaults to `tracking_mature` for ready candidates and `tracking_observe` otherwise
- `tracking_transition_reason` still defaults to:
  - `candidate_meets_current_entry_contract`
  - `candidate_retained_for_tracking`
- `wave1 tracking-only` still appends:
  - soft flag `wave1_tracking_only`
  - reason `capture-first: 1浪仅保留 tracking，不进入正式建仓`
- `candidate_contract.source_layer` stays `discovery`
- `tracking_contract.source_layer` stays `tracking`
- `entry_contract.source_layer` stays `entry`

Completion check:

- no current consumer needs to change its externally visible contract

### M3-P1C-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/phase1_signal_contracts.py`

Move the real phase1 semantic body into that module:

- `candidate_tier_from_signal(...)`
- `tracking_snapshot_from_signal(...)`
- `decorate_signal_with_phase1_contracts(...)`

Implementation rules:

- the owner must not know about hold / exit / API consumers
- the owner must not move or redefine `_layer_contract_payload()`
- the owner may accept injected callbacks where the generic builder is required
- the owner must preserve current `wave1 tracking-only` copy exactly

Completion check:

- the phase1 semantic contract can be understood independently from the engine loop shell

### M3-P1C-S3: Switch engine methods to thin facades

In `lowfreq_engine_v16_advanced.py`:

- import the shared owner helpers
- replace the real bodies of:
  - `_candidate_tier_from_signal(...)`
  - `_tracking_snapshot_from_signal(...)`
  - `_decorate_signal_with_phase1_contracts(...)`
- keep `_layer_contract_payload()` untouched

Do not change:

- `generate_buy_signals()` loop structure
- hold / exit contract generation
- API closed-trade payload assembly
- tracking runtime event recording flow

Completion check:

- the engine keeps the same helper names but no longer owns the real phase1 body inline

### M3-P1C-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_phase1_signal_contracts.py`

Minimum owner cases:

- `candidate_tier_from_signal(...)` returns `soft_retained` when `soft_flags` are present
- `candidate_tier_from_signal(...)` returns `execution_eligible` when `soft_flags` are empty
- `tracking_snapshot_from_signal(...)` emits the current mature defaults for ready candidates
- `tracking_snapshot_from_signal(...)` emits the current observe defaults for soft-retained candidates
- `decorate_signal_with_phase1_contracts(...)` appends the `wave1_tracking_only` soft flag and reason exactly once
- `decorate_signal_with_phase1_contracts(...)` preserves the three layer-contract `source_layer` values

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`

Completion check:

- the shared phase1 contract semantics have a direct focused carrier
- current consumer tests still pass unchanged

### M3-P1C-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_phase1_signal_contracts.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/phase1_signal_contracts.py tests/unit/test_lowfreq_engine_v16_phase1_signal_contracts.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### M3-P1C-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/phase1_signal_contracts.py`
- `tests/unit/test_lowfreq_engine_v16_phase1_signal_contracts.py`

Must exclude:

- `apps/api/main.py`
- `neotrade3/decision_engine/contracts.py`
- hold / exit logic files
- signal seed / signal payload / formal-front files
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- drifting current M3 signal semantics while extracting the owner

Guard:

- keep the current engine helper names and preserve existing consumer tests

Risk 2:

- accidentally broadening into generic contract-builder migration

Guard:

- keep `_layer_contract_payload()` in place and inject it into the owner as needed

Risk 3:

- accidentally broadening into `generate_buy_signals()` orchestration refactor

Guard:

- limit engine changes to the three helper facades only

Risk 4:

- breaking tracking runtime because it still consumes `_tracking_snapshot_from_signal(...)`

Guard:

- keep runtime flow unchanged and re-run `test_lowfreq_engine_v16_tracking_runtime.py`

## 6. Success Criteria

This slice is complete when:

- `M3 phase1 signal contracts` have one shared owner
- the real body no longer lives inline in the engine
- `_layer_contract_payload()` remains stable for hold/exit/API consumers
- the current `candidate_tier`, `tracking_*`, and `wave1 tracking-only` semantics stay unchanged
- owner-focused tests pass
- current M3 nucleus and tracking consumers still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-phase1-signal-contracts-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/*`
- `tests/unit/*`
- any other workspace changes
