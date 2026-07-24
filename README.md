# NeoTrade3

NeoTrade3 is the next-generation A-share research and execution operating system.

Current status:
- The core NeoTrade3 worker + API are the current execution and snapshot backbone.
- The current browser UI is `neotrade3-dashboard/` (React + Vite); the legacy Python bootstrap dashboard under `apps/dashboard/` was removed on 2026-07-23 and survives only in git history.
- Low-frequency model (v16 advanced) can generate signals, simulate runs, and produce backtest reports.
- NeoTrade2 was decommissioned and deliberately cleared on 2026-07-23; migration reference material survives under `docs/migration/`.
- NeoTrade3 will become the new IDE project and the future system of record for:
  - data control
  - daily orchestration
  - lab operations
  - learning loop
  - issue aggregation

## v1 Scope

NeoTrade3 v1 focuses on four foundation areas:
- data control: capture -> compose -> publish
- daily master orchestrator
- unified registration for four labs
- minimal learning loop and issue center

## Repository Layout

- `docs/`: architecture, handoffs, operations
- `config/`: environment, orchestrator, and lab registrations
- `apps/`: API and worker entrypoints
- `neotrade3/`: core Python packages
- `scripts/`: bootstrap and maintenance helpers
- `tests/`: unit, integration, and smoke tests
- `var/`: local runtime artifacts, logs, and ledgers

## Current Transition Principle

- NeoTrade3 is built as a standalone system from now on.
- NeoTrade2 can be used as migration reference only.
- NeoTrade3 must not depend on NeoTrade2 runtime data, databases, services, scripts, or generated artifacts.

## Current Entrypoints

- `apps/worker/main.py`
  - builds the current bootstrap snapshot chain and is the single execution truth source for bootstrap orchestration
- `apps/api/main.py` + `apps/api/router.py`
  - exposes API endpoints (supports both `/api/...` and `/api/v1/...` prefixes) and projects worker snapshots into compatibility ledgers/artifacts where needed
- `neotrade3-dashboard/`
  - current React + Vite dashboard frontend

Current API groups:

- health:
  - `/healthz`
- low-frequency trading:
  - `POST /api/model/run`
  - `GET /api/sectors/hot`
  - `POST /api/lowfreq/backtest/run`
  - `GET /api/lowfreq/backtest/reports?limit=N`
  - `GET /api/lowfreq/backtest/reports/<report_id>.pdf|.json`
  - `GET /api/lowfreq/backtest/status?report_id=<report_id>`
  - `GET /api/lowfreq/backtest/window-summary?end_date=YYYY-MM-DD&window_trading_days=60`
  - `GET /api/lowfreq-score/pool?date=YYYY-MM-DD`
  - `GET /api/lowfreq-score/pool/<code>?date=YYYY-MM-DD`
  - `GET /api/lowfreq-score/events?date=YYYY-MM-DD`
  - `GET /api/lowfreq-score/summary?date=YYYY-MM-DD`
  - `POST /api/lowfreq-score/manual/buy-intent`
  - `POST /api/lowfreq-score/manual/abandon`
  - `GET /api/lowfreq/confidence/overview?date=YYYY-MM-DD`
  - `GET /api/lowfreq/confidence/calibration?date=YYYY-MM-DD`
  - `POST /api/lowfreq/confidence/run`
  - `GET /api/lowfreq/rsi/regression`
  - `POST /api/lowfreq/rsi/weekly-record`
  - `GET /api/lowfreq/portfolio?date=YYYY-MM-DD` `[deprecated]`
  - `POST /api/lowfreq/manual/buy-intent` `[deprecated]`
  - `POST /api/lowfreq/manual/abandon` `[deprecated]`
  - `POST /api/lowfreq/settings/autopilot`
  - `GET /api/lowfreq/execution/queue`
  - `POST /api/lowfreq/execution/processed`
  - `POST /api/lowfreq/execution/abandon`
- A-share universe audit:
  - `GET /api/ashare/midcap/audit?date=YYYY-MM-DD`
- concepts:
  - `GET /api/concepts/mainline?date=YYYY-MM-DD`
  - `GET /api/concepts/mainline/detail?concept_code=...&date=YYYY-MM-DD`
- domain views:
  - `/api/data-control`
  - `/api/orchestration`
  - `/api/labs`
  - `/api/config-contracts`
  - `/api/migration/feature-manual`
  - `/api/issue-center`
  - `/api/learning`

Current API read modes:

- `source=live`
  - build snapshot at request time
- `source=stored`
  - read previously written snapshot files under `var/`

Current API behavior notes:

- returns structured errors under `error.code / error.message / error.details`
- uses a minimal in-memory cache for snapshot and registry reads
- returns minimal CORS headers so the local dashboard can read the API from a separate port
- validates `labs / orchestrator / source_registry` config contracts during load and exposes the current status through `/api/config-contracts`
- exposes the first code-derived NeoTrade2 migration inventory through `/api/migration/feature-manual`
- exposes NeoTrade3 migration mapping decisions through `/api/migration/feature-mapping?domain=...` and supports `status` / `strategy` filters
- exposes per-domain mapping coverage reports through `/api/migration/feature-mapping-coverage?domain=...`

Current runtime boundary notes:

- `var/ledgers/bootstrap_runs` + `var/artifacts/bootstrap_runs` are the primary bootstrap snapshot fact source
- `var/ledgers/orchestration_runs` + `var/artifacts/orchestration_runs` are compatibility projections for orchestration-run APIs
- `var/ledgers/lab_runs` + `var/artifacts/lab_runs` are compatibility projections for legacy lab-run readers
- snapshot root `publish_succeeded` reflects the effective result of the current run; `requested_publish_succeeded` preserves the requested planning hint

Current dashboard behavior notes:

- `neotrade3-dashboard/` is the active UI codebase and currently exposes `Overview` / `Screeners` / `Stock Check` / `Lowfreq`
- the legacy Python dashboard was removed on 2026-07-23 (survives only in git history) and must not be treated as the current frontend

## Current Runbook

- Operational runbook:
  - `docs/operations/bootstrap_runbook.md`
- Architecture notes:
  - `docs/architecture/neotrade3_research_goal_and_definitions_v1.md`
  - `docs/architecture/neotrade3_research_model_and_module_taxonomy_v1.md`
- Migration baseline:
  - `docs/migration/neotrade2_feature_manual_v3.md`
  - `docs/migration/neotrade2_feature_inventory.v3.json`
  - `docs/migration/mappings/neotrade3_feature_mapping_strategy_and_lab_v1.md`
  - `docs/migration/mappings/neotrade3_feature_mapping_strategy_and_lab_v1.json`
  - `docs/migration/mappings/neotrade3_feature_mapping_assistant_v1.md`
  - `docs/migration/mappings/neotrade3_feature_mapping_assistant_v1.json`
  - `docs/migration/mappings/neotrade3_feature_mapping_operations_v1.md`
  - `docs/migration/mappings/neotrade3_feature_mapping_operations_v1.json`
  - `docs/migration/mappings/neotrade3_feature_mapping_screeners_v1.md`
  - `docs/migration/mappings/neotrade3_feature_mapping_screeners_v1.json`
  - `docs/migration/neotrade3_independence_principle.md`
  - `docs/migration/neotrade3_ui_design_principles.md`

Recommended local order:

1. run `worker`
2. start `api`
3. start `neotrade3-dashboard`
