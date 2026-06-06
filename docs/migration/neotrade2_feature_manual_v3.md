# NeoTrade2 Feature Manual V3

## Purpose

This file is the third code-derived feature manual for NeoTrade2.
It keeps the migration rule unchanged:

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
- screener and research scripts used by labs and assistant flows

## Current Scope

The structured inventory lives in:

- `docs/migration/neotrade2_feature_inventory.v3.json`

This version keeps all v2 items and adds the same subfeature-level decomposition for the remaining active domains:

- `strategy_and_lab`
- `assistant`
- `operations`

## Inventory Summary

- Current identified features: 68
- Current identified subfeatures: 51
- Domains:
- `assistant`
- `data_pipeline`
- `operations`
- `screeners`
- `strategy_and_lab`
- `web_and_api`

## Refinement Notes

This version extends the active checklist baseline in three directions:

1. `strategy_and_lab`
   - paper trading artifact catalog/download
   - paper trading portfolio backtest
   - paper trading recommendation portfolio
   - paper trading follow tracking
   - paper trading signal backtest
   - strategy run create/execute
   - strategy run registry query
   - strategy run logs/artifacts
   - strategy lab recent signals summary
   - cup-handle summary/daily trend
   - cup-handle stock pool/watch pool
   - cup-handle alignment/V4 compare
   - cup-handle daily brief/audit
   - cup-handle feedback/retrain
   - five-flags health/unprocessed summary
   - five-flags pool query/upload
   - five-flags run queue/registry
   - five-flags results timeline/diagnosis
   - five-flags miss analysis/logs
   - five-flags flow timing/profile publish
2. `assistant`
   - lao-ya-tou pool commonalities
   - lao-ya-tou label summary
   - lao-ya-tou baseline evaluation
   - lao-ya-tou daily compare
   - five-flags parameter overrides
   - assistant query router
   - rules analyze
3. `operations`
   - data health summary/lifecycle view
   - data health manual upload
   - system task readiness board
   - system task manual trigger/wait mode
   - system job status polling

## Evidence Notes

- V3 only records features that have direct runtime evidence in NeoTrade2 code.
- During this round, `frontend/src/api/index.ts` declares assistant client methods for feedback submission/listing and rules verification, but matching Flask routes were not confirmed in `backend/app.py`.
- Those client declarations are treated as interface drift signals, not as confirmed delivered features.

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
- V3 should now be treated as the active checklist baseline for ongoing migration analysis.
- The next round should move from feature decomposition to feature-by-feature migration destination mapping inside NeoTrade3.
