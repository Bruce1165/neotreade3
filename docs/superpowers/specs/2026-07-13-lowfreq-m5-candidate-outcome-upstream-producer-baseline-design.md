Status: active
Owner: lowfreq / governance / runtime
Scope: Narrow design for the `M5 candidate outcome upstream producer baseline`
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Background

当前 `M5` 已具备两段明确能力：

- `governance handoff` 能把 persisted benchmark 结果投影成 pending validation baseline
- `candidate_validation_outcome` 能接收显式 `ValidationResult`，完成校验与持久化

但当前仍缺少一个“非人工 upstream producer owner”：

- handoff 当前只产出 pending validation，不产出 final outcome
- `candidate_validation_outcome` 当前只负责校验/持久化，不负责自动推导 outcome
- `final_validation_selection` 已完成独立 owner，但仍依赖上游先存在 persisted candidate outcome

因此，当前 `daily` 无法安全接入的根因，不是 orchestrator 接线缺失，而是 upstream
truth producer 缺失。

# 2. Goal

本切片目标是设计一个独立的 `candidate outcome upstream producer owner`，满足：

- 输入为 persisted governance truth，而不是人工传入的 `validation_result`
- 输出直接复用现有 `ValidationResult` contract
- 输出可被现有 `run_governance_candidate_validation_outcome(...)` 直接消费
- 不改 handoff baseline schema
- 不改 candidate outcome artifact / ledger schema
- 不提前声明 `daily adoption` 已完成

# 3. Non-Goals

本切片明确不做：

- 不修改 `ValidationResult` contract
- 不新建并行的中间 schema
- 不把 producer 逻辑并入 `run_governance_for_benchmark_run(...)`
- 不做 multi-candidate comparison / ranking / winner selection
- 不做 `final_validation_selection` 的 `daily` 注册
- 不做 CLI / API / docs 同步
- 不修改 `daily_master_orchestrator.json`

# 4. Approaches

## A. 独立 upstream producer owner（推荐）

新增一个独立 owner：

- 位于 handoff 之后
- 位于 `candidate_validation_outcome` 之前
- 输入 persisted truth
- 输出合法 `ValidationResult`

优点：

- 保持 handoff immutable baseline 语义不变
- 复用现有 `candidate_validation_outcome` contract 与持久化链
- 边界最窄，漂移最小

## B. 并入 handoff owner

把自动 outcome producer 写进 `run_governance_for_benchmark_run(...)`。

不推荐：

- 会把 pending baseline 与 final outcome 混到同一 owner
- handoff 当前的职责是“formal pending baseline”，不是“final decision truth”

## C. 新建并行 contract

先产出中间对象，再转换成 `ValidationResult`。

不推荐：

- 会产生第二套 schema
- 会引入额外 projection owner
- 当前证据不足以支持这种宽边界

# 5. Chosen Design

采用方案 A：新增独立 upstream producer owner，且输出直接复用现有
`ValidationResult` contract。

# 6. Design Decisions

## 6.1 Owner Position

新增一个独立的 governance runtime owner，推荐位置：

- `neotrade3/governance/runtime.py`

推荐命名：

- `run_governance_candidate_outcome_upstream_producer(...)`

它的职责只有一个：

- 基于 persisted governance truth，推导并产出一个可被现有
  `candidate_validation_outcome` runtime 消费的 `ValidationResult`

它不是：

- handoff owner
- candidate outcome persistence owner
- final selection owner

## 6.2 Input Truth Sources

该 owner 的输入必须只来自 persisted truth：

- `source_run_id`
- persisted governance handoff bundle
- handoff bundle 中的 pending `validation_results`
- 与 handoff 同源、已在仓库中存在的正式 evidence sources

硬约束：

- 不接受人工提交的 `validation_result`
- 不改写 handoff bundle 中的 pending validation
- 不扫描任何未定义的新证据源

## 6.3 Output Contract

该 owner 的输出直接复用现有 `ValidationResult` contract。

这意味着：

- 不新建中间 schema
- 不新建 parallel payload
- 输出必须能被现有
  `run_governance_candidate_validation_outcome(project_root=..., source_run_id=..., validation_result=...)`
  直接消费

推荐最小输出字段保持与现有 contract 一致：

- `validation_id`
- `experiment_id`
- `baseline_run_id`
- `candidate_run_id`
- `outcome`
- `introduced_risk_count`
- `cleared_guardrail_codes`
- `remaining_guardrail_codes`
- `evidence_refs`

## 6.4 Semantic Boundary

本 design 只允许“outcome derivation / projection”，不允许“winner selection”。

允许的语义：

- 对某个已存在的 pending validation，基于正式 evidence sources 推导出一个 final
  `ValidationResult`
- 该结果仍与原 `validation_id` / `experiment_id` / `baseline_run_id` 对齐

不允许的语义：

- 从多个 validation 中自动挑“最佳”一个
- 引入 comparison score
- 引入 ranking
- 引入 candidate tournament
- 在多 candidate 之间做自动优先级判定

若 evidence 不足，必须 fail-closed，而不是猜测 outcome。

## 6.5 Relation To Existing Owners

与现有 owner 的关系必须清晰拆分：

- `run_governance_for_benchmark_run(...)`
  - 负责生成 pending validation baseline
- `run_governance_candidate_outcome_upstream_producer(...)`
  - 负责从 persisted truth 推导非人工 final `ValidationResult`
- `run_governance_candidate_validation_outcome(...)`
  - 负责校验并持久化 final `ValidationResult`
- `run_governance_final_validation_selection(...)`
  - 负责从 persisted candidate outcomes 中投影 single final truth

该拆分保证：

- handoff 不被污染成 final outcome producer
- candidate outcome persistence 不被污染成自动推导 owner
- final selection 不承担 upstream producer 职责

## 6.6 Failure Semantics

该 owner 必须 fail-closed：

- 若 handoff 不存在：失败
- 若 pending validation 不存在：失败
- 若 evidence source 不足以支撑 outcome：失败
- 若输出无法构造成合法 `ValidationResult`：失败

不允许：

- 默认产出 `rejected`
- 默认沿用 pending outcome
- 缺证据时伪造 `candidate_run_id`
- 自动补齐不存在的 evidence refs

# 7. File Boundary

本 design 对应的后续实现预计只涉及：

- `neotrade3/governance/runtime.py`
- 可能的同目录 helper owner 文件
- focused tests

明确不应先改：

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `apps/worker/main.py`
- `apps/api/main.py`
- `apps/api/router.py`

# 8. Verification

设计切片最小校验：

- spec 明确 owner 位置、输入、输出、失败语义
- spec 明确“复用现有 `ValidationResult` contract”
- spec 明确“不做 daily adoption / comparison / parallel schema”
- spec 与当前 `PROJECT_STATUS` 冻结边界一致

# 9. Risks And Guardrails

- 风险：把 producer 逻辑塞回 handoff owner
  - Guardrail：明确 handoff 只负责 pending baseline
- 风险：为了后续扩展过早引入并行 contract
  - Guardrail：强制复用现有 `ValidationResult`
- 风险：把 outcome derivation 偷换成 winner selection
  - Guardrail：明确禁止 ranking / comparison / auto-pick
- 风险：在 producer 未实现前继续推进 `daily`
  - Guardrail：design 明确不触碰 `daily_master_orchestrator.json`

# 10. Dual-axis Audit

- `M5` 归属：补齐 governance candidate outcome 的非人工 upstream producer owner
- `G5` 归属：为后续 scheduler-facing adoption 提供真实上游，而不是继续扩大手工触发面
- `G6` 归属：保持 truth production、truth persistence、truth selection 三层 owner 分离
- 当前未触碰边界：
  - daily adoption
  - CLI / API surface
  - candidate comparison
  - final selection daily registration
