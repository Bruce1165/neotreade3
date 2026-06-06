# NeoTrade2 Feature Manual V1

## Purpose

This file is the first code-derived feature manual for NeoTrade2.
It exists to support NeoTrade3 migration under one hard rule:

- NeoTrade2 features may be reorganized in NeoTrade3
- NeoTrade2 features must not be omitted
- migration confirmation must be possible feature by feature

## Source Of Truth

- Primary source: NeoTrade2 codebase under `/Users/mac/NeoTrade2`
- Secondary source: only used for cross-check when code intent is unclear

This version was extracted from code entrypoints first:

- Flask routes in `backend/app.py`
- React dashboard tabs and pages in `frontend/src/App.tsx` and `frontend/src/pages/`
- data and orchestration scripts in `scripts/`
- screener modules in `screeners/`

## Current Scope

The structured inventory lives in:

- `docs/migration/neotrade2_feature_inventory.v1.json`

This inventory is machine-readable and intended to become the migration checklist baseline.

## Inventory Summary

- Current identified features: 16
- Domains:
  - `web_and_api`
  - `screeners`
  - `data_pipeline`
  - `operations`
  - `strategy_and_lab`
  - `assistant`

## Confirmation Rules

Each feature item must eventually support the following confirmation questions:

1. What is the feature definition?
2. What is the runtime path?
3. What are the upstream data sources?
4. Which module owns it in NeoTrade2?
5. Where does it land in NeoTrade3?
6. Has it been migrated, replaced, merged, or explicitly retired?

## Notes

- This is an inventory baseline, not the final migration mapping.
- Algorithm internals for each screener or lab are not fully decomposed yet.
- The next pass should refine each identified feature into sub-features where the code shows separate user-visible responsibilities.
