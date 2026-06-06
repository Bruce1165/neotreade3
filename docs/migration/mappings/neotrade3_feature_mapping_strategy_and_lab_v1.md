# NeoTrade3 Feature Mapping: strategy_and_lab (v1)

## Purpose

This document records the NeoTrade3 landing targets for the NeoTrade2 features in domain `strategy_and_lab`.

It is intentionally separate from the NeoTrade2 feature inventory:

- inventory: facts extracted from NeoTrade2 code, with evidence paths
- mapping: NeoTrade3 ownership, landing targets, and migration status

## Inputs

- NeoTrade2 inventory baseline: `docs/migration/neotrade2_feature_inventory.v3.json`
- Mapping file: `docs/migration/mappings/neotrade3_feature_mapping_strategy_and_lab_v1.json`
- NeoTrade3 architecture responsibilities: `docs/architecture/neotrade3_master_architecture_and_migration_plan_v1.md`
- NeoTrade3 independence rule: `docs/migration/neotrade3_independence_principle.md`

## Core Landing Targets (NeoTrade3)

Based on the current NeoTrade3 skeleton:

- `labs`: unified lab registration and daily job contracts
- `orchestration`: Daily Master Orchestrator, phases, task dependencies, run/task ledgers
- `issue_center`: unified issue aggregation with evidence links
- `learning`: unified result collection, evaluation, candidate adjustments, auditing
- `api` / `dashboard`: read-only visibility and navigation layers

## Status Semantics

- `planned`: target is decided but no 3.0 skeleton exists for this capability
- `scaffolded`: 3.0 has a contract skeleton (registry/task/artifact placeholder) but no real implementation
- `implemented`: real domain logic exists in 3.0 (not the case for most strategy_and_lab items yet)
- `deferred`: explicitly postponed
- `retired`: explicitly dropped or replaced

## Notes

- This mapping must never introduce runtime dependency from NeoTrade3 to NeoTrade2.
- Mapping is a migration decision artifact; it must be auditable and versioned.
- Where a 2.0 feature spans multiple layers (e.g. queue + logs + diagnosis), the mapping records multiple NeoTrade3 landing domains to preserve full scope.

