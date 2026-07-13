Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow `M3 decision_lifecycle_log nucleus` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M3 Decision Lifecycle Log Nucleus Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m3-decision-lifecycle-log-nucleus-design.md`

## 1. Goal

This plan implements the next truthful `M3 backhalf` slice after the already-landed:

- `M3 hold/exit formal bridge`
- `M3 position snapshot production carrier`
- `M3 local/global exit semantics nucleus`

This slice must:

- add formal `DecisionLifecycleEvent` and `DecisionLifecycleLog` contracts
- add assembler helpers for those contracts
- add one shared owner that formalizes current `sell_signal_audit` rows into per-stock backhalf lifecycle logs
- keep the slice strictly on top of the already-exposed raw carrier
- lock the new contract with focused tests

This slice explicitly does not include:

- front-half runtime lifecycle logging
- a rewrite of `_sell_signal_audit_current_run`
- a rewrite of lowfreq sell logic
- `formal_front` rewiring
- `M4` benchmark consumer changes
- `M5` governance consumer changes
- `M6`

## 2. Starting Point

Repository evidence before implementation:

- `neotrade3/decision_engine/contracts.py` has no lifecycle-log object yet
- `neotrade3/decision_engine/assembler.py` has no lifecycle-log builders yet
- `lowfreq_engine_v16_advanced.py` already emits raw backhalf audit rows through:
  - `_record_sell_signal_audit_event(...)`
  - `_record_system_exit_audit_event(...)`
  - `_record_system_exit_grace_audit_event(...)`
- `run_backtest(...)` already exposes those rows as `sell_signal_audit`
- current runtime tests already prove the raw sell-side event chain is alive

So the implementation strategy is:

- complete the missing formal contract layer first
- add one shared owner on top of the existing raw carrier
- keep runtime append orchestration unchanged
- add one owner-focused test carrier plus one nearby runtime compatibility regression

## 3. File Boundary

Production files:

- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/decision_lifecycle_log.py`
- `neotrade3/decision_engine/__init__.py`

Focused test files:

- `tests/unit/test_m3_decision_lifecycle_log.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Files intentionally not modified:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `neotrade3/benchmark/*`
- `neotrade3/governance/*`
- report scripts

## 4. Execution Steps

### M3LOG-S1: Add the formal lifecycle contracts

Modify:

- `neotrade3/decision_engine/contracts.py`

Implementation:

1. add `DECISION_LIFECYCLE_EVENT_OBJECT_TYPE`
2. add `DECISION_LIFECYCLE_LOG_OBJECT_TYPE`
3. add `DecisionLifecycleEvent`
4. add `DecisionLifecycleLog`
5. add `to_payload()` for both objects

Minimum event fields:

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

Minimum log fields:

- `stock_code`
- `events`

Implementation rule:

- `DecisionLifecycleLog` remains per-stock
- `position_contract_snapshot` stays first-class
- event-specific spillover stays under `evidence_ref`

Completion check:

- the lifecycle nucleus has a formal object surface in `M3`

### M3LOG-S2: Add assembler helpers

Modify:

- `neotrade3/decision_engine/assembler.py`

Implementation:

1. add `build_decision_lifecycle_event(...)`
2. add `build_decision_lifecycle_log(...)`
3. keep builder behavior pure and input-driven

Implementation rule:

- builders do not infer runtime events
- builders do not read config
- builders do not mutate input rows

Completion check:

- formal lifecycle objects can be built independently from lowfreq runtime append behavior

### M3LOG-S3: Add the shared formalization owner

Create:

- `neotrade3/decision_engine/decision_lifecycle_log.py`

Implementation:

1. add one helper to formalize a single raw row:
   - `build_decision_lifecycle_event_from_sell_audit_entry(...)`
2. add one helper to group and formalize a raw run:
   - `build_decision_lifecycle_logs(...)`
3. use the current raw `sell_signal_audit` row shape as the only input
4. group by stock code
5. sort each stock chain by trade date while preserving stable same-day order
6. prefer upstream `position_contract_snapshot` for:
   - `stage`
   - `decision`
   - `exit_scope`
7. use conservative event-name fallback only when the snapshot is absent

Implementation rule:

- accept only existing raw carrier rows
- drop rows that have no usable `code` or `event`
- do not create front-half events
- do not create synthetic rows

Completion check:

- one shared owner can turn raw backhalf audit rows into stable per-stock lifecycle logs

### M3LOG-S4: Export the new owner surface

Modify:

- `neotrade3/decision_engine/__init__.py`

Implementation:

1. export the new object types
2. export `DecisionLifecycleEvent`
3. export `DecisionLifecycleLog`
4. export `build_decision_lifecycle_event(...)`
5. export `build_decision_lifecycle_log(...)`
6. export `build_decision_lifecycle_event_from_sell_audit_entry(...)`
7. export `build_decision_lifecycle_logs(...)`

Completion check:

- the lifecycle owner is consumable as a stable `decision_engine` surface

### M3LOG-S5: Lock the contract with focused tests

Modify:

- `tests/unit/test_m3_decision_lifecycle_log.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

Required coverage:

1. one raw watch event becomes a formal event with hold-side stage/decision
2. one raw confirm event becomes a formal event with exit-side stage/decision
3. one raw grace downgrade event preserves grace evidence fields
4. mixed-code raw rows become separate per-stock logs
5. current sell logic runtime rows remain formalizable through the new owner

Testing rule:

- do not widen into buy-side tracking events
- do not widen into `formal_front`
- do not widen into `M4/M5/M6`

Completion check:

- the new lifecycle contract is locked both as a pure owner and against current runtime sell rows

### M3LOG-S6: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/decision_engine/contracts.py neotrade3/decision_engine/assembler.py neotrade3/decision_engine/decision_lifecycle_log.py neotrade3/decision_engine/__init__.py tests/unit/test_m3_decision_lifecycle_log.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `python3 -m pytest tests/unit/test_m3_decision_lifecycle_log.py tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `git diff --check`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run one inline assertion script that:
  - formalizes one watch row
  - formalizes one confirm row
  - groups mixed-code rows into separate logs
  - formalizes real runtime rows from a `trend_exhausted` or `market_top_confirmed` scenario

## 5. Risks And Guardrails

- **Risk: false full-lifecycle completion**
  - Guardrail: keep the slice strictly backhalf-only
- **Risk: truth duplication**
  - Guardrail: preserve `sell_signal_audit` as raw carrier and `position_contract_snapshot` as explicit event field
- **Risk: append behavior drift**
  - Guardrail: do not modify `lowfreq_engine_v16_advanced.py`
- **Risk: contract explosion**
  - Guardrail: keep event-specific spillover in `evidence_ref`

## 6. Done Criteria

This slice is done only when all of the following are true:

- `DecisionLifecycleEvent` and `DecisionLifecycleLog` exist in `M3`
- a shared owner can formalize current `sell_signal_audit` rows into per-stock lifecycle logs
- current backhalf snapshot truth is preserved in lifecycle events
- the slice remains backhalf-only
- focused tests and minimum verification pass

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - implementation belongs to `M3`, completing the missing formal backhalf lifecycle object above the existing raw audit carrier
- `G1-G6` target mapping:
  - this is a `G4` truth-completion step that stabilizes the backhalf event chain before later cross-layer consumption
- new contract introduced:
  - `DecisionLifecycleEvent`
  - `DecisionLifecycleLog`
  - `build_decision_lifecycle_event_from_sell_audit_entry(...)`
  - `build_decision_lifecycle_logs(...)`
- boundaries not touched:
  - no front-half runtime lifecycle
  - no lowfreq append rewrite
  - no `formal_front`
  - no `M4/M5/M6`
