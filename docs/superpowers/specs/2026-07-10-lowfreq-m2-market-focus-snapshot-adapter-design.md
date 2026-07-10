# Lowfreq M2 Market Focus Snapshot Adapter Design

Date: 2026-07-10

## 1. Goal

This design only covers the next narrow slice after `global selector` inside `E4: M2 legacy recognition zone`.

This slice only freezes:

- `_market_focus_snapshot()`

The goal is to:

- extract the engine-owned `market focus snapshot` evidence adapter into a narrow `cycle_intelligence` owner module
- keep the boundary limited to `M2 focus evidence assembly`, not orchestration or `M3` contracts
- preserve the current injected usage from `passes_core_focus_gate(...)`
- add owner-focused coverage for the real snapshot implementation instead of relying only on tests that stub the loader

This design is not:

- a `generate_buy_signals()` orchestration rewrite
- a change to `passes_core_focus_gate(...)` contract semantics
- a rewrite of `_weekly_returns_view()`
- a shared utility merge between engine and `apps/api/main.py`
- a broad market-intelligence refactor

## 2. Scope

Included:

- [_market_focus_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1285-L1487) ownership extraction
- the helper cluster that currently exists only to support that snapshot path:
  - [_ts_code_for_stock_code](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L820-L827)
  - [_match_market_keywords](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L830-L848)
  - [_market_ai_keywords](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L851-L879)
  - [_market_kshape_up_keywords](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L882-L897)
  - [_market_kshape_down_keywords](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L900-L924)
  - [_market_head_broker_names](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L927-L934)
  - [_table_has_rows](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L944-L954)
  - [_load_stock_concepts_cache](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L956-L1019)
  - [_load_penetration_keywords](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1021-L1044)
- consumer compatibility for:
  - [passes_core_focus_gate](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/legacy_recognition.py#L41-L90)
  - the selector facades that inject `market_focus_snapshot_loader`

Excluded:

- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2743-L2880)
- [_decorate_signal_with_phase1_contracts](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1209-L1283)
- [_weekly_returns_view](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2077-L2096)
- `apps/api/main.py` duplicate market helper cleanup
- any changes to formal-front payloads or `M3 nucleus`

## 3. Existing Context

Current repository evidence shows six important facts:

- `_market_focus_snapshot()` remains fully owned by the engine and has not yet been moved into `cycle_intelligence`:
  - [lowfreq_engine_v16_advanced.py:L1285-L1487](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1285-L1487)
- it is already treated as an injected evidence adapter by the selector layer, not as orchestration:
  - [get_sector_candidates facade](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2628-L2670)
  - [get_global_candidates facade](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2672-L2712)
- `passes_core_focus_gate(...)` consumes `market_focus_snapshot_loader` as an external dependency and does not need to know engine internals:
  - [legacy_recognition.py:L41-L90](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/legacy_recognition.py#L41-L90)
- the existing focus-gate tests only verify the gate contract by stubbing the loader and therefore do not cover the real snapshot implementation:
  - [test_lowfreq_engine_v16_focus_gate.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_focus_gate.py)
- `_market_focus_snapshot()` is the only engine consumer of its helper cluster, which means the helper set can move together without dragging unrelated runtime behavior:
  - [_load_stock_concepts_cache usage](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L956-L1019)
  - [_load_penetration_keywords usage](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1021-L1044)
- `generate_buy_signals()` is no longer a clean `M2` owner; it already spans selector consumption, dedupe, contract decoration, and formal-front attachment:
  - [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2743-L2880)
  - [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)

The problem is not that market focus evidence is unused. The problem is:

- the real `M2` focus evidence adapter is still embedded in the engine
- its helper cluster is also still embedded there
- focused tests cover the gate consumer, not the owner implementation

## 4. Approach Options

### Option A: Move the full market focus snapshot adapter plus its helper cluster into a new module (Recommended)

- create a narrow module under `neotrade3/cycle_intelligence/`
- move `_market_focus_snapshot()` and the helper set that exists only for it
- keep the engine method name as a thin facade

Pros:

- keeps the owner boundary coherent instead of splitting the adapter across two files
- aligns with the earlier selector extractions
- enables real owner-focused tests

Cons:

- requires passing cache/config state into the new module
- temporarily leaves similar helper code in `apps/api/main.py` untouched

### Option B: Move only `_market_focus_snapshot()` and keep helpers in the engine

- move the main method body but keep keyword/cache/config helpers where they are

Pros:

- smaller diff

Cons:

- leaves the owner split across engine and module
- does not fully solve the boundary problem

### Option C: Merge engine and API market helpers into one shared utility now

- extract a broader shared market helper package used by both engine and API

Pros:

- may reduce duplication longer term

Cons:

- crosses project layers and file families in one slice
- mixes owner extraction with cross-consumer deduplication
- exceeds the narrow boundary needed right now

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- stock concept lookup and keyword matching for market-theme focus evidence
- ETF / fund / index configuration evidence aggregation
- research / consensus / survey attention evidence aggregation
- focus-pass and focus-bonus decision output
- snapshot caching and cache-key shaping

These responsibilities should be treated as:

- `M2 market focus evidence adapter`

They should not be treated as:

- `M3` gate logic
- signal orchestration
- frontend or API payload shaping

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/cycle_intelligence/market_focus_snapshot.py`

This module should own:

- `build_market_focus_snapshot(...)`
- `ts_code_for_stock_code(...)`
- `match_market_keywords(...)`
- `market_ai_keywords(...)`
- `market_kshape_up_keywords(...)`
- `market_kshape_down_keywords(...)`
- `market_head_broker_names(...)`
- `table_exists(...)`
- `table_has_rows(...)`
- `load_stock_concepts_cache(...)`
- `load_penetration_keywords(...)`

It should not own:

- `passes_core_focus_gate(...)`
- `generate_buy_signals()`
- selector logic
- `apps/api/main.py` helper cleanup

### 5.3 Adapter Surface

Recommended public entrypoint:

- `build_market_focus_snapshot(...)`

Recommended inputs:

- `cursor`
- `code`
- `stock_name`
- `target_date`
- `market_focus_cache`
- `nonempty_table_cache`
- `stock_concepts_cache`
- `penetration_keywords_cache`
- `themes_snapshot_dir`
- `market_intelligence_config_dir`

Recommended output:

- `dict[str, Any]` with the same shape currently returned by `_market_focus_snapshot()`

Key design decision:

- the new module should not import engine state directly
- engine remains responsible for holding mutable caches and directory paths
- the new owner module receives those values explicitly and returns a plain snapshot dict

### 5.4 What Stays In Engine

After this slice, the engine should still keep:

- `_market_focus_snapshot()` method name, as a compatibility facade
- cache attributes:
  - `_market_focus_cache`
  - `_nonempty_table_cache`
  - `_stock_concepts_cache`
  - `_penetration_keywords_cache`
- directory attributes:
  - `_themes_snapshot_dir`
  - `_market_intelligence_config_dir`
- `passes_core_focus_gate(...)` consumer injection sites

Reason:

- this slice only extracts ownership, not engine object layout
- existing tests and consumers can continue calling `engine._market_focus_snapshot(...)`

### 5.5 Relationship With Other Remaining Code

This slice must stay separate from two nearby areas:

- `generate_buy_signals()`
  - already spans selector consumption, dedupe, decoration, and formal-front attachment
  - no longer qualifies as the next narrow `M2` extraction
- `_weekly_returns_view()`
  - is still a valid small adapter, but materially lower-value than the market-focus adapter because it has a smaller helper surface and lower boundary payoff

### 5.6 Testing Strategy

This slice should add a new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_market_focus_snapshot.py`

It should directly protect at least:

- concept keyword matching into `ai_hits` / `hardtech_hits` / `down_hits`
- penetration keyword loading and `penetration_hits`
- ETF / fund / index evidence aggregation into `config_score`
- research / consensus / survey evidence aggregation into `attention_score`
- `focus_pass` / `focus_bonus` output semantics
- cache reuse behavior for repeated `(code, date)` calls

Existing consumer-level guard that should remain unchanged:

- [test_lowfreq_engine_v16_focus_gate.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_focus_gate.py)

That file should remain a gate consumer test, not become the owner carrier for the snapshot implementation.

### 5.7 Validation Baseline

After implementation, at minimum verify:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_market_focus_snapshot.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_focus_gate.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/market_focus_snapshot.py`

If the facade wiring touches selector injection behavior, also re-run:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

## 6. Risks And Guards

Risk 1:

- accidentally treating `generate_buy_signals()` as the next owner slice

Guard:

- this slice only touches `_market_focus_snapshot()` and its helper cluster

Risk 2:

- moving only the facade and leaving half the helper logic behind

Guard:

- move the whole helper cluster that is uniquely owned by the snapshot path

Risk 3:

- expanding into `apps/api/main.py` duplication cleanup

Guard:

- keep API duplication explicitly out of scope for this slice

Risk 4:

- changing `passes_core_focus_gate(...)` semantics while moving the adapter

Guard:

- keep the gate untouched and preserve the snapshot output contract

## 7. Success Criteria

This slice is successful when:

- the market-focus evidence adapter is owned by `cycle_intelligence`
- engine keeps only a thin `_market_focus_snapshot()` facade
- current gate consumers keep working unchanged
- a new focused test covers the real snapshot implementation
- `generate_buy_signals()` and `M3 nucleus` code remain untouched

## 8. Commit Boundary

The design commit should include only:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-market-focus-snapshot-adapter-design.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- any other workspace changes
