Status: Approved
Owner: governance
Scope: M5 final_validation_selection standalone CLI and API adoption
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-m5-final-validation-selection-cli-api-adoption-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# M5 Final Validation Selection CLI/API Adoption Design

## 背景

`run_governance_final_validation_selection(...)` 已在 runtime 中存在，且 `daily` / worker 已能消费该能力。

当前缺口仅在 standalone adoption：

- `neotrade3/governance/cli.py` 尚无独立 `final_validation_selection` 命令
- API 尚无独立 `mode="governance_final_validation_selection"` 入口

## 目标

- 为 `final_validation_selection` 增加最小独立 CLI adoption
- 为 `final_validation_selection` 增加最小独立 API adoption
- 保持输入 contract 只包含 `source_run_id`

## 非目标

- 不修改 `run_governance_final_validation_selection(...)` 内部选择逻辑
- 不修改 `daily` 调度与 orchestrator 配置
- 不扩 `reject_execution` / `status_transition`
- 不新增独立 HTTP endpoint

## 方案

采用“复用现有 mode”方案：

- CLI 新增 `final-validation-selection`
- API 复用现有治理 on-demand 执行入口，新增 `mode="governance_final_validation_selection"`
- worker / API 只做最小桥接，不改变 runtime contract

## 实现范围

仅允许修改：

- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `apps/api/main.py`
- `apps/api/router.py`
- 对应聚焦测试

## 验证

最小验证集合：

1. CLI 可独立触发 `final_validation_selection`
2. API mode 可独立触发 `final_validation_selection`
3. fail-closed 仍由 runtime 原样抛出

## M/G 双轴审计

### M 轴

- 仅补 standalone adoption
- 不改治理对象、artifact/ledger schema 与选择逻辑

### G 轴

- 保持显式 on-demand 触发
- 不把强副作用治理动作加入 `daily`
