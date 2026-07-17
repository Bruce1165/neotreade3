# Status: draft
# Owner: platform / m3
# Scope: Standardize report_id → m3_lifecycle_log record_id mapping
# Canonical: self
# Supersedes: none
# Superseded_by: none
# Last_reviewed: 2026-07-17

## 1. 目标

将 report runner 回测输出中的 `_meta.report_id` 与 M3 lifecycle log 的 `record_id` 映射规则固化为单一 helper，避免调用方自行拼接导致不一致或路径安全问题。

## 2. 规则

### 2.1 关键事实

- `report_id` 是本次 backtest 的 `run_id`（并且 `source_run_id == run_id`，在 report runner 路径的最小闭环里成立）。
- M3 lifecycle log 的 `record_id` 格式固定为：
  - `{stock_code}-{run_id}`

因此，想要通过 report_id 读回 lifecycle log，必须同时知道 `stock_code`。

### 2.2 Helper（唯一入口）

- `neotrade3/decision_engine/lifecycle_log_store.py`
  - `build_decision_m3_lifecycle_log_record_id_from_report_id(stock_code, report_id) -> record_id`

该 helper 复用 `build_decision_m3_lifecycle_log_record_id(...)` 的 fail-closed 校验：

- `stock_code` / `report_id` 不能为空
- `record_id` 必须是单段路径（防 path traversal）

## 3. 调用示例

### 3.1 从 report payload 读回 lifecycle log

1) 从 report payload 取 `report_id`：

- `report_id = report_payload["_meta"]["report_id"]`

2) 构造 `record_id`：

- `record_id = build_decision_m3_lifecycle_log_record_id_from_report_id(stock_code=code, report_id=report_id)`

3) 调用 API：

- `GET /api/m3/lifecycle-logs/{record_id}`

## 4. 验收口径

- helper 单测覆盖正常映射与 fail-closed 边界
- 存在串联单测证明：report_id → record_id → API 读回可行
