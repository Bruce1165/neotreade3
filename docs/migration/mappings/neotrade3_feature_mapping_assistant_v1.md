# NeoTrade3 Feature Mapping: assistant (v1)

## Purpose

This document records the NeoTrade3 landing targets for the NeoTrade2 features in domain `assistant`.

It is separate from the NeoTrade2 feature inventory:

- inventory: facts extracted from NeoTrade2 code, with evidence paths
- mapping: NeoTrade3 ownership, landing targets, and migration status

## Inputs

- NeoTrade2 inventory baseline: `docs/migration/neotrade2_feature_inventory.v3.json`
- Mapping file: `docs/migration/mappings/neotrade3_feature_mapping_assistant_v1.json`
- NeoTrade3 architecture responsibilities: `docs/architecture/neotrade3_master_architecture_and_migration_plan_v1.md`
- NeoTrade3 independence rule: `docs/migration/neotrade3_independence_principle.md`

## Landing Principle

NeoTrade3 does not introduce a standalone "NeoTrade2-style assistant service" as a runtime dependency model.

Instead, assistant-like analysis capabilities must land in:

- `learning`: evaluation, comparisons, and auditable candidate adjustments
- `issue_center`: evidence association and actionable cases
- `dashboard` / `api`: unified, read-only visibility

## Status Semantics

- `planned`: target is decided but no 3.0 implementation exists yet
- `scaffolded`: 3.0 has a contract skeleton but not real implementation
- `implemented`: real domain logic exists in 3.0
- `deferred`: explicitly postponed
- `retired`: explicitly dropped or replaced

