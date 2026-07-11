Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution report signal snapshot contract extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Signal Snapshot Design

Date: 2026-07-11

## 1. Goal

This design covers the next narrow slice after the attribution execution audit reason extraction.

This slice freezes only the pure signal snapshot assembler that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L254-L328)
  - `_signal_layer_snapshot(...)`

The goal is to:

- move the report-side signal snapshot assembler into one analysis owner
- keep `AuditContext` and report orchestration in the script
- preserve current candidate/entry split and summary fields exactly
- add direct owner-focused coverage while keeping a nearby consumer guard

This design is not:

- a rewrite of `AuditContext`
- a rewrite of `project_lowfreq_formal_front(...)`
- a rewrite of signal generation in the engine
- a rewrite of report row assembly

Project-phase note:

- domain: `top200 attribution report signal snapshot`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- raw signal payload normalization into `candidate_signals`, `entry_signals`, and `signal_summary`
- formal-front priority override for `entry_ready` and `soft_retained`
- default summary counts
- reuse of existing `decision_engine` projection helper
- owner-focused tests for shape and priority behavior

Excluded:

- changes to `generate_buy_signals(...)`
- changes to `AuditContext` caching rules
- changes to report output schema
- changes to engine/API contracts

## 3. Existing Context

Current repository evidence shows:

- the script still owns one self-contained snapshot assembler:
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L254-L328)
- the formal-front projection kernel is already centralized elsewhere:
  - [projections.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/projections.py#L8-L61)
- there is already a dedicated focused test carrier around the current script helper:
  - [test_lowfreq_attribution_signal_snapshot.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_signal_snapshot.py)

The problem is:

- the snapshot assembler is still embedded in the report script
- the helper is pure report-consumer assembly over already-produced signal payloads
- the helper reuses a producer-side projection helper, but its own candidate/entry split belongs to report consumption

## 4. Approach Options

### Option A: Move only `_signal_layer_snapshot(...)` into a dedicated analysis owner and keep `AuditContext` as a thin consumer (Recommended)

- add one analysis module for the snapshot contract
- reuse `project_lowfreq_formal_front(...)`
- keep the script responsible only for calling the owner

Pros:

- isolates a real consumer-side contract kernel with minimal risk
- keeps producer projection and consumer assembly properly separated
- preserves current `AuditContext` shape

Cons:

- the script still keeps the surrounding caching/orchestration code

### Option B: Move `AuditContext.signal_snapshot(...)` and surrounding cache behavior into the owner

Pros:

- removes more script code

Cons:

- broadens into orchestration and cache lifecycle
- increases regression surface

### Option C: Move the helper into `decision_engine`

Pros:

- keeps more signal-related code near engine artifacts

Cons:

- this helper assembles a report-consumer snapshot, not a producer kernel
- would blur the owner boundary already established by `project_lowfreq_formal_front(...)`

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Create one dedicated report-side owner:

- `neotrade3/analysis/attribution_signal_snapshot.py`

Recommended function:

- `build_attribution_signal_snapshot(raw: Any) -> dict[str, Any]`

Why create a new file instead of extending `attribution_reasoning.py`:

- this helper is a snapshot assembler, not a reason-text selector
- it is materially larger than the tiny wording contracts already living in `attribution_reasoning.py`
- a dedicated file keeps the contract discoverable and avoids overloading the reasoning owner

### 5.2 Script Boundary

The script should keep:

- `AuditContext.signal_snapshot(...)` cache ownership
- the call to `engine.generate_buy_signals(...)`
- downstream consumers of the snapshot

The script should no longer own:

- `_signal_layer_snapshot(...)` assembly logic
- local nested helper logic for formal-front priority overrides

### 5.3 Behavior Preservation Rules

This slice must preserve current semantics exactly:

- only accept dict payloads
- read `entry_signals` only from a list
- default `candidate_signals` source to `entry_signals` only when `candidate_signals` is not a list
- ignore legacy `buy_signals` payloads that do not populate `entry_signals`
- attach `formal_front` only when `project_lowfreq_formal_front(...)` returns a dict
- if formal-front entry is actionable/ready, force `candidate_tier = "entry_ready"`
- else if tracking is `tracking` or identify is `identified`, force `candidate_tier = "soft_retained"`
- set `entry_ready` to the formal-front-derived boolean
- preserve default `candidate_count`, `entry_count`, and `soft_retained_count`

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_signal_snapshot_owner.py`

Minimum owner cases:

- candidate/entry split and summary defaults
- formal-front priority override to `entry_ready`
- legacy `buy_signals` ignored when `entry_signals` is absent

Keep and re-run the nearby consumer guard:

- [test_lowfreq_attribution_signal_snapshot.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_signal_snapshot.py)

## 6. Risks and Guardrails

Main risk:

- broadening into `AuditContext` cache ownership or engine generation flow

Guardrail:

- move only the snapshot assembler

Secondary risk:

- drifting current `candidate_tier` / `entry_ready` override behavior

Guardrail:

- preserve current override rules exactly
- verify owner-focused tests plus the existing consumer guard

## 7. Implementation Outline

Planned steps:

1. add `neotrade3/analysis/attribution_signal_snapshot.py`
2. move `_signal_layer_snapshot(...)` logic there
3. switch the script helper into a thin wrapper
4. add owner-focused tests
5. run focused verification

## 8. Success Criteria

This slice is complete when:

- the signal snapshot contract has one analysis owner
- the report script no longer owns the assembly logic inline
- returned snapshot shape stays unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
