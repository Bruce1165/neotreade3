Status: active
Owner: lowfreq / governance / operations / docs
Scope: Implementation plan for the narrow `M5 governance status transition operations/docs baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Objective

以 docs-only 最小切片补齐 `M5 governance status transition` 的运维可见性与状态真相同步。

# 2. File Boundary

Production docs only:

- `docs/operations/bootstrap_runbook.md`
- `PROJECT_STATUS.md`

No code changes:

- no runtime / worker / api edits
- no orchestrator config edits
- no test edits

# 3. Execution Steps

### M5TDOC-S1: Extend worker runbook section

Modify `docs/operations/bootstrap_runbook.md`:

- 在现有 `Governance reject 按需执行` 之后补 status transition 小节
- 写入 worker CLI 样例
- 明确 `source_run_id` / `validation_id` 必填
- 明确独立产物路径
- 明确该能力不属于 daily 自动编排

### M5TDOC-S2: Extend API runbook section

Modify `docs/operations/bootstrap_runbook.md`:

- 在 `POST /api/orchestration/run` 说明中把 mode 扩展到 `governance_status_transition`
- 增加 status transition 的 curl 样例
- 明确 API orchestration envelope 路径与底层 transition 路径是两层产物

### M5TDOC-S3: Sync PROJECT_STATUS truth source

Modify `PROJECT_STATUS.md`:

- 在“当前运行边界”位置补 status transition 已闭环事实
- 明确其仍为 on-demand surface，而非 daily scheduled task

### M5TDOC-S4: Minimum verification

Run:

- `git diff -- docs/operations/bootstrap_runbook.md PROJECT_STATUS.md`
- `git diff --check`

# 4. Risks and Guardrails

- 风险：把 on-demand 写成 daily 编排
  - Guardrail：文案固定使用 `on-demand` / `不属于 daily 自动编排`
- 风险：把 API envelope 路径与 transition 底层路径混淆
  - Guardrail：分别列出两层路径
- 风险：状态真相源写成“已 scheduled adoption”
  - Guardrail：只写“runtime -> CLI -> worker -> API 闭环”

# 5. Done Criteria

- runbook 能指导 operator 用 worker 或 API 触发 status transition
- PROJECT_STATUS 能反映该能力已闭环但仍属 on-demand
- `git diff --check` 通过

# 6. Dual-axis Audit

- M5 归属：本 plan 只收口治理状态转移的文档入口与状态同步
- G5 归属：把治理能力从“实现存在”提升到“操作可见、状态可追”
- 新增 contract：docs 真相与 code truth 对齐
- 未触碰边界：runtime、worker、api、orchestrator config、tests
