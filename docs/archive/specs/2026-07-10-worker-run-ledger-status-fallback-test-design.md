# Worker Run Ledger Status Fallback Test Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `worker main` 的状态回退契约测试对齐：为 `apps/worker/main.py` 中已存在的 `run_ledger.status` 回退逻辑补上最小单测，覆盖“当 `snapshot.status` 缺失时，CLI 输出状态回退到 `orchestration.run_ledger.status`”这一行为，不扩展到 `orchestration_run_view()`、API key、factor matrix 或其他测试主题。

目标是：

- 让 `tests/unit/test_bootstrap_skeleton.py` 明确覆盖 `apps/worker/main.py` 的 `run_ledger.status` 回退分支
- 保持当前 `worker main` 的 `0/1` 退出码与输出 `status` 契约可核验
- 将剩余混合测试 diff 中一条可独立解释的 worker 状态主题切出来

本切片不是：

- `apps/api/main.py` 的 `orchestration_run_view()` 聚合状态测试
- legacy `X-API-Key` header 契约调整
- `factor_matrix_daily_output_supports_live_and_stored_modes()` 的断言扩展
- `test_v1_screener_results_endpoint_returns_not_implemented()` 的位置移动
- `apps/worker/main.py` 的生产代码修改

## 2. Scope

Included:

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`

Excluded:

- `apps/worker/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中相邻的 `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
- `tests/unit/test_bootstrap_skeleton.py` 中 API handler / factor matrix / v1 endpoint 相关 hunk
- 其他任何生产文件与文档

## 3. Existing Context

当前代码已经给出直接证据：

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L663-L669) 先读取 `snapshot.get("status")`
- 若 `snapshot.status` 缺失，则回退读取 `orchestration.run_ledger.status`
- 最终 `status = str(snapshot.get("status") or run_ledger_status or "ok").strip().lower()`
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1406-L1471) 已覆盖两条相邻契约：
  - `status == "blocked"` 时返回码为 `1`
  - `status == "ok"` 时返回码为 `0`
- 当前剩余 diff 中新增的 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing` 正好覆盖尚未被现有测试显式命中的回退分支

现状风险：

- 如果整体提交 `tests/unit/test_bootstrap_skeleton.py`，会把 worker 状态回退测试与 orchestration / API / factor matrix 多条主题混成脏切片
- 如果顺手修改 `apps/worker/main.py`，会把“已存在契约的测试补齐”扩大成生产实现主题
- 如果把相邻的 `orchestration_run_view` 测试一起带上，本轮边界会从 worker CLI 状态回退扩大到 API 状态聚合

## 4. Approach Options

### Option A: 只提交 worker `run_ledger.status` 回退测试（推荐）

仅处理：

- `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`

Pros:

- 边界最窄，只覆盖 `apps/worker/main.py` 已存在的一条明确分支
- 与相邻的 `blocked/ok` 测试形成完整且连续的 worker CLI 状态测试组
- 不需要改生产代码

Cons:

- `orchestration_run_view` 的共享状态测试仍需后续独立治理

### Option B: 同时提交 worker 回退测试 + `orchestration_run_view` 共享状态测试

Pros:

- 一次性减少两条新增测试 drift

Cons:

- 会把 worker CLI 主题与 API 状态聚合主题混在一起
- 边界明显变宽

### Option C: 直接修改 `apps/worker/main.py` 并补测试

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

- `apps/worker/main.py`
  - 继续保留现有 `snapshot.status -> run_ledger.status -> "ok"` 的回退顺序
- `tests/unit/test_bootstrap_skeleton.py`
  - 为 `worker main` 新增一条只验证回退分支的最小单测

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. 新增 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
2. 该测试只构造：
   - 无顶层 `status` 的 snapshot
   - `orchestration.run_ledger.status == "blocked"`
   - `summary` 与 `target_date` 的最小必要字段
3. 断言：
   - `worker_main.main() == 1`
   - CLI 输出中的 `payload["status"] == "blocked"`

本轮不允许顺手改动：

- `apps/worker/main.py`
- 相邻的 `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
- `test_bootstrap_api_handler_accepts_screener_run_post`
- `test_v1_screener_results_endpoint_returns_not_implemented`
- `test_factor_matrix_daily_output_supports_live_and_stored_modes`

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `apps/worker/main.py`
- 不重构相邻 `worker_main` 既有测试
- 不把 `orchestration_run_view` 共享状态测试一起提交
- 若无法从 `tests/unit/test_bootstrap_skeleton.py` 的混合 diff 中仅隔离这条 worker 测试，则应停止并报告边界问题

## 6. Testing Design

验证优先采用：

1. 针对新测试本身的最小 pytest 选择执行
2. 确认该测试与相邻 `blocked/ok` 既有测试形成连续且自洽的状态契约组

默认不要求：

- 跑整份 `test_bootstrap_skeleton.py`
- 扩大到 `orchestration_run_view`、API handler 或 factor matrix 相关测试
- 修改生产代码再做更大回归

原因：

- 本轮风险主要在边界纯度，而不是实现正确性
- `apps/worker/main.py` 当前已有直接代码证据表明逻辑存在

## 7. Validation

预期验证方式：

- 运行 `tests/unit/test_bootstrap_skeleton.py -k worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- 确认本轮 staged diff 只包含该单测
- 确认 `apps/worker/main.py` 不进入提交

## 8. Commit Boundary

目标提交应限制为：

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`

必须排除：

- `apps/worker/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中其他 hunk
- `apps/api/main.py`
- 其他配置、文档和前端文件

若相对 `HEAD` 无法将该测试与相邻新增测试安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
