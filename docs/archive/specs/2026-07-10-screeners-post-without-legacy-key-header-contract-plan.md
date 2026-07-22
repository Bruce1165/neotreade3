# Screeners Post Without Legacy Key Header Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-screeners-post-without-legacy-key-header-contract-design.md`

## 1. 目标

本计划只覆盖 `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()` 的恢复实施：在不修改 `apps/api/http.py` 与 `apps/api/main.py` 生产逻辑的前提下，隔离并提交这一个测试函数，用来恢复当前 NeoTrade3 活跃 POST 契约的直接测试证据。

本轮目标只有三个：

1. 恢复 `/api/screeners/run` 在无 `X-API-Key` 请求头时可成功 POST 的测试证据。
2. 保持 invalid legacy key 的 `401` 兼容边界测试不变。
3. 在不卷入 `v1` 占位壳与 `F3` 相邻主题的前提下，形成一个可独立解释的单一测试切片。

本轮必须产出的核心结果：

- `tests/unit/test_bootstrap_skeleton.py` 中目标测试函数被恢复
- 提交中不包含 `apps/api/http.py`
- 提交中不包含 `apps/api/main.py`
- 提交中不包含 `test_v1_screener_results_endpoint_returns_not_implemented`
- 提交中不包含 `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- staged diff 只表达“恢复无 `X-API-Key` POST 契约测试”

## 2. 不在本轮完成

- `apps/api/http.py` 生产逻辑修改
- `apps/api/main.py` 生产逻辑修改
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_rejects_invalid_legacy_api_key_on_post`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_v1_screener_results_endpoint_returns_not_implemented`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- 其他文档、配置、前端或运行时实现文件

## 3. 当前实施起点

### 3.1 已有现实基础

- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L88-L100) 已明确 `_accept_legacy_api_key()` 的语义：
  - `X-API-Key` 仅保留为 backward-compatible header contract
  - active local write paths 不再强制门禁
- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L201-L219) 的 `do_POST()` 调用 `_accept_legacy_api_key()`，不是 `_require_api_key()`
- 当前工作区 [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L2008-L2068) 缺失了目标测试函数
- `HEAD` 版本仍包含目标测试函数，且请求头仅包含 `Content-Type`（无 `X-API-Key`）

### 3.2 结构性风险

- 最大风险不是测试内容，而是从同一文件混合 diff 中误带入 `v1` 占位壳或 `F3` 主题
- 如果顺手改动 `apps/api/http.py` 或 `apps/api/main.py`，会把“恢复测试证据”扩大成实现改造
- 如果误动 invalid key 的 `401` 测试，会破坏当前兼容边界

## 4. 实施原则

- 只改 `tests/unit/test_bootstrap_skeleton.py`
- 只恢复 `test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()`
- 不改 `apps/api/http.py`
- 不改 `apps/api/main.py`
- 不改 invalid key 的 `401` 测试
- 不改 `v1` 占位壳测试
- 不改 `F3` lab signal 相邻主题
- 若无法安全隔离目标 hunk，则停止提交，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `tests/unit/test_bootstrap_skeleton.py`

允许的逻辑：

- 恢复 `HEAD` 中目标测试函数的最小语义
- 请求头只包含 `Content-Type: application/json`
- 断言 POST 成功并返回 `screener_id` 与 `target_date`
- 保留该函数对应的 cleanup

明确不改：

- `apps/api/http.py`
- `apps/api/main.py`
- `test_bootstrap_api_handler_rejects_invalid_legacy_api_key_on_post`
- `test_v1_screener_results_endpoint_returns_not_implemented`
- `test_factor_matrix_daily_output_supports_live_and_stored_modes`

## 6. 总体分段

本计划建议分为四段执行：

- `SKH-R1`：冻结目标测试函数的精确边界
- `SKH-R2`：只恢复目标测试函数
- `SKH-R3`：做最小验证
- `SKH-R4`：隔离目标 hunk 并提交

## 7. 分段实施计划

### SKH-R1：冻结目标测试函数的精确边界

目标：

- 明确当前工作区与 `HEAD` 的差异中，只有目标测试函数属于本切片。

任务：

- 读取当前工作区目标位置代码
- 对照 `HEAD` 中对应区间
- 标记 include / exclude：
  - include：`test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()`
  - exclude：`v1` 占位壳、invalid key 测试、`F3` 相关删除 hunk

完成判定：

- 目标函数边界明确
- 相邻主题全部列入排除清单

### SKH-R2：只恢复目标测试函数

目标：

- 在不影响相邻测试的前提下，恢复目标函数完整语义。

任务：

- 将目标函数按 `HEAD` 基线恢复到工作区
- 核对函数内部关键点位：
  - `POST /api/screeners/run`
  - header 仅 `Content-Type`
  - 成功响应断言
  - cleanup 完整

关键约束：

- 不修改 `apps/api/http.py`
- 不修改 `apps/api/main.py`
- 不修改任何非目标函数测试

完成判定：

- 工作区中目标函数恢复完成
- 其他测试函数语义保持原状

### SKH-R3：做最小验证

目标：

- 证明恢复后的目标函数在当前契约下可通过。

任务：

- 运行：
  - `python3 -m pytest tests/unit/test_bootstrap_skeleton.py -k allows_post_without_legacy_api_key_header`
- 若失败，先判断是否为：
  - 边界恢复错误
  - fixture/断言错误
  - 或与生产契约冲突

完成判定：

- 目标测试通过
- 无需修改生产代码

### SKH-R4：隔离目标 hunk 并提交

目标：

- 形成单一目的提交，只表达目标测试函数恢复。

任务：

- 检查 `git diff HEAD -- tests/unit/test_bootstrap_skeleton.py`
- 仅暂存目标函数相关 hunk
- 排除 `v1` 与 `F3` 相邻 hunk
- 仅在可安全隔离时提交

完成判定：

- staged diff 只含目标函数恢复
- staged diff 不含生产文件
- staged diff 不含相邻主题

If isolation fails:

- 停止提交
- 报告边界需重新评估
- 不扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读取当前工作区与 `HEAD` 的目标区间差异
2. 恢复目标函数
3. 跑最小 pytest 验证
4. 再做 `HEAD`-relative diff 复核
5. 最后仅暂存目标 hunk

原因：

- 先冻结边界再恢复，能避免误带入 `v1` 与 `F3`
- 先测试后暂存，能避免无效或污染提交

## 9. 建议提交切分

建议单一提交：

### Commit SKH：restore screeners post without legacy key header test

范围：

- `tests/unit/test_bootstrap_skeleton.py` 中目标测试函数恢复

目的：

- 恢复当前活跃 POST 契约的直接测试证据

若提交纯度达不到该范围，正确结果是“不提交”，而不是扩大为混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 目标测试函数恢复
2. 目标测试通过
3. `apps/api/http.py` 不改
4. `apps/api/main.py` 不改
5. `v1` 与 `F3` 相邻主题不进入提交
6. 提交可被单独解释为“恢复无 `X-API-Key` POST 契约测试”
