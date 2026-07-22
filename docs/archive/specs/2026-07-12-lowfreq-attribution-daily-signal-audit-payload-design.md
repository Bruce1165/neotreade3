Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution daily signal-audit payload extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Daily Signal-Audit Payload Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the segment-failed row extraction.

This slice freezes only the two heaviest return payloads inside:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `entry_signal_selected`
  - `candidate_signal_selected`

The goal is to:

- move the nested `stage/reason/signal` payload assembly for the two signal-hit branches into an analysis owner
- keep `_audit_daily_reason(...)` responsible for branch ordering and decision flow
- preserve all current field names, coercions, and semantics
- continue shrinking the script toward a thin consumer without broadening into full audit orchestration

This design is not:

- a rewrite of `_audit_daily_reason(...)` as a whole
- a rewrite of market / sector / global filter logic
- a rewrite of `build_attribution_signal_snapshot(...)`
- a rewrite of reason-ranking or aggregate logic

Project-phase note:

- domain: `top200 attribution daily signal-audit payload`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the `entry_signal_selected` payload builder
- extracting the `candidate_signal_selected` payload builder
- preserving the surrounding branch order in `_audit_daily_reason(...)`
- adding owner-focused tests for the two payload builders

Excluded:

- any change to the order of `market_filter -> entry_signal -> candidate_signal -> sector/global`
- any extraction of the simpler one-line stage returns
- any change to `ctx.entry_signals(...)` or `ctx.candidate_signals(...)`
- any re-projection of raw signal snapshots

## 3. Existing Context

Current repository evidence shows:

- `_audit_daily_reason(...)` still owns the full decision chain plus all return payload assembly:
  - [generate_lowfreq_top200_attribution_report.py:L436-L583](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L436-L583)
- among all branches, the two signal-hit returns are the only ones with nested `signal` payloads:
  - [generate_lowfreq_top200_attribution_report.py:L453-L484](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L453-L484)
- the script already consumes a separate signal snapshot owner upstream:
  - [generate_lowfreq_top200_attribution_report.py:L36](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L36)
  - [attribution_signal_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_signal_snapshot.py)
- existing script-focused tests already anchor the observable output of those branches:
  - [test_lowfreq_attribution_reasoning.py:L37-L143](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L37-L143)

The current problem is:

- the decision flow and the richest payload assembly are still entangled in one script-local function
- the two signal-hit returns are materially denser than the other simple stage returns
- extracting the whole function would be too broad, but leaving these payloads inline preserves the thickest remaining consumer contract

## 4. Approach Options

### Option A: Extract only the two signal-hit payload builders into a dedicated daily-audit payload owner (Recommended)

- keep branch ordering in `_audit_daily_reason(...)`
- move only payload assembly for:
  - `entry_signal_selected`
  - `candidate_signal_selected`

Pros:

- smallest slice that removes the densest nested payloads
- preserves all runtime decision flow in place
- creates a clean owner for later daily-audit payload extractions

Cons:

- some simple stage returns remain inline for now

### Option B: Extend `attribution_signal_snapshot.py` to also build daily-audit payloads

Pros:

- reuses an existing signal-related owner file

Cons:

- mixes snapshot normalization with audit-event envelope assembly
- blurs owner responsibility

### Option C: Extract the entire `_audit_daily_reason(...)` function

Pros:

- removes more script logic at once

Cons:

- too broad for one narrow slice
- mixes decision ordering, threshold logic, and payload builders

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add a dedicated owner for the two signal-hit daily-audit payloads:

- `neotrade3/analysis/attribution_daily_audit_payload.py`

Recommended public functions:

- `build_entry_signal_selected_audit(...) -> dict[str, Any]`
- `build_candidate_signal_selected_audit(...) -> dict[str, Any]`

Why a new file:

- these payloads are not raw signal snapshots
- these payloads are not aggregate summaries or reasoning decisions
- they are audit-event envelopes with their own stable `stage/reason/signal` contract

### 5.2 Script Boundary

The script should keep:

- loading market / entry / candidate / sector / global context
- deciding which branch fires first
- selecting `sig` from entry or candidate maps
- all threshold and filter computations outside the two extracted branches

The script should stop owning:

- the inline dict for `entry_signal_selected`
- the inline dict for `candidate_signal_selected`

### 5.3 Contract Freeze

The extracted entry-signal payload must remain exactly:

- `date`
- `stage: "entry_signal_selected"`
- `reason: "进入正式建仓池"`
- `signal.buy_score`
- `signal.role`
- `signal.wave_phase`
- `signal.candidate_tier`
- `signal.reasons`

The extracted candidate-signal payload must remain exactly:

- `date`
- `stage: "candidate_signal_selected"`
- `reason: "进入候选池，但未进入正式建仓池"`
- `signal.buy_score`
- `signal.role`
- `signal.wave_phase`
- `signal.candidate_tier`
- `signal.entry_ready`
- `signal.reasons`

Coercion rules must remain unchanged:

- numeric score -> `float(...)`
- string fields -> `str(... or "")`
- boolean `entry_ready` -> `bool(...)`
- reasons list -> `list(... or [])`

### 5.4 Testing Strategy

Keep the existing script-focused tests:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

Add owner-focused tests in a new carrier:

- `tests/unit/test_lowfreq_attribution_daily_audit_payload.py`

Minimum owner cases:

- entry-signal payload projects current field set and coercions
- candidate-signal payload projects current field set and coercions
- candidate-signal payload keeps `entry_ready` independent and preserves `candidate_tier`

## 6. Risks and Guardrails

Main risk:

- accidentally broadening from payload extraction into decision-flow extraction

Guardrail:

- only replace the two returned dicts with owner calls

Secondary risk:

- silently changing the nested `signal` shape

Guardrail:

- freeze the exact current field set and coercions with owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add the daily signal-audit payload owner with two builder functions
2. switch the two script return sites to use the owner
3. add owner-focused tests
4. run focused verification and syntax checks

## 8. Success Criteria

This slice is complete when:

- the two signal-hit payloads are owned outside the script
- `_audit_daily_reason(...)` still keeps the same branch ordering
- all nested `signal` fields remain unchanged
- owner-focused tests pass
- syntax verification passes
