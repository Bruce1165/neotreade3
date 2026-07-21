# LowFreq v16 Step8（评估与治理闭环）设计说明
Date: 2026-07-19

## 1. 背景与问题

LowFreq v16 需要把“评估 → 调整 → 再评估”的演进闭环固化为可追溯的对象与产物路径，否则会出现：

- 评估结论不可复算（缺少输入/输出契约与证据路径）
- 调整决策不可追责（缺少 proposal / verdict / application record）
- 文档漂移（rulebook 与实现、计划与进度彼此脱钩）

Step8 的目标是在不扩大实现范围的前提下，先冻结最小的“评估与治理输出契约”，为后续落地 M4/M5 的自动化演进链路提供 SSOT 级别的对象边界。

## 2. 目标与非目标

### 2.1 目标

- 定义 Step8 的三类输出契约（RB ids）：
  - `tracking_pool_quality_report`
  - `adjustment_proposal`
  - `governance_decision_log`
- 冻结 Chapter 4（M4→M5）的契约边界（RB ids）：
  - `evaluation_trigger_inputs`
  - `evaluation_outputs`
  - `proposal_contract`
  - `governance_verdict`
  - `adjustment_application_record`
- 明确治理闭环的 fail-closed 原则：
  - 输入不足时不输出“看似完整”的评估结论
  - 治理决策必须绑定可复核证据路径

### 2.2 非目标

- 本文档不宣称任何 Step8/M4/M5 自动化已落地，仅冻结契约（供后续实现与测试）
- 不在本 slice 内定义具体模型调参策略，也不引入“自动改规则”的在线写路径

## 3. 分层定位（与现有工程边界一致）

- M4：评估层（benchmark / quality report / 证据聚合）
- M5：演进控制层（proposal / verdict / application record）

本设计只定义“对象形态与证据绑定”，不扩展为调度器、worker、API、UI 或自动执行链路。

## 4. Chapter 4 契约（RB.M4.CH4.* / RB.M5.CH4.*）

### 4.1 `evaluation_trigger_inputs`（RB.M4.CH4.EVAL_TRIGGER_INPUTS.001）

建议对象用于表达“为什么这次触发评估、评估什么范围、评估用什么证据”：

- `trigger_id`: `str`
- `trigger_type`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_run_id`: `str | null`
- `inputs_ready`: `"ready" | "pending"`
- `pending_reason`: `str | null`
- `evidence_paths`: `list[str]`

约束：

- `inputs_ready="pending"` 时不得输出完整评估（必须 fail-closed）
- `evidence_paths` 仅允许引用“已存在或将被写入的产物路径”，不得凭空虚构

### 4.2 `evaluation_outputs`（RB.M4.CH4.EVAL_OUTPUTS.001）

建议对象用于表达“评估输出的稳定摘要”，并为下游 proposal 提供引用点：

- `report_id`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_run_id`: `str | null`
- `outputs_ready`: `"ready" | "pending"`
- `pending_reason`: `str | null`
- `report_paths`: `list[str]`

约束：

- `outputs_ready="pending"` 时不得输出 `report_paths`（必须为空），避免产物路径漂移

### 4.3 `proposal_contract`（RB.M5.CH4.PROPOSAL_CONTRACT.001）

建议对象用于表达“准备调整什么、基于什么证据、预期影响是什么”，但不执行写入：

- `proposal_id`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_report_id`: `str`
- `status`: `"draft" | "submitted" | "withdrawn"`
- `rb_ids_touched`: `list[str]`
- `change_summary`: `str`
- `evidence_paths`: `list[str]`

约束：

- `rb_ids_touched` 必须是显式 RB ids，便于与 Contract Registry 对齐

### 4.4 `governance_verdict`（RB.M5.CH4.GOVERNANCE_VERDICT.001）

建议对象用于表达“治理结论”，确保可追责：

- `verdict_id`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_proposal_id`: `str`
- `decision`: `"accept" | "reject" | "defer"`
- `rationale`: `str`
- `evidence_paths`: `list[str]`

### 4.5 `adjustment_application_record`（RB.M5.CH4.ADJUSTMENT_APPLICATION_RECORD.001）

建议对象用于表达“调整是否已应用、应用到哪里”，并保留可复核落点：

- `application_id`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_verdict_id`: `str`
- `status`: `"not_applied" | "applied"`
- `applied_artifacts`: `list[str]`
- `notes`: `str | null`

约束：

- `status="applied"` 时 `applied_artifacts` 必须非空（例如指向 config snapshot / rulebook 更新证据等）

## 5. Step8 输出契约（RB.M4.STEP8.* / RB.M5.STEP8.*）

### 5.1 `tracking_pool_quality_report`（RB.M4.STEP8.QUALITY_REPORT.001）

建议输出对象（可落盘/可复算的“质量报告”最小形态）：

- `report_id`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_run_id`: `str | null`
- `quality_verdict`: `"pass" | "warn" | "fail"`
- `summary_metrics`: `dict[str, float | int]`
- `evidence_paths`: `list[str]`

约束：

- `summary_metrics` 的 key 必须来自显式定义或可回溯的统计口径；实现前不在此处预设具体指标列表
- `evidence_paths` 必须可复核（例如评估脚本输出、落盘报告、SQL 统计产物等）

### 5.2 `adjustment_proposal`（RB.M5.STEP8.ADJUSTMENT_PROPOSAL.001）

建议输出对象：

- `proposal_id`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_report_id`: `str`
- `status`: `"draft" | "submitted" | "withdrawn"`
- `rb_ids_touched`: `list[str]`
- `proposed_changes`: `list[dict[str, str]]`
- `risk_notes`: `str | null`
- `evidence_paths`: `list[str]`

约束：

- `proposed_changes` 的每个条目必须为“可机器审计”的描述（例如 `target` / `action` / `before` / `after`），避免自然语言不可复算

### 5.3 `governance_decision_log`（RB.M5.STEP8.GOVERNANCE_DECISION_LOG.001）

建议输出对象：

- `log_id`: `str`
- `asof_date`: `YYYY-MM-DD`
- `source_proposal_id`: `str`
- `decision`: `"accept" | "reject" | "defer"`
- `rationale`: `str`
- `evidence_paths`: `list[str]`
- `application_record_id`: `str | null`

约束：

- decision log 必须能关联到 application record（如果已应用），否则必须显式为 null

## 6. 校验与测试（后续实现要求）

实现落地时至少需要：

- 单测锁定“证据绑定”：
  - 当 `inputs_ready/outputs_ready` 为 pending 时，禁止输出伪造的 `report_paths`
- 单测锁定 RB ids 可追溯：
  - proposal 中 `rb_ids_touched` 必须在 rulebook 的 Contract Registry 中存在登记

---

## 7. Step8 v0 落地切片（对象 + 落盘）

本节冻结 Step8 的 v0 交付边界：**只做对象构建 + 单文件落盘**，不引入 ledger/index，不接入 orchestrator/worker/API/UI，不直接读 DB。

### 7.1 权威输入（Backtest 结果 dict）

Step8 v0 的评估输入以 backtest 的内存结果 dict 为权威源（例如 `run_backtest()` 的返回 dict）。

必需字段（缺失则 fail-closed）：

- `asof_date`：由调用方提供（`YYYY-MM-DD`）
- `source_run_id`：由调用方提供（用于产物目录与 report_id 推导）
- `backtest_result.buy_signal_audit`：`list[dict]`
- `backtest_result.trade_discipline_audit`：`list[dict]`

可选字段（存在则可纳入 metrics，但不得作为必需依赖）：

- `backtest_result.sell_signal_audit`
- `backtest_result.trades`
- `backtest_result.config_snapshot`

### 7.2 v0 统计口径（summary_metrics）

v0 只统计可从 `buy_signal_audit` / `trade_discipline_audit` 直接计数得到的指标，避免引入 DB 口径或不可复算推理。

建议 `summary_metrics` keys（全部为 int）：

- `tracking_started_n`
- `tracking_promoted_to_entry_n`
- `tracking_dropped_n`
- `buy_executed_n`
- `reservation_created_n`
- `reservation_expired_n`
- `execution_signal_gate_blocked_n`
- `chase_entry_blocked_n`
- `trade_discipline_guard_blocked_n`
- `discipline_block_days_n`（从 `trade_discipline_audit[].guard_verdict.status=="block"` 计数）

### 7.3 v0 质量判定（quality_verdict）

判定必须 fail-closed：

- 若必需字段缺失，则输出 `inputs_ready="pending"` 或 `outputs_ready="pending"`，并强制：
  - `report_paths=[]`
  - `quality_verdict="fail"`
- 若 `discipline_block_days_n > 0`，则 `quality_verdict="fail"`
- 若 `trade_discipline_guard_blocked_n > 0`，则 `quality_verdict="fail"`（更硬：出现过“因纪律阻断而拦下新增买入”即判 fail）
- 否则默认 `quality_verdict="pass"`

### 7.4 产物落盘（单文件，无索引）

Step8 v0 将三类对象分别落盘为单个 JSON 文件（每类 1 个 writer），并返回 record（含相对路径）。JSON 格式保持与既有 writer 一致：

- `indent=2`
- `sort_keys=True`
- `ensure_ascii=False`
- 文件结尾换行

推荐路径（相对 project_root）：

- quality_report：
  - `var/artifacts/step8_quality_reports/<report_id>/tracking_pool_quality_report.json`
- adjustment_proposal：
  - `var/artifacts/step8_adjustment_proposals/<proposal_id>/adjustment_proposal.json`
- governance_decision_log：
  - `var/artifacts/step8_governance_decision_logs/<log_id>/governance_decision_log.json`

约束：

- `<report_id>/<proposal_id>/<log_id>` 必须由输入的 `source_run_id` + `asof_date` 派生生成，禁止随机值
- `evidence_paths` 至少包含对应 artifact 的相对路径（ready 时）；若调用方提供 backtest 输入证据（例如 `output_dir/backtest_payload.json`），则必须一并纳入（更硬：可复算输入）

### 7.5 v0 与 Chapter 4 契约的映射

v0 会同步构建：

- `evaluation_trigger_inputs`：以 `asof_date/source_run_id` 为核心，`evidence_paths` 指向 backtest 产物或 Step8 产物路径
- `evaluation_outputs`：`report_id/report_paths/outputs_ready` 对齐 quality_report 的落盘结果

注意：

- v0 不自动生成“内容丰富的 proposal”，但必须提供 `adjustment_proposal` 的对象/落盘能力
- v0 默认 `governance_decision_log.decision="defer"`（除非调用方提供明确的人类决策输入）
