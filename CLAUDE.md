# CLAUDE.md

This file provides project-level guidance for NeoTrade3.

---

## Working Rules

- 永远使用中文回复。
- 不猜测，不扩大范围，不把“已设计”表述成“已实现”。
- 关键决策、关键步骤先沟通；确认后再实施。
- 结论必须基于可核验证据，证据不足时明确说明边界。
- 代码、配置、文档变更后，必须完成最小语法/结构校验。
- NeoTrade3 是独立项目，不复用 NeoTrade2 的项目上下文、状态文件或运行说明。
- NeoTrade2 当前只作为运行基线、迁移参考和回退对照；不要在 NeoTrade3 中把 2.0 结构直接复制进来。

## Project Goal

NeoTrade3 targets a data-management-driven operating system that supports:
- unified data control
- unified daily orchestration
- unified lab registration
- unified learning loop
- unified issue aggregation

The user should focus on model and screener adjustment, while the platform automates daily data and run management as much as possible.

## Current Phase

Current phase is project bootstrap.

Before major implementation work, always confirm:
1. which 3.0 domain is being implemented
2. whether the change belongs to skeleton, migration, or cutover
3. whether NeoTrade2 remains the reference or the active dependency

## Required Project Files

- `PROJECT_STATUS.md`: current 3.0 handoff and next step
- `docs/architecture/`: architecture plans
- `docs/handoffs/`: session handoffs
- `config/orchestrator/`: orchestrator registration and phase configs
- `config/labs/`: lab registration configs

## Bootstrap Boundaries

During bootstrap, do not:
- introduce NeoTrade2 runtime ownership changes
- cut over production write paths
- silently add legacy cron behavior into 3.0
- claim learning-loop automation beyond candidate generation and audit scaffolding
