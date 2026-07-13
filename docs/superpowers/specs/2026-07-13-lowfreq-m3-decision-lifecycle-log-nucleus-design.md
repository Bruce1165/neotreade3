Status: active
Owner: lowfreq / decision_engine
Scope: Narrow `M3 decision_lifecycle_log nucleus` slice after the local/global exit semantics nucleus
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Decision Lifecycle Log Nucleus Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful `M3 backhalf` step after the already-landed:

- `M3 hold/exit formal bridge`
- `M3 position snapshot production carrier`
- `M3 local/global exit semantics nucleus`

Current repository evidence shows:

- `M3` formal contracts already include:
  - `identify_state`
  - `tracking_state`
  - `entry_state`
  - `hold_state`
  - `exit_state`
- but there is still no formal `decision_lifecycle_log` object in:
  - [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py)
  - [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py)
- runtime backhalf event evidence already exists in one production carrier:
  - `sell_signal_audit`
- lowfreq runtime currently appends raw event dictionaries into that carrier through:
  - `_record_sell_signal_audit_event(...)`
  - `_record_system_exit_audit_event(...)`
  - `_record_system_exit_grace_audit_event(...)`

So the real next problem is not:

- another sell-rule rewrite
- a full `identify -> tracking -> entry -> hold -> exit` runtime chain
- benchmark, governance, or delivery wiring

It is:

- formalize the already-existing `M3 backhalf` runtime event chain
- do so from the existing production `sell_signal_audit` carrier
- keep the slice inside current repository evidence, without inventing front-half runtime events

Project-phase note:

- domain: `M3 backhalf lifecycle nucleus`
- change type: `formal object completion`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G4`

## 2. Scope

Included:

- add formal `DecisionLifecycleEvent` and `DecisionLifecycleLog` contracts under `neotrade3/decision_engine/contracts.py`
- add assembler helpers that build those objects from already-decided inputs
- add one shared owner that formalizes current `sell_signal_audit` entries into stable lifecycle objects
- keep the lifecycle slice strictly `backhalf only`
- add focused tests that lock the current runtime event vocabulary and the new formalization contract

Excluded:

- no `identify / tracking / entry` runtime lifecycle logging
- no rewrite of lowfreq sell logic
- no rewrite of `_sell_signal_audit_current_run` storage
- no `formal_front` rewiring
- no new `M4` benchmark consumer changes
- no new `M5` governance consumer changes
- no `M6`

## 3. Existing Evidence

### 3.1 Formal M3 Is Still Missing The Lifecycle Log Object

Current repository evidence in [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py) shows:

- `M3` formal objects currently stop at:
  - `IdentifyState`
  - `TrackingState`
  - `EntryState`
  - `HoldState`
  - `ExitState`
- no `DecisionLifecycleEvent`
- no `DecisionLifecycleLog`

Current repository evidence in [m3-decision-engine-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m3-decision-engine-design.md) also states:

- `O6 decision_lifecycle_log` is part of the intended `M3` formal surface

So the missing capability is not theoretical.

It is a real contract gap between design and code.

### 3.2 Runtime Backhalf Events Already Exist

Current repository evidence in [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py) shows three existing append helpers:

- `_record_sell_signal_audit_event(...)`
- `_record_system_exit_audit_event(...)`
- `_record_system_exit_grace_audit_event(...)`

Those helpers already append raw runtime events into `_sell_signal_audit_current_run`.

Current repository evidence also shows the resulting list is already exposed as one production carrier:

- `gross_metrics["sell_signal_audit"] = sell_signal_audit`

That means the repository already has:

- a real runtime event source
- a stable production raw carrier

What it does not have is a formal `M3` lifecycle owner on top of that carrier.

### 3.3 The Current Event Vocabulary Is Backhalf-Only

Current repository evidence in [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py) shows current sell-side event names such as:

- `market_exit_watch_started`
- `market_exit_review_started`
- `market_exit_watch_expired`
- `market_exit_confirmed`
- `sector_exit_watch_started`
- `sector_exit_review_started`
- `sector_exit_watch_expired`
- `sector_exit_confirmed`
- `trend_exhausted`
- `system_exit_downgraded`
- `system_exit_downgraded_then_confirmed`
- `system_exit_downgraded_then_stop_loss`
- `system_exit_downgraded_then_end_flat`

Repository evidence does not show any current front-half runtime event chain for:

- `identify`
- `tracking`
- `entry`

So this slice must stay backhalf-only.

### 3.4 Position Snapshot Is Already The Backhalf Truth Carrier

Current repository evidence in [position_contract_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/position_contract_snapshot.py) shows:

- backhalf runtime meaning is already concentrated in `position_contract_snapshot`
- sell-side events already carry that snapshot in raw audit rows when available
- the snapshot now already includes:
  - exit semantics
  - local/global exit semantics

That means the lifecycle log does not need to recreate sell meaning.

It should reference and preserve the already-ownerized backhalf snapshot.

## 4. Approach Options

### Option A: Add A Pure Formalization Owner On Top Of Existing `sell_signal_audit` (Recommended)

- keep `sell_signal_audit` as the raw runtime carrier
- add formal lifecycle contracts
- add one shared owner that turns raw audit rows into stable lifecycle objects
- keep front-half out of scope

Pros:

- reuses the strongest current evidence
- keeps the slice narrow
- avoids rewriting engine lifecycle orchestration
- does not fabricate unavailable front-half runtime events

Cons:

- does not yet create one full `M3` front-to-back lifecycle chain

### Option B: Rewrite Engine Append Helpers To Emit Formal Lifecycle Rows Directly

Pros:

- stronger runtime purity

Cons:

- reopens append orchestration
- broadens the slice into engine behavior, not only object completion
- risks unnecessary observable drift in raw audit rows

### Option C: Define A Full Five-Stage Lifecycle Skeleton Now

Pros:

- conceptually complete

Cons:

- current repository evidence does not justify front-half runtime events
- would force placeholders or fabricated chains

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should introduce one new ownership chain:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/decision_lifecycle_log.py`
- `neotrade3/decision_engine/__init__.py`
- focused tests

Files intentionally not modified in the first stage:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/benchmark/*`
- `neotrade3/governance/*`
- report scripts

Reason:

- the raw carrier already exists
- this slice only completes the missing formal object layer on top of it

### 5.2 Formal Object Freeze

This slice should add two formal objects.

`DecisionLifecycleEvent` minimum fields:

- `stock_code`
- `trade_date`
- `event`
- `source_layer`
- `stage`
- `decision`
- `exit_scope`
- `details`
- `position_contract_snapshot`
- `evidence_ref`

`DecisionLifecycleLog` minimum fields:

- `stock_code`
- `events`

Design rule:

- `DecisionLifecycleLog` is a per-stock formal object
- a backtest run may still contain multiple logs after grouping raw rows by `stock_code`

Reason:

- repository design describes one stock's lifecycle chain
- current raw carrier is run-level and cross-stock, so grouping is required before formalization

### 5.3 Formalization Rule

The shared owner should expose two public helpers:

- `build_decision_lifecycle_event_from_sell_audit_entry(...)`
- `build_decision_lifecycle_logs(...)`

Behavior:

1. accept only current raw `sell_signal_audit` rows
2. keep only rows with a non-empty `code` and `event`
3. group rows by `stock_code`
4. sort each stock's rows by `trade_date`, preserving stable append order within the same day
5. formalize each row into `DecisionLifecycleEvent`
6. emit one `DecisionLifecycleLog` per stock

This slice does not:

- derive new events
- backfill front-half stages
- infer missing lifecycle rows

### 5.4 Stage And Decision Rule

The lifecycle owner should prefer existing upstream truth:

- use `position_contract_snapshot.current_stage` when present
- use `position_contract_snapshot.decision` when present

Only when the snapshot is missing should the owner use conservative fallback mapping derived from current event names.

Recommended fallback:

- watch/review/expired/downgraded events fall back to a hold-side decision
- confirmed / `trend_exhausted` / stop-loss / end-flat events fall back to an exit-side decision

Reason:

- the snapshot is already the canonical backhalf truth carrier
- fallback should exist only to keep current raw rows formalizable when the snapshot is absent

### 5.5 Evidence Rule

`position_contract_snapshot` must remain a first-class field in `DecisionLifecycleEvent`.

Additional event-specific fields should be preserved under `evidence_ref`.

Examples from current raw rows include:

- `scope`
- `state`
- `watch_day`
- `watch_hits`
- `confirm_hits_required`
- `leader_hold_active`
- `grace_used`
- `grace_scope`
- `grace_date`
- `market_label`
- `sector_label`
- `trend_state`
- `current_return_pct`
- `peak_return_pct`
- `profit_keep_ratio`

Reason:

- these fields are already emitted by runtime append helpers
- preserving them under `evidence_ref` avoids exploding the first-stage formal object surface

### 5.6 Backhalf Boundary Rule

This slice must formalize only currently evidenced backhalf events.

Included event families:

- system-exit watch
- system-exit review
- system-exit watch expiry
- system-exit confirm
- trend exhaustion
- system-exit grace downgrade chain

Excluded:

- `tracking_started`
- `tracking_promoted_to_entry`
- `tracking_dropped`
- buy execution / reservation events

Reason:

- those belong to buy-side tracking/execution carriers, not this backhalf nucleus

### 5.7 Production Carrier Rule

This slice should not add a new runtime storage path.

The formalization input remains:

- `sell_signal_audit`

Consumers that need formal lifecycle objects can build them from that existing raw carrier through the new shared owner.

Reason:

- the repository already exposes `sell_signal_audit`
- adding another raw storage path here would duplicate truth

## 6. Testing Strategy

Focused tests should lock three layers only.

Required coverage:

1. owner-focused event formalization:
   - one watch event
   - one confirm event
   - one grace downgrade event
2. per-stock grouping:
   - mixed-code raw audit rows become separate lifecycle logs
3. runtime compatibility:
   - current sell logic still produces raw audit rows that can be formalized without loss of current backhalf truth

Testing rule:

- do not widen into front-half runtime logging
- do not widen into `formal_front`
- do not widen into `M4/M5/M6`
- do not rewrite report-script consumers in this slice

## 7. Risks And Guardrails

### 7.1 Main Risk

The main risk is silently treating current raw audit rows as a complete full-lifecycle chain.

Guardrail:

- formalize only backhalf rows
- do not emit front-half events not present in runtime evidence

### 7.2 Contract Risk

Another risk is hiding the current snapshot truth inside flattened free-form fields only.

Guardrail:

- preserve `position_contract_snapshot` as an explicit lifecycle-event field

### 7.3 Scope Risk

Another risk is broadening into engine append rewrites or new consumer surfaces.

Guardrail:

- keep raw audit storage unchanged
- add only the missing formal object layer and focused tests

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- `DecisionLifecycleEvent` and `DecisionLifecycleLog` exist as formal `M3` contracts
- a shared owner can formalize current `sell_signal_audit` rows into stable lifecycle objects
- the formalization stays backhalf-only
- current `position_contract_snapshot` truth is preserved in lifecycle events
- focused tests lock grouping, event formalization, and runtime compatibility

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves the following for later:

- full `identify -> tracking -> entry -> hold -> exit` runtime lifecycle chaining
- buy-side lifecycle unification with `buy_signal_audit`
- `formal_front` lifecycle projection
- `M4` lifecycle-log benchmark consumption
- `M5` governance lifecycle consumption
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M3`, completing the missing formal backhalf lifecycle object on top of the already-exposed raw audit carrier
- `G1-G6` target mapping:
  - this is a `G4` truth-completion step that stabilizes the backhalf event chain before later cross-layer consumption
- new contract introduced:
  - `DecisionLifecycleEvent`
  - `DecisionLifecycleLog`
  - `build_decision_lifecycle_event_from_sell_audit_entry(...)`
  - `build_decision_lifecycle_logs(...)`
- boundaries not touched:
  - no front-half runtime lifecycle
  - no raw audit storage rewrite
  - no `formal_front`
  - no `M4/M5/M6`
