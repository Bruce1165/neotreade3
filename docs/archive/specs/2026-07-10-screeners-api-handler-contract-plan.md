# Screeners API Handler Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-screeners-api-handler-contract-design.md`

## 1. 目标

本计划只覆盖 `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_accepts_screener_run_post` 的活跃 `screeners` POST 契约对齐：在不修改 `apps/api/http.py` 与 `apps/api/main.py` 生产逻辑的前提下，隔离并提交这条测试里的三类最小变化，用来让测试准确描述当前仍在 NeoTrade3 新体系中生效的 API handler 行为。

本轮目标只有三个：

1. 让 `POST /api/screeners/run` 的首次请求头断言与现行 HTTP 契约对齐。
2. 让 `POST /api/screeners/bulk-run` 的状态断言与现行 service 返回结构对齐。
3. 在不卷入 `v1` 占位壳、`factor matrix` 或 invalid legacy key 测试的前提下，形成一个可独立解释的 `screeners` API handler 契约切片。

本轮必须产出的核心结果：

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_accepts_screener_run_post` 完成最小契约对齐
- 提交中不包含 `apps/api/http.py`
- 提交中不包含 `apps/api/main.py`
- 提交中不包含 `test_v1_screener_results_endpoint_returns_not_implemented`
- 提交中不包含 `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- staged diff 只表达 `screeners` 活跃 POST 契约

## 2. 不在本轮完成

- `apps/api/http.py` 生产逻辑修改
- `apps/api/main.py` 生产逻辑修改
- `test_bootstrap_api_handler_rejects_invalid_legacy_api_key_on_post`
- `test_v1_screener_results_endpoint_returns_not_implemented`
- `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- `screeners` 下载链路
- 其他文档、配置或前端文件

## 3. 当前实施起点

### 3.1 已有现实基础

- [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2228-L2365) 仍显式注册：
  - `POST /api/screeners/run`
  - `POST /api/screeners/bulk-run`
- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L88-L100) 已明确 `_accept_legacy_api_key()` 的语义：
  - `X-API-Key` 仅保留为 backward-compatible header contract
  - active local write paths 不再由它强制拦截
- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L201-L219) 的 `do_POST()` 入口实际调用 `_accept_legacy_api_key()`
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L2069-L2122) 已明确 `screeners_bulk_run_view()` 返回：
  - `_meta.status == bulk_status`
  - `bulk_run.status == bulk_status`
  - `bulk_run.run_ledgers` 为返回结构的一部分
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1719-L1958) 中当前剩余 diff 已集中到三处对齐点：
  - 首次 `screeners/run` POST 去掉 `X-API-Key`
  - `bulk-run` 状态断言与 `bulk_run.status` 对齐
  - `bulk_run.run_ledgers` 长度断言

### 3.2 结构性风险

- 最大风险不是测试内容本身，而是从 `tests/unit/test_bootstrap_skeleton.py` 的混合 diff 中误带入 `v1` 占位壳与 `factor matrix` 主题
- 如果顺手修改 `apps/api/http.py`，会把“测试契约收口”扩大成 HTTP 行为变更
- 如果顺手修改 `apps/api/main.py`，会把“测试对齐”扩大成 service 契约变更
- 如果错误删除 invalid legacy key 的 401 测试，会破坏当前仍保留的兼容边界

## 4. 实施原则

- 只改 `tests/unit/test_bootstrap_skeleton.py`
- 只保留 `test_bootstrap_api_handler_accepts_screener_run_post` 中与活跃 POST 契约直接相关的 hunk
- 不改 `apps/api/http.py`
- 不改 `apps/api/main.py`
- 不改 invalid legacy key 测试
- 不改 `v1` compatibility 与 `factor matrix` 相邻测试
- 若无法安全隔离目标 hunk，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `tests/unit/test_bootstrap_skeleton.py`

允许的逻辑：

- 将首次 `POST /api/screeners/run` 的 header 断言对齐为仅传 `Content-Type`
- 将 `bulk-run` 的 `_meta.status` 断言从固定 `"ok"` 对齐为 `payload["bulk_run"]["status"]`
- 为 `bulk_run.run_ledgers` 增加最小结构断言

明确不改：

- `apps/api/http.py`
- `apps/api/main.py`
- invalid legacy key 的 401 断言
- `v1` results not implemented 测试
- `factor matrix` / `lab artifact` 相邻改动

## 6. 总体分段

本计划建议分为四段执行：

- `SAH-R1`：冻结 `screeners` API handler 契约测试的精确边界
- `SAH-R2`：只保留活跃 POST 契约相关 hunk
- `SAH-R3`：做最小验证
- `SAH-R4`：隔离目标 hunk 并提交

## 7. 分段实施计划

### SAH-R1：冻结 `screeners` API handler 契约测试的精确边界

目标：

- 明确 `tests/unit/test_bootstrap_skeleton.py` 中哪些改动属于 `screeners` 活跃 POST 契约，哪些相邻改动必须排除。

任务：

- 读取 `test_bootstrap_api_handler_accepts_screener_run_post` 完整区块
- 对照 `HEAD` 检查该测试周围的剩余 diff
- 只标记以下目标点位：
  - 首次 `screeners/run` POST header
  - `bulk-run` `_meta.status`
  - `bulk_run.run_ledgers`
- 显式排除：
  - invalid legacy key 测试
  - `v1` endpoint 测试
  - `factor matrix` 相关 hunk

完成判定：

- include / exclude 列表明确
- 该测试与同文件其他主题边界清楚分开

### SAH-R2：只保留活跃 POST 契约相关 hunk

目标：

- 在不改变现有生产代码与相邻测试语义的前提下，只保留 `screeners` 活跃 POST 契约相关断言。

任务：

- 确认首次 `screeners/run` POST 只保留 `Content-Type` header 仍可成功
- 确认 `bulk-run` 状态断言只对齐到 `payload["bulk_run"]["status"]`
- 确认 `run_ledgers` 结构断言保持最小，只验证当前样例下长度为 `2`
- 若当前工作区测试文件同时混有其他主题，优先采用仅隔离目标 hunk 的方式处理

关键约束：

- 不修改 `apps/api/http.py`
- 不修改 `apps/api/main.py`
- 不删除 invalid key 的 401 测试
- 不扩展 async 分支、下载分支或其他额外断言

完成判定：

- 目标测试只表达 `screeners` 活跃 POST 契约
- 相邻既有测试与其他主题保持原状

### SAH-R3：做最小验证

目标：

- 证明该测试本身成立，并且无需扩大到更大范围回归。

任务：

- 运行：
  - `python3 -m pytest tests/unit/test_bootstrap_skeleton.py -k bootstrap_api_handler_accepts_screener_run_post`
- 若验证失败，先判断是：
  - 边界隔离问题
  - 测试断言问题
  - 还是生产契约与设计证据不一致
- 只有在证据明确要求时才重新评估边界，不能自动扩大范围

完成判定：

- 目标测试通过
- 无需修改 `apps/api/http.py` 或 `apps/api/main.py`

### SAH-R4：隔离目标 hunk 并提交

目标：

- 生成一个单一目的的测试提交，只表达 `screeners` 活跃 POST 契约对齐。

任务：

- 检查 `git diff HEAD -- tests/unit/test_bootstrap_skeleton.py`
- 只暂存 `test_bootstrap_api_handler_accepts_screener_run_post` 中目标 hunk
- 排除同文件中的 `v1`、`factor matrix` 与 invalid legacy key 相邻主题
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含该测试主题相关 hunk
- staged diff 不含 `apps/api/http.py`
- staged diff 不含 `apps/api/main.py`
- staged diff 不含同文件其他主题

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读目标测试完整区块
2. 对照 `HEAD` 确认目标 hunk 的精确范围
3. 只保留活跃 POST 契约相关断言
4. 跑最小 pytest 验证
5. 再检查 `HEAD`-relative diff
6. 只暂存目标 hunk

原因：

- 先冻结边界，再做隔离，能避免把 `v1` 与 `factor matrix` 主题一起带入
- 先跑最小测试，再决定是否提交，能把风险控制在单一 `screeners` API handler 契约上

## 9. 建议提交切分

建议单一提交：

### Commit SAH：screeners API handler contract

范围：

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_accepts_screener_run_post` 的最小契约对齐

目的：

- 让测试准确描述当前仍在运行期生效的 `screeners` POST 契约

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成“screeners + v1 + factor matrix”的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `test_bootstrap_api_handler_accepts_screener_run_post` 完成三处最小对齐
2. 目标测试通过
3. `apps/api/http.py` 不改
4. `apps/api/main.py` 不改
5. `tests/unit/test_bootstrap_skeleton.py` 其他主题不进入提交
6. 提交能被单独解释为“screeners API handler contract”

## 11. 风险提示

- 最大风险是测试文件混合 diff 过宽，导致目标 hunk 难以隔离
- 第二风险是把现有 HTTP 兼容策略误读成“应该彻底删除 legacy header 契约”
- 第三风险是为了顺手清理相邻测试而扩大到 `v1` compatibility 或 `factor matrix`

## 12. 结论

本计划的核心不是“整理整个 `test_bootstrap_skeleton.py`”，而是完成一条可独立解释的 `screeners` 活跃 POST 契约测试线：

- 只保留三处直接对齐点
- 只做最小 pytest 验证
- 只在相对 `HEAD` 能保持原子性的前提下提交

这样后续如需处理 `factor matrix` 或其他低价值兼容测试主题，仍可作为独立切片继续推进。
