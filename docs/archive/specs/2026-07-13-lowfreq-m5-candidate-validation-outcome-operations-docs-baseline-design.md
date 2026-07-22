Status: active
Owner: lowfreq / governance / operations / docs
Scope: Narrow `M5 candidate validation outcome operations/docs baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Background

`M5 candidate validation outcome trigger adoption` 已完成 runtime/CLI/worker/API 链路，但当前运维文档和项目状态真相源仍停留在 `governance_reject` 与 `governance_status_transition`。

现状证据：

- governance CLI 已支持 `candidate-validation-outcome`
- worker 已支持 `--mode governance_candidate_validation_outcome`
- API 已支持 `mode="governance_candidate_validation_outcome"`
- `docs/operations/bootstrap_runbook.md` 尚未给出 candidate validation outcome 的 worker/API 用法、参数约束与产物路径
- `PROJECT_STATUS.md` 尚未同步该 trigger adoption 已完成的事实

# 2. Goal

以 docs-only 最小切片收口 `candidate validation outcome` 的操作可见性与状态真相源一致性：

- 在 `bootstrap_runbook` 写清如何触发 candidate validation outcome
- 在 `PROJECT_STATUS` 写清该能力已闭环、且仍属于 on-demand 面

# 3. Non-Goals

本切片明确不做：

- 不改 runtime/CLI/worker/API 行为
- 不引入 scheduled orchestrator adoption
- 不改任何 ledger/artifact schema
- 不新增或修改测试用例
- 不处理 candidate selection / projection semantics

# 4. File Boundary

只修改以下文档：

- `docs/operations/bootstrap_runbook.md`
- `PROJECT_STATUS.md`

# 5. Design Decisions

## 5.1 Runbook 补齐 candidate validation outcome 操作面

在现有 reject / status transition 说明旁补齐 candidate validation outcome 对称说明，包含：

- worker 命令示例（`--mode governance_candidate_validation_outcome`）
- governance CLI 命令示例（`candidate-validation-outcome`）
- API `POST /api/orchestration/run` 示例（`mode="governance_candidate_validation_outcome"`）
- 参数硬约束：
  - `source_run_id` 必填
  - `validation_result` 必填，且必须匹配 `ValidationResult` contract
- 产物路径：
  - `var/artifacts/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome.json`
  - `var/ledgers/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome_run.json`
- API 编排 envelope 路径仍沿用：
  - `var/ledgers/orchestration_runs/<date>/orchestrator_run.json`
  - `var/artifacts/orchestration_runs/<date>/orchestrator_result.json`
- 边界声明：该能力是 on-demand surface，不属于 daily 自动编排

## 5.2 PROJECT_STATUS 同步状态真相

在现有 `M5` 运行边界段落补充事实性状态：

- candidate validation outcome 已在 runtime -> CLI -> worker -> API 闭环
- 当前显式输入 contract 为：
  - `source_run_id`
  - `validation_result`
- 当前仍是 on-demand 触发面，不是 daily scheduled task
- 下游 `reject_execution` 与 `status_transition` 已消费该 persisted outcome truth

## 5.3 文案边界保持“已实现”与“未实现”分离

文档必须显式区分：

- 已实现：
  - on-demand trigger adoption
  - persisted outcome truth
  - downstream persisted-truth consumption
- 未实现：
  - scheduler-facing selection semantics
  - daily orchestrator registration
  - automatic candidate comparison / final validation auto-pick

这样可以避免把 docs/status 收口误写成“治理自动化已完成”。

# 6. Risks and Guardrails

- 风险：把 on-demand 写成 scheduled
  - Guardrail：明确写出“不属于 daily 自动编排”
- 风险：把 `validation_result` 简化成 `validation_id`
  - Guardrail：文档必须写清 `validation_result` 是显式 structured payload
- 风险：产物路径写错
  - Guardrail：路径仅引用现有 `governance_candidate_validations` 命名空间
- 风险：把 docs 切片扩大到实现或调度语义
  - Guardrail：只动上述两份 Markdown，不写 scheduler adoption 细节

# 7. Verification

文档切片最小校验：

- `git diff -- docs/operations/bootstrap_runbook.md PROJECT_STATUS.md`
- `git diff --check`

# 8. Dual-axis Audit

- M5 归属：仅补 candidate validation outcome trigger 的 operations/docs 可见面，不触碰治理执行语义
- G5 归属：确保 candidate validation outcome 能力可被稳定触发、回放与审计，不再只存在于代码与测试
- 新增 contract：文档层明确该 trigger 的入口、参数约束、产物位置、API envelope 与 on-demand 边界
- 未触碰边界：runtime、cli、worker、api、orchestrator、selection semantics、schema、tests
