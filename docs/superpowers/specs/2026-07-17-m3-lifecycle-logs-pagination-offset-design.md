# Status: draft
# Owner: platform / m3
# Scope: Add offset pagination for M3 lifecycle logs list (run_id filtered)
# Canonical: self
# Supersedes: none
# Superseded_by: none
# Last_reviewed: 2026-07-17

## 1. 目标

为 `GET /api/m3/lifecycle-logs` 增加 offset 分页能力，使调用方在 `run_id/report_id` 过滤条件下可以“可控地拉全量”，同时保持：

- cron-free（纯查询参数驱动）
- 显式参数（run_id/limit/offset）
- fail-closed（参数非法直接 400；ledger 解析异常仍 500）

## 2. 现状证据（可核验）

- 当前已支持 `run_id` 过滤与 `_meta.matched_count`：
  - [main.py:L3338-L3405](file:///Users/mac/NeoTrade3/apps/api/main.py#L3338-L3405)
- 当前 store 排序逻辑为 `(written_at, record_id)` 倒序，并在末尾截断到 `limit`：
  - [lifecycle_log_store.py:L298-L354](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/lifecycle_log_store.py#L298-L354)

## 3. 设计

### 3.1 API 形态

保持原路径不变，新增 query 参数：

- `run_id`: 可选，string；用于按 run_id/report_id 聚合过滤（现有能力）
- `limit`: 可选，int；默认 20，最大 200（现有能力）
- `offset`: 可选，int；默认 0；表示在“过滤 + 排序”后的结果集上跳过的条数

请求示例：

- `GET /api/m3/lifecycle-logs?run_id=<report_id>&limit=200&offset=0`
- `GET /api/m3/lifecycle-logs?run_id=<report_id>&limit=200&offset=200`

### 3.2 排序与截断语义

结果集按如下顺序生成：

1) 从 ledger root 扫描并解析所有 ledger（fail-closed）
2) 若 `run_id` 给定：只保留 `record.run_id == run_id` 的记录
3) 排序：按 `(written_at, record_id)` 倒序
4) `matched_count = len(records_after_filter)`
5) `records_after_offset = records_after_filter[offset:]`
6) `returned = records_after_offset[:limit]`
7) `returned_count = len(returned)`

说明：`matched_count` 不受 `offset/limit` 影响；`returned_count` 受两者影响。

### 3.3 _meta 契约

在现有基础上补齐：

- `returned_count`: 本次返回条数（现有）
- `matched_count`: 过滤后总命中条数（现有）
- `limit`: 本次实际使用的 limit（新增）
- `offset`: 本次实际使用的 offset（新增）
- `run_id`: 仅当请求传入 run_id 时回显（现有）

### 3.4 fail-closed 参数校验

- `offset` 必须可解析为 int，且 `offset >= 0`，否则返回 400：
  - code: `invalid_offset`
- `limit` 仍沿用既有校验（非正/超上限等）
- `run_id` 仍沿用既有校验（空/路径非法等）

### 3.5 兼容性

- 不传 `offset` 时行为与当前一致（offset=0）
- 不影响 record_id read/download/download-ledger 等路径

## 4. 验收口径

### 4.1 单测（必须锁定）

在 `tests/unit/test_m3_lifecycle_log_api_readback.py` 追加/更新断言：

- `offset=0, limit=1` 时：
  - `_meta.matched_count == 2`
  - `_meta.returned_count == 1`
  - `_meta.offset == 0`，`_meta.limit == 1`
- `offset=1, limit=1` 时：
  - 返回第二条记录
  - `_meta.matched_count == 2`，`_meta.returned_count == 1`
- `offset>=matched_count` 时：
  - 返回空列表
  - `_meta.matched_count == N`，`_meta.returned_count == 0`
- `offset` 非法（负数/非整数）时 400 `invalid_offset`

### 4.2 checklist 快照回写

在“决策可审计”条目下追加证据链接（API 实现 + 单测）。
