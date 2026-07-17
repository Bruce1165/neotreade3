# M5 治理对象契约（单一真相源）

日期：2026-07-17

## 1. 范围与边界

本文件冻结并声明 `M5` 治理层对外可读回的核心对象契约（candidate / final_validation / rejection / status_transition / handoff），作为单一真相源（SSOT）。

边界：

- 本文件冻结的是“对象契约与落盘形态”，不是“治理策略正确性”。
- 以 `neotrade3/governance/` 下的契约与 ledger/artifact 读写代码为实现态真相源；新增/变更必须伴随本文件更新。

## 2. 版本策略

- 治理领域内多数细粒度对象（diagnostic / change_request / validation_result / attention_item / promotion_blocker / decision_record）使用统一版本号 `M5_OBJECT_VERSION=1`。
- handoff bundle 自身有独立 `object_type/object_version`。

证据：

- `M5_OBJECT_VERSION=1` 与 object_type 常量：[contracts.py:L9-L17](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L9-L17)
- `governance_handoff_bundle` object_type/object_version：[handoff.py:L31-L75](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py#L31-L75)

## 3. 对外可读回的核心对象（冻结清单）

本节冻结 “可落盘 + 可读回 + 有对外 API 入口” 的治理对象集合及其标识符与落盘位置。

### 3.1 handoff（governance_handoff_bundle）

- 标识符：`source_run_id`
- artifact 路径：`var/artifacts/governance_handoffs/{source_run_id}/governance_handoff_bundle.json`
- ledger 路径：`var/ledgers/governance_handoffs/{source_run_id}/governance_handoff_run.json`
- artifact 内容：`GovernanceHandoffBundle.to_payload()` + `written_at`
- ledger 内容：`GovernanceRunLedgerRecord`（统计计数 + artifact/ledger 路径）

证据：

- bundle 契约（字段结构、to_payload/from_dict）：[handoff.py:L60-L160](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py#L60-L160)
- artifact 写入（含路径与写入 payload）：[artifact_writer.py:L73-L107](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L73-L107)
- ledger record 契约：[run_ledger.py:L26-L86](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L26-L86)
- ledger/artifact 文件路径函数：[run_ledger.py:L289-L305](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L289-L305)
- ledger 写入：[run_ledger.py:L379-L417](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L379-L417)

### 3.2 candidate（governance_candidate_validation）

- 标识符：`validation_id`（同时携带 `source_run_id`）
- artifact 路径：`var/artifacts/governance_candidate_validations/{validation_id}/governance_candidate_validation.json`
- ledger 路径：`var/ledgers/governance_candidate_validations/{validation_id}/governance_candidate_validation_run.json`
- artifact 内容：包含 `validation_result`（`ValidationResult`）
- ledger 内容：`GovernanceCandidateValidationRecord`

证据：

- `ValidationResult` 契约：[contracts.py:L379-L441](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L379-L441)
- artifact record 契约：[artifact_writer.py:L38-L47](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L38-L47)
- artifact 写入（payload 字段集合）：[artifact_writer.py:L159-L206](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L159-L206)
- ledger record 契约：[run_ledger.py:L133-L175](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L133-L175)
- ledger/artifact 文件路径函数：[run_ledger.py:L325-L341](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L325-L341)

### 3.3 final_validation（governance_final_validation）

- 标识符：`source_run_id`
- artifact 路径：`var/artifacts/governance_final_validations/{source_run_id}/governance_final_validation.json`
- ledger 路径：`var/ledgers/governance_final_validations/{source_run_id}/governance_final_validation_run.json`
- artifact 内容：包含 `selected_validation_id`、选择依据与候选引用路径
- ledger 内容：`GovernanceFinalValidationRecord`

证据：

- artifact record 契约：[artifact_writer.py:L62-L71](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L62-L71)
- artifact 写入（payload 字段集合）：[artifact_writer.py:L270-L338](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L270-L338)
- ledger record 契约：[run_ledger.py:L233-L272](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L233-L272)
- ledger/artifact 文件路径函数：[run_ledger.py:L361-L377](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L361-L377)

### 3.4 rejection（governance_reject_execution）

- 标识符：`validation_id`（同时携带 `source_run_id`）
- artifact 路径：`var/artifacts/governance_rejections/{validation_id}/governance_reject_execution.json`
- ledger 路径：`var/ledgers/governance_rejections/{validation_id}/governance_reject_execution_run.json`
- artifact 内容：包含 `validation_result` 与 `decision_record`
- ledger 内容：`GovernanceRejectExecutionLedgerRecord`

证据：

- `GovernanceDecisionRecord` 契约：[contracts.py:L504-L577](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L504-L577)
- artifact record 契约：[artifact_writer.py:L27-L36](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L27-L36)
- artifact 写入（payload 字段集合）：[artifact_writer.py:L110-L157](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L110-L157)
- ledger record 契约：[run_ledger.py:L88-L130](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L88-L130)
- ledger/artifact 文件路径函数：[run_ledger.py:L307-L323](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L307-L323)

### 3.5 status_transition（governance_status_transition）

- 标识符：`validation_id`（同时携带 `source_run_id`）
- artifact 路径：`var/artifacts/governance_status_transitions/{validation_id}/governance_status_transition.json`
- ledger 路径：`var/ledgers/governance_status_transitions/{validation_id}/governance_status_transition_run.json`
- artifact 内容：包含 `effective_attention_item` 与 `effective_promotion_blocker`，并指向 `trigger_artifact_path`
- ledger 内容：`GovernanceStatusTransitionRecord`

证据：

- `AttentionItem` / `PromotionBlocker` / `GovernanceDecisionRecord` 契约片段：[contracts.py:L297-L377](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L297-L377)、[contracts.py:L443-L501](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L443-L501)、[contracts.py:L504-L577](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L504-L577)
- artifact record 契约：[artifact_writer.py:L49-L60](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L49-L60)
- artifact 写入（payload 字段集合）：[artifact_writer.py:L209-L267](file:///Users/mac/NeoTrade3/neotrade3/governance/artifact_writer.py#L209-L267)
- ledger record 契约：[run_ledger.py:L177-L230](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L177-L230)
- ledger/artifact 文件路径函数：[run_ledger.py:L343-L359](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L343-L359)

## 4. 对外读回入口（只读 API）

治理对象的对外读回入口（read/list/download/download-ledger）由路由层分发到 API service 的 view/download 实现。

证据：

- 路由分发（final-validations / rejections / status-transitions / handoffs / candidate-validations / index）：[router.py:L1429-L1721](file:///Users/mac/NeoTrade3/apps/api/router.py#L1429-L1721)
- API service 实现（final_validation / rejection / status_transition / candidate_validation / handoff / index）：[main.py:L1745-L2839](file:///Users/mac/NeoTrade3/apps/api/main.py#L1745-L2839)

## 5. 变更流程（新增或变更治理对象契约的最小门禁）

新增/变更治理对象契约必须同时满足：

1. 更新本文件中的“冻结清单与路径/标识符”。
2. 更新对应的 artifact/ledger dataclass 与写入/读回函数。
3. 更新对外 API（如新增端点）并补齐单测锁定。
