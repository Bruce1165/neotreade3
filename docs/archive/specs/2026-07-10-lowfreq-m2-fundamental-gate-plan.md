# Lowfreq M2 Fundamental Gate Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-fundamental-gate-design.md`

## 1. Goal

This plan covers only the next narrow `E4: M2 legacy recognition zone` slice after the `market focus snapshot adapter` extraction.

This slice only handles:

- `check_fundamentals()`

The goal is to:

- move the engine-owned fundamentals scoring rule into a dedicated `cycle_intelligence` owner module
- keep the engine method name as a thin compatibility facade
- preserve the current selector injection contract
- add owner-focused tests for the real scoring contract

This slice does not:

- rewrite `_get_fundamentals_batch()`
- rewrite `get_fundamentals()`
- rewrite `generate_buy_signals()`
- touch `get_market_sentiment()`
- change API or report consumers
- redesign any fundamentals thresholds or scoring semantics

## 2. Starting Point

The current owner still lives fully inside:

- `lowfreq_engine_v16_advanced.py`

The engine currently owns both:

- the `check_fundamentals()` rule body
- the threshold injection site via `self.MAX_PE`, `self.MIN_PROFIT_GROWTH`, and `self.MIN_ROE`

Existing consumer coverage exists here:

- `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

But those files only stub the scoring callable, so the real owner logic still lacks a focused direct carrier.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as the earlier E4 slices:

- add a new owner module:
  - `neotrade3/cycle_intelligence/fundamental_gate.py`
- move the real scoring logic into:
  - `score_fundamentals(...)`
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - holding thresholds
  - calling the new owner module through a thin `check_fundamentals()` facade
- add one new owner-focused test carrier:
  - `tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`
- keep the existing selector tests as consumer guards

## 4. Execution Steps

### E4-FG-S1: Freeze file boundary and contract

Before implementation, freeze the file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/fundamental_gate.py`
- `tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`

Freeze the output contract of `check_fundamentals()`:

- it still returns `tuple[bool, float, list[str]]`
- `passed` semantics remain unchanged
- `score` math remains unchanged
- reason strings remain unchanged

Completion check:

- no selector consumer should need to change how it calls or interprets fundamentals scoring

### E4-FG-S2: Implement the new owner module

Create:

- `neotrade3/cycle_intelligence/fundamental_gate.py`

Move the owner logic into that module:

- `score_fundamentals(...)`

Implementation rules:

- the module must not import engine state directly
- thresholds are passed in explicitly
- the module reads only the provided `fundamentals` dict
- the module returns the same `(passed, score, reasons)` shape as the current engine method

Completion check:

- the fundamentals gate can be understood independently from engine internals and database access

### E4-FG-S3: Convert engine to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import `score_fundamentals(...)`
- keep `check_fundamentals()` as the public compatibility method
- make that method only inject:
  - `fundamentals`
  - `self.MAX_PE`
  - `self.MIN_PROFIT_GROWTH`
  - `self.MIN_ROE`

Do not change:

- `_get_fundamentals_batch()`
- `get_fundamentals()`
- `sector_entry_selector.py`
- `global_entry_selector.py`
- `generate_buy_signals()`

Completion check:

- engine no longer holds the owner body of the fundamentals scoring rule

### E4-FG-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`

Minimum owner cases:

- missing-table pass-through returns `(True, 50, ["基本面数据不可用，跳过筛选"])`
- healthy case accumulates the expected full score and reasons
- `pe <= 0` with `profit_growth > 30` keeps the high-growth exception behavior
- `pe <= 0` with `profit_growth <= 30` marks `passed = False`
- high PE / low growth / low ROE composition preserves the current partial-score behavior

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

Completion check:

- the real owner logic has a direct focused carrier
- selector consumers still work unchanged

### E4-FG-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/fundamental_gate.py tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### E4-FG-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/fundamental_gate.py`
- `tests/unit/test_lowfreq_engine_v16_fundamental_gate.py`

Must exclude:

- `_get_fundamentals_batch()` changes beyond import-adjacent noise avoidance
- `get_fundamentals()` changes
- selector module edits unless strictly required for compatibility
- `generate_buy_signals()` edits
- API/report files
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- drifting into fundamentals data-loader extraction while touching nearby code

Guard:

- this slice only moves the scoring rule, not the retrieval layer

Risk 2:

- accidentally changing score math or reason strings during relocation

Guard:

- preserve the current branch order, literals, and threshold comparisons exactly

Risk 3:

- expanding into selector refactors because both selectors consume the same rule

Guard:

- selector files remain consumer guards only; no production edits there unless strictly necessary

Risk 4:

- using this slice to redesign the fundamentals policy

Guard:

- no threshold changes and no semantic tightening are allowed in this plan

## 6. Success Criteria

This slice is complete when:

- the real fundamentals scoring owner lives in `cycle_intelligence`
- engine keeps only a thin `check_fundamentals()` facade
- selector consumers keep working without call-site changes
- a focused owner test protects the real implementation
- no loaders, orchestrators, or API/report consumers are changed

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-fundamental-gate-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- any other workspace changes
