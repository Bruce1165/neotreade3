# Status: draft
# Owner: platform / m3
# Scope: Add cursor pagination for M3 lifecycle logs list (run_id filtered)
# Canonical: self
# Supersedes: 2026-07-17-m3-lifecycle-logs-pagination-offset-design.md
# Superseded_by: none
# Last_reviewed: 2026-07-17

## 1. 目标

为 `GET /api/m3/lifecycle-logs` 增加 cursor 游标分页能力，使调用方在 `run_id/report_id` 过滤条件下能够稳定翻页，并保持：

- cron-free（纯查询参数驱动）
- 显式参数（run_id/limit/cursor）
- fail-closed（参数非法直接 400；ledger 解析异常仍 500）

## 2. 现状证据（可核验）

- 当前已支持 `run_id` 过滤、`matched_count`、以及 offset 分页（用于对照）：
  - [main.py:L3338-L3416](file:///Users/mac/NeoTrade3/apps/api/main.py#L3338-L3416)
- 当前 store 排序逻辑为 `(written_at, record_id)` 倒序：
  - [lifecycle_log_store.py:L298-L376](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/lifecycle_log_store.py#L298-L376)

## 3. 设计

### 3.1 API 形态

保持原路径不变，新增 query 参数：

- `cursor`: 可选，string；表示“从该游标之后继续”（不包含游标指向的那条）

请求示例：

- `GET /api/m3/lifecycle-logs?run_id=<report_id>&limit=200`
- `GET /api/m3/lifecycle-logs?run_id=<report_id>&limit=200&cursor=<cursor>`

### 3.2 cursor 编码（opaque）

cursor 为 URL-safe base64 的 JSON（无 padding），包含：

- `v`: int，版本号（固定为 1）
- `written_at`: string（来自 ledger）
- `record_id`: string（来自 ledger）

示例结构（未编码）：

```json
{"v":1,"written_at":"2026-06-20T00:00:00Z","record_id":"300001-xxx"}
```

fail-closed 规则：

- base64 解码失败 / JSON 解析失败 / 顶层非 object / 缺字段 / 类型不对 / v != 1 → 400 `invalid_cursor`
- `record_id` 必须满足“单段路径”约束（防 path traversal）→ 400 `invalid_cursor`
- `written_at` 必须为非空 string（不做时间格式解析）→ 400 `invalid_cursor`

### 3.3 排序与翻页语义

1) 过滤（run_id 可选）
2) 排序：按 `(written_at, record_id)` 倒序
3) 若提供 cursor：
   - 仅保留 key 严格小于 cursor_key 的记录（表示“之后”）
4) `matched_count` 定义为“run_id 过滤后总命中条数”，不受 cursor/limit 影响
5) `returned = page[:limit]`
6) 若存在更多记录（has_more），`next_cursor` 为本页最后一条记录对应的 cursor

### 3.4 与 offset 的互斥规则

为避免语义歧义，cursor 与 offset 互斥：

- 若请求同时给定 `cursor` 且 `offset != 0`，返回 400 `invalid_pagination`

### 3.5 _meta 契约

在现有基础上补齐：

- `returned_count` / `matched_count` / `limit` / `offset` / `run_id`（沿用现有）
- `cursor`: 当请求传入 cursor 时回显原值
- `next_cursor`: 当 has_more 为真时给出下一页 cursor
- `has_more`: bool，是否还有下一页

说明：cursor 分页仍保持 `offset` 字段存在（值为 0），以维持客户端统一处理，但 offset 翻页时不返回 cursor 字段。

## 4. 验收口径

### 4.1 单测（必须锁定）

在 `tests/unit/test_m3_lifecycle_log_api_readback.py` 增加断言：

- 首次请求（无 cursor）返回 `next_cursor`，且 `has_more` 正确
- 带 cursor 请求返回下一页，且不会重复上一页最后一条
- `invalid_cursor`（错误 base64 / v 不匹配 / record_id 非法）返回 400
- `cursor + offset` 冲突返回 400 `invalid_pagination`
- `run_id` 过滤下 cursor 翻页仍成立

### 4.2 checklist 快照回写

在“决策可审计”条目下追加 cursor 分页的证据链接（API 实现 + 单测 + spec）。
