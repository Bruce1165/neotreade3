# Orchestration Shared Status Test Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `orchestration_run_view` 的共享状态测试对齐：为 `tests/unit/test_bootstrap_skeleton.py` 中 `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses` 补齐或隔离一条最小测试，用来验证当 snapshot 没有顶层 `status`、也没有 `orchestration.run_ledger.status` 时，`BootstrapApiService.orchestration_run_view()` 会基于 `task_results` 的共享状态汇总结果生成 `orchestrator_run.status`、`artifact.status` 与 `_meta.status`。

目标是：

- 让 `apps/api/main.py` 里已存在的 `_resolve_orchestration_snapshot_status()` 分支有直接测试覆盖
- 明确 `status_counts` 与最终共享状态之间的契约
- 从 `tests/unit/test_bootstrap_skeleton.py` 的剩余混合 diff 中切出一条单一 API 状态聚合主题

本切片不是：

- `apps/api/main.py` 的生产逻辑改动
- `worker_main` 的状态回退主题
- legacy `X-API-Key` header 契约调整
- factor matrix 相关断言扩展
- `v1_screener_results_endpoint` 的位置搬移

## 2. Scope

Included:

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`

Excluded:

- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中 worker / API handler / factor matrix / v1 endpoint 相邻 hunk
- 其他任何生产文件与文档

## 3. Existing Context

当前代码已经给出直接证据：

- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1356-L1377) 会先收集 `all_results`，计算 `status_counts`，再写入 `run_ledger_payload`
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1362) 将 `overall_status` 交给 `_resolve_orchestration_snapshot_status(snapshot)`
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L2148-L2164) 的 `_resolve_orchestration_snapshot_status()` 顺序为：
  - 先看 snapshot 顶层 `status`
  - 再看 `orchestration.run_ledger.status`
  - 都没有时，基于 `task_results[].status` 走 shared-status 汇总
- 当前新增测试 [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1338-L1403) 构造了两个任务状态：
  - `ok`
  - `skipped`
- 现有断言要求：
  - `payload["_meta"]["status"] == "skipped"`
  - `payload["orchestrator_run"]["status"] == "skipped"`
  - `ledger_payload["status"] == "skipped"`
  - `ledger_payload["status_counts"] == {"ok": 1, "skipped": 1}`
  - `artifact_payload["status"] == "skipped"`

现状风险：

- 如果整体提交 `tests/unit/test_bootstrap_skeleton.py`，会把 orchestration 共享状态测试与 API key / factor matrix / 其他主题混成脏切片
- 如果顺手改动 `apps/api/main.py`，会把“测试补齐”扩大成生产实现主题
- 如果把 worker 测试或 API handler 变更一起带上，本轮边界会从 API 状态聚合扩大到多主题混合提交

## 4. Approach Options

### Option A: 只提交 orchestration shared-status 测试（推荐）

仅处理：

- `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`

Pros:

- 边界最窄，只覆盖 `orchestration_run_view()` 的一条现有状态汇总契约
- 直接命中 `_resolve_orchestration_snapshot_status()` 的 shared-status 分支
- 不需要改生产代码

Cons:

- API handler / factor matrix 等剩余测试主题仍需后续独立治理

### Option B: 同时提交 orchestration shared-status 测试 + API handler 契约测试

Pros:

- 一次性减少两条测试 drift

Cons:

- 会把状态聚合主题和接口 header 主题混在一起
- 边界明显变宽

### Option C: 修改 `apps/api/main.py` 并补测试

Pros:

- 表面上“实现+测试”更完整

Cons:

- 当前无证据表明生产逻辑缺失
- 会把已存在契约误包装为新实现

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `apps/api/main.py`
  - 继续保留现有 `top_level_status -> run_ledger.status -> shared task status` 的解析顺序
- `tests/unit/test_bootstrap_skeleton.py`
  - 为 `orchestration_run_view()` 新增或保留一条只验证 shared-status 聚合分支的最小单测

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
2. 该测试只构造：
   - 无顶层 `status`
   - 无 `orchestration.run_ledger.status`
   - `task_results` 中混合 `ok` 与 `skipped`
3. 断言：
   - 返回值 `_meta.status == "skipped"`
   - `orchestrator_run.status == "skipped"`
   - ledger 文件 `status == "skipped"`
   - ledger 文件 `status_counts == {"ok": 1, "skipped": 1}`
   - artifact 文件 `status == "skipped"`

本轮不允许顺手改动：

- `apps/api/main.py`
- `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- `test_bootstrap_api_handler_accepts_screener_run_post`
- `test_v1_screener_results_endpoint_returns_not_implemented`
- `test_factor_matrix_daily_output_supports_live_and_stored_modes`

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `apps/api/main.py`
- 不扩展到 API handler 或 worker 主题
- 不改测试文件中相邻的其他 hunk
- 若无法从 `tests/unit/test_bootstrap_skeleton.py` 的混合 diff 中仅隔离这条 orchestration 测试，则应停止并报告边界问题

## 6. Testing Design

验证优先采用：

1. 针对这条测试本身的最小 pytest 选择执行
2. 确认它只覆盖 shared-status 聚合分支，而不是顶层 `status` 或 `run_ledger.status` 分支

默认不要求：

- 跑整份 `test_bootstrap_skeleton.py`
- 扩大到 API handler、worker 或 factor matrix 测试
- 修改生产代码再做更大回归

原因：

- 本轮风险主要在边界纯度，而不是实现正确性
- `apps/api/main.py` 当前已有直接代码证据表明逻辑存在

## 7. Validation

预期验证方式：

- 运行 `tests/unit/test_bootstrap_skeleton.py -k orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
- 确认本轮 staged diff 只包含该单测
- 确认 `apps/api/main.py` 不进入提交

## 8. Commit Boundary

目标提交应限制为：

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`

必须排除：

- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中其他 hunk
- 其他配置、文档和前端文件

若相对 `HEAD` 无法将该测试与相邻新增测试安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
