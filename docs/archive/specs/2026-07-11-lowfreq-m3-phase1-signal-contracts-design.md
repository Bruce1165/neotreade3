# Lowfreq M3 Phase1 Signal Contracts Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `cross-sector wave policy` extraction.

This slice only freezes:

- the `M3 discovery -> tracking -> entry` phase1 contract semantics now still owned inline by:
  - [lowfreq_engine_v16_advanced.py:_candidate_tier_from_signal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L911-L915)
  - [lowfreq_engine_v16_advanced.py:_tracking_snapshot_from_signal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L969-L1003)
  - [lowfreq_engine_v16_advanced.py:_decorate_signal_with_phase1_contracts](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1005-L1079)

The goal is to:

- move the real phase1 signal-contract body into one shared owner
- keep `generate_buy_signals()` loop/orchestration stable
- preserve current `candidate_tier`, `tracking_*`, `candidate_contract`, `tracking_contract`, and `entry_contract` semantics exactly
- preserve current `wave1_tracking_only` soft-retain behavior exactly
- add direct owner-focused coverage for the phase1 signal-contract contract

This design is not:

- a rewrite of `generate_buy_signals()`
- a rewrite of `hold` / `exit` contract payload generation
- a rewrite of `LayerContract`
- a rewrite of tracking runtime event recording
- a rewrite of formal-front projection or payload finalize

Project-phase note:

- domain: `M3 phase1 signal contracts`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- the inline `candidate_tier` resolution currently in [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L911-L915)
- the inline tracking snapshot builder currently in [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L969-L1003)
- the inline phase1 decorator currently in [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1005-L1079)
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for the phase1 contract semantics
- focused regression for:
  - [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

Excluded:

- `generate_buy_signals()` loop/orchestration changes
- `LayerContract` relocation or renaming
- `hold_contract` / `exit_contract` generation
- `apps/api/main.py` consumer rewrites
- signal seed shaping
- signal dedup / signal payload / formal-front logic

## 3. Existing Context

Current repository evidence shows four important facts:

- phase1 contract decoration is still fully inline in the engine:
  - `candidate_tier` is derived from `soft_flags`
  - tracking snapshot is derived from `candidate_tier` / `entry_ready`
  - three layer contracts are assembled in one block
- the phase1 decorator also owns a specific `wave1 tracking-only` soft-retain rule:
  - soft flag: `wave1_tracking_only`
  - reason: `capture-first: 1浪仅保留 tracking，不进入正式建仓`
- this contract is already directly regression-tested through `M3 nucleus` behavior
- the generic `LayerContract` builder cannot be moved in the same slice because it is also used by `hold`, `exit`, and API-side closed-trade payload assembly

Repository evidence:

- [lowfreq_engine_v16_advanced.py:_decorate_signal_with_phase1_contracts](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1005-L1079)
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py#L92-L134)
- [lowfreq_engine_v16_advanced.py:_layer_contract_payload](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L855-L879)
- [apps/api/main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L18077-L18087)

The problem is not missing behavior definition. The problem is:

- `M3 phase1 signal contracts` still have no dedicated owner module
- the current body is semantically denser than the remaining `generate_buy_signals()` loop shell
- extracting loop shells first would be less meaningful than extracting the real M3 contract kernel
- `_layer_contract_payload()` has broader consumers, so this slice needs a tighter boundary than a generic contract-builder migration

## 4. Approach Options

### Option A: Extract a dedicated phase1 signal-contract owner and keep the generic builder injected (Recommended)

- add one small shared module under `neotrade3/decision_engine/`
- move `candidate_tier`, tracking snapshot, and phase1 decorator logic there
- keep `_layer_contract_payload()` in the engine and inject it into the new owner where needed

Pros:

- removes a real M3 semantic kernel from the engine
- preserves the current generic contract-builder surface for hold/exit/API consumers
- gives the phase1 semantics a direct owner and focused tests

Cons:

- the owner needs one injected builder dependency

### Option B: Move `LayerContract` builder and phase1 logic together

- move `_layer_contract_payload()` along with the phase1 helpers
- then rewire hold/exit/API consumers in the same slice

Pros:

- fewer remaining engine helpers after the slice

Cons:

- broadens scope into non-M3 consumers
- risks mixing `phase1 signal contracts` with generic hold/exit/API payload assembly

### Option C: Keep phase1 logic in the engine and add tests only

- preserve the inline methods
- add more focused tests without changing ownership

Pros:

- smallest code diff

Cons:

- leaves the real M3 contract kernel inline in the engine
- misses the current best owner boundary

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- resolving `candidate_tier` from signal state
- building the tracking snapshot from phase1 signal state
- applying the `wave1 tracking-only` soft-retain rule
- assembling `candidate_contract`, `tracking_contract`, and `entry_contract` into one decorated signal payload

These responsibilities should be treated as:

- `M3 phase1 signal contracts`

They should not be treated as:

- generic `LayerContract` infrastructure
- buy-loop orchestration
- tracking runtime event recording
- hold or exit lifecycle assembly

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/phase1_signal_contracts.py`

This module should own:

- `candidate_tier_from_signal(...)`
- `tracking_snapshot_from_signal(...)`
- `decorate_signal_with_phase1_contracts(...)`

Recommended signatures:

- `candidate_tier_from_signal(sig: dict[str, Any]) -> str`
- `tracking_snapshot_from_signal(sig: dict[str, Any], *, candidate_tier_resolver: Callable[[dict[str, Any]], str]) -> dict[str, Any]`
- `decorate_signal_with_phase1_contracts(sig: dict[str, Any], *, wave1_tracking_only_enabled: bool, wave1_value: str, layer_contract_builder: Callable[..., dict[str, Any]], candidate_tier_resolver: Callable[[dict[str, Any]], str], tracking_snapshot_builder: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]`

This module should:

- preserve current `soft_flags` normalization
- preserve current `reasons` normalization
- preserve current `wave1_tracking_only` append semantics exactly
- preserve current `tracking_state`, `tracking_days`, `tracking_transition_reason`, and `tracking_next_action` defaults exactly
- preserve current `entry_ready` semantics exactly

This module should not own:

- generic `LayerContract` construction logic beyond calling the injected builder
- `WavePhase` enum definition
- runtime event recording
- signal discovery loops

### 5.3 Engine Facade Boundary

The engine should continue to expose:

- `_candidate_tier_from_signal(...)`
- `_tracking_snapshot_from_signal(...)`
- `_decorate_signal_with_phase1_contracts(...)`

But those methods should become thin facades that delegate the real body to `phase1_signal_contracts.py`.

Why keep the facades:

- current tests already call these engine methods directly
- downstream engine methods still consume them
- this preserves the current private surface while still moving ownership out

### 5.4 Generic Builder Guardrail

`_layer_contract_payload()` must stay in `lowfreq_engine_v16_advanced.py` in this slice.

Reason:

- it is still used by:
  - hold-side contract assembly in the engine
  - exit-side contract assembly in the engine
  - API closed-trade payload assembly in [apps/api/main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L18077-L18087)

So this slice should only inject `_layer_contract_payload()` into the new phase1 owner rather than relocating it.

### 5.5 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- any non-empty `soft_flags` still force `candidate_tier == "soft_retained"`
- otherwise `candidate_tier == "execution_eligible"`
- `entry_ready` still defaults to `candidate_tier != "soft_retained"` when not explicitly provided
- `tracking_state` still defaults to:
  - `tracking_mature` when `entry_ready`
  - `tracking_observe` otherwise
- `tracking_transition_reason` still defaults to:
  - `candidate_meets_current_entry_contract` when `entry_ready`
  - `candidate_retained_for_tracking` otherwise
- `wave1 tracking-only` still appends:
  - soft flag `wave1_tracking_only`
  - reason `capture-first: 1浪仅保留 tracking，不进入正式建仓`
- `candidate_contract.source_layer` stays `discovery`
- `tracking_contract.source_layer` stays `tracking`
- `entry_contract.source_layer` stays `entry`

No copy changes and no tier-semantic changes are included in this slice.

### 5.6 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_phase1_signal_contracts.py`

This carrier should directly exercise the shared owner and cover at least:

- `candidate_tier_from_signal(...)` returns `soft_retained` when `soft_flags` are present
- `tracking_snapshot_from_signal(...)` emits the current mature defaults for `entry_ready=True`
- `tracking_snapshot_from_signal(...)` emits the current observe defaults for `soft_retained`
- `decorate_signal_with_phase1_contracts(...)` appends the `wave1_tracking_only` soft-retain semantics exactly once
- `decorate_signal_with_phase1_contracts(...)` preserves the three layer-contract `source_layer` values

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
- [test_lowfreq_engine_v16_tracking_runtime.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_tracking_runtime.py)

## 6. Risks and Guardrails

Main risk:

- drifting the public M3 signal semantics while extracting the owner

Guardrails:

- move only the phase1 semantic kernel, not the generic builder
- preserve the current engine facade methods
- preserve the current `wave1 tracking-only` copy exactly
- keep this slice limited to `candidate_tier`, tracking snapshot, and phase1 decorator semantics

Secondary risk:

- over-broadening into tracking runtime recording because `_tracking_snapshot_from_signal(...)` is consumed there too

Guardrails:

- keep runtime event recording code unchanged
- only switch it to the delegated engine facade if needed

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/decision_engine/phase1_signal_contracts.py`
2. move `candidate_tier`, tracking snapshot, and phase1 decorator logic there
3. keep `_layer_contract_payload()` in the engine and inject it into the new owner
4. turn the three engine methods into thin facades
5. add owner-focused tests
6. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- `M3 phase1 signal contracts` have one shared owner
- the real body no longer lives inline in the engine
- `_layer_contract_payload()` remains stable for hold/exit/API consumers
- the current `candidate_tier`, `tracking_*`, and `wave1 tracking-only` semantics stay unchanged
- owner-focused tests pass
- current M3 nucleus and tracking consumers still pass
