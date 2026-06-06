# NeoTrade3 Feature Mapping: operations (v1)

## Purpose

This document records the NeoTrade3 landing targets for the NeoTrade2 features in domain `operations`.

It is separate from the NeoTrade2 feature inventory:

- inventory: facts extracted from NeoTrade2 code, with evidence paths
- mapping: NeoTrade3 ownership, landing targets, and migration status

## Inputs

- NeoTrade2 inventory baseline: `docs/migration/neotrade2_feature_inventory.v3.json`
- Mapping file: `docs/migration/mappings/neotrade3_feature_mapping_operations_v1.json`
- NeoTrade3 architecture responsibilities: `docs/architecture/neotrade3_master_architecture_and_migration_plan_v1.md`
- NeoTrade3 independence rule: `docs/migration/neotrade3_independence_principle.md`

## Landing Principle

Operations capabilities in NeoTrade3 are not separate “tools pages”.

They should be expressed as unified operational visibility over:

- `data_control`: data lifecycle, batches, quality gates
- `orchestration`: single-run entrypoint, phases, task dependencies, run/task ledgers
- `issue_center`: centralized failure aggregation and evidence association
- `dashboard` / `api`: read-only visibility

Where NeoTrade2 used `cron/launchd` task registry as the operational center, NeoTrade3 replaces it with the Daily Master Orchestrator.

