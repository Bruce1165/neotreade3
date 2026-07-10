# Lowfreq M2 Market Focus Snapshot Adapter Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-market-focus-snapshot-adapter-design.md`

## 1. Goal

This plan covers only the next narrow `E4: M2 legacy recognition zone` slice after the selector extractions.

This slice only handles:

- `_market_focus_snapshot()`

The goal is to:

- move the engine-owned market-focus evidence adapter into a dedicated `cycle_intelligence` owner module
- move the helper cluster that exists only to support that adapter
- keep the engine method name as a thin compatibility facade
- preserve the existing `passes_core_focus_gate(...)` injection contract
- add owner-focused tests for the real snapshot implementation

This slice does not:

- rewrite `generate_buy_signals()`
- change `passes_core_focus_gate(...)`
- change `_weekly_returns_view()`
- deduplicate market helper code with `apps/api/main.py`
- alter formal-front or `M3 nucleus` behavior

## 2. Starting Point

The current owner is still split entirely inside:

- `lowfreq_engine_v16_advanced.py`

The engine currently owns both:

- `_market_focus_snapshot()`
- the full helper cluster that supports concept matching, config loading, and table/cache probing

Existing consumer coverage exists here:

- `tests/unit/test_lowfreq_engine_v16_focus_gate.py`

But that file only stubs the snapshot loader, so the real adapter body still lacks a focused owner carrier.

## 3. Implementation Strategy

Use the same extraction pattern as the previous selector slices:

- add a new owner module:
  - `neotrade3/cycle_intelligence/market_focus_snapshot.py`
- move the real adapter body and its dedicated helpers into that module
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - holding caches
  - holding directory paths
  - calling the new owner module through a thin `_market_focus_snapshot()` facade
- add one new owner-focused test carrier:
  - `tests/unit/test_lowfreq_engine_v16_market_focus_snapshot.py`
- keep the existing focus-gate tests as consumer guards

## 4. Execution Steps

### E4-MF-S1: Freeze file boundary and contract

Before implementation, freeze the file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/market_focus_snapshot.py`
- `tests/unit/test_lowfreq_engine_v16_market_focus_snapshot.py`

Freeze the output contract of `_market_focus_snapshot()`:

- it still returns `dict[str, Any]`
- it still includes `focus_pass`
- it still includes `focus_bonus`
- it still includes the existing evidence keys used by `passes_core_focus_gate(...)`

Completion check:

- no consumer should need to change how it reads snapshot fields

### E4-MF-S2: Implement the new owner module

Create:

- `neotrade3/cycle_intelligence/market_focus_snapshot.py`

Move the owner logic into that module:

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

Implementation rules:

- the module must not import engine state directly
- mutable caches are passed in explicitly
- directory paths are passed in explicitly
- the module returns a plain snapshot dict

Completion check:

- the market-focus adapter can be understood independently from engine internals

### E4-MF-S3: Convert engine to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import `build_market_focus_snapshot(...)`
- keep `_market_focus_snapshot(...)` as the public compatibility method
- make that method only inject:
  - `cursor`
  - `code`
  - `stock_name`
  - `target_date`
  - `_market_focus_cache`
  - `_nonempty_table_cache`
  - `_stock_concepts_cache`
  - `_penetration_keywords_cache`
  - `_themes_snapshot_dir`
  - `_market_intelligence_config_dir`

Do not change:

- `passes_core_focus_gate(...)`
- `generate_buy_signals()`
- selector facades
- `apps/api/main.py`

Completion check:

- engine no longer holds the owner body of the market-focus snapshot adapter

### E4-MF-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_market_focus_snapshot.py`

Minimum owner cases:

- concept keyword matching populates `ai_hits`, `hardtech_hits`, and `down_hits`
- penetration keyword config loading populates `penetration_hits`
- ETF / fund / index evidence contributes to `config_score`
- research / consensus / survey evidence contributes to `attention_score`
- `focus_pass` and `focus_bonus` remain stable
- repeated `(code, target_date)` calls reuse the snapshot cache

Keep and re-run the existing consumer guard:

- `tests/unit/test_lowfreq_engine_v16_focus_gate.py`

Completion check:

- the real owner logic has a direct focused carrier
- the gate consumer still works unchanged

### E4-MF-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_market_focus_snapshot.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_focus_gate.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/market_focus_snapshot.py`

If facade wiring touches selector injection behavior, also run:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### E4-MF-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/market_focus_snapshot.py`
- `tests/unit/test_lowfreq_engine_v16_market_focus_snapshot.py`

Must exclude:

- `generate_buy_signals()` edits
- `_weekly_returns_view()` edits
- `apps/api/main.py`
- any selector module edits unless strictly required for compatibility
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- drifting into orchestration cleanup while touching nearby code

Guard:

- this slice only moves the market-focus snapshot adapter and its direct helpers

Risk 2:

- leaving half the helper cluster behind in the engine

Guard:

- move the helper set that is uniquely owned by the snapshot path together

Risk 3:

- changing focus-gate semantics while moving the adapter

Guard:

- treat `passes_core_focus_gate(...)` as a fixed consumer contract

Risk 4:

- expanding into cross-project deduplication with API helpers

Guard:

- keep `apps/api/main.py` explicitly out of scope

## 6. Success Criteria

This slice is complete when:

- the real market-focus snapshot owner lives in `cycle_intelligence`
- engine keeps only a thin `_market_focus_snapshot()` facade
- the output contract remains compatible with focus-gate consumers
- a focused owner test protects the real implementation
- no unrelated orchestration or API code is changed

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-market-focus-snapshot-adapter-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- any other workspace changes
