# Status: draft
# Owner: platform / decision_engine
# Scope: M3 lifecycle log persisted store + readback API
# Canonical: self
# Supersedes: none
# Superseded_by: none
# Last_reviewed: 2026-07-17

## 1. 目标

补齐 M3 “退出/卖出事件链”的审计闭环：将 `DecisionLifecycleLog` 作为独立可落盘对象，提供 artifact+ledger 双写、fail-closed 读回与对外 read/list/download/download-ledger API。

## 2. 边界

### 2.1 In scope

- 新增 `m3_lifecycle_log` 的持久化 store（artifact/ledger）与读回/list 能力。
- 新增 API：`/api/m3/lifecycle-logs` 的 list/read/download/download-ledger。
- ledger 落盘“审计索引字段”（事件摘要 + artifact_sha256）。
- 单测 + checklist 快照证据回写。

### 2.2 Out of scope

- 修改/扩展 lifecycle contract（`DecisionLifecycleEvent/DecisionLifecycleLog`）字段集合与版本。
- 修改 sell-side audit 的生成逻辑（`engine._sell_signal_audit_current_run` 生产者侧）。
- 让 lifecycle log 自动挂接到 `m3_front_context`（仍保持两者解耦）。

## 3. 现状证据（可核验）

- lifecycle contract 已存在（fail-closed `from_dict` + unknown-fields 拒绝）：
  - [contracts.py:L513-L660](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L513-L660)
- lifecycle log 构造逻辑已存在（从 sell audit rows 归一化）：
  - [decision_lifecycle_log.py:L126-L198](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/decision_lifecycle_log.py#L126-L198)
- 当前缺口：未发现 lifecycle log 的落盘/读回实现与 API 路由（对照仅有 front-contexts）：
  - [router.py:L1690-L1730](file:///Users/mac/NeoTrade3/apps/api/router.py#L1690-L1730)
- 已存在的落盘/读回/API 样板（front_contexts）：
  - store：[front_context_store.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/front_context_store.py)
  - API view：[main.py:L3101-L3294](file:///Users/mac/NeoTrade3/apps/api/main.py#L3101-L3294)
  - API tests：[test_m3_front_context_api_readback.py:L14-L193](file:///Users/mac/NeoTrade3/tests/unit/test_m3_front_context_api_readback.py#L14-L193)

## 4. 设计

### 4.1 主键（record_id）

采用按 run 聚合、按 stock_code 切分的主键：

- `record_id = f"{stock_code}-{run_id}"`

动机：lifecycle log 内的 event 可能跨多日；以 run 为单位更符合审计闭环（一次运行的一条退出链）。

### 4.2 落盘布局

- artifact：`var/artifacts/m3_lifecycle_logs/<record_id>/lifecycle_log.json`
- ledger：`var/ledgers/m3_lifecycle_logs/<record_id>/lifecycle_log.json`

文件命名与目录分层对齐现有 `m3_front_contexts` 模式。

### 4.3 store 模块

新增文件：`neotrade3/decision_engine/lifecycle_log_store.py`，提供：

- `build_decision_m3_lifecycle_log_record_id(stock_code: str, run_id: str) -> str`
- `write_decision_m3_lifecycle_log_artifact(project_root, record_id, lifecycle_log: DecisionLifecycleLog, dry_run=False)`
- `write_decision_m3_lifecycle_log_ledger(project_root, record_id, lifecycle_log: DecisionLifecycleLog, artifact_record, dry_run=False)`
- `materialize_decision_m3_lifecycle_log(project_root, record_id, lifecycle_log: DecisionLifecycleLog, dry_run=False)`
- `read_decision_m3_lifecycle_log_artifact(project_root, record_id) -> dict | None`
- `read_decision_m3_lifecycle_log(project_root, record_id) -> DecisionLifecycleLog | None`
- `read_decision_m3_lifecycle_log_ledger(project_root, record_id) -> LedgerRecord | None`
- `list_decision_m3_lifecycle_log_ledgers(project_root, limit=200) -> list[LedgerRecord]`

语义与 fail-closed：

- 文件不存在：返回 `None`（或 list 返回空列表）
- 读文件失败 / JSON 非法 / JSON 顶层非 object / ledger payload 非法 / contract 不满足：抛错（上层封装为 500）

### 4.4 ledger 审计索引字段（最小闭环）

ledger payload 至少包含：

- `record_id`, `written_at`, `artifact_path`, `ledger_path`
- `stock_code`, `run_id`, `source_run_id`
- `events_count`
- `first_trade_date`, `last_trade_date`
- `last_event`, `last_stage`, `last_decision`, `last_exit_scope`
- `artifact_sha256`：对 artifact 文件内容做 sha256(hex)

约束：

- `artifact_sha256` 必须与 artifact 实际文件内容一致（单测强校验）。
- `events_count` 与 `events` 长度一致；first/last_* 取 `events` 的 trade_date（按输入顺序或排序规则在实现中固定并测试锁定）。

### 4.5 对外 API

新增 API 路径（与 front-contexts 同模式）：

- list：`GET /api/m3/lifecycle-logs?limit=20`
- read：`GET /api/m3/lifecycle-logs/{record_id}`
- download：`GET /api/m3/lifecycle-logs/{record_id}/download`
- download-ledger：`GET /api/m3/lifecycle-logs/{record_id}/download-ledger`

记录 id 安全：

- `record_id` 必须是单段相对路径名；拒绝 `..`、绝对路径、多段路径（复用 `front_context` 的归一化口径）。
- download 时强制 root 限制（resolve + relative_to(root)）。

返回结构建议对齐：

- list：返回 ledger record `__dict__` + `url/download_url/download_ledger_url`
- read：返回 `_meta.status=ok` + `ledger_record` + `lifecycle_log_payload` + `lifecycle_log_artifact`

### 4.6 集成点（不强制）

本刀仅提供“落盘/读回/API”基础设施；生成者（engine）侧可在后续切片接入：

- 由 `engine._sell_signal_audit_current_run` 调用 `build_decision_lifecycle_logs(...)` 生成 payload
- 再调用 `materialize_decision_m3_lifecycle_log(...)` 落盘

## 5. 验收口径

### 5.1 行为断言

- lifecycle log 可落盘为 artifact+ledger，且 ledger 含审计摘要与 `artifact_sha256`。
- read/list/download/download-ledger API 可用，且 fail-closed 语义一致（坏 JSON 触发 500，路径穿越触发 400）。

### 5.2 单测

- store 单测：落盘后读回成功；`artifact_sha256` == sha256(artifact 文件内容)；事件摘要字段正确。
- API 单测：list/read/download/download-ledger；path traversal 400；invalid JSON 500。

### 5.3 checklist 快照回写

- 在 `docs/superpowers/specs/2026-07-16-m1-m6-checklist-current-status.md` 的 “决策可审计” 项下补充 lifecycle log 的端到端证据链接（store + tests）。

## 6. 风险与回滚

- 风险：新增 API 与落盘目录；与现有模块解耦，风险集中在路由分发与路径安全。
- 回滚：删除 lifecycle_log_store 与 API 分支，不影响既有 front_context 与其它模块。

