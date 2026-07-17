# Status: draft
# Owner: platform / lowfreq_engine
# Scope: Auto materialize M3 lifecycle logs from sell-side audit (end-to-end closure)
# Canonical: self
# Supersedes: none
# Superseded_by: none
# Last_reviewed: 2026-07-17

## 1. 目标

把 “engine sell-side audit → M3 lifecycle log → var/artifacts + var/ledgers → API readback” 这条链路接通，形成端到端可审计闭环。

## 2. 边界

### 2.1 In scope

- 在 lowfreq engine 侧新增“物化 lifecycle logs”的接入点：基于 `sell_signal_audit` 生成 `DecisionLifecycleLog` 并落盘。
- 接入点放在 `LowFreqTradingEngineV16.run_backtest(...)` 的末尾（清空 `_sell_signal_audit_current_run` 之前）。
- 新增单测：使用现有 sell audit 生成逻辑（`engine._sell_signal_audit_current_run`）验证落盘与可读回。
- checklist 快照证据回写（补“端到端闭环”的证据链接）。

### 2.2 Out of scope

- 修改 lifecycle contract/version（仍使用现有 v2）。
- 改造 engine 的 sell audit 事件内容（保持现状）。
- worker/orchestrator 阶段化改造（本刀仅连接 lowfreq backtest 路径）。

## 3. 现状证据（可核验）

- sell-side audit 的生产与生命周期：
  - `run_backtest(...)` 初始化 `sell_signal_audit` 并设置 `self._sell_signal_audit_current_run`：[lowfreq_engine_v16_advanced.py:L3315-L3318](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3315-L3318)
  - 末尾把 `sell_signal_audit` 写入 `gross_metrics` 并清空 current_run：[lowfreq_engine_v16_advanced.py:L3967-L3978](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3967-L3978)
- sell audit → lifecycle log 的 formalize builder 已存在：[decision_lifecycle_log.py:L153-L198](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/decision_lifecycle_log.py#L153-L198)
- lifecycle log store + API readback 已实现：[lifecycle_log_store.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/lifecycle_log_store.py)；`/api/m3/lifecycle-logs`（router/main + tests）。
- 当前缺口：生产链路未调用 `materialize_decision_m3_lifecycle_log(...)`（仅测试调用）。

## 4. 设计

### 4.1 接入策略（推荐：显式参数启用）

为避免“猜测 run_id/source_run_id/project_root”的口径，本刀采用 **显式参数启用**：

- 在 `LowFreqTradingEngineV16.run_backtest(...)` 增加可选参数：
  - `project_root: str | Path | None = None`
  - `run_id: str | None = None`
  - `source_run_id: str | None = None`
- **仅当** `project_root/run_id/source_run_id` 三者都提供且非空时，才触发 lifecycle log 物化；否则保持原行为（不落盘）。

失败策略（fail-closed）：

- 启用物化时：任何 formalize/contract/materialize 失败都抛出异常，中止本次 `run_backtest` 返回（由调用方决定是否捕获）。
- 未启用时：不做任何物化动作，不改变现有返回结构。

### 4.2 实现形态（可测试、可复用）

在 `lowfreq_engine_v16_advanced.py` 中新增纯函数 helper（便于单测与未来复用）：

```
def materialize_sell_signal_audit_as_m3_lifecycle_logs(
    *,
    project_root: str | Path,
    sell_signal_audit: list[dict[str, Any]] | None,
    run_id: str,
    source_run_id: str,
    dry_run: bool = False,
) -> list[DecisionM3LifecycleLogLedgerRecord]
```

逻辑：

1) `build_decision_lifecycle_logs(sell_signal_audit, run_id, source_run_id)` 得到 payload list  
2) 对每个 payload：`DecisionLifecycleLog.from_dict(payload)`（fail-closed）  
3) `record_id = build_decision_m3_lifecycle_log_record_id(stock_code=..., run_id=run_id)`  
4) `materialize_decision_m3_lifecycle_log(project_root, record_id, lifecycle_log, dry_run)`  
5) 返回 ledger records（可用于调用方进一步记录/索引）

`run_backtest(...)` 末尾接入：

- 在 `self._sell_signal_audit_current_run = None` 之前调用 helper（仅当启用参数齐备）。

### 4.3 原子性与部分落盘风险说明

本刀保证“逻辑层 all-or-nothing”：

- 先构造并通过 `DecisionLifecycleLog.from_dict` 校验全部 log，再进入 materialize 写入循环；
- 若 sell audit 本身不完整/不合法，直接 fail-closed，避免产生部分日志。

IO 层面仍可能出现“部分 record_id 已写、后续写失败”的情况（磁盘/权限等不可控）。该风险在 spec 中显式记录；后续可通过临时目录+rename 两阶段提交优化（不在本刀范围）。

## 5. 验收口径

### 5.1 行为断言

- 启用参数齐备时：`run_backtest` 会将本次 run 的 sell-side audit 物化为 `var/artifacts/m3_lifecycle_logs/...` 与 `var/ledgers/m3_lifecycle_logs/...`。
- 物化结果可被：
  - `read_decision_m3_lifecycle_log_ledger/read_decision_m3_lifecycle_log` 读回；
  - `/api/m3/lifecycle-logs` read/list/download/download-ledger 查询与下载。

### 5.2 单测

- 基于现有 `test_lowfreq_engine_v16_sell_logic.py` 的 sell audit 生产路径：
  - 触发 `engine.check_sell_signal_v2(...)` 产生 `_sell_signal_audit_current_run`
  - 调用 helper 做 materialize
  - 断言对应 record_id 的 artifact/ledger 存在，且 `DecisionLifecycleLog` 可读回

### 5.3 Checklist 快照回写

- 在 “决策可审计” 下补充 “engine→落盘→API readback”的证据链接（helper + 单测）。

## 6. 风险与回滚

- 风险：修改 `run_backtest` 签名（新增可选参数）；默认不启用不影响现有调用。
- 回滚：移除 helper 与 `run_backtest` 末尾调用；不影响已落盘文件（读回仍可用）。

