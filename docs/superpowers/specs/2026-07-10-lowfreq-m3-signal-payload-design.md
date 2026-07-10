# Lowfreq M3 Signal Payload Design

Date: 2026-07-10

## 1. Goal

This design covers only the next narrow slice after the `financial report retrieval` extraction.

This slice only freezes:

- `_build_signal_structure_payload()`

The goal is to:

- move the engine-owned signal payload assembly into a dedicated `M3` decision-engine owner
- keep the engine method as a thin compatibility facade for `generate_buy_signals()`
- preserve the current payload shape used by existing engine-facing and formal-front consumers
- add direct owner-focused coverage for the payload assembly contract

This design is not:

- a rewrite of `generate_buy_signals()`
- a rewrite of `get_market_sentiment()`
- a rewrite of candidate generation or deduplication
- a redesign of formal-front attachment
- a change to buy-score or resonance ranking rules beyond preserving the current sort behavior

Project-phase note:

- domain: `M3 decision payload`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- [_build_signal_structure_payload](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2165-L2192) ownership extraction
- one new `decision_engine` owner module for signal payload assembly
- engine facade preservation for current `generate_buy_signals()` consumers
- owner-focused tests for payload sorting, cloning, summary counts, and note propagation
- focused regression for:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)

Excluded:

- [get_market_sentiment](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1722-L1777)
- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2194-L2417) orchestration changes beyond preserving the current call site
- formal-front assembly and attachment logic
- candidate sourcing from hot-sector or global scans
- API/report-side consumers of `generate_buy_signals()`

## 3. Existing Context

Current repository evidence shows four important facts:

- the engine still owns `_build_signal_structure_payload()` as an internal helper that sorts `deduped_signals`, derives `entry_signals`, and emits the final payload shell:
  - [lowfreq_engine_v16_advanced.py:L2165-L2192](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2165-L2192)
- `generate_buy_signals()` consumes that helper internally and then continues with formal-front attachment:
  - [lowfreq_engine_v16_advanced.py:L2398-L2417](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2398-L2417)
- existing tests already assert the output contract through `generate_buy_signals()`:
  - [test_lowfreq_engine_v16_signal_convergence.py:L132-L252](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L252)
  - [test_lowfreq_engine_v16_formal_front.py:L147-L188](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py#L147-L188)
- the project already uses `decision_engine` for ownership that is neither M1 retrieval nor M2 recognition:
  - [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py)
  - [projections.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/projections.py)

The problem is not contract uncertainty. The problem is:

- the payload assembly owner is still embedded inside the engine monolith
- there is no standalone owner module for the final `buy/candidate/entry/summary` payload contract
- existing tests only protect the contract indirectly through `generate_buy_signals()`

## 4. Approach Options

### Option A: Extract one dedicated `decision_engine` owner module and keep engine as a thin facade (Recommended)

- create a dedicated module under `neotrade3/decision_engine/`
- move the real signal payload assembly there
- keep `_build_signal_structure_payload()` as the engine compatibility point

Pros:

- aligns ownership with `M3 decision payload`
- avoids mixing formal state assembly with raw signal output assembly
- preserves the current `generate_buy_signals()` consumer surface

Cons:

- adds one extra production file

### Option B: Move the helper into `decision_engine/assembler.py`

- reuse an existing `decision_engine` file
- place payload assembly next to formal state builders

Pros:

- smaller file-count diff

Cons:

- mixes formal state construction with final payload shell assembly
- weakens the physical boundary between state objects and final response payloads

### Option C: Keep production code unchanged and add tests only

- preserve the helper inside the engine
- add direct tests around engine methods

Pros:

- smallest code diff

Cons:

- does not reduce engine ownership
- leaves the payload contract without a standalone owner

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- sorting candidate payload rows by:
  - `buy_score`
  - `resonance`
- deriving `entry_signals` from `candidate_signals`
- cloning entry-ready rows for the `buy_signals` and `entry_signals` lists
- computing `signal_summary`
- emitting:
  - `date`
  - `capture_first_mode`
  - `market_filter_note`

These responsibilities should be treated as:

- `M3 final decision payload assembly`

They should not be treated as:

- candidate discovery
- signal deduplication
- formal-front enrichment
- market sentiment calculation

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/signal_payload.py`

This module should own:

- `build_signal_structure_payload(...)`

Recommended signature:

- `build_signal_structure_payload(*, deduped_signals: dict[str, dict[str, Any]], target_date: date, market_filter_note: str | None) -> dict[str, Any]`

This module should not own:

- DB access
- engine config reads
- formal object creation
- post-payload mutation

### 5.3 Engine Compatibility Surface

The engine should keep:

- `_build_signal_structure_payload()`

But its responsibility should shrink to:

- delegate directly to `build_signal_structure_payload(...)`
- return the resulting dict unchanged

This keeps the current internal call site unchanged:

- [lowfreq_engine_v16_advanced.py:L2403-L2407](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2403-L2407)

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- `candidate_signals` is `sorted(deduped_signals.values(), key=(buy_score, resonance), reverse=True)`
- `entry_signals` contains `dict(sig)` copies only for rows where `entry_ready` is truthy
- `buy_signals` remains `list(entry_signals)`
- `signal_summary` contains:
  - `candidate_count`
  - `entry_count`
  - `soft_retained_count`
- `soft_retained_count` remains based on `candidate_tier == "soft_retained"`
- `date` remains `target_date.isoformat()`
- `capture_first_mode` remains `True`
- `market_filter_note` is passed through unchanged

No semantic tightening is included in this slice. The purpose is owner relocation, not payload redesign.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_signal_payload.py`

This carrier should directly exercise `build_signal_structure_payload(...)` and cover at least:

- sort order by `buy_score` then `resonance`
- `entry_signals` and `buy_signals` only include `entry_ready` rows
- `entry_signals` rows are copies, not direct references
- `signal_summary` counts are correct
- `date` and `market_filter_note` are preserved

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
- [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)

## 6. Risks and Guardrails

Main risk:

- changing the observable payload order or copy semantics while relocating ownership

Guardrails:

- preserve the current sort key exactly
- preserve the `dict(sig)` cloning behavior for `entry_signals`
- keep `_build_signal_structure_payload()` present as a compatibility facade
- avoid touching `generate_buy_signals()` logic beyond the call-through
- avoid changing formal-front attachment in the same slice

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/decision_engine/signal_payload.py`
2. move the real payload assembly logic into `build_signal_structure_payload(...)`
3. convert engine helper into a thin facade
4. add `tests/unit/test_lowfreq_engine_v16_signal_payload.py`
5. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the real signal payload assembly owner lives outside `lowfreq_engine_v16_advanced.py`
- engine keeps only a thin `_build_signal_structure_payload()` facade
- existing `generate_buy_signals()` contract stays unchanged
- an owner-focused test directly protects the payload assembly owner
- signal convergence and formal-front consumer tests still pass
