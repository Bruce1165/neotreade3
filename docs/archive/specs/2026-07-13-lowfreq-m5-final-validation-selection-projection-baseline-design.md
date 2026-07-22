Status: active
Owner: lowfreq / governance / orchestrator
Scope: Narrow design for the `M5 final validation selection/projection baseline`
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Background

`M5 candidate validation outcome` 已完成 persisted truth materialization 与
`runtime -> CLI -> worker -> API` trigger adoption，但当前仍停留在 on-demand
surface。

现状证据：

- `daily orchestrator` 当前只注册到 `governance.materialize_handoff`
- `candidate_validation_outcome` 需要显式 `source_run_id + validation_result`
- `reject_execution` 与 `status_transition` 已消费 persisted candidate validation truth
- 仓库当前只提供按 `validation_id` 的 candidate validation 读回，不存在按
  `source_run_id` 的正式 listing / selection owner

因此，当前缺口不是再次扩展 trigger，而是补一个可被 scheduler / daily 消费的
formal owner，用来把 persisted candidate validation outcomes 收敛成单一的
`final validation truth`。

# 2. Goal

设计一个独立的 `selection/projection owner`，满足以下目标：

- 输入来源固定为 persisted `candidate validation outcome` truth
- 输出固定为按 `source_run_id` 键控的单一 `final validation truth`
- 输出形态可被 `daily orchestrator` 直接消费，不要求 consumer 再做二次投影
- 不修改既有 `candidate_validation_outcome` schema 与命名空间
- 不把当前 on-demand 语义误写成已完成的 `daily scheduled adoption`

# 3. Non-Goals

本切片明确不做：

- 不修改 `ValidationResult` contract
- 不修改 `candidate_validation_outcome` artifact / ledger schema
- 不把 `candidate_validation_outcome` 直接注册为 `daily` task
- 不引入多 candidate 的自动比较、评分或 winner-ranking 逻辑
- 不改 `reject_execution` 与 `status_transition` 的 runtime 语义
- 不触碰 `launchd`、`scheduler` job 配置
- 不处理 `M6`

# 4. Chosen Approach

选用独立 owner 方案：

- 新建独立命名空间承载 `final validation truth`
- 该 owner 只消费 persisted candidate validation outcomes
- 该 owner 自己完成选择与最小投影，不把投影责任下放给 `daily` consumer
- 该 owner 的输出键使用 `source_run_id`，因为 `daily orchestrator` 当前的治理主链
  与 benchmark/handoff 都以 `source_run_id` 为跨层关联键

放弃的两个方案：

- 薄选择器方案：只写 `selected_validation_id`
  - 问题：会把 projection 责任分散到 consumer，daily 仍然没有单一真相源
- 完整拷贝方案：复制整份 `ValidationResult`
  - 问题：会和现有 persisted candidate outcome truth 重复，形成双份 payload

# 5. Design Decisions

## 5.1 Owner 与命名空间

新增一个独立的 final-truth owner，推荐命名为：

- runtime owner:
  - `run_governance_final_validation_selection(...)`
- artifact namespace:
  - `var/artifacts/governance_final_validations/<source_run_id>/governance_final_validation.json`
- ledger namespace:
  - `var/ledgers/governance_final_validations/<source_run_id>/governance_final_validation_run.json`

该命名空间与现有四类治理对象保持并列关系，而不是覆写：

- `governance_handoffs`
- `governance_candidate_validations`
- `governance_rejections`
- `governance_status_transitions`

## 5.2 输入真相源

该 owner 的输入必须全部来自已持久化对象：

- `source_run_id`
- persisted governance handoff bundle
- persisted candidate validation outcomes under the same `source_run_id`

约束：

- 不接受调用方直接提交新的 `validation_result`
- 不从 handoff payload 直接把 baseline validation 当作 final truth
- 不通过 `validation_id` 单点读取来假装完成 selection

这意味着实现阶段必须补一个正式 listing/read-model，用于按 `source_run_id`
枚举 candidate validation records；不能让 `daily` 或 runtime caller 自己扫描。

## 5.3 选择语义基线

本设计采用最保守的唯一性选择语义：

- 对于给定 `source_run_id`
- owner 读取所有 persisted candidate validation outcomes
- 只接受“恰好存在 1 条 finalized candidate validation outcome”的场景
- 这 1 条记录必须：
  - 其 `baseline_run_id` 与 `source_run_id` 一致
  - 其 `validation_id` 能在 persisted handoff baseline 中找到
  - 其 outcome 已是 final 状态，而不是 pending / incomplete

若出现以下任一情况，owner 必须 fail-closed，而不是猜测：

- 没有 persisted candidate validation outcome
- 存在多条 candidate validation outcomes
- persisted outcome 与 handoff baseline 不一致
- persisted outcome 不是 final 结果

这样做的原因是：

- 当前仓库没有 formal 的 candidate-comparison owner
- 当前也没有任何证据支持“多 candidate 下如何自动选 winner”
- 在缺少 formal comparison semantics 前，唯一性选择是唯一不会伪造业务语义的基线

## 5.4 输出投影 contract

该 owner 输出的是单一投影真值，而不是完整复制 `ValidationResult`。

推荐最小 artifact payload：

- `source_run_id`
- `selected_validation_id`
- `baseline_run_id`
- `candidate_run_id`
- `outcome`
- `selection_basis`
- `candidate_validation_artifact_path`
- `candidate_validation_ledger_path`
- `handoff_artifact_path`
- `written_at`

其中：

- `selection_basis` 固定为
  `unique_persisted_candidate_validation`
- 不内嵌完整 `validation_result` payload
- 需要保留到上游 truth 的 path/ref，便于 downstream 回溯与审计

推荐 ledger contract 字段：

- `source_run_id`
- `status`
- `selected_validation_id`
- `baseline_run_id`
- `candidate_run_id`
- `outcome`
- `artifact_path`
- `ledger_path`
- `written_at`

## 5.5 与 orchestrator 的关系

本 design 先冻结 formal owner，不直接把它写进 `daily` config。

原因：

- 当前主链缺的是 `selection/projection semantics`
- 不是 `daily_master_orchestrator.json` 的 JSON 写法
- 只有在 formal owner 落地后，`daily` 才有资格消费一个单一 final truth

因此，本切片之后的顺序应为：

1. 先实现 `final validation selection/projection owner`
2. 补 focused tests 与 readback
3. 再单独审计是否需要把该 owner 注册成 `daily` governance task

## 5.6 失败语义

该 owner 必须是 deterministic failure，而不是 silent fallback：

- zero candidates:
  - fail with explicit `no persisted candidate validation outcome found`
- multiple candidates:
  - fail with explicit `ambiguous candidate validation outcomes`
- mismatch with handoff:
  - fail with explicit `persisted candidate validation does not match handoff baseline`

不允许：

- 从多条中按时间最新一条自动选中
- 按 outcome 值做隐式优先级
- 自动回退到 handoff baseline validation

# 6. File Boundary

本 design 对应的后续实现预计只会涉及以下范围：

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `apps/worker/main.py` 或 `config/orchestrator/daily_master_orchestrator.json`
  中的后续 adoption 文件
- focused tests

本 design 文档本身不要求立即修改上述生产文件。

# 7. Risks and Guardrails

- 风险：把 `selection owner` 误做成 `candidate_validation_outcome` 的 schema 扩展
  - Guardrail：独立命名空间，禁止改写既有 outcome artifact/ledger
- 风险：在多 candidate 场景下偷偷引入比较语义
  - Guardrail：唯一性选择，非唯一即失败
- 风险：让 consumer 自己做二次投影
  - Guardrail：owner 必须产出单一 final truth projection
- 风险：在 owner 未实现前就把能力表述成 `daily adoption`
  - Guardrail：设计中明确将 daily registration 放到后续独立切片

# 8. Verification

设计切片最小校验：

- 文档内容与当前代码事实一致
- 不把已实现的 on-demand truth materialization 描述成 scheduler adoption
- 明确写出唯一性选择语义与 fail-closed 边界

# 9. Dual-axis Audit

- `M5` 归属：为治理层补齐 `final validation truth` 的 formal owner，而不是再次扩展 trigger surface
- `G5/G6` 归属：为 scheduler-facing consumption 提供单一真相源与可审计投影，避免多 consumer 各自推导最终结论
- 已冻结边界：
  - input truth source = persisted candidate validation outcomes
  - output truth shape = source_run_id-keyed final projection
  - selection semantics = unique-only, otherwise fail
- 未触碰边界：
  - candidate comparison
  - daily registration
  - launchd scheduler wiring
  - M6 delivery
