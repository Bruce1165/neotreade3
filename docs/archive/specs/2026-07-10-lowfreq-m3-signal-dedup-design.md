# Lowfreq M3 Signal Dedup Design

Date: 2026-07-10

## 1. Goal

This design covers only the next narrow slice after the `signal payload owner` extraction.

This slice only freezes:

- the `raw_signals -> deduped` collapse inside `generate_buy_signals()`

The goal is to:

- move the engine-owned signal dedup logic into a dedicated `M3` decision-engine owner
- keep the current engine-side call site as a thin compatibility facade
- preserve the current dedup contract exactly
- add direct owner-focused coverage for the dedup rule set

This design is not:

- a rewrite of `generate_buy_signals()`
- a rewrite of `get_market_sentiment()`
- a redesign of candidate sourcing
- a redesign of signal payload assembly
- a broader “merge strategy” framework

Project-phase note:

- domain: `M3 decision refinement`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- the `deduped` build block inside [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2280-L2287)
- one new `decision_engine` owner module for signal dedup
- engine/internal call-site preservation
- owner-focused tests for blank-code skip, higher-score replacement, tie preservation, and clone semantics
- focused regression for:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

Excluded:

- [get_market_sentiment](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1722-L1777)
- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2194-L2417) orchestration changes beyond preserving the current dedup call point
- signal payload assembly
- formal-front assembly and attachment
- hot-sector or cross-sector candidate production
- API/report-side consumers

## 3. Existing Context

Current repository evidence shows four important facts:

- the engine still owns the full dedup rule block:
  - [lowfreq_engine_v16_advanced.py:L2280-L2287](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2280-L2287)
- the current logic is narrow and deterministic:
  - blank `code` rows are skipped
  - only one row per `code` survives
  - a row replaces the current survivor only when its `buy_score` is strictly greater
- the current output path immediately feeds the dedup result into the already-extracted payload owner:
  - [lowfreq_engine_v16_advanced.py:L2289-L2293](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2289-L2293)
- current tests protect the downstream contract only indirectly through `generate_buy_signals()`:
  - [test_lowfreq_engine_v16_signal_convergence.py:L132-L252](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L252)

The problem is not uncertainty about behavior. The problem is:

- the dedup owner is still embedded in the engine monolith
- the rule set has no standalone owner-focused carrier
- downstream tests do not directly pin the tie/replacement semantics

## 4. Approach Options

### Option A: Extract one dedicated `decision_engine` owner module and keep engine as a thin facade (Recommended)

- create a dedicated module under `neotrade3/decision_engine/`
- move the real dedup logic there
- keep the engine responsible only for calling that owner

Pros:

- aligns ownership with `M3` decision refinement
- preserves the narrow contract without inventing new abstractions
- keeps `generate_buy_signals()` stable

Cons:

- adds one extra production file

### Option B: Move the dedup helper into `signal_payload.py`

- reuse the just-created payload module
- let one module own both dedup and payload assembly

Pros:

- smaller file count

Cons:

- mixes two distinct steps:
  - signal survivor selection
  - final payload projection
- weakens the physical boundary between refinement and projection

### Option C: Keep production code unchanged and add tests only

- preserve the block inside the engine
- add direct tests around `generate_buy_signals()`

Pros:

- smallest code diff

Cons:

- does not reduce engine ownership
- still leaves the dedup contract without a standalone owner

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- normalizing `code` from each raw signal row
- skipping rows with blank normalized `code`
- selecting one survivor per `code`
- replacing the current survivor only when the new row has a strictly higher `buy_score`
- copying the winning row into the dedup result

These responsibilities should be treated as:

- `M3 signal survivor selection`

They should not be treated as:

- candidate discovery
- payload assembly
- formal-front enrichment
- score recalculation

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/signal_dedup.py`

This module should own:

- `dedupe_signals_by_code(...)`

Recommended signature:

- `dedupe_signals_by_code(raw_signals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]`

This module should not own:

- DB access
- engine config reads
- payload projection
- formal state attachment

### 5.3 Engine Compatibility Surface

The engine should keep a local compatibility point inside `generate_buy_signals()`, but the real dedup body should move out.

Recommended use:

- call `dedupe_signals_by_code(raw_signals)`
- pass the result unchanged into `_build_signal_structure_payload(...)`

This preserves the current downstream flow:

- dedup
- payload assembly
- formal-front attachment

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- iterate `raw_signals` in original order
- normalize `code` with `str(sig.get("code") or "").strip()`
- skip rows where normalized `code` is empty
- if a `code` has no current survivor, install `dict(sig)`
- if a `code` already has a survivor, replace it only when:
  - `float(sig.get("buy_score") or 0.0) > float(current.get("buy_score") or 0.0)`
- ties do not replace the current survivor because the comparison is strict `>`
- the stored survivor remains a copied `dict(sig)`

No semantic tightening is included in this slice. The purpose is owner relocation, not dedup redesign.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_signal_dedup.py`

This carrier should directly exercise `dedupe_signals_by_code(...)` and cover at least:

- blank-code rows are skipped
- a higher `buy_score` row replaces the current survivor
- an equal `buy_score` row does not replace the current survivor
- the stored survivor is a copy, not the original dict reference

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

## 6. Risks and Guardrails

Main risk:

- accidentally changing the current tie-handling semantics while extracting the owner

Guardrails:

- preserve the strict `>` replacement rule exactly
- preserve `dict(sig)` copy semantics
- avoid touching payload assembly and formal-front logic in the same slice
- avoid broadening the helper into a configurable dedup framework

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/decision_engine/signal_dedup.py`
2. move the real `raw_signals -> deduped` logic into `dedupe_signals_by_code(...)`
3. switch `generate_buy_signals()` to call the shared owner
4. add `tests/unit/test_lowfreq_engine_v16_signal_dedup.py`
5. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the real signal dedup owner lives outside `lowfreq_engine_v16_advanced.py`
- `generate_buy_signals()` keeps the same downstream behavior
- the strict higher-score replacement rule stays unchanged
- an owner-focused test directly protects the dedup contract
- downstream signal convergence tests still pass
