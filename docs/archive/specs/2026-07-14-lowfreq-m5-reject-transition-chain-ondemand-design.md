Status: Approved
Owner: system_governance
Scope: M5 governance on-demand chain for `final_validation_selection -> reject_execution -> status_transition`
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-14-lowfreq-m5-reject-transition-chain-ondemand-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-14

# M5 Reject Transition Chain (On-Demand) Design

## 背景

当前 M5 已具备以下独立 owner 与触发面：

- `final_validation_selection`：从 persisted candidate validation outcome 中做 `unique-only` 选择，并物化 `governance_final_validations`
- `reject_execution`：基于 `validation_id` 物化 reject execution 产物（decision record + ledger）
- `status_transition`：基于 `validation_id` 与 reject proof 物化有效的 blocker/attention 状态投影

现状问题是：`reject_execution` 与 `status_transition` 的 on-demand 触发面要求调用方显式提供 `validation_id`，导致“链路触发成本高、人工拼接容易出错”。同时，由于这两个动作具备明确副作用（写入治理产物），不能进入 `daily` 默认自动化链路。

## 目标

- 提供一个新的 **显式 on-demand 链路 owner**：只输入 `source_run_id`，内部自动完成：
  - `final_validation_selection`
  - 若最终 outcome 为 `rejected`：自动执行 `reject_execution` 与 `status_transition`
- 保持 fail-closed：
  - 若 `final_validation_selection` fail，则整个链路 fail（不产生副作用产物）
  - 若 `final_validation_selection` 返回 non-rejected，则链路停在 selection（不产生 reject/transition 副作用）

## 非目标

- 不进入 `daily` scheduled adoption
- 不扩 CLI / API mode
- 不改变 `reject_execution/status_transition` 的契约（仍然以 `validation_id` 为显式输入）
- 不在 governance 内推断 `passed`（链路只消费已存在的 selection/outcome 真相）

## 关键约束（契约与真相源）

- `candidate_run_id` 的 truth source 位于 benchmark persisted truth；治理链路不得发明该字段
- `final_validation_selection` 采用 `unique-only` 语义：存在 0 或 >1 个候选 outcome 时 fail-closed
- 只有当 selected outcome 为 `rejected` 时允许触发 reject/transition 副作用

## 方案概述

### 1) 新增 runtime owner

新增 runtime owner：

```python
def run_governance_reject_transition_chain(
    *,
    project_root: str | Path,
    source_run_id: str,
    dry_run: bool = False,
) -> dict[str, object]:
    ...
```

内部顺序：

1. `final_record = run_governance_final_validation_selection(project_root, source_run_id, dry_run=dry_run)`
2. 若 `final_record.outcome != "rejected"`：
   - 返回 chain result（包含 `selection` 结果）
   - 不执行 reject/transition
3. 若 `final_record.outcome == "rejected"`：
   - `reject_record = run_governance_reject_execution(project_root, source_run_id, validation_id=final_record.selected_validation_id, dry_run=dry_run)`
   - `transition_record = run_governance_status_transition(project_root, source_run_id, validation_id=final_record.selected_validation_id, dry_run=dry_run)`
   - 返回 chain result（包含三段 record 的关键字段与 artifact refs）

### 2) 新增 worker/orchestrator on-demand carrier

新增一个治理 on-demand task：

- `task_id`: `governance.reject_transition_chain`
- `args_template`: `{ "source_run_id": <caller_provided> }`

执行时仅调用上述 runtime owner；不新增 CLI/API mode。

## 输出（chain result）建议形状

返回 `TaskResult.details` 最小字段（建议）：

- `source_run_id`
- `selected_validation_id`
- `outcome`
- `executed_reject_execution: bool`
- `executed_status_transition: bool`
- `final_validation_artifact_refs`（可选：与 worker 当前 final_selection 返回一致）
- `reject_artifact_refs`（当且仅当 executed）
- `transition_artifact_refs`（当且仅当 executed）
- `dry_run`

## 失败闭合语义

- selection 失败：返回 FAILED（保留底层异常 message），后续步骤不执行
- selection outcome 非 rejected：返回 OK，但 `executed_* == False`
- reject_execution 失败：返回 FAILED，status_transition 不执行
- status_transition 失败：返回 FAILED

## 测试策略（最小）

### runtime focused tests

- rejected 全链 success（selection + reject + transition）
- non-rejected（passed）仅 selection success，不产生 reject/transition 产物
- dry-run：三段均不写文件
- selection fail-closed：无 outcome 或 ambiguous outcome 时链路 fail

### orchestrator-fit

通过 `OnDemandTaskRequest` 触发新 task，覆盖：

- success（rejected）返回 OK 并带全链 details
- non-rejected 不产生下游产物
- fail-closed：缺 candidate outcome 时 selection 失败，链路失败

## 迁移与风险

- 风险：链路把“选择真相”与“执行治理动作”串联，若误触发会扩大副作用范围
- 缓解：维持 on-demand；仅对 `rejected` 执行；默认 fail-closed；不进入 daily
