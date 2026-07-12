Status: superseded
Owner: lowfreq / decision_engine
Scope: Narrow `M3 backhalf production hold/exit wiring` slice after the persisted M5 truth switch
Canonical: self
Supersedes: none
Superseded_by: `docs/superpowers/specs/2026-07-13-lowfreq-m3-position-snapshot-carrier-design.md`
Last_reviewed: 2026-07-13

# Lowfreq M3 Production Hold/Exit Wiring Design

Superseded on 2026-07-13 after implementation feasibility audit showed that
`formal_front.py` does not have the runtime inputs required to truthfully rebuild
`position_contract_snapshot(...)`. The active replacement spec is:

- `docs/superpowers/specs/2026-07-13-lowfreq-m3-position-snapshot-carrier-design.md`

Date: 2026-07-13

## 1. Goal

This slice is the next narrow `M3 backhalf` step after:

- the already-landed `M3 hold/exit formal bridge`
- the already-landed `M4 -> M5` truth-path cleanup

Current repository evidence shows:

- `HoldState` and `ExitState` already exist as formal `M3` objects
- `build_m3_hold_exit_bridge(...)` already translates `position_contract_snapshot` into stable hold/exit payloads
- `M4` already consumes that bridge minimally
- but the lowfreq production formal front still stops at:
  - `small_cycle`
  - `identify_state`
  - `tracking_state`
  - `entry_state`
  - `m1_constraints_ref`
- and the compact projection path still exposes only the front-half objects

So the current problem is no longer:

- how to formalize hold/exit bridge semantics
- how to let `M4` consume minimal hold/exit context

It is:

- how to wire the already-landed bridge into the production `M3` output path
- how to let lowfreq formal payloads carry truthful backhalf objects
- how to do that without widening into:
  - `decision_lifecycle_log`
  - local/global exit semantic expansion
  - API/workbench behavior changes
  - `M4` taxonomy redesign
  - `M5/M6`

Project-phase note:

- domain: `M3 backhalf production mainline`
- change type: `bridge baseline -> production wiring`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G4-G5`

## 2. Scope

Included:

- extend the lowfreq formal front production payload to carry:
  - `hold_state`
  - `exit_state`
  - `m3_hold_exit_bridge`
- reuse the existing `position_contract_snapshot` owner and `build_m3_hold_exit_bridge(...)`
- expose the new backhalf objects through the compact formal projection path
- add focused tests that lock:
  - production formal front payload now carries backhalf objects
  - compact projection now preserves the narrow backhalf fields

Excluded:

- no new `decision_lifecycle_log`
- no new `local_exit_semantics` or `global_thesis_end_semantics` fields
- no change to `position_contract_snapshot` output semantics
- no change to sell-side runtime logic
- no new `M4` gap taxonomy
- no `M5` governance changes
- no `M6` delivery or report work

## 3. Existing Evidence

### 3.1 Bridge Baseline Already Exists

Current repository evidence shows:

- `HoldState` and `ExitState` are already defined in `neotrade3/decision_engine/contracts.py`
- `build_m3_hold_exit_bridge(...)` already maps `position_contract_snapshot` into stable:
  - `hold_state`
  - `exit_state`
  - `position_status`
  - `hold_quality_signal`

So this slice should not redesign hold/exit semantics.

It should only move those semantics into the production formal output path.

### 3.2 Formal Front Still Stops At Front-Half

Current repository evidence in `neotrade3/decision_engine/formal_front.py` shows:

- `build_lowfreq_formal_front_payload(...)` only emits:
  - `small_cycle`
  - `identify_state`
  - `tracking_state`
  - `entry_state`
  - `m1_constraints_ref`

There is no:

- `hold_state`
- `exit_state`
- `m3_hold_exit_bridge`

So the mainline production payload is still incomplete relative to the already-landed bridge baseline.

### 3.3 Production Lowfreq Engine Already Has The Needed Runtime Evidence

Current repository evidence in `lowfreq_engine_v16_advanced.py` shows:

- the engine already imports `build_position_contract_snapshot`
- the engine already builds and finalizes lowfreq formal-front payloads through:
  - `build_lowfreq_formal_front_payload_from_connection(...)`
  - `finalize_lowfreq_formal_front_payload(...)`

This means the narrowest production wiring move is not to invent a new engine owner.

It is to extend the existing formal-front builder path so it can reuse already-available `M3` runtime evidence.

### 3.4 Compact Projection Is Also Still Front-Half Only

Current repository evidence in `neotrade3/decision_engine/projections.py` shows:

- compact projection currently exposes only:
  - `small_cycle`
  - `identify_state`
  - `tracking_state`
  - `entry_state`
  - `m1_constraints`

So even if production formal payload starts carrying backhalf objects, the compact projection would still hide them unless updated in the same slice.

This is why the slice must cover both:

- formal payload production
- narrow projection exposure

### 3.5 What Must Still Wait

Repository evidence also shows:

- `decision_lifecycle_log` is still design-only
- explicit `local_exit_semantics` / `global_thesis_end_semantics` are still not implemented
- previous hold/exit bridge design explicitly excluded lifecycle work

So this slice must not pretend to complete the whole `M3 backhalf`.

It only completes production wiring for the already-landed bridge baseline.

## 4. Approach Options

### Option A: Wire Existing Bridge Into Formal Front And Projection (Recommended)

- reuse `position_contract_snapshot`
- reuse `build_m3_hold_exit_bridge(...)`
- extend formal front payload to carry hold/exit bridge outputs
- extend compact projection to show only narrow backhalf summaries

Pros:

- smallest production delta
- reuses already-tested semantics
- advances `M3 backhalf` mainline truthfully
- avoids reopening sell logic

Cons:

- still does not provide lifecycle logging
- still does not provide full exit semantic taxonomy

### Option B: Add Backhalf Objects Directly Inside Lowfreq Engine Output Without Formal-Front Ownership

Pros:

- may look faster at first glance

Cons:

- bypasses the existing `decision_engine` ownership boundary
- would reintroduce engine-local semantic shaping
- weakens later `M3` semantic audit

### Option C: Wait Until Lifecycle And Exit-Semantics Expansion Are Designed Together

Pros:

- fewer intermediate shapes

Cons:

- leaves production payload truth behind existing bridge baseline
- delays a needed mainline convergence step
- increases the chance of larger, riskier future diffs

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should touch only the minimum owners needed for production wiring:

- `neotrade3/decision_engine/formal_front.py`
  - extend the formal payload builder
- `neotrade3/decision_engine/projections.py`
  - extend compact projection exposure
- focused tests around formal front and compact projection

Files intentionally reused but not redesigned:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/hold_exit_bridge.py`
- `neotrade3/decision_engine/position_contract_snapshot.py`
- `neotrade3/decision_engine/assembler.py`

Files intentionally not modified:

- `neotrade3/benchmark/*`
- `neotrade3/governance/*`
- `apps/api/*` production routing logic
- `lowfreq_engine_v16_advanced.py` sell-side runtime logic

### 5.2 Formal Payload Extension

The lowfreq formal payload item for each code should be extended to carry:

- `hold_state`
- `exit_state`
- `m3_hold_exit_bridge`

Recommended behavior:

1. keep current front-half payload fields unchanged
2. resolve existing runtime evidence for each code through the already-frozen snapshot owner
3. build one bridge payload via `build_m3_hold_exit_bridge(...)`
4. write:
   - `hold_state` from bridge payload
   - `exit_state` from bridge payload
   - `m3_hold_exit_bridge` as the full bridge payload

Naming decision:

- use `m3_hold_exit_bridge` for the full bridge payload

Reason:

- `hold_state` and `exit_state` remain formal objects
- the bridge payload itself contains extra transport context:
  - `bridge_version`
  - `source_contract`
  - `position_status`
  - `hold_quality_signal`
- using a dedicated field avoids pretending the full bridge is itself one formal object

### 5.3 Narrow Runtime Evidence Rule

This slice must not invent new lowfreq runtime evidence sources.

Recommended rule:

- production formal front should only consume the already-ownerized snapshot semantics

That means:

- no rebuilding hold/exit logic from raw trade collaborators inside `formal_front.py`
- no inline re-derivation of exit scopes or reasons
- no hidden sell-side behavior changes

If current formal-front builder does not yet have enough access to the snapshot owner for each code, the extension should remain a narrow adapter move, not a semantic rewrite.

### 5.4 Compact Projection Extension

The compact formal projection should expose only a narrow backhalf summary.

Recommended added fields:

- `hold_state`
  - `status`
  - `hold_state`
  - `warning_flags`
- `exit_state`
  - `status`
  - `exit_ready`
  - `exit_scope`
  - `exit_reason_type`
- `m3_backhalf`
  - `position_status`
  - `hold_quality_signal`

Reason:

- compact projection is a summary surface, not the canonical full payload
- it should expose enough to confirm backhalf semantics are now in production
- it should avoid over-projecting raw evidence internals

### 5.5 Error Handling

The current formal-front builder already returns per-code error payloads when formal projection fails.

This slice should preserve that behavior.

Recommended rule:

- if backhalf wiring fails for one code, that code should continue to use the existing `formal_projection_failed` path
- do not silently drop backhalf payloads while still marking the item `ok`

Reason:

- silent omission would make semantic audit impossible

### 5.6 Testing Strategy

Focused tests should lock only production wiring.

Required coverage:

1. formal-front payload now carries `hold_state` and `m3_hold_exit_bridge` for a non-exit case
2. formal-front payload now carries `exit_state` and `m3_hold_exit_bridge` for an exit-ready case
3. compact projection preserves the narrow backhalf summary when the formal payload is `ok`
4. existing front-half fields remain unchanged

Testing rule:

- do not re-test sell-side execution behavior
- do not widen into `decision_lifecycle_log`
- do not widen into `M4/M5/M6`

## 6. Risks And Guardrails

### 6.1 Main Risk

The main risk is accidental widening into lifecycle or exit taxonomy work.

Guardrail:

- this slice wires existing backhalf objects into production payloads only

### 6.2 Semantic Risk

Another risk is bypassing existing owners and re-deriving hold/exit semantics in the wrong place.

Guardrail:

- only reuse `position_contract_snapshot` and `build_m3_hold_exit_bridge(...)`

### 6.3 Projection Risk

Another risk is exposing too much raw bridge internals through compact projection.

Guardrail:

- compact projection should expose a narrow summary only

## 7. Acceptance Criteria

This slice is complete only when all of the following are true:

- lowfreq formal-front payloads carry `hold_state`, `exit_state`, and `m3_hold_exit_bridge`
- compact projection exposes a narrow backhalf summary
- front-half payload shape remains stable
- the implementation reuses the existing snapshot owner and bridge owner
- focused tests lock the new production wiring

## 8. Out Of Scope Follow-Ups

This slice intentionally leaves the following for later:

- `decision_lifecycle_log`
- explicit `local_exit_semantics`
- explicit `global_thesis_end_semantics`
- API/workbench dedicated backhalf rendering
- `M4` expanded hold/exit taxonomy
- `M5` governance closure
- version unification
- `M6`

## 9. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M3`, turning an already-landed bridge baseline into production mainline truth
- `G1-G6` target mapping:
  - this is a `G4 -> G5` preparation step so later `M4/M5` consume less partial `M3` truth
- new contract introduced:
  - production formal payload includes `hold_state`, `exit_state`, and `m3_hold_exit_bridge`
- boundaries not touched:
  - no lifecycle object
  - no exit semantic expansion
  - no `M4/M5/M6`
