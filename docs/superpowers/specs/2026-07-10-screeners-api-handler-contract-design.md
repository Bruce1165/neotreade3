# Screeners API Handler Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_accepts_screener_run_post` 的活跃 `screeners` POST 契约对齐，目标是把剩余混合 diff 中真正仍在 NeoTrade3 新体系发挥作用的 API handler 主题单独切出来。

目标是：

- 明确 `POST /api/screeners/run` 在当前 HTTP 层已不再强制要求 `X-API-Key`
- 明确 `POST /api/screeners/bulk-run` 返回的 `_meta.status` 应与 `bulk_run.status` 保持一致，而不是硬编码为 `"ok"`
- 为当前仍在运行期注册的 `screeners` POST 入口保留最小直接测试覆盖

本切片不是：

- `v1` 兼容占位壳测试
- `factor matrix / lab artifact` 主题
- `apps/api/http.py` 或 `apps/api/main.py` 的生产逻辑改造
- `screeners` 下载链路主题
- `worker` / `orchestration` / `factor matrix` 的相邻测试主题

## 2. Scope

Included:

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_accepts_screener_run_post`

Excluded:

- `apps/api/http.py`
- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_rejects_invalid_legacy_api_key_on_post`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_v1_screener_results_endpoint_returns_not_implemented`
- `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- 其他任何生产文件、测试文件和文档

## 3. Existing Context

当前代码已经给出直接证据：

- [PROJECT_STATUS.md](file:///Users/mac/NeoTrade3/PROJECT_STATUS.md#L41-L49) 明确 `Screeners → Pools → 候选集` 仍是当前正式主链
- [router.py](file:///Users/mac/NeoTrade3/apps/api/router.py#L2228-L2365) 仍显式注册：
  - `POST /api/screeners/run`
  - `POST /api/screeners/bulk-run`
- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L88-L100) 的 `_accept_legacy_api_key()` 注释已明确写明：
  - API key 仅作为 backward-compatible header contract 保留
  - active local write paths 不再由它强制拦截
- [http.py](file:///Users/mac/NeoTrade3/apps/api/http.py#L201-L219) 的 `do_POST()` 入口调用的是 `_accept_legacy_api_key()`，不是 `_require_api_key()`
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L2069-L2122) 中 `screeners_bulk_run_view()` 返回：
  - `_meta.status = bulk_status`
  - `bulk_run.status = bulk_status`
  - `bulk_run.run_ledgers = [record.__dict__ for record in run_records]`
- 当前测试 diff [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1719-L1958) 中剩余对齐点正好对应上述现行契约：
  - `POST /api/screeners/run` 首次请求去掉 `X-API-Key`
  - `bulk-run` 断言从固定 `"ok"` 改为与 `bulk_run.status` 对齐
  - 新增 `len(payload["bulk_run"]["run_ledgers"]) == 2`

现状风险：

- 如果继续沿用旧断言，会把当前 HTTP 层“兼容 header、非强制鉴权”的事实错误地描述为“必须带 key”
- 如果把该测试与 `v1` 占位壳或 `factor matrix` 主题一起提交，会形成低价值和高价值主题混杂
- 如果顺手改动 `apps/api/http.py` 或 `apps/api/main.py`，会把“测试收口”扩大成生产契约变更

## 4. Approach Options

### Option A: 只提交 screeners API handler 契约测试对齐（推荐）

仅处理：

- `test_bootstrap_api_handler_accepts_screener_run_post` 中与活跃 POST 契约直接相关的断言

Pros:

- 边界最窄，只覆盖仍在运行期生效的 `screeners` POST 契约
- 所有改动都有直接生产代码证据支撑
- 不需要改生产代码

Cons:

- `factor matrix` 剩余主题仍需后续再拆

### Option B: 同时处理 screeners API handler + v1 兼容占位壳

Pros:

- 一次性减少更多 diff

Cons:

- 会把活跃入口与低优先级兼容壳混在同一条线里
- 不符合“先判断是否仍在新体系发挥作用”的约束

### Option C: 修改 HTTP 层或 service 层生产实现，再同步测试

Pros:

- 表面上看起来更“完整”

Cons:

- 当前没有证据表明生产逻辑缺失
- 会把已存在的契约误包装成新实现

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `apps/api/http.py`
  - 继续保留现有 `_accept_legacy_api_key()` 语义：`X-API-Key` 是兼容头，不是本地 active write path 的强制门禁
- `apps/api/main.py`
  - 继续保留 `screeners_bulk_run_view()` 的状态返回方式：`_meta.status` 与 `bulk_run.status` 同步
- `tests/unit/test_bootstrap_skeleton.py`
  - 为上述两条已存在生产契约保留直接测试证据

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `POST /api/screeners/run` 的首次请求头断言
   - 从“必须带 `X-API-Key`”对齐为“只传 `Content-Type` 也可成功”
2. `POST /api/screeners/bulk-run` 的状态断言
   - 从固定断言 `_meta.status == "ok"`
   - 对齐为 `_meta.status == payload["bulk_run"]["status"]`
3. `bulk-run` 返回结构断言
   - 明确 `run_ledgers` 是返回契约的一部分
   - 至少验证本例下 `len(run_ledgers) == 2`

本轮不允许顺手改动：

- `test_bootstrap_api_handler_rejects_invalid_legacy_api_key_on_post`
- `test_v1_screener_results_endpoint_returns_not_implemented`
- `test_factor_matrix_daily_output_supports_live_and_stored_modes`
- `apps/api/http.py`
- `apps/api/main.py`

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改生产代码
- 不把“可不带 header”扩大解释为“完全移除 legacy header 契约”
- 不修改 invalid key 的 401 测试，它仍验证“提供了错误 legacy key 仍会报错”的兼容边界
- 不把 `bulk-run` 状态断言扩展到 async 分支或其他非当前测试已覆盖的场景
- 若无法从 `tests/unit/test_bootstrap_skeleton.py` 的混合 diff 中只隔离该测试主题，应停止并报告边界问题

## 6. Testing Design

验证优先采用：

1. 针对 `test_bootstrap_api_handler_accepts_screener_run_post` 的最小 pytest 选择执行
2. 确认同文件中的 invalid legacy API key 测试不被本轮改动触碰
3. 确认本轮 staged diff 不包含 `v1` compatibility 与 `factor matrix` 相邻主题

默认不要求：

- 跑整份 `test_bootstrap_skeleton.py`
- 扩大到 `factor matrix` 或 `v1` endpoint 测试
- 修改生产实现后再回归

原因：

- 当前风险主要在测试契约是否仍准确描述现行代码，而不是实现缺失
- 现行行为已有明确生产代码证据

## 7. Validation

预期验证方式：

- 运行 `tests/unit/test_bootstrap_skeleton.py -k bootstrap_api_handler_accepts_screener_run_post`
- 复核 staged diff 只包含该测试主题相关 hunk
- 确认 `apps/api/http.py` 与 `apps/api/main.py` 不进入提交

## 8. Commit Boundary

目标提交应限制为：

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_bootstrap_api_handler_accepts_screener_run_post` 的最小契约对齐

必须排除：

- `apps/api/http.py`
- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中 invalid legacy key / `v1` / `factor matrix` 相邻 hunk
- 其他配置、文档和前端文件

若相对 `HEAD` 无法将该测试主题与相邻主题安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
