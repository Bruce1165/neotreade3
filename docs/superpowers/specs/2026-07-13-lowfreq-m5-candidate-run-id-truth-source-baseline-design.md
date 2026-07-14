Status: active
Owner: lowfreq / experiment / governance
Scope: Narrow design for the `M5 candidate_run_id truth source baseline`
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Background

当前 `M5` 已具备：

- pending governance handoff baseline
- `candidate_validation_outcome` persistence owner
- `final_validation_selection` owner

但仍缺一个关键上游真相源：

- `candidate_run_id`

现状问题：

- pending `ValidationResult` 允许 `candidate_run_id=""`
- final `ValidationResult` 又要求 `candidate_run_id` 非空
- handoff / experiment_request 当前都不提供这个字段
- 因此 governance 目前无法在不造假的前提下自动产出 final `ValidationResult`

所以当前真正缺口不是 governance 内部逻辑，而是：

- `candidate_run_id truth source`

# 2. Goal

设计一个独立的 `candidate_run_id truth source owner`，满足：

- owner 归属在实验侧，而不是治理侧
- governance 只消费该 truth source
- 不修改当前 `ValidationResult` contract
- 不要求 governance 发明或映射 `candidate_run_id`
- 为后续 `candidate outcome upstream producer` 提供合法输入

# 3. Non-Goals

本切片明确不做：

- 不实现 `candidate outcome upstream producer`
- 不修改 `ValidationResult` contract
- 不修改 `handoff` 现有 pending baseline 语义
- 不修改 `candidate_validation_outcome` persistence schema
- 不做 `daily` 接线
- 不做 worker / CLI / API adoption
- 不做 docs/status 同步

# 4. Approaches

## A. 实验侧 truth source owner（推荐）

把 `candidate_run_id` 视为 candidate execution / experiment result 的正式身份字段。

优点：

- 语义自然
- ownership 清晰
- governance 只消费，不越权造字段
- 后续 drift 最小

## B. 治理侧映射 owner

在 governance 内定义一个 mapping/lookup owner，把 pending validation 绑定到某个
`candidate_run_id`。

不推荐：

- governance 会承担 experiment identity 的发明责任
- 长期容易和真实 experiment/candidate lifecycle 漂移
- 会让 `candidate_run_id` 从 truth source 退化成“治理层内部映射”

# 5. Chosen Design

采用方案 A：

- `candidate_run_id` 的 truth source owner 必须在实验侧
- governance 不负责生成它，只负责读取和消费

# 6. Design Decisions

## 6.1 Owner Position

`candidate_run_id` 的正式 owner 必须位于 experiment/candidate execution domain。

它应满足：

- 由实验侧写入
- 可被 governance 读取
- 生命周期与 candidate execution 一致

它不应位于：

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/runtime.py`
- `candidate_validation_outcome` persistence 层
- `final_validation_selection` 层

## 6.2 Semantics

`candidate_run_id` 的语义应固定为：

- 某次 candidate execution / candidate experiment result 的正式唯一标识

不是：

- governance 生成的衍生 id
- handoff 内部临时占位符
- final selection 的投影字段

这意味着：

- governance 若需要 final `ValidationResult`
- 必须从实验侧 truth source 读到已存在的 `candidate_run_id`
- 不能自己拼接、猜测或补默认值

## 6.3 Governance Consumption Boundary

governance 未来只应做消费，不应做所有权扩张：

- handoff 继续只生成 pending validation baseline
- `candidate outcome upstream producer` 未来读取 `candidate_run_id truth source`
- `candidate_validation_outcome` 继续只校验并持久化 final `ValidationResult`
- `final_validation_selection` 继续只消费 persisted candidate outcomes

## 6.4 Handoff Boundary

当前 handoff 的 pending baseline 语义保持不变：

- `candidate_run_id=""`
- `outcome="awaiting_candidate_validation"`

这一点不应为了“补字段”而被破坏。

原因：

- handoff 的职责是 formal pending baseline
- 不是 candidate execution registry

## 6.5 Allowed Future Shape

后续可行的最小演进方向应是：

- 在 experiment/candidate 侧新增正式 artifact 或 registry
- 其中至少包含：
  - `experiment_id`
  - `candidate_run_id`
  - 与 benchmark / source 的关联键

governance 读取该 truth source 时：

- 应通过稳定键定位
- 不应做模糊匹配
- 不应依赖目录扫描推断业务语义

## 6.6 Failure Semantics

若 governance 后续需要消费 `candidate_run_id`，但 truth source 不存在：

- 必须 fail-closed

不允许：

- 默认用 `experiment_id` 代替
- 直接用 `validation_id` 代替
- 用 `source_run_id` 拼接出伪造 id
- 在 governance 层缓存一个临时 mapping 当正式真相源

# 7. File Boundary

本 design 对应的后续实现预计不会先改 governance 文件。

应优先审计：

- experiment / candidate execution domain 中哪个文件或 artifact 更适合作为 truth source owner

明确不应先改：

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `apps/worker/main.py`

# 8. Verification

设计切片最小校验：

- 明确 `candidate_run_id` 的 owner 在实验侧
- 明确 governance 不负责生成 / 映射 / 伪造该字段
- 明确当前 handoff pending baseline 不应改
- 明确后续应先审 experiment-side truth source owner，再继续治理自动化

# 9. Risks And Guardrails

- 风险：为了快，直接在 governance 层拼 `candidate_run_id`
  - Guardrail：明确禁止拼接、默认值、临时 mapping
- 风险：为了“字段完整”，污染 handoff baseline
  - Guardrail：handoff 继续保持 pending 语义
- 风险：继续在 governance 内叠 owner，掩盖 experiment 侧缺口
  - Guardrail：明确把 owner 归属冻结在实验侧

# 10. Dual-axis Audit

- `M5` 归属：识别并冻结 governance 依赖的上游 identity truth source 边界
- `G5` 归属：为后续 candidate outcome upstream producer 提供合法输入前提
- `G6` 归属：保持 execution identity truth 与 governance truth consumption 分离
- 当前未触碰边界：
  - candidate outcome producer implementation
  - daily adoption
  - CLI / API / worker surface
