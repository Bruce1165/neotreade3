# Lowfreq Code Wiki

This document is the operational index for the active lowfreq model code.

It answers four practical questions:

- where the active lowfreq engine lives
- which layer owns which behavior
- where derived reporting logic is allowed
- what to rerun after structural or strategy changes

## 1. Authority

- Active engine: `lowfreq_engine_v16_advanced.py`
- Official backtest owner: `LowFreqTradingEngineV16.run_backtest()`
- Active lowfreq API surface: lowfreq-related parts of `apps/api/main.py`
- Active lowfreq frontend page: `neotrade3-dashboard/src/pages/Lowfreq.jsx`

The active lowfreq model must be tuned from the engine file above unless the task is explicitly about API projection, report formatting, or frontend presentation.

## 2. Layer Map

### Engine

Path:

- `lowfreq_engine_v16_advanced.py`

Owns:

- buy signal generation
- sell logic
- execution constraints
- `TradeRecord` schema
- canonical backtest loop
- canonical backtest outputs
- buy/sell audit fields

Does not own:

- API request parsing
- report rendering
- frontend-only layout logic

### API

Path:

- `apps/api/main.py`

Owns:

- request parsing
- state loading
- serialization / deserialization
- frontend-facing payload shaping
- orchestration around the engine

Does not own:

- a separate lowfreq backtest simulation path

### Scripts

Paths:

- `scripts/run_lowfreq_top200_capacity_experiment.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `scripts/generate_lowfreq_top200_process_research_report.py`
- `scripts/generate_lowfreq_research_report_assets.py`

Own:

- experiment setup
- attribution
- process research
- markdown / JSON output generation

Must rely on:

- canonical outputs from the engine-owned backtest path

### Frontend

Path:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`

Owns:

- visual presentation
- process timeline rendering
- status badge rendering

Must not own:

- model semantics
- frontend-only trade lifecycle concepts with no backend owner

### Tests

Key paths:

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`

Purpose:

- protect engine semantics
- protect API trade payload compatibility
- protect frontend rendering of canonical fields

## 3. Active vs Legacy

### Active

- `lowfreq_engine_v16_advanced.py`
- active lowfreq API code in `apps/api/main.py`
- active lowfreq scripts under `scripts/`
- lowfreq frontend page and tests

### Legacy

- `legacy/lowfreq/lowfreq_engine_v3.py`
- `legacy/lowfreq/lowfreq_engine_v15_final.py`
- files under `scripts/archive/lowfreq/`

Legacy files are reference-only and must not be used for active calibration, official validation, or current tuning.

## 4. Canonical Outputs

Canonical engine-owned outputs include:

- summary metrics
- trades
- trade block counters
- config snapshot
- buy/sell audit logs

Derived outputs include:

- attribution summaries
- process research summaries
- report markdown
- frontend-only grouping or sorting for display

If a field is needed by frontend or reports and its meaning is part of the model, it should be created in the engine or backend contract first, not invented in the consumer layer.

## 5. Safe Change Guide

### If tuning the model

Edit:

- `lowfreq_engine_v16_advanced.py`

Then rerun:

- engine unit tests
- any targeted backtest or attribution validation needed by the change

### If changing API payload shape

Edit:

- `apps/api/main.py`

Then rerun:

- lowfreq API-related tests
- frontend lowfreq tests if the UI contract changes

### If changing research/report logic

Edit:

- the relevant script under `scripts/`

Then rerun:

- the target script
- any parity check needed to confirm canonical outputs were not redefined

### If changing frontend display

Edit:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`

Then rerun:

- `Lowfreq.test.jsx`
- any backend test if the frontend change requires new backend-owned fields

## 6. Validation Checklist

After structural lowfreq changes, verify:

1. backtest authority still points to `LowFreqTradingEngineV16.run_backtest()`
2. no active code path depends on `legacy/lowfreq/*`
3. lowfreq trade payloads still deserialize correctly
4. targeted lowfreq unit tests pass
5. frontend still renders canonical process fields correctly

## 7. Dependency Rule

The allowed dependency flow is:

- engine -> API adapters / scripts -> frontend / docs

The reverse is not allowed.

If a change requires logic to flow backward from a consumer into the engine contract, the contract should be redesigned explicitly rather than patched indirectly.
