Status: active
Owner: lowfreq / decision_engine
Scope: Narrow M3 buy-signal-audit contract extraction from the lowfreq engine
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Buy Signal Audit Contract Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the `position contract snapshot` extraction.

This slice freezes only the pure audit-contract mapping that still lives inline in:

- [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py)
  - `_normalize_execution_block_reason(...)`
  - `_execution_action_fields(...)`
  - the `funnel_stage` event mapping inside `_record_buy_signal_audit_event(...)`

The goal is to:

- move the dense buy-signal audit mapping contract into one shared owner
- keep audit-log append orchestration in the engine
- preserve current `action_type`, `order_action`, `reserve_action`, `execution_status`, `execution_block_reason`, and `funnel_stage` semantics unchanged
- add direct owner-focused coverage for the audit contract

This design is not:

- a rewrite of `_record_buy_signal_audit_event(...)`
- a rewrite of tracking or execution orchestration
- a rewrite of reservation lifecycle behavior
- a rewrite of API-side normalization helpers
- a rewrite of report-side attribution reasoning

Project-phase note:

- domain: `buy signal audit contract`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- execution block reason normalization
- event-to-action field mapping
- event-to-funnel-stage mapping
- one new shared owner module under `neotrade3/decision_engine/`
- owner-focused tests for audit contract outputs

Excluded:

- audit event append/write behavior
- tracking/execution state transitions
- reservation creation/release/expiry business logic
- API-side duplicate normalization cleanup
- attribution report wording logic

## 3. Existing Context

Current repository evidence shows:

- the engine still owns the pure audit mapping helpers:
  - [lowfreq_engine_v16_advanced.py:_normalize_execution_block_reason](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L803-L830)
  - [lowfreq_engine_v16_advanced.py:_execution_action_fields](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L837-L886)
- `_record_buy_signal_audit_event(...)` still owns the event-to-`funnel_stage` mapping inline:
  - [lowfreq_engine_v16_advanced.py:_record_buy_signal_audit_event](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2714-L2783)
- nearby convergence tests already lock the observable payload fields:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L676-L815)
- repository evidence also shows parallel consumption of normalized `execution_block_reason` in API/report layers, which confirms that this is a real contract surface, not just local cleanup:
  - [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L16630-L16677)
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L693-L700)

The problem is:

- the engine still owns a small but real audit contract kernel
- this kernel is pure and self-contained
- the kernel already has consumer-grade tests on the emitted audit rows

## 4. Approach Options

### Option A: Extract only the pure buy-signal audit contract mappings into one owner and keep audit append orchestration in the engine (Recommended)

- add a dedicated owner module under `neotrade3/decision_engine/`
- move:
  - execution block reason normalization
  - action field mapping
  - funnel stage mapping
- keep audit row assembly and append in the engine

Pros:

- isolates a real contract kernel without touching runtime behavior
- preserves current engine orchestration boundary
- fits the current narrow-slice discipline

Cons:

- API/report duplicate normalization remains for a later slice

### Option B: Extract the full audit event builder including row assembly

Pros:

- removes more inline code from the engine

Cons:

- broadens from pure mapping into append/orchestration
- increases regression surface unnecessarily

### Option C: Extract a cross-layer shared normalization used by engine and API now

Pros:

- addresses duplication more aggressively

Cons:

- touches API and possibly report-side consumers
- broadens the blast radius beyond the narrowest stable cut

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own only the pure buy-signal audit contract mapping:

- map raw blocked reasons to normalized `execution_block_reason`
- map event type plus snapshot context to:
  - `action_type`
  - `order_action`
  - `reserve_action`
  - `execution_status`
- map event type to `funnel_stage`

This slice should not own:

- audit row append behavior
- source layer selection
- queue name/position delta/near-high flag copying
- tracking or execution lifecycle decisions

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/buy_signal_audit_contract.py`

Recommended functions:

- `normalize_execution_block_reason(...)`
- `resolve_execution_action_fields(...)`
- `resolve_buy_signal_audit_funnel_stage(...)`

Why keep them together:

- they are one observable contract family
- they are consumed together inside `_record_buy_signal_audit_event(...)`
- grouping them prevents scattering tiny audit mappings across multiple owners

### 5.3 Engine Facade Boundary

The engine should keep:

- `_record_buy_signal_audit_event(...)`

But with a narrower role:

- identify tracking vs execution source layer
- normalize payload/snapshot inputs
- delegate contract mapping to the new owner
- append the final audit row

The engine should no longer own:

- blocked-reason normalization rules
- event-to-action-field mapping
- event-to-funnel-stage mapping

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- tracking events:
  - `tracking_started`
  - `tracking_promoted_to_entry`
  - `tracking_dropped`
  still map to empty action fields and `execution_status=tracking`
- `reservation_created` still maps to:
  - `action_type=reserve`
  - `order_action=block`
  - `reserve_action=reserve`
  - `execution_status=reserved`
- `reservation_released_into_buy` still maps to:
  - `action_type=buy`
  - `order_action=buy`
  - `reserve_action=release`
  - `execution_status=executed`
- `buy_executed` still maps to:
  - `action_type=buy`
  - `order_action=buy`
  - `reserve_action=release` only when `queue_name == reserved`
- `reservation_expired` still maps to:
  - `action_type=block`
  - `order_action=block`
  - `reserve_action=expire`
  - `execution_status=expired`
- all other execution-side events still fall back to blocked fields
- blocked reason normalization remains:
  - full-book aliases -> `positions_full`
  - cash aliases -> `cash_insufficient`
  - reservation-expired aliases -> `entry_window_missed`
  - conflict alias -> `conflict_with_exit`
  - execution-rule aliases -> `execution_rule_blocked`
  - otherwise passthrough
- funnel stage mapping remains:
  - `tracking_started -> candidate_detected`
  - `tracking_promoted_to_entry -> entry_ready`
  - `tracking_dropped -> expired`
  - `reservation_created -> reserved`
  - `reservation_expired -> expired`
  - `reservation_released_into_buy -> released`
  - fallback -> `blocked`

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_buy_signal_audit_contract.py`

Minimum owner cases:

- blocked reason aliases normalize correctly
- `buy_executed` in reserved queue emits reserve release
- `buy_executed` outside reserved queue emits empty reserve action
- `reservation_created` emits reserved action fields
- `reservation_expired` emits expired action fields
- funnel stage mapping matches current event semantics

Keep and re-run nearby consumer guard:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L676-L815)

## 6. Risks and Guardrails

Main risk:

- accidentally broadening into audit row assembly or execution lifecycle behavior

Guardrail:

- keep `_record_buy_signal_audit_event(...)` as the only append site
- extract only pure mapping helpers

Secondary risk:

- drifting emitted bucket strings that current convergence tests rely on

Guardrail:

- preserve strings exactly
- verify direct owner contract plus convergence test

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/decision_engine/buy_signal_audit_contract.py`
2. move the pure audit mapping helpers there
3. turn `_record_buy_signal_audit_event(...)` into a thinner facade
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the buy-signal audit mapping kernel has one shared owner
- the engine no longer owns the pure mapping rules inline
- emitted audit fields remain unchanged
- owner-focused tests pass
- nearby convergence tests pass
- syntax verification passes
