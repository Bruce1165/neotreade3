# Status: draft
# Owner: platform / decision_engine
# Scope: M3 front_context audit minimal closure (ledger audit index)
# Canonical: self
# Supersedes: none
# Superseded_by: none
# Last_reviewed: 2026-07-17

## 1. 目标

把「M3 决策可审计（最小闭环）」闭合在 *仅前台链路* 上：从 `m3_front_context` 的 ledger 中可以直接看到输入引用与关键派生/中间状态的定位线索，并可通过 `artifact_sha256` 对 artifact 做可比对校验。

## 2. 边界

### 2.1 In scope

- `m3_front_context` ledger 增强为“审计索引”：补齐 run/source、状态摘要、输入引用摘要、artifact hash。
- `m2_cycle_ref` 补齐 `record_id`（用于跨层定位 M2 small_cycle 的落盘文件）。
- 单测覆盖与 checklist 快照证据回写。

### 2.2 Out of scope

- `DecisionLifecycleLog`（sell-side event chain）的 artifact/ledger 落盘与 readback。
- M2 small_cycle 的对外 API（read/list/download）。

## 3. 现状证据（可核验）

- `m3_front_context` 已具备 artifact+ledger 双写与 read/list/download API（但 ledger 缺少审计摘要字段）：
  - store：`materialize_decision_m3_front_context` / `write_*` / `read_*` / `list_*`：[front_context_store.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/front_context_store.py)
  - API：`/api/m3/front-contexts` read/list/download/download-ledger：[main.py:L3101-L3294](file:///Users/mac/NeoTrade3/apps/api/main.py#L3101-L3294)
- M3 state 合同内已有 `evidence_ref/m2_cycle_ref/m1_constraints_ref` 槽位（字段类型严格为 JSON object，但未形成审计索引）：
  - 以 IdentifyState 为例：[contracts.py:L125-L191](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L125-L191)
- 当前 checklist 中「决策可审计」仍未勾选：[checklist-current-status.md:L115-L117](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-16-m1-m6-checklist-current-status.md#L115-L117)

## 4. 设计方案（推荐）

### 4.1 m2_cycle_ref 增强：补齐 record_id

- 在 `neotrade3/decision_engine/assembler.py::_cycle_ref` 返回结构中加入 `record_id = f"{cycle.stock_code}-{cycle.trade_date}"`。
- 兼容性：`m2_cycle_ref` 在 M3 contract 中仅要求为 dict，不对其内部 key 集合做冻结；新增 key 不破坏 readback。

### 4.2 m3_front_context ledger 增强为“审计索引”

在 `write_decision_m3_front_context_ledger(...)` 的 payload 中补齐以下字段（同时扩展 `DecisionM3FrontContextLedgerRecord` 以便 API 透传）：

- **身份/运行轴**
  - `stock_code`, `trade_date`（与 record_id 一致）
  - `run_id`, `source_run_id`
- **状态摘要轴**
  - `identify_status`
  - `tracking_status`
  - `entry_status`, `entry_decision`, `entry_actionable`, `entry_blocking_reasons`
- **输入引用摘要轴**
  - `m1_blocked`, `m1_blocking_reasons`
  - `m2_cycle_record_id`, `m2_cycle_state`, `m2_state_stability_level`
- **可比对轴**
  - `artifact_sha256`：对 artifact 文件内容做 sha256（hex），写入 ledger

约束：

- read/list 对旧 ledger 兼容：旧 ledger 不含新增字段仍可正常解析与返回（新增字段留空/默认值）。
- 新写入 ledger 必须写全新增字段（由 writer 负责从 `front_context` 中抽取，且 `artifact_sha256` 与实际 artifact 内容一致）。

## 5. 验收口径（本刀必须闭环）

### 5.1 行为断言

- 生成 `m3_front_context` 时，ledger 中出现 `run_id/source_run_id`、状态摘要、输入引用摘要字段。
- ledger 的 `artifact_sha256` 等于对下载到的 artifact 内容计算的 sha256。
- `m2_cycle_ref.record_id` 存在，且可用于定位 `var/artifacts/m2_small_cycles/<record_id>/small_cycle.json`（仅作为定位线索，不要求对外 API）。

### 5.2 单测

- 覆盖“生成并落盘后，ledger 字段齐全 + sha256 正确”。
- 覆盖“m2_cycle_ref 含 record_id”（可通过构造 SmallCycle 调用 `_cycle_ref` 或通过更高层 builder 间接断言）。

### 5.3 Checklist 快照回写

- 将 `docs/superpowers/specs/2026-07-16-m1-m6-checklist-current-status.md` 中：
  - `- [ ] 决策可审计...` 改为 `- [x]`，并补证据链接到 ledger writer + 单测。

## 6. 风险与回滚

- 风险：ledger schema 扩展会让 API 返回字段变多，但保持向后兼容（仅新增字段）。
- 回滚：恢复 `DecisionM3FrontContextLedgerRecord` 字段与 writer payload 即可；不会影响已存在 artifact/ledger 的读取（读回逻辑对未知字段不敏感）。

