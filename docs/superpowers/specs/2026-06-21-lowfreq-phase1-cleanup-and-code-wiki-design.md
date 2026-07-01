# Lowfreq Phase 1 Cleanup and Code Wiki Design

Date: 2026-06-21
Scope: Lowfreq code ownership cleanup, engine-owned backtest authority, legacy engine isolation, code wiki, version/test/calibration organization baseline

## 1. Background

Recent lowfreq work has moved quickly across:

- discovery / hold / peak research
- sell-side redesign
- process-view frontend updates
- attribution and Top100 / Top200 research scripts
- repeated long-window backtests

This produced real strategy progress, but it also exposed a growing structural problem:

- active lowfreq logic is no longer cleanly separated from historical versions
- backtest ownership is split across the engine and the API layer
- report scripts do not all depend on a single canonical backtest path
- frontend, docs, tests, and scripts are increasingly vulnerable to contract drift

The user has also explicitly clarified that cleanup is not the primary business goal by itself.

The primary goal remains:

- fine tune the low frequency engine toward a basically qualified state

Therefore, this Phase 1 cleanup must be judged only by one standard:

- does it reduce drift and make future lowfreq engine tuning safer, faster, and easier to verify?

If not, it is out of scope.

## 2. Problem Statement

The current lowfreq code surface has three concrete problems.

### 2.1 Backtest authority is duplicated

There are currently two active semantic owners of lowfreq backtest behavior:

1. `lowfreq_engine_v16_advanced.py`
   - `LowFreqTradingEngineV16.run_backtest()`
2. `apps/api/main.py`
   - `_lowfreq_backtest_with_trades()`

This is the highest-risk source of drift because:

- one semantic change may require edits in two places
- metrics, trade records, and audit fields can silently diverge
- scripts and API endpoints can end up validating different implementations

### 2.2 Active workspace and historical versions are mixed together

The repository root still contains historical lowfreq engines such as:

- `lowfreq_engine_v3.py`
- `lowfreq_engine_v15_final.py`
- current active `lowfreq_engine_v16_advanced.py`

This makes the active working surface ambiguous and increases the chance of:

- editing the wrong file
- misunderstanding which version is authoritative
- letting tests, scripts, or docs reference obsolete versions by accident

### 2.3 Ownership is not explicit across engine, API, scripts, frontend, and docs

Today, it is not obvious which layer owns:

- canonical trade semantics
- canonical backtest outputs
- derived report fields
- frontend-visible process fields

This makes future lowfreq tuning less reliable because cleanup debt and model work become entangled.

## 3. Design Goal

Phase 1 exists to support lowfreq model work, not replace it.

The design goal is to create a stable lowfreq working surface that:

1. establishes a single semantic owner for official backtests
2. isolates historical engines from the active workspace
3. defines clear layer ownership for engine, API, scripts, frontend, tests, and docs
4. adds a code wiki so future tuning work can proceed without version confusion
5. preserves strategy behavior while structure is cleaned up

The intended outcome is not cosmetic tidiness.

The intended outcome is:

- fewer accidental regressions during fine tuning
- faster verification after model changes
- clearer evidence that any performance change came from model logic rather than path drift

## 4. Design Principles

1. **Lowfreq tuning stays primary**
   - cleanup must directly serve future engine tuning and verification
   - unrelated repository refactors are out of scope

2. **Single semantic authority**
   - official lowfreq backtest semantics must have exactly one owner

3. **Behavior-preserving cleanup**
   - Phase 1 does not intentionally change strategy thresholds, ranking logic, or trading behavior

4. **Legacy must remain accessible but inactive**
   - old engines may be preserved for reference
   - they must not remain in the active working surface

5. **Derived fields must be marked as derived**
   - canonical engine outputs and report-only enrichments must not be mixed silently

6. **One-direction dependency flow**
   - engine -> adapters -> reports/API -> frontend/docs
   - not the reverse

## 5. Approach Options

### Approach A: Wiki-only clarification

- Keep the current code structure
- Add documentation explaining which files should be used

Pros:
- lowest immediate change risk
- fast to complete

Cons:
- duplicate backtest ownership remains
- historical files still clutter the active surface
- drift risk remains structurally unresolved

### Approach B: Engine-owned authority cleanup

- Make the engine the single official owner of lowfreq backtest semantics
- Convert API and scripts into callers/adapters
- Move retired engines out of the root active surface
- Add a code wiki and ownership map

Pros:
- directly solves the main drift source
- keeps cleanup focused on lowfreq work
- creates a stable base for continued model tuning

Cons:
- requires careful parity validation
- touches multiple lowfreq-adjacent files even without changing strategy semantics

### Approach C: Full lowfreq subsystem rewrite

- Rebuild engine / API / report / frontend boundaries at once

Pros:
- potentially the cleanest final architecture

Cons:
- too much change at once
- high regression risk
- likely to distract from the main lowfreq tuning objective

## 6. Chosen Approach

Adopt **Approach B: Engine-owned authority cleanup**.

The user explicitly confirmed:

- historical root-level lowfreq engines should be moved out of the main working surface
- official backtest authority should be `Engine-owned`

Therefore, this design freezes the following rule:

- `LowFreqTradingEngineV16.run_backtest()` is the only official lowfreq backtest implementation

## 7. Target Architecture

### 7.1 Engine Core

`lowfreq_engine_v16_advanced.py` is the sole semantic owner of:

- buy generation
- sell logic
- execution constraints
- trade record schema
- audit/event schema
- official backtest loop
- canonical backtest outputs

### 7.2 API Layer

`apps/api/main.py` remains responsible for:

- request parsing
- runtime state loading
- payload serialization / deserialization
- frontend-facing response shaping
- orchestration around the engine

`apps/api/main.py` no longer owns a parallel lowfreq backtest simulation path.

### 7.3 Research and Report Scripts

Lowfreq scripts remain responsible for:

- experiment setup
- attribution
- process research
- markdown / JSON report generation

They must not re-own official backtest semantics.

They may:

- call the engine backtest path
- compute derived analytics from canonical outputs

They may not:

- fork lowfreq trading simulation into a separate active implementation

### 7.4 Frontend Layer

The lowfreq frontend remains a presentation layer.

Its role is to render backend-owned canonical fields such as:

- process stage
- buy progress label
- hold / exit states
- grace / audit summaries

Frontend pages must not invent semantic fields that have no backend owner.

### 7.5 Legacy Layer

Historical lowfreq engines are preserved for reference, but relocated into a clearly named legacy/archive area.

They must be treated as:

- readable
- non-authoritative
- excluded from active calibration and official validation

## 8. Component Boundaries and Data Flow

### 8.1 Ownership Boundaries

- **Engine**
  - owns canonical semantics and canonical output contract
- **API**
  - owns transport and projection
- **Scripts**
  - own derived analysis and reporting
- **Frontend**
  - owns presentation only
- **Wiki**
  - owns explanation of file responsibilities and dependency flow

### 8.2 Canonical Backtest Flow

1. a request originates from an API endpoint or a script
2. the adapter constructs input parameters
3. the adapter calls `LowFreqTradingEngineV16.run_backtest()`
4. the engine returns the canonical result bundle
5. API reshapes it for UI clients
6. scripts derive research and report outputs from it

### 8.3 Canonical Result Bundle

The engine-owned backtest result is the only source of truth for fields such as:

- summary metrics
- trades
- trade block counters
- config snapshot
- audit outputs

Any report-only or UI-only enrichment must be explicitly marked as derived.

## 9. Phase 1 File Strategy

### 9.1 Active Files

These remain part of the active lowfreq working surface:

- `lowfreq_engine_v16_advanced.py`
- lowfreq-related sections of `apps/api/main.py`
- active lowfreq scripts under `scripts/`
- active frontend lowfreq page and tests
- lowfreq unit tests
- lowfreq specs and wiki docs

### 9.2 Legacy Files

These should be relocated out of the root active surface:

- `lowfreq_engine_v3.py`
- `lowfreq_engine_v15_final.py`
- any other retired root-level lowfreq engine not serving the current active path

The relocation target should be explicit and easy to scan, for example a dedicated legacy/archive area under the project tree.

### 9.3 Archived Scripts

Existing archived scripts under `scripts/archive/lowfreq/` remain reference-only and should stay clearly separated from active scripts.

## 10. Code Wiki Design

Phase 1 adds one lowfreq code wiki document whose purpose is operational clarity, not research narration.

The wiki should contain:

1. **Authority**
   - active engine file
   - official backtest owner

2. **Layer map**
   - engine
   - API
   - scripts
   - frontend
   - tests
   - docs

3. **File ownership table**
   - file or directory
   - responsibility
   - depends on
   - active vs legacy

4. **Canonical outputs**
   - which fields are engine-owned
   - which fields are derived

5. **Safe change guide**
   - where to edit for strategy logic
   - where to edit for API projection
   - where to edit for reports
   - where to edit for frontend rendering

6. **Validation checklist**
   - what to rerun after structural changes

The wiki is successful if a future tuning task can quickly answer:

- where should I change the model?
- what depends on that change?
- how do I verify I did not cause drift?

## 11. Migration Plan

### Step 1: Freeze authority

Declare:

- `lowfreq_engine_v16_advanced.py` is the active lowfreq engine
- `LowFreqTradingEngineV16.run_backtest()` is the only official lowfreq backtest implementation

### Step 2: Remove duplicate backtest ownership

Refactor the API backtest path so that:

- API remains a caller and serializer
- backtest semantics are delegated to the engine

The API must stop being a second active simulator.

### Step 3: Relocate legacy root-level engines

Move historical root-level lowfreq engines into a dedicated legacy/archive location and mark them as non-active.

### Step 4: Align active scripts

Refactor active lowfreq scripts to consume the engine-owned canonical backtest output rather than owning alternate active simulation behavior.

### Step 5: Add the code wiki

Write the lowfreq code wiki and ownership map after the file boundaries are finalized.

### Step 6: Record Phase 2 frontend handoff

Document which backend contracts are canonical so later frontend cleanup stays aligned with the cleaned lowfreq backend structure.

## 12. Validation Requirements

### 12.1 Behavior Preservation

Phase 1 must not intentionally change:

- buy thresholds
- sell thresholds
- ranking semantics
- execution constraints
- research formula semantics

### 12.2 Backtest Parity

For representative windows, pre-cleanup and post-cleanup results must remain materially aligned in:

- total return
- max drawdown
- trade count
- trade block counts
- trade-level outputs

If a difference appears, it must be explained as:

- an approved bug fix
- or a serialization-only difference

Otherwise it is a regression.

### 12.3 Test Preservation

Existing lowfreq tests must continue to pass, especially:

- engine sell-logic regression tests
- lowfreq API serialization tests
- frontend lowfreq rendering tests where affected

### 12.4 Legacy Isolation

After cleanup:

- no active lowfreq API path should depend on legacy engines
- no active lowfreq script should implicitly depend on legacy engines
- no official validation path should use a legacy engine by accident

## 13. Non-Goals

Phase 1 does **not** do the following:

- redesign the lowfreq strategy
- change hold / peak / discovery rules
- recalibrate thresholds
- replace the current frontend information architecture
- rewrite the entire lowfreq subsystem
- clean unrelated repository areas just because they are old

## 14. Risks and Controls

### Risk 1: Cleanup changes behavior by accident

Control:

- use parity validation
- treat semantic differences as regressions unless explicitly approved

### Risk 2: Cleanup scope expands beyond lowfreq support

Control:

- reject unrelated refactors
- keep the success criterion tied to future lowfreq tuning efficiency

### Risk 3: Scripts still depend on hidden parallel logic

Control:

- audit active lowfreq scripts one by one
- classify each as canonical caller, derived analyzer, or legacy reference

### Risk 4: Wiki becomes stale immediately

Control:

- keep the wiki focused on ownership and flow
- avoid duplicating full research history or implementation detail already covered elsewhere

## 15. Success Criteria

Phase 1 is successful only if all of the following are true:

1. there is one official lowfreq backtest owner
2. the active lowfreq working surface is visually and structurally clear
3. historical lowfreq engines no longer clutter the root active surface
4. active scripts, API, and frontend depend on canonical lowfreq outputs
5. future lowfreq tuning can proceed with lower drift risk and faster verification

The ultimate test is practical:

- the next round of lowfreq fine tuning should become easier to execute and easier to trust

## 16. Immediate Next Step

Implement Phase 1 in this order:

1. freeze engine-owned authority
2. remove duplicate API backtest ownership
3. relocate root-level legacy engines
4. align active scripts to canonical outputs
5. write the lowfreq code wiki

Only after Phase 1 is validated should Phase 2 frontend cleanup proceed further.
