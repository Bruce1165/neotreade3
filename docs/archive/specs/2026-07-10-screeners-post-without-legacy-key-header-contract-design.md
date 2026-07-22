# Screeners Post Without Legacy Key Header Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()` 的恢复设计，目标是把当前工作区里仍然对应 NeoTrade3 活跃运行时契约的一条 POST 测试，从混合 diff 中单独切出来。

目标是：

- 恢复 `POST /api/screeners/run` 在无 `X-API-Key` 请求头时仍可成功的直接测试证据
- 让测试重新准确描述当前 HTTP 层对 legacy API key 的兼容语义
- 为后续实现阶段提供一个可独立隔离、可独立验证、可 index-only 提交的最小边界

本切片不是：

- `v1` 兼容占位壳测试治理
- `factor matrix / lab signal` 主题
- `apps/api/http.py` 或 `apps/api/main.py` 的生产逻辑改动
- `screeners` bulk-run 契约或下载链路主题
- `tests/unit/test_bootstrap_skeleton.py` 中其他相邻测试的顺序整理

## 2. Scope

Included:

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()`

Excluded:

- `apps/api/http.py`
- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_rejects_invalid_legacy_api_key_on_post`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_v1_screener_results_endpoint_returns_not_implemented`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- 其他任何测试、文档、配置和前端文件

## 3. Existing Context

当前代码已经给出直接证据：

- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L88-L100) 中 `_accept_legacy_api_key()` 注释已明确：
  - `X-API-Key` 只作为 backward-compatible header contract 保留
  - active local write paths 不再被它强制门禁
- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L201-L219) 中 `do_POST()` 调用的是 `_accept_legacy_api_key()`，不是 `_require_api_key()`
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L2008-L2068) 的当前工作区版本中，这条活跃测试已经缺失，当前位置被 `v1` 兼容占位壳测试占据
- `HEAD` 版本仍包含 `test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()`，并且其请求头只有 `Content-Type`，没有 `X-API-Key`

现状风险：

- 如果不恢复这条测试，当前测试文件将不再直接覆盖“本地 active write path 不强制要求 legacy key header”的现行契约
- 如果把恢复动作与 `v1` 501 占位壳一起提交，会混入低优先级主题
- 如果顺手修改生产实现，会把“恢复测试证据”扩大成“重写契约”

## 4. Approach Options

### Option A: 只恢复无 `X-API-Key` POST 契约测试（推荐）

仅处理：

- `test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()`

Pros:

- 边界最窄，只覆盖当前仍有直接生产代码证据支持的活跃契约
- 不需要修改任何生产代码
- 与先前的 `screeners API handler contract` 主题保持一致的方法论

Cons:

- `v1` 占位壳和 `F3` 相邻主题仍保留在工作区，后续还需单独治理或排除

### Option B: 同时恢复无 `X-API-Key` 测试并整理 `v1` 501 占位壳顺序

Pros:

- 一次减少更多 diff

Cons:

- 会把活跃契约与低优先级兼容占位壳混在一条线上
- 偏离“只处理仍在新体系发挥作用的契约”这一边界

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `apps/api/http.py`
  - 保持现有 `_accept_legacy_api_key()` 语义不变
- `tests/unit/test_bootstrap_skeleton.py`
  - 恢复一条直接测试，证明 `/api/screeners/run` 在未提供 `X-API-Key` 时仍可成功 POST

### 5.2 Contract Strategy

本切片只允许恢复 `HEAD` 中这条测试函数的最小语义：

1. 构造 trading calendar fixture
2. 发起 `POST /api/screeners/run`
3. 请求头只包含 `Content-Type: application/json`
4. 断言响应成功
5. 断言 `screener_id` 与 `target_date` 正常返回
6. 保留相应 cleanup

本轮不允许顺手改动：

- invalid legacy key 的 401 测试
- `v1` `501 not implemented` 占位壳测试
- `factor matrix` 相关断言
- 任何生产代码

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不把“请求头可缺省”扩大解释为“删除 legacy key 兼容契约”
- 不修改错误 legacy key 仍然返回 `401` 的测试语义
- 不把这条恢复动作包装成“新增功能”或“新实现”
- 若无法只隔离这一个测试函数而不带入相邻 `v1` 或 `F3` hunk，应停止并报告边界问题

## 6. Testing Design

验证优先采用：

1. 运行 `tests/unit/test_bootstrap_skeleton.py -k allows_post_without_legacy_api_key_header`
2. 复核 staged diff 只包含该测试函数相关 hunk
3. 确认 `apps/api/http.py` 与 `apps/api/main.py` 不进入提交

默认不要求：

- 跑整份 `test_bootstrap_skeleton.py`
- 修改生产代码后再回归
- 扩大到 `v1` 或 `factor matrix` 相邻主题

## 7. Validation

预期验证方式：

- `python3 -m pytest tests/unit/test_bootstrap_skeleton.py -k allows_post_without_legacy_api_key_header`
- 复核 index/staged diff 只包含这一个测试主题
- 确认提交中不包含 `v1` 占位壳和 `F3` lab signal 删除线

## 8. Commit Boundary

目标提交应限制为：

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_allows_post_without_legacy_api_key_header()` 的恢复

必须排除：

- `apps/api/http.py`
- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_v1_screener_results_endpoint_returns_not_implemented`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- 其他任何工作区改动

若相对 `HEAD` 无法将该测试主题与相邻主题安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
