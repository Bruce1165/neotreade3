# M1 缺失与异常可见（Attention）输出契约（单一真相源）

日期：2026-07-17

## 1. 范围与边界

本文件冻结并声明 `M1` Phase 1 正式对象的 attention 机制（缺失与异常可见）的对外输出位置与落盘形态，作为单一真相源（SSOT）。

边界：

- 本文件冻结的是“attention 的输出契约与落点”，不扩展到未来 `D2-D6` 对象族。
- attention 的细粒度业务规则（何时产生、严重度判定）以实现代码为准；本文件只保证“如何被看到、如何被追溯”。

## 2. Attention item 结构（实现态）

`M1AttentionItem` 是 M1 phase-1 的最小结构化 attention 单元：

- `issue_code`：稳定问题码
- `severity`：严重度（字符串）
- `message`：面向使用者的解释
- `impacts`：影响面（例如 `m2`/`m3`）
- `details`：可选的结构化细节（用于定位线索）

证据：

- `M1AttentionItem` 与 `build_attention_item(...)`：[quality.py:L57-L109](file:///Users/mac/NeoTrade3/neotrade3/data_control/quality.py#L57-L109)

## 3. 对外输出（API）

M1 phase-1 正式对象的只读 API 响应体包含 `attention_items` 字段；当关键输入缺失时会生成对应 attention item（例如 D1 target_date 无数据）。

证据：

- D1 端点响应包含 `attention_items`（缺失时生成 `m1_d1_missing_for_target_date`）：[main.py:L16360-L16401](file:///Users/mac/NeoTrade3/apps/api/main.py#L16360-L16401)
- 路由端点集合（D1/D7/D8）：[router.py:L1197-L1277](file:///Users/mac/NeoTrade3/apps/api/router.py#L1197-L1277)

## 4. 稳定落盘（DataControl stage artifact/ledger）

DataControl pipeline 会把 `m1_formal_artifacts` 写入各 stage 的结果 JSON 中；其中包含各正式对象 payload，因此包含 `attention_items`，构成稳定落盘与可追溯证据链。

落盘路径规则：

- ledger：`var/ledgers/data_control/<YYYY-MM-DD>/data_control_<stage>_ledger.json`
- artifact：`var/artifacts/data_control/<YYYY-MM-DD>/data_control_<stage>_result.json`

证据：

- stage 产物路径计算（ledger/artifact）：[pipeline.py:L910-L918](file:///Users/mac/NeoTrade3/neotrade3/data_control/pipeline.py#L910-L918)

## 5. 变更流程（最小门禁）

变更 attention 的“对外可见性契约”（字段名、落点、是否落盘）必须同时满足：

1. 更新本文件。
2. 更新对应 API handler / pipeline 产物结构。
3. 补齐单测或端到端证据，锁定 `attention_items` 输出不漂移。
