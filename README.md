# NeoTrade3

NeoTrade3 is the next-generation A-share research and execution operating system.

Current status:
- The project skeleton is initialized.
- NeoTrade2 remains the running baseline and migration reference.
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
- `apps/`: API, dashboard, and worker entrypoints
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
  - builds the current bootstrap snapshot chain
- `apps/api/main.py`
  - exposes read-only bootstrap endpoints
- `apps/dashboard/main.py`
  - serves the current read-only bootstrap dashboard shell with domain-based loading, `live/stored` switching, summary cards, and structured error display
- `apps/dashboard/static/`
  - contains the current dashboard CSS and browser-side JS assets

Current API groups:

- health:
  - `/healthz`
- bootstrap:
  - `/api/bootstrap-summary`
  - `/api/bootstrap-snapshot`
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

Current dashboard behavior notes:

- shows summary-first cards for target date, source mode, cache status, planned tasks, issue cases, and learning candidates
- shows per-domain summary text and keeps raw JSON payloads available in expandable sections

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
3. start `dashboard`
