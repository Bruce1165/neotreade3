# Status: draft
# Owner: platform / orchestration
# Scope: Pass project_root/run_id/source_run_id into lowfreq backtest to enable lifecycle log materialization
# Canonical: self
# Supersedes: none
# Superseded_by: none
# Last_reviewed: 2026-07-17

## 1. 目标

让“真实 backtest”（report runner 路径）在调用 `engine.run_backtest(...)` 时补齐 `project_root/run_id/source_run_id`，从而触发 lowfreq engine 侧的 M3 lifecycle log 自动物化：

- `sell_signal_audit → build_decision_lifecycle_logs → materialize_decision_m3_lifecycle_log`
- 产物落盘到 `var/artifacts/m3_lifecycle_logs` 与 `var/ledgers/m3_lifecycle_logs`

## 2. 边界

### 2.1 In scope

- 在 `neotrade3/orchestration/report_runner_backtest_source.py` 的 `engine.run_backtest(...)` 调用处传入：
  - `project_root=service.project_root`
  - `run_id/source_run_id`：复用 API 的 backtest `report_id` 生成规则
- 更新对应单测 `tests/unit/test_lowfreq_report_runner_backtest_source.py` 以适配随机 report_id（仅断言前缀与一致性）。
- checklist 快照证据回写（补“真实 backtest 路径触发落盘”的证据链接）。

### 2.2 Out of scope

- 修改 lowfreq engine 的 backtest 计算逻辑与 sell audit 生产内容。
- 调整 lifecycle log store / API。
- 将 report runner 的产物（pdf/json）与 lifecycle log 做强绑定目录结构（本刀仅触发物化，不做归档聚合）。

## 3. 现状证据（可核验）

- report runner 当前调用 `run_backtest` 未传入 project_root/run_id/source_run_id：
  - [report_runner_backtest_source.py:L30-L40](file:///Users/mac/NeoTrade3/neotrade3/orchestration/report_runner_backtest_source.py#L30-L40)
- lowfreq engine 仅在三参齐备时物化 lifecycle logs：
  - [lowfreq_engine_v16_advanced.py:L4032-L4040](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L4032-L4040)
- API 侧已有稳定的 report_id 生成规则（可复用）：
  - [main.py:L24511-L24516](file:///Users/mac/NeoTrade3/apps/api/main.py#L24511-L24516)

## 4. 设计

### 4.1 run_id/source_run_id 口径（复用 API report_id）

在 report runner 侧生成 `effective_report_id`，规则与 API 对齐：

- `lowfreq_v16_{start_key}_{end_key}__{stamp}_{uuid8}`
- `stamp` 使用 UTC 时间戳：`%Y%m%dT%H%M%SZ`

并设置：

- `run_id = effective_report_id`
- `source_run_id = effective_report_id`

说明：当前 report runner 没有上游“source_run_id”事实来源，因此最小闭环采用“本次 run 即 source”。未来若引入 orchestrator/screener 的上游 run_id，再扩展为 `source_run_id=upstream_run_id`。

### 4.2 project_root 传递

直接传 `project_root=service.project_root`（该值在 `BootstrapApiService.__init__` 中为 `Path(project_root)`）。

### 4.3 行为与失败策略

- 该变更不改变 `run_backtest` 的默认行为，只是让 report runner 路径“显式启用” lifecycle log 物化。
- 物化失败策略遵循 engine 侧 fail-closed：若落盘/contract 失败，异常向上抛出（由 report runner 调用方决定是否捕获）。

## 5. 验收口径

### 5.1 行为断言

- `load_lowfreq_report_backtest_payload(...)` 在调用 `engine.run_backtest(...)` 时：
  - 传入 `project_root=service.project_root`
  - 传入 `run_id/source_run_id` 且二者相等，且以 `lowfreq_v16_{start}_{end}__` 开头

### 5.2 单测

- 在 `tests/unit/test_lowfreq_report_runner_backtest_source.py`：
  - FakeService 增加 `project_root` 属性（Path）
  - FakeEngine.run_backtest 接收并记录 `project_root/run_id/source_run_id`
  - 断言：
    - `project_root` 被透传
    - `run_id == source_run_id`
    - `run_id` 前缀符合日期区间（包含 start/end）

### 5.3 checklist 快照回写

- 在 “决策可审计” 下补充 “report runner 路径为真实 backtest 启用 lifecycle log 物化”的证据链接（report_runner + 单测）。

## 6. 风险与回滚

- 风险：新增依赖 `datetime/timezone/uuid` 用于生成 report_id（仅用于 run_id/source_run_id，不改变回测计算本身）。
- 回滚：移除 report runner 传参即可恢复旧行为（不再自动物化）。

