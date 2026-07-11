Status: active
Owner: lowfreq / decision_engine
Scope: Implementation plan for the narrow M3 buy-signal-audit contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Buy Signal Audit Contract Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-buy-signal-audit-contract-design.md`

## 1. Goal

This plan covers only the next narrow `buy signal audit contract` slice after the `position contract snapshot` extraction.

This slice only handles:

- execution block reason normalization
- event-to-action-field mapping
- event-to-funnel-stage mapping
- owner-focused coverage for the emitted audit contract

The goal is to:

- move the pure audit mapping kernel into one shared owner
- keep audit-log append orchestration in the engine
- preserve current emitted audit fields exactly

This slice does not:

- rewrite `_record_buy_signal_audit_event(...)` append behavior
- rewrite tracking or reservation lifecycle
- rewrite API-side normalization helpers
- rewrite attribution report wording logic

## 2. Starting Point

Current repository evidence shows:

- `_normalize_execution_block_reason(...)` and `_execution_action_fields(...)` still live in the engine
- `_record_buy_signal_audit_event(...)` still owns the `funnel_stage` mapping inline
- nearby convergence tests already assert observable audit rows for reservation and buy execution paths
- repository evidence also shows parallel normalized-reason consumption in API/report, confirming this is a real contract surface

So the correct next slice is:

- extract only the pure audit contract mappings
- keep audit row append orchestration in the engine

## 3. Implementation Strategy

Add one dedicated shared owner:

- `neotrade3/decision_engine/buy_signal_audit_contract.py`

Move the pure audit mappings there:

- `normalize_execution_block_reason(...)`
- `resolve_execution_action_fields(...)`
- `resolve_buy_signal_audit_funnel_stage(...)`

Keep the engine append method as a thin facade:

- `_record_buy_signal_audit_event(...)`

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_buy_signal_audit_contract.py`

## 4. Execution Steps

### BAC-S1: Freeze file boundary and observable contract

Freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/buy_signal_audit_contract.py`
- `tests/unit/test_lowfreq_engine_v16_buy_signal_audit_contract.py`

Freeze the observable contract:

- `action_type` values remain unchanged
- `order_action` values remain unchanged
- `reserve_action` values remain unchanged
- `execution_status` values remain unchanged
- `execution_block_reason` values remain unchanged
- `funnel_stage` values remain unchanged

Completion check:

- no lifecycle logic or append-site changes are part of this slice

### BAC-S2: Implement the shared owner

Create:

- `neotrade3/decision_engine/buy_signal_audit_contract.py`

Move the pure mapping logic into:

- `normalize_execution_block_reason(...)`
- `resolve_execution_action_fields(...)`
- `resolve_buy_signal_audit_funnel_stage(...)`

Implementation rules:

- accept only normalized scalar inputs and optional snapshot context
- do not read config
- do not append audit rows
- do not mutate tracking/execution state

Completion check:

- the audit mapping contract can be understood independently from engine orchestration

### BAC-S3: Switch engine append helper to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the new owner helpers
- keep snapshot/payload normalization in the engine
- keep append behavior in the engine
- replace inline audit mapping with owner delegation

Do not change:

- tracking/execution lifecycle behavior
- audit list storage location
- non-contract audit fields

Completion check:

- the engine keeps `_record_buy_signal_audit_event(...)` but no longer owns the pure mapping rules inline

### BAC-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_buy_signal_audit_contract.py`

Minimum owner cases:

- blocked reason aliases normalize correctly
- `buy_executed` in reserved queue emits reserve release
- `buy_executed` outside reserved queue emits empty reserve action
- `reservation_created` emits reserved fields
- `reservation_expired` emits expired fields
- funnel stage mapping matches current event semantics

Completion check:

- the audit mapping contract has direct focused coverage

### BAC-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_buy_signal_audit_contract.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/buy_signal_audit_contract.py tests/unit/test_lowfreq_engine_v16_buy_signal_audit_contract.py`

Completion check:

- owner tests pass
- nearby convergence tests pass
- syntax validation passes

### BAC-S6: Narrow commit

For the implementation commit, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/buy_signal_audit_contract.py`
- `tests/unit/test_lowfreq_engine_v16_buy_signal_audit_contract.py`

Must exclude:

- API files
- report files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally broadening into audit append behavior or lifecycle orchestration

Guard:

- keep row append and source-layer selection in the engine

Risk 2:

- silently drifting emitted field strings that convergence tests rely on

Guard:

- preserve strings exactly
- verify direct owner contract plus convergence tests

## 6. Success Criteria

This slice is complete when:

- the buy-signal audit mapping kernel has one shared owner
- the engine no longer owns the pure mapping rules inline
- emitted audit fields remain unchanged
- owner-focused tests pass
- nearby convergence tests pass
- syntax verification passes
