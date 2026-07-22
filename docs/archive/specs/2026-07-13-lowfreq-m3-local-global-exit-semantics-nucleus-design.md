Status: active
Owner: lowfreq / decision_engine
Scope: Narrow `M3 local/global exit semantics nucleus` slice after the position snapshot carrier baseline
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Local/Global Exit Semantics Nucleus Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful `M3 backhalf` step after:

- the already-landed `M3 hold/exit formal bridge`
- the already-landed `M3 position snapshot production carrier`
- the already-landed `M5` persisted `M4` truth switch

Current repository evidence shows:

- `position_contract_snapshot(...)` is the canonical runtime owner for current sell-side backhalf truth
- `sell_signal_audit` already carries that snapshot as a stable production surface
- `build_m3_hold_exit_bridge(...)` can already map current snapshots into `HoldState` and `ExitState`
- but no current `M3` owner emits explicit:
  - `local_exit_semantics`
  - `global_thesis_end_semantics`

At the same time, repository design evidence already requires:

- `M3` must explicitly separate local exit from global thesis end
- downstream layers must not infer that distinction by guesswork
- `E5 Global Thesis End Exit` must be used extremely conservatively in the first stage

So the real next problem is not:

- lifecycle logging
- front-half rewiring
- benchmark/governance expansion

It is:

- add explicit local/global exit semantics at the current canonical `M3` backhalf owner
- expose those semantics through the existing `ExitState` bridge path
- do so without fabricating global-thesis claims that current runtime evidence cannot support

Project-phase note:

- domain: `M3 backhalf semantic nucleus`
- change type: `canonical owner field completion`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G4`

## 2. Scope

Included:

- add explicit `local_exit_semantics` and `global_thesis_end_semantics` to the canonical `position_contract_snapshot` exit payload
- extend `ExitState` formal contract to carry those semantics
- extend `build_m3_hold_exit_bridge(...)` to pass the new semantics through the existing formal bridge
- add focused tests that lock the new owner and bridge contract

Excluded:

- no `decision_lifecycle_log`
- no `formal_front` rewiring
- no API/workbench/report rendering changes
- no new `HoldState` semantic vocabulary
- no `M4` benchmark consumer changes
- no `M5` governance consumer changes
- no `M6`

## 3. Existing Evidence

### 3.1 The Canonical Runtime Owner Already Exists

Current repository evidence in [position_contract_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/position_contract_snapshot.py) shows:

- `build_position_contract_snapshot(...)` is the canonical shaper for current backhalf runtime truth
- when `sell_payload` exists, it already emits:
  - `hold_state = "exit_ready"`
  - `exit_scope`
  - `exit_reason_type`
  - `exit_attribution_bucket`
  - `current_stage`
  - `decision`
  - `next_action`
- when `sell_payload` does not exist, it emits the hold-side shape instead

So the missing capability is not exit detection.

It is explicit local/global semantic classification.

### 3.2 The Existing Bridge Path Is Real But Incomplete

Current repository evidence in [hold_exit_bridge.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/hold_exit_bridge.py) and [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py) shows:

- `build_m3_hold_exit_bridge(...)` already maps `exit_ready` snapshots into formal `ExitState`
- `ExitState` already carries:
  - `exit_ready`
  - `exit_scope`
  - `exit_reason_type`
  - `exit_attribution_bucket`
- but `ExitState` currently has no explicit local/global semantic fields

So the bridge exists, but the formal contract is still missing the exact semantic distinction the higher-level design requires.

### 3.3 Repository Vocabulary Already Exists

Current repository evidence in [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/contracts.py), [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/assembler.py), and [benchmark/assembler.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py) shows an existing local/global vocabulary line:

- `local_end_only`
- `needs_global_confirmation`
- `possible_global_end`
- `global_end_only`

Repository evidence also shows:

- `M2` currently owns `local_end_vs_global_end`
- current `M2` default assembly only produces:
  - `local_end_only`
  - `needs_global_confirmation`
- richer values such as `possible_global_end` and `global_end_only` appear only in fixture or governance-diagnosis contexts, not as current `M3` runtime truth

So this slice should reuse repository vocabulary, but must stay within the subset currently justified by `M3` runtime evidence.

### 3.4 The High-Level M3 Design Is Explicit

Current repository evidence in [m3-decision-engine-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m3-decision-engine-design.md) states:

- `Exit` must distinguish local exit from global thesis end
- `local_exit_semantics` and `global_thesis_end_semantics` cannot stay implicit
- `E5 Global Thesis End Exit` must be extremely conservative in the first stage
- a single `small_cycle` end must not be mechanically rewritten as full-thesis termination

That means the next design must protect against false global claims, not only against missing fields.

## 4. Approach Options

### Option A: Add The Two Fields Only To The Existing Exit Path (Recommended)

- extend the canonical exit snapshot owner
- extend `ExitState`
- extend the existing hold/exit bridge
- keep hold-side semantics unchanged

Pros:

- smallest truthful move
- closes the exact missing semantic gap
- stays aligned with current runtime evidence

Cons:

- does not yet complete lifecycle logging
- does not formalize hold-side local/global vocabulary

### Option B: Add The Fields Everywhere Including HoldState

Pros:

- more symmetrical object shape

Cons:

- current repository evidence does not justify a stable hold-side vocabulary
- risks inventing semantics that current runtime owner does not yet possess

### Option C: Jump Directly To Lifecycle Log

Pros:

- would surface a richer behavior chain

Cons:

- lifecycle is downstream of semantics, not a substitute for semantics
- would leave the owner ambiguity unresolved

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should modify only the current semantic owner chain:

- `neotrade3/decision_engine/position_contract_snapshot.py`
- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/hold_exit_bridge.py`
- focused tests

Files intentionally not modified:

- `lowfreq_engine_v16_advanced.py` semantic logic itself
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/benchmark/*`
- `neotrade3/governance/*`
- `M6` delivery/observability surfaces

### 5.2 First-Stage Semantic Rule

The first-stage rule must be conservative:

- current `M3` runtime can prove that the current position should exit
- current `M3` runtime cannot, by itself, prove that the entire higher-level thesis has ended

Therefore:

- an `exit_ready` event may produce a local exit semantic
- but it must not automatically escalate into a global thesis end semantic

This directly follows the existing `H1-H4` guardrail direction in the repository design.

### 5.3 First-Stage Vocabulary

This slice should use only the repository vocabulary subset already justified by current evidence:

- `local_exit_semantics = "local_end_only"`
- `global_thesis_end_semantics = "needs_global_confirmation"`

This slice must not emit:

- `possible_global_end`
- `global_end_only`

Reason:

- current `M3` runtime owner does not have a higher-level thesis owner or a formal global-end proof chain
- emitting those stronger values here would be a semantic overreach

### 5.4 Snapshot Shape Rule

For the canonical `position_contract_snapshot`:

- when `sell_payload` exists:
  - set `local_exit_semantics = "local_end_only"`
  - set `global_thesis_end_semantics = "needs_global_confirmation"`
- when `sell_payload` does not exist:
  - keep both fields as empty strings in the first stage

Reason:

- the current owner already uses empty strings for exit-only fields on hold-side snapshots:
  - `exit_scope`
  - `exit_reason_type`
  - `exit_attribution_bucket`
- matching that style is safer than inventing a new hold-side semantic taxonomy in this slice

### 5.5 Formal Contract Rule

`ExitState` must be extended with explicit formal fields:

- `local_exit_semantics`
- `global_thesis_end_semantics`

These fields should be first-class payload members, not hidden inside `evidence_ref`.

Reason:

- repository design explicitly requires them as semantic fields
- downstream `M4/M5/M6` must be able to consume them without parsing free-form evidence blobs

### 5.6 Bridge Rule

`build_m3_hold_exit_bridge(...)` must:

- read the two new fields from the exit-ready snapshot
- pass them through the `build_exit_state(...)` call
- keep hold-side behavior unchanged

This slice should not:

- add new local/global fields to `HoldState`
- infer stronger semantics from `m2_cycle_ref`
- reinterpret snapshot values in the bridge

The bridge remains a thin translator, not a second semantic owner.

### 5.7 Error Handling

This slice should preserve the existing style:

- exit snapshots must always contain the two fields
- hold snapshots may leave them as empty strings
- no fallback inference if the upstream owner did not provide a value

Reason:

- the goal is explicitness without fabrication

## 6. Testing Strategy

Focused tests should lock only the new semantic contract surface.

Required coverage:

1. canonical exit snapshots now contain:
   - `local_exit_semantics`
   - `global_thesis_end_semantics`
2. current `trend_exhausted` exit produces:
   - `local_end_only`
   - `needs_global_confirmation`
3. current `market_top_confirmed` exit also produces:
   - `local_end_only`
   - `needs_global_confirmation`
4. `build_m3_hold_exit_bridge(...)` preserves the two fields in `ExitState`
5. hold-side bridge behavior remains unchanged

Testing rule:

- do not widen into lifecycle logging
- do not widen into `formal_front`
- do not widen into `M4/M5/M6`

## 7. Risks And Guardrails

### 7.1 Main Risk

The main risk is semantic over-claiming:

- turning a position-level exit into a thesis-level end

Guardrail:

- first-stage global value stays fixed at `needs_global_confirmation`

### 7.2 Contract Risk

Another risk is hiding these semantics inside `evidence_ref` only.

Guardrail:

- promote them to explicit `ExitState` payload fields

### 7.3 Scope Risk

Another risk is widening into lifecycle, API projection, benchmark, or governance.

Guardrail:

- keep the slice inside owner, formal contract, bridge, and focused tests

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- `position_contract_snapshot` exit payload contains explicit local/global semantic fields
- the values are conservative and repository-vocabulary-aligned
- `ExitState` carries the same fields as first-class payload members
- `build_m3_hold_exit_bridge(...)` preserves them without reinterpretation
- focused tests lock the new contract

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves the following for later:

- `decision_lifecycle_log`
- hold-side local/global semantic taxonomy
- richer values such as `possible_global_end` or `global_end_only`
- `formal_front` backhalf generation
- `M4` richer local/global benchmark consumption
- `M5` governance closure
- version unification
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M3`, completing the canonical backhalf exit semantics owner
- `G1-G6` target mapping:
  - this is a `G4` semantic truth-completion step that reduces later `M4/M5` local/global misread risk
- new contract introduced:
  - `position_contract_snapshot.local_exit_semantics`
  - `position_contract_snapshot.global_thesis_end_semantics`
  - `ExitState.local_exit_semantics`
  - `ExitState.global_thesis_end_semantics`
- boundaries not touched:
  - no lifecycle object
  - no new hold-side semantic taxonomy
  - no `formal_front`
  - no `M4/M5/M6`
