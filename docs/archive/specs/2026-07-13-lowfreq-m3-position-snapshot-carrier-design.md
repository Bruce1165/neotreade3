Status: active
Owner: lowfreq / decision_engine
Scope: Narrow `M3 position snapshot production carrier` slice after the persisted M5 truth switch
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Position Snapshot Production Carrier Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful `M3 backhalf` step after:

- the already-landed `M3 hold/exit formal bridge`
- the already-landed `M5` persisted `M4` truth switch

Current repository evidence shows:

- `HoldState`, `ExitState`, and `build_m3_hold_exit_bridge(...)` already exist
- but `build_lowfreq_formal_front_payload(...)` cannot rebuild `position_contract_snapshot(...)`
  - it only consumes buy-side candidate inputs plus formal `M1/M2/M3 front-half` data
- the canonical hold/exit runtime truth still lives only inside:
  - `lowfreq_engine_v16_advanced.py::_position_contract_snapshot(...)`
- and that snapshot is not yet carried into a stable production output surface

So the real problem is not:

- how to redesign backhalf semantics
- how to generate backhalf objects from the buy-side formal-front builder

It is:

- how to expose the already-ownerized `position_contract_snapshot` through one stable production carrier
- how to do that without pretending the entire `M3 backhalf` is complete

Project-phase note:

- domain: `M3 backhalf runtime truth exposure`
- change type: `internal owner -> production carrier`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G4`

## 2. Scope

Included:

- attach the output of `_position_contract_snapshot(...)` to one stable lowfreq production result carrier
- preserve canonical snapshot semantics unchanged
- add focused tests that lock the new production carrier contract

Excluded:

- no `decision_lifecycle_log`
- no `local_exit_semantics` / `global_thesis_end_semantics`
- no `formal_front` backhalf generation
- no API/workbench rendering changes
- no `M4` richer hold/exit taxonomy
- no `M5/M6`

## 3. Existing Evidence

### 3.1 Canonical Snapshot Owner Already Exists

Current repository evidence in `lowfreq_engine_v16_advanced.py` shows:

- `_position_contract_snapshot(...)` is the canonical owner for backhalf runtime truth
- it already delegates the semantic shaping to `build_position_contract_snapshot(...)`

The snapshot already contains:

- `hold_state`
- `noise_evidence`
- `not_exit_reasons`
- `warning_flags`
- `hold_attribution_bucket`
- `exit_attribution_bucket`
- `exit_ready`
- `exit_scope`
- `exit_reason_type`
- `exit_evidence_bundle`
- layer-contract fields such as:
  - `current_stage`
  - `decision`
  - `next_action`
  - `last_transition`

So the missing capability is not semantic generation.

It is production carrying.

### 3.2 Formal Front Is The Wrong Carrier For This Slice

Current repository evidence in `neotrade3/decision_engine/formal_front.py` shows:

- it builds per-code payloads from:
  - `D1`
  - `security master`
  - `trading_day_status`
  - `price history`
  - buy-side candidate signals

It does not have:

- `TradeRecord`
- market/sector exit states
- market/sector exit snapshots
- trend-exhaustion snapshot
- system-exit grace state
- sell payload

That means the formal-front builder cannot truthfully recreate `position_contract_snapshot(...)`.

So any slice that tries to wire backhalf through `formal_front.py` first would be based on a false premise.

### 3.3 Current Snapshot Is Not Yet A Stable Production Surface

Current repository evidence shows:

- `_position_contract_snapshot(...)` is created inside the engine
- tests verify it directly
- but a repository search does not show it being carried into a stable external result surface

So later layers cannot rely on this runtime truth without reaching into engine internals.

That is the exact gap this slice closes.

## 4. Approach Options

### Option A: Expose `position_contract_snapshot` Through One Existing Production Carrier (Recommended)

- reuse the current snapshot owner
- choose one existing engine output surface
- carry the snapshot there without reinterpretation

Pros:

- smallest truthful move
- no semantic duplication
- creates a stable audit surface for later layers

Cons:

- does not yet complete the whole `M3 backhalf`

### Option B: Rebuild The Snapshot Inside Formal Front

Pros:

- would appear to connect backhalf to formal payload quickly

Cons:

- false ownership
- missing required runtime inputs
- semantic duplication

### Option C: Delay Until Lifecycle/Exit-Semantics Expansion

Pros:

- fewer intermediate carrier shapes

Cons:

- leaves current canonical runtime truth trapped inside engine internals
- delays later `M3 -> M4/M5` convergence

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should modify only:

- `lowfreq_engine_v16_advanced.py`
- one focused test carrier, preferably `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Files intentionally not modified:

- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/decision_engine/projections.py`
- `neotrade3/decision_engine/hold_exit_bridge.py`
- `neotrade3/benchmark/*`
- `neotrade3/governance/*`

### 5.2 Carrier Decision

The implementation must choose one existing engine result surface that is already part of the production output path.

Rules for the carrier:

- it must already belong to a production result, not a temporary local debug object
- it must allow attaching trade-level runtime truth
- it must not require inventing a new subsystem in this slice

This slice intentionally leaves the exact carrier selection to implementation audit within the engine file, because the correct choice must be based on current code evidence, not assumption.

### 5.3 Snapshot Handling Rule

The carried `position_contract_snapshot` must remain semantically identical to the canonical owner output.

Allowed:

- shallow copying for output safety
- stable placement inside the chosen production carrier

Not allowed:

- renaming fields
- recomputing fields elsewhere
- silently dropping fields
- rewriting exit scope or reason semantics

### 5.4 Error Handling

This slice should preserve existing engine behavior.

Recommended rule:

- if the current path already produces a snapshot, carry it
- if the path currently has no snapshot, do not fabricate one

Reason:

- the goal is runtime truth exposure, not broad backfill

### 5.5 Testing Strategy

Focused tests should lock only the production carrier contract.

Required coverage:

1. the chosen production result surface now includes `position_contract_snapshot`
2. the carried snapshot preserves canonical fields:
   - `hold_state`
   - `exit_ready`
   - `exit_scope`
   - `exit_reason_type`
   - `current_stage`
   - `decision`
   - `next_action`
   - `last_transition`
3. existing sell-side behavior stays unchanged

Testing rule:

- do not widen into `build_m3_hold_exit_bridge(...)`
- do not widen into `formal_front`
- do not widen into `M4/M5/M6`

## 6. Risks And Guardrails

### 6.1 Main Risk

The main risk is pretending this slice completes `M3 backhalf`.

Guardrail:

- document and test it as `position snapshot carrier` only

### 6.2 Semantic Risk

The next risk is semantic duplication.

Guardrail:

- use `_position_contract_snapshot(...)` as the only producer

### 6.3 Scope Risk

Another risk is widening into API/report/UI or formal-front work.

Guardrail:

- keep the change inside one engine output carrier plus focused tests

## 7. Acceptance Criteria

This slice is complete only when all of the following are true:

- one stable production result carrier now includes `position_contract_snapshot`
- the carried snapshot matches canonical owner semantics
- existing sell-side behavior is unchanged
- focused tests lock the new carrier contract

## 8. Out Of Scope Follow-Ups

This slice intentionally leaves the following for later:

- `decision_lifecycle_log`
- explicit local/global exit semantics
- `HoldState / ExitState` production formalization
- `build_m3_hold_exit_bridge(...)` production mainline wiring
- `M4` richer hold/exit consumption
- `M5` governance closure
- version unification
- `M6`

## 9. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M3`, exposing existing backhalf runtime truth to a production surface
- `G1-G6` target mapping:
  - this is a `G4` truth-exposure step before later `G5` benchmark/governance consumption
- new contract introduced:
  - engine production output includes `position_contract_snapshot`
- boundaries not touched:
  - no lifecycle object
  - no exit semantic expansion
  - no formal-front backhalf generation
  - no `M4/M5/M6`
