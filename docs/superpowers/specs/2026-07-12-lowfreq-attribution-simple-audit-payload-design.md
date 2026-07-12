Status: active
Owner: lowfreq / analysis
Scope: Narrow top200 attribution simple daily-audit envelope extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Simple Audit Payload Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the daily signal-audit payload extraction.

This slice freezes only the remaining simple return payloads inside:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - `market_filtered`
  - `sector_seed_miss`
  - `sector_candidate_filtered`
  - `score_below_threshold`
  - `follower_filtered`
  - `resonance_filtered`
  - `sector_candidate_not_selected`
  - `global_seed_miss`
  - `global_candidate_filtered`
  - `global_follower_filtered`
  - `global_resonance_filtered`
  - `global_wave_filtered`
  - `global_score_filtered`
  - `global_cap_filtered`

The goal is to:

- move the repeated `date/stage/reason` envelope assembly into an analysis owner
- keep `_audit_daily_reason(...)` responsible for branch ordering, threshold math, and reason-string construction
- preserve all current stage names and reason texts exactly
- continue shrinking the script toward a thin consumer without broadening into full audit orchestration

This design is not:

- a rewrite of `_audit_daily_reason(...)` as a whole
- a rewrite of any market / sector / global filter condition
- a rewrite of the previously extracted signal-hit payload builders
- a rewrite of reasoning priority or aggregate consumers

Project-phase note:

- domain: `top200 attribution simple daily-audit payload`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the repeated simple `date/stage/reason` envelope builder
- switching the simple return sites in `_audit_daily_reason(...)` to that owner
- preserving all branch order and all existing reason-string formatting at each call site
- adding owner-focused tests for the simple envelope contract

Excluded:

- any change to the order of `market_filter -> entry_signal -> candidate_signal -> sector/global`
- any extraction of threshold calculations, role checks, resonance checks, or wave checks
- any change to `build_entry_signal_selected_audit(...)` or `build_candidate_signal_selected_audit(...)`
- any change to `resolve_not_picked_primary_reason(...)` stage semantics

## 3. Existing Context

Current repository evidence shows:

- `_audit_daily_reason(...)` now has only two kinds of return payloads:
  - rich signal-hit payloads already moved to the owner:
    - [generate_lowfreq_top200_attribution_report.py:L457-L465](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L457-L465)
    - [attribution_daily_audit_payload.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_daily_audit_payload.py)
  - repeated simple `date/stage/reason` envelopes still inline:
    - [generate_lowfreq_top200_attribution_report.py:L449-L564](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L449-L564)
- existing tests anchor several simple-stage observables and their downstream meaning:
  - [test_lowfreq_attribution_reasoning.py:L146-L192](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py#L146-L192)
  - [test_lowfreq_attribution_not_picked_primary_reason.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_not_picked_primary_reason.py)

The current problem is:

- the remaining inline payloads are no longer decision-rich, but they still duplicate the same envelope assembly many times
- their only stable contract is `date/stage/reason`
- leaving them inline keeps the script owning a repeated projection concern that already has a natural M3 owner shape

## 4. Approach Options

### Option A: Add one explicit builder for simple audit envelopes and reuse it across all simple stage returns (Recommended)

- keep all reason computation in the script
- move only the final `{"date", "stage", "reason"}` assembly into a shared owner

Pros:

- smallest slice that removes the remaining repeated envelope shape
- keeps stage names explicit at each call site
- preserves the current decision flow and per-branch message construction

Cons:

- the script still owns all conditional logic and message interpolation

### Option B: Add one builder per simple stage

Pros:

- each stage gets its own dedicated symbol

Cons:

- very low information density
- spreads identical envelope logic across many tiny wrappers
- adds symbol noise without reducing more behavior than Option A

### Option C: Extract the rest of `_audit_daily_reason(...)` into a full owner

Pros:

- removes more script logic at once

Cons:

- too broad for one narrow slice
- mixes branch ordering, thresholds, and envelope projection

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Extend the existing owner:

- `neotrade3/analysis/attribution_daily_audit_payload.py`

Recommended new public function:

- `build_simple_stage_audit(*, audit_date: str, stage: str, reason: str) -> dict[str, Any]`

Why extend the existing file:

- the file already owns daily-audit payload projection
- these simple returns are the same audit-event family as the previously extracted signal-hit payloads
- this keeps all daily-audit payload owners co-located without mixing them into reasoning or snapshot owners

### 5.2 Script Boundary

The script should keep:

- evaluating every `if` condition
- calculating `required` thresholds
- formatting dynamic reason strings such as market score, buy-score gaps, resonance gaps, and wave-phase text
- deciding which stage fires first

The script should stop owning:

- the repeated final assembly of `{"date": ..., "stage": ..., "reason": ...}`

### 5.3 Contract Freeze

The new simple envelope builder must always return exactly:

- `date`
- `stage`
- `reason`

It must preserve current coercion rules:

- `date` -> `str(... or "")`
- `stage` -> `str(... or "")`
- `reason` -> `str(... or "")`

It must not:

- add `signal`
- add any extra metadata
- reinterpret stage names
- change any reason text

### 5.4 Testing Strategy

Keep the existing script-focused tests:

- [test_lowfreq_attribution_reasoning.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_attribution_reasoning.py)

Add owner-focused tests in a new carrier:

- `tests/unit/test_lowfreq_attribution_daily_simple_payload.py`

Minimum owner cases:

- simple envelope preserves current `date/stage/reason` fields
- simple envelope keeps empty-string fallback behavior

Keep one script-focused regression for a dynamic branch:

- `global_wave_filtered` stays unchanged through `_audit_daily_reason(...)`

## 6. Risks and Guardrails

Main risk:

- accidentally broadening the slice from envelope projection into conditional extraction

Guardrail:

- only replace returned dict literals with `build_simple_stage_audit(...)`

Secondary risk:

- silently changing reason strings while deduplicating code

Guardrail:

- keep all reason construction at the call site and add owner-focused tests that freeze only the envelope contract

## 7. Implementation Outline

Planned steps:

1. add `build_simple_stage_audit(...)` to the daily-audit payload owner
2. switch the simple return sites in `_audit_daily_reason(...)` to the new builder
3. add owner-focused tests for the simple envelope contract
4. run focused verification and syntax checks

## 8. Success Criteria

This slice is complete when:

- the remaining simple daily-audit envelopes are owned outside the script
- `_audit_daily_reason(...)` keeps the same branch ordering and threshold logic
- stage names and reason texts remain unchanged
- owner-focused tests pass
- syntax verification passes
