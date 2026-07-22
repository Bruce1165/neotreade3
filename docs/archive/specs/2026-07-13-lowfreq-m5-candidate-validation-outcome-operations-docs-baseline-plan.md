Status: active
Owner: lowfreq / governance / operations / docs
Scope: Implementation plan for the narrow `M5 candidate validation outcome operations/docs baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Objective

以 docs-only 最小切片补齐 `M5 candidate validation outcome` 的运维可见性与状态真相同步。

# 2. File Boundary

Production docs only:

- `docs/operations/bootstrap_runbook.md`
- `PROJECT_STATUS.md`

No code changes:

- no runtime / cli / worker / api edits
- no orchestrator config edits
- no schema or ledger/artifact edits
- no test edits

# 3. Execution Steps

### M5CVDOC-S1: Extend worker and governance CLI runbook sections

Modify `docs/operations/bootstrap_runbook.md`:

- 在现有 governance on-demand 小节中补齐 `candidate validation outcome` 对称说明
- 写入 worker CLI 样例：
  - `--mode governance_candidate_validation_outcome`
- 写入 governance CLI 样例：
  - `candidate-validation-outcome`
- 明确 `source_run_id` 必填
- 明确 `validation_result` 必填，且必须匹配 `ValidationResult` contract
- 明确该能力属于 on-demand surface，不属于 `daily` 自动编排

### M5CVDOC-S2: Extend API runbook section

Modify `docs/operations/bootstrap_runbook.md`:

- 在 `POST /api/orchestration/run` 说明中把 governance mode 扩展到 `governance_candidate_validation_outcome`
- 增加 candidate validation outcome 的 curl 样例
- 明确 API orchestration envelope 路径与底层 outcome 路径是两层产物
- 列出底层产物路径：
  - `var/artifacts/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome.json`
  - `var/ledgers/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome_run.json`

### M5CVDOC-S3: Sync PROJECT_STATUS truth source

Modify `PROJECT_STATUS.md`:

- 在“当前运行边界”位置补充 candidate validation outcome 已完成 `runtime -> CLI -> worker -> API` 闭环
- 明确当前显式输入 contract 为：
  - `source_run_id`
  - `validation_result`
- 明确该能力仍是 on-demand surface，而非 `daily` scheduled task
- 明确下游 `reject_execution` 与 `status_transition` 已消费该 persisted outcome truth

### M5CVDOC-S4: Preserve implemented vs. unimplemented wording boundary

Modify `docs/operations/bootstrap_runbook.md` and `PROJECT_STATUS.md`:

- 已实现只写：
  - on-demand trigger adoption
  - persisted outcome truth
  - downstream persisted-truth consumption
- 未实现仍需明确排除：
  - scheduler-facing selection semantics
  - daily orchestrator registration
  - automatic candidate comparison / final validation auto-pick

### M5CVDOC-S5: Minimum verification

Run:

- `git diff -- docs/operations/bootstrap_runbook.md PROJECT_STATUS.md`
- `git diff --check`

# 4. Risks and Guardrails

- 风险：把 on-demand 写成 daily 编排
  - Guardrail：文案固定使用 `on-demand` / `不属于 daily 自动编排`
- 风险：把 `validation_result` 错写成 `validation_id`
  - Guardrail：文档显式写明 `validation_result` 是 structured payload，且匹配 `ValidationResult` contract
- 风险：把 orchestration envelope 与底层 outcome 路径混淆
  - Guardrail：分别列出两层路径
- 风险：状态真相源写成“治理自动化已完成”
  - Guardrail：只写已闭环的 trigger adoption 与 persisted-truth consumption，不写 scheduled adoption

# 5. Done Criteria

- runbook 能指导 operator 用 worker、governance CLI 或 API 触发 candidate validation outcome
- PROJECT_STATUS 能反映该能力已闭环但仍属 on-demand
- 文档明确 `source_run_id + validation_result` 的显式输入 contract
- `git diff --check` 通过

# 6. Dual-axis Audit

- M5 归属：本 plan 只收口 candidate validation outcome 的文档入口与状态同步
- G5 归属：把治理能力从“实现存在”提升到“操作可见、状态可追、边界可审计”
- 新增 contract：docs 真相与 code truth 对齐，明确 trigger 入口、显式输入、产物位置与 on-demand 边界
- 未触碰边界：runtime、cli、worker、api、orchestrator config、selection semantics、schema、tests
