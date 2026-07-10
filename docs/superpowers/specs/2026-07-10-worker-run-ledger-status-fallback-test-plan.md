# Worker Run Ledger Status Fallback Test 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-worker-run-ledger-status-fallback-test-design.md`

## 1. 目标

本计划只覆盖 `worker main` 的状态回退测试对齐：在不改动 `apps/worker/main.py` 生产逻辑的前提下，隔离并提交 `tests/unit/test_bootstrap_skeleton.py` 中 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing` 这一条新增单测，用来验证当顶层 `snapshot.status` 缺失时，CLI 输出状态会回退到 `orchestration.run_ledger.status`。

本轮目标只有三个：

1. 让 `worker_main.main()` 的 `run_ledger.status` 回退分支具备直接测试覆盖。
2. 保持相邻 `blocked/ok` 测试和生产代码不变。
3. 在不卷入同文件其他测试主题的前提下，形成一个可独立解释的 worker CLI 状态契约切片。

本轮必须产出的核心结果：

- `tests/unit/test_bootstrap_skeleton.py` 新增 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- 提交中不包含 `apps/worker/main.py`
- 提交中不包含 `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
- 提交中不包含 API handler / factor matrix / v1 endpoint 相关 hunk

## 2. 不在本轮完成

- `apps/worker/main.py` 生产代码修改
- `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
- `test_bootstrap_api_handler_accepts_screener_run_post` 的 header/status 断言调整
- `test_v1_screener_results_endpoint_returns_not_implemented` 的位置调整
- `test_factor_matrix_daily_output_supports_live_and_stored_modes` 的断言扩展
- 其他文档、配置或前端文件

## 3. 当前实施起点

### 3.1 已有现实基础

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L663-L669) 已存在 `snapshot.status` 缺失时回退读取 `orchestration.run_ledger.status` 的逻辑
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1406-L1505) 中已有两条相邻测试：
  - `test_worker_main_returns_nonzero_for_blocked_snapshot`
  - `test_worker_main_returns_zero_for_ok_snapshot`
- 当前剩余 diff 中的 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing` 与上述两条测试连续排布，语义集中在 worker CLI 状态
- 该测试只依赖：
  - monkeypatch 的 `parse_args`
  - `require_python_310` 与 `log_python_runtime` stub
  - 一个仅返回 `orchestration.run_ledger.status = "blocked"` 的假 `BootstrapWorkerApp`

### 3.2 结构性风险

- 最大风险不是测试内容本身，而是从 `tests/unit/test_bootstrap_skeleton.py` 的混合 diff 中误带入其他主题
- 如果顺手修改 `apps/worker/main.py`，本轮会从“测试补齐”扩大成生产实现主题
- 如果把相邻 `orchestration_run_view` 或 API handler 变更一起提交，本轮就失去单一 worker CLI 主题的纯度

## 4. 实施原则

- 只改 `tests/unit/test_bootstrap_skeleton.py`
- 只保留 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- 不改 `apps/worker/main.py`
- 不重构相邻 `worker_main` 既有测试
- 不改测试文件中的其他 hunk
- 若无法安全隔离该单测，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `tests/unit/test_bootstrap_skeleton.py`

允许的逻辑：

- 新增 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- 构造无顶层 `status` 的 snapshot
- 通过 `orchestration.run_ledger.status == "blocked"` 触发回退分支
- 断言返回码与 CLI 输出状态均为 `blocked`

明确不改：

- `apps/worker/main.py`
- `test_worker_main_returns_nonzero_for_blocked_snapshot`
- `test_worker_main_returns_zero_for_ok_snapshot`
- `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
- API handler / factor matrix / v1 endpoint 相邻改动

## 6. 总体分段

本计划建议分为四段执行：

- `WRL-R1`：冻结 worker 回退测试的精确边界
- `WRL-R2`：只保留该单测并排除相邻主题
- `WRL-R3`：做最小验证
- `WRL-R4`：隔离单测 hunk 并提交

## 7. 分段实施计划

### WRL-R1：冻结 worker 回退测试的精确边界

目标：

- 明确 `tests/unit/test_bootstrap_skeleton.py` 中哪些改动属于 worker CLI 状态回退测试，哪些相邻改动必须排除。

任务：

- 读取相邻 `worker_main` 测试块与新增测试块
- 对照 `HEAD` 检查 `tests/unit/test_bootstrap_skeleton.py` 剩余 diff
- 只标记以下目标点位：
  - `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- 显式排除：
  - `test_orchestration_run_view_uses_shared_status_for_mixed_task_statuses`
  - API handler 相关 hunk
  - factor matrix 相关 hunk

完成判定：

- include / exclude 列表明确
- 该单测与同文件其他主题边界清楚分开

### WRL-R2：只保留 worker 回退单测

目标：

- 在不改变现有生产代码与相邻测试语义的前提下，保留这条最小 worker 状态回退单测。

任务：

- 确认测试内容仅包含：
  - `parse_args` stub
  - runtime/noise 依赖 stub
  - `_RunLedgerOnlyApp`
  - `main() == 1`
  - `payload["status"] == "blocked"`
- 若当前工作区测试文件同时混有其他主题，优先采用仅隔离目标 hunk 的方式处理

关键约束：

- 不修改 `apps/worker/main.py`
- 不调整相邻 `blocked/ok` 既有测试
- 不补充与本轮无关的新断言
- 不引入额外 helper

完成判定：

- 新增测试只表达 `run_ledger.status` 回退契约
- 相邻既有测试与其他主题保持原状

### WRL-R3：做最小验证

目标：

- 证明该单测本身成立，并且无需扩大到更大范围回归。

任务：

- 运行：
  - `python3 -m pytest tests/unit/test_bootstrap_skeleton.py -k worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- 若验证失败，先判断是：
  - 边界隔离问题
  - 测试构造问题
  - 还是生产契约与设计证据不一致
- 只有在证据明确要求时才重新评估边界，不能自动扩大范围

完成判定：

- 目标测试通过
- 无需修改 `apps/worker/main.py`

### WRL-R4：隔离单测 hunk 并提交

目标：

- 生成一个单一目的的测试提交，只表达 worker CLI 的 `run_ledger.status` 回退测试补齐。

任务：

- 检查 `git diff HEAD -- tests/unit/test_bootstrap_skeleton.py`
- 只暂存 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`
- 排除同文件其他新增或调整
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含该单测
- staged diff 不含 `apps/worker/main.py`
- staged diff 不含同文件其他主题

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `worker_main` 相邻三条测试的连续区块
2. 对照 `HEAD` 确认新增单测的完整 hunk
3. 只保留这条测试
4. 跑最小 pytest 验证
5. 再检查 `HEAD`-relative diff
6. 只暂存目标 hunk

原因：

- 先冻结边界，再做隔离，能避免把同文件里的 API / orchestration / factor matrix 主题一起带入
- 先跑最小测试，再决定是否提交，能把风险控制在单一 worker CLI 契约上

## 9. 建议提交切分

建议单一提交：

### Commit WRL：worker run ledger status fallback test

范围：

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_worker_main_uses_run_ledger_status_when_snapshot_status_is_missing`

目的：

- 为已存在的 `worker_main` 状态回退逻辑补上最小测试覆盖

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成“worker 测试 + API 测试 + factor matrix 断言”的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `tests/unit/test_bootstrap_skeleton.py` 新增该单测
2. 该单测通过
3. `apps/worker/main.py` 不改
4. `tests/unit/test_bootstrap_skeleton.py` 其他主题不进入提交
5. 提交中能被单独解释为“worker run_ledger status fallback test”

## 11. 风险提示

- 最大风险是测试文件混合 diff 过宽，导致单测难以隔离
- 第二风险是把已有生产逻辑误判为“需要补实现”
- 第三风险是为了顺手清理相邻测试而扩大到 API 或 orchestration 主题

## 12. 结论

本计划的核心不是“整理整个 `test_bootstrap_skeleton.py`”，而是完成一条可独立解释的 worker CLI 状态测试线：

- 只保留 `run_ledger.status` 回退单测
- 只做最小 pytest 验证
- 只在相对 `HEAD` 能保持原子性的前提下提交

这样后续如需处理 `orchestration_run_view` 或 API handler 的剩余测试主题，仍可作为独立切片继续推进。
