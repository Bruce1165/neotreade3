# Status

Status: active
Owner: NeoTrade3
Scope: 版本/策略统一 → lowfreq v16 的 StrategyConfig 适配入口（仅参数映射 + fail-closed 校验）
Canonical: yes
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-16

# Goal

- 将 `config/strategies/<strategy_id>.json`（`StrategyConfig`）的 `parameters` 映射为 `LowFreqV16Config`，并提供一个可对 `LowFreqTradingEngineV16` 应用的适配入口。
- 不修改 lowfreq v16 的任何策略逻辑（不改选股/买卖/回测算法，只做配置适配与校验）。

# Non-Goals

- 不引入新的回测/报告输出能力。
- 不改动 `LowFreqTradingEngineV16` 内部字段命名或行为。
- 不把 lowfreq v16 接入 labs/orchestrator（本刀只做适配入口，不做调度 adoption）。

# Contracts

## StrategyConfig

- 文件路径：`config/strategies/<strategy_id>.json`
- 本刀限定：`strategy_id == "lowfreq_v16"`（其余 fail-closed）。
- 允许字段：
  - `strategy_id: str`
  - `version: int`
  - `description: str`
  - `parameters: dict`

## Adapter API

- `build_lowfreq_v16_config_from_strategy(strategy: StrategyConfig) -> LowFreqV16Config`
- `apply_lowfreq_v16_strategy_config(engine: LowFreqTradingEngineV16, strategy: StrategyConfig) -> None`

# Mapping Rules (Fail-Closed)

- `parameters` 允许两种层级：
  - 顶层 key：必须对应 `LowFreqV16Config` 的字段名（排除 `version/cost_model/execution`）
  - `cost_model: dict`：字段必须对齐 `TradeCostModel`
  - `execution: dict`：字段必须对齐 `ExecutionConstraints`
- 任一未知 key → `ValueError`
- 任一类型不匹配 → `ValueError`
  - `int` 字段只接受 `int`
  - `float` 字段接受 `int|float`，统一转 `float`
  - `bool` 字段只接受 `bool`
  - `str` 字段只接受 `str`

# Tests

- 单元测试覆盖：
  - 正常映射：strategy parameters → LowFreqV16Config → engine 应用
  - 未知 key fail-closed
  - 类型不匹配 fail-closed
  - strategy_id 不匹配 fail-closed

# M/G + Syntax/Semantic Audit (Acceptance)

- M（模型层定位）：版本/策略统一层 → lowfreq v16 配置适配层
- G（目标推进）：推进 `PROJECT_STATUS.md` 的 “版本与策略统一（最高优先级）”中“策略参数/版本号抽成可配置对象并形成唯一入口”的 v16 适配基线
- Syntax：pytest 定点通过 + compileall 通过
- Semantic：不引入第二真相源；仅做白名单映射与校验；不改变 lowfreq v16 内部逻辑
