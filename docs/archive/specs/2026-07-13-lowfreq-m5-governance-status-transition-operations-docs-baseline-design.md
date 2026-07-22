Status: active
Owner: lowfreq / governance / operations / docs
Scope: Narrow `M5 governance status transition operations/docs baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Background

`M5 governance status transition` 已完成 runtime/CLI/worker/API 链路，但当前运维文档仍停留在 `governance_reject`。

现状证据：

- worker 已支持 `--mode governance_status_transition`
- API 已支持 `mode="governance_status_transition"`
- `docs/operations/bootstrap_runbook.md` 尚未给出 status transition 的 worker/API 用法、参数约束与产物路径
- `PROJECT_STATUS.md` 尚未同步 status transition 能力闭环事实

# 2. Goal

以 docs-only 最小切片收口 status transition 的操作可见性与状态真相源一致性：

- 在 `bootstrap_runbook` 写清如何触发 status transition
- 在 `PROJECT_STATUS` 写清该能力已闭环、且仍属于 on-demand 面

# 3. Non-Goals

本切片明确不做：

- 不改 runtime/worker/api 行为
- 不引入 scheduled orchestrator adoption
- 不改任何 ledger/artifact schema
- 不新增或修改测试用例

# 4. File Boundary

只修改以下文档：

- `docs/operations/bootstrap_runbook.md`
- `PROJECT_STATUS.md`

# 5. Design Decisions

## 5.1 Runbook 补齐 status transition 操作面

在现有 reject 说明旁补齐 status transition 对称说明，包含：

- worker 命令示例（`--mode governance_status_transition`）
- API `POST /api/orchestration/run` 示例（`mode="governance_status_transition"`）
- 参数硬约束：`source_run_id` 与 `validation_id` 必填
- 产物路径：
  - `var/artifacts/governance_status_transitions/<validation_id>/governance_status_transition.json`
  - `var/ledgers/governance_status_transitions/<validation_id>/governance_status_transition_run.json`
- 边界声明：该能力是 on-demand surface，不属于 daily 自动编排

## 5.2 PROJECT_STATUS 同步状态真相

在现有“当前运行边界”段落补充一句事实性状态：

- status transition 已在 runtime -> CLI -> worker -> API 闭环
- 目前仍是 on-demand 触发面，不是 daily scheduled task

# 6. Risks and Guardrails

- 风险：文案把 on-demand 写成 scheduled
  - Guardrail：明确写出“不属于 daily 自动编排”
- 风险：产物路径写错
  - Guardrail：路径仅引用现有 `governance_status_transitions` 命名空间
- 风险：文档范围扩大到实现面
  - Guardrail：只动上述两份 Markdown

# 7. Verification

文档切片最小校验：

- `git diff -- docs/operations/bootstrap_runbook.md PROJECT_STATUS.md`
- `git diff --check`

# 8. Dual-axis Audit

- M5 归属：仅补治理状态转移的 operations/docs 可见面，不触碰代码执行语义
- G5 归属：确保治理状态转移能力可被稳定触发与审计，不再只存在于代码/测试
- 新增 contract：文档层明确 status transition 的触发方式、参数约束、产物位置与触发边界
- 未触碰边界：runtime、worker、api、orchestrator、schema、tests
