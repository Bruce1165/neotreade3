# NeoTrade2 Feature Manual V2

## Purpose

This file is the second code-derived feature manual for NeoTrade2.
It keeps the original migration rule unchanged:

- NeoTrade2 features may be reorganized in NeoTrade3
- NeoTrade2 features must not be omitted
- migration confirmation must be possible feature by feature

## Source Of Truth

- Primary source: NeoTrade2 codebase under `/Users/mac/NeoTrade2`
- Secondary source: only used for cross-check when code intent is unclear

This version continues to extract from code entrypoints first:

- Flask routes in `backend/app.py`
- React dashboard tabs and pages in `frontend/src/App.tsx` and `frontend/src/pages/`
- data and orchestration scripts in `scripts/`
- screener modules in `screeners/`

## Current Scope

The structured inventory lives in:

- `docs/migration/neotrade2_feature_inventory.v2.json`

This version keeps the v1 system-level items and adds finer-grained subfeatures for the two domains currently under active decomposition:

- `screeners`
- `data_pipeline`

## Inventory Summary

- Current identified features: 36
- Current identified subfeatures: 19
- Domains:
- `assistant`
- `data_pipeline`
- `operations`
- `screeners`
- `strategy_and_lab`
- `web_and_api`

## Refinement Notes

This version refines the previous baseline in two specific directions:

1. `screeners`
   - catalog listing
   - config read/write
   - single run
   - bulk run
   - results query/export
   - single stock check
   - stock chart inspection
   - base filter/runtime contract
   - screener monitor summary
2. `data_pipeline`
   - Tencent capture batches
   - compose candidate and conflict ledger
   - publish quality gate
   - capture-compose-publish shortcut path
   - download orchestrator main chain
   - historical backfill
   - authoritative overwrite repair
   - stock meta synchronization detail
   - integrity verification
   - data gap filling

## Confirmation Rules

Each feature item must eventually support the following confirmation questions:

1. What is the feature definition?
2. What is the runtime path?
3. What are the upstream data sources?
4. Which module owns it in NeoTrade2?
5. Where does it land in NeoTrade3?
6. Has it been migrated, replaced, merged, or explicitly retired?

## Notes

- This is still not the final migration mapping.
- `strategy_and_lab`, `assistant`, and operations-related modules still need the same level of subfeature decomposition.
- V2 should now be treated as the active checklist baseline for ongoing migration analysis.
