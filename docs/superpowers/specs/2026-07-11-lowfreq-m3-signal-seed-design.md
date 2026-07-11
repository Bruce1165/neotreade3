# Lowfreq M3 Signal Seed Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `formal front payload finalize` extraction.

This slice only freezes:

- the two `StockCandidate -> signal seed dict` build blocks inside `generate_buy_signals()`

The goal is to:

- move the duplicated signal-seed shaping logic into a dedicated `M3` owner
- keep the engine-side loops and `_decorate_signal_with_phase1_contracts(...)` call site stable
- preserve the current field mapping, reason assembly, and cross-sector soft-penalty semantics exactly
- add direct owner-focused coverage for the seed-building contract

This design is not:

- a rewrite of `generate_buy_signals()`
- a rewrite of `_decorate_signal_with_phase1_contracts(...)`
- a rewrite of `get_sector_candidates()` or `get_global_candidates()`
- a redesign of market filtering, dedup, payload assembly, or formal-front handling

Project-phase note:

- domain: `M3 decision refinement`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- the hot-sector candidate seed dict block inside [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2213-L2244)
- the cross-sector candidate seed dict block inside [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2263-L2291)
- one new `decision_engine` owner module for signal seed shaping
- engine/internal call-site preservation
- owner-focused tests for field mapping, reason passthrough, market-filter append, and cross-sector wave soft-penalty
- focused regression for:
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)

Excluded:

- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2194-L2313) loop/orchestration changes beyond preserving the current call points
- [_decorate_signal_with_phase1_contracts](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L995-L1069)
- signal deduplication
- signal payload assembly
- formal-front payload build/finalize
- hot-sector / global selector ownership itself

## 3. Existing Context

Current repository evidence shows four important facts:

- the engine still owns two near-parallel seed dict build blocks:
  - [lowfreq_engine_v16_advanced.py:L2221-L2244](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2221-L2244)
  - [lowfreq_engine_v16_advanced.py:L2263-L2291](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2263-L2291)
- both blocks project the same core `StockCandidate` fields into a signal dict:
  - `code`, `name`, `sector`, `buy_score`, `market_cap_yi`, `wave_phase`, `role`, `pe`, `profit_growth`, `resonance`, `cup_handle_ok`, `signal_source`
- the real M3 enrichment still happens afterward in one stable engine helper:
  - [_decorate_signal_with_phase1_contracts](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L995-L1069)
- current tests already protect downstream behavior through `generate_buy_signals()`:
  - [test_lowfreq_engine_v16_signal_convergence.py:L132-L299](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L299)
  - [test_lowfreq_engine_v16_formal_front.py:L126-L188](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py#L126-L188)

The problem is not uncertainty about behavior. The problem is:

- the seed-shaping owner is still embedded in the engine monolith
- there is duplicated field mapping between hot-sector and cross-sector paths
- downstream tests do not directly pin the pre-decoration seed contract

## 4. Approach Options

### Option A: Extract a dedicated `decision_engine` seed owner module and keep engine loops stable (Recommended)

- create a small owner module under `neotrade3/decision_engine/`
- move the real seed-building logic there
- let engine loops only call the owner and then pass the result into `_decorate_signal_with_phase1_contracts(...)`

Pros:

- aligns ownership with M3 signal shaping
- removes duplicated projection logic without touching loop orchestration
- preserves the existing decorate/dedup/payload chain

Cons:

- adds one extra production file

### Option B: Inline both paths into one engine helper method

- keep ownership inside `lowfreq_engine_v16_advanced.py`
- reduce duplication with a local private method only

Pros:

- smallest physical diff

Cons:

- does not reduce engine ownership
- still leaves the owner inside the monolith

### Option C: Move the logic into selectors

- let hot-sector and global selectors emit fully shaped signal dicts
- skip engine-side seed building

Pros:

- moves signal shaping upstream

Cons:

- crosses an ownership boundary into M2 selectors
- broadens the slice far beyond current evidence

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- projecting core candidate fields into a signal seed dict
- building `reasons` for hot-sector candidates
- building `reasons` and `soft_flags` for cross-sector candidates
- appending `market_filter_note` when provided
- appending the cross-sector wave soft-penalty when current config requires it

These responsibilities should be treated as:

- `M3 signal seed shaping`

They should not be treated as:

- candidate discovery
- phase1 decoration
- deduplication
- payload projection
- formal-front enrichment

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/signal_seed.py`

This module should own:

- `build_hot_sector_signal_seed(...)`
- `build_cross_sector_signal_seed(...)`

Recommended signatures:

- `build_hot_sector_signal_seed(candidate: Any, *, market_filter_note: str | None) -> dict[str, Any]`
- `build_cross_sector_signal_seed(candidate: Any, *, market_filter_note: str | None, wave3_only: bool, allowed_waves: set[str]) -> dict[str, Any]`

This module should not own:

- engine config reads beyond explicit function parameters
- loops over sectors/global candidates
- calls to `_decorate_signal_with_phase1_contracts(...)`

### 5.3 Engine Compatibility Surface

The engine should keep the current loops and `_decorate_signal_with_phase1_contracts(...)` call points, but the real seed body should move out.

Recommended use:

- hot-sector loop:
  - call `build_hot_sector_signal_seed(...)`
  - pass the seed into `_decorate_signal_with_phase1_contracts(...)`
- cross-sector loop:
  - call `build_cross_sector_signal_seed(...)`
  - pass the seed into `_decorate_signal_with_phase1_contracts(...)`

This preserves the current downstream flow:

- candidate sourcing
- signal seed shaping
- phase1 decoration
- dedup
- payload assembly
- formal-front handling

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- hot-sector reasons start with `list(c.buy_reasons)`
- cross-sector reasons start with `["跨板块扫描"] + list(c.buy_reasons)`
- hot-sector `soft_flags` defaults to `list(getattr(c, "soft_flags", []) or [])`
- cross-sector `soft_flags` defaults to `list(getattr(c, "soft_flags", []) or [])`
- cross-sector wave soft-penalty triggers only when:
  - `wave3_only` is true
  - and `str(c.wave_phase) not in allowed_waves`
- in that case append:
  - reason: `"capture-first: 波段不符，降权保留"`
  - soft flag: `"wave_uncertain"`
- when `market_filter_note` is provided, append it to reasons
- preserve current field mapping and default `signal_source` values:
  - hot-sector: `"hot_sector"`
  - cross-sector: `"cross_sector"`

No semantic tightening is included in this slice. The purpose is owner relocation, not signal redesign.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`

This carrier should directly exercise the new seed owners and cover at least:

- hot-sector seed maps the expected fields
- hot-sector appends `market_filter_note`
- cross-sector seed adds the fixed `"跨板块扫描"` reason prefix
- cross-sector seed adds wave soft-penalty only when the current rule says so
- cross-sector seed preserves default `signal_source` and `cross_sector=True`

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
- [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)

## 6. Risks and Guardrails

Main risk:

- accidentally changing reasons/soft-flags ordering while moving the owner

Guardrails:

- preserve current reason prefix order exactly
- preserve current `soft_flags` append order exactly
- avoid changing `_decorate_signal_with_phase1_contracts(...)` in the same slice
- avoid moving candidate loops out of engine in the same slice

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/decision_engine/signal_seed.py`
2. move the hot-sector and cross-sector seed bodies into that module
3. switch `generate_buy_signals()` loops to call the owner module
4. add `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
5. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the real signal-seed owner lives outside `lowfreq_engine_v16_advanced.py`
- `generate_buy_signals()` keeps the same downstream behavior
- hot-sector and cross-sector seed contracts stay unchanged
- an owner-focused test directly protects the new seed owners
- downstream convergence/formal-front tests still pass
