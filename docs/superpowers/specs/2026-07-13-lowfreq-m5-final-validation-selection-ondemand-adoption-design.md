Status: active
Owner: lowfreq / governance / worker / orchestrator
Scope: Narrow design for the `M5 final validation selection on-demand adoption baseline`
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# 1. Background

`M5 final validation selection/projection owner` 已完成 runtime、artifact、ledger 与 focused
tests，但当前还没有进入外部可触发的 orchestration ownership surface。

现状证据：

- `run_governance_final_validation_selection(...)` 已存在
- governance worker executor 当前只分流：
  - handoff
  - candidate validation outcome
  - reject execution
  - status transition
- `daily_master_orchestrator.json` 当前没有 candidate outcome truth producer，因此若直接注册
  `final validation selection` 为 `daily` 任务，会稳定失败

因此，当前最窄且高质量的下一步不是 `daily adoption`，而是先补：

- worker/orchestrator explicit on-demand adoption

# 2. Goal

本切片目标是为已存在的 `final validation selection owner` 增加最小 external execution
surface，同时保持边界收敛：

- 让 governance worker executor 能识别并执行
  `governance.final_validation_selection`
- 让 orchestrator on-demand task shape 能显式承载该任务
- 通过 focused orchestrator-fit tests 锁定 success / dry-run / failure 行为

# 3. Non-Goals

本切片明确不做：

- 不修改 `run_governance_final_validation_selection(...)` 语义
- 不修改 final validation artifact / ledger schema
- 不增加 CLI 入口
- 不增加 API 入口
- 不修改 `daily_master_orchestrator.json`
- 不同步 docs/status
- 不引入 candidate outcome 自动触发或 `daily` 自动衔接

# 4. Chosen Approach

采用 worker-governance executor 的薄接线方案：

- 不新增新的 runtime owner
- 不新增新的 orchestration phase
- 只在现有 `GOVERNANCE` executor 中新增一个 `task_id` 分支
- 只通过 `OnDemandTaskRequest` 暴露这条链路

放弃的两个方案：

- 直接注册 `daily` task
  - 当前 upstream 没有 daily candidate outcome producer，会形成稳定失败任务
- 先做 CLI/API adoption
  - 会增加多处 surface 维护成本，但不能优先解决 scheduler-facing/worker-owned execution gap

# 5. Design Decisions

## 5.1 Task Shape

新增的 on-demand governance task 形态固定为：

- `task_id`: `governance.final_validation_selection`
- `phase`: `GOVERNANCE`
- `entrypoint`:
  - `neotrade3.governance.runtime:run_governance_final_validation_selection`
- `args_template`:
  - `source_run_id`
- `outputs`:
  - `governance_final_validation_artifact`
  - `governance_final_validation_ledger`

不接受：

- `validation_id`
- `validation_result`
- 其它推导字段

因为当前 owner 的 contract 只依赖 persisted truth 与 `source_run_id`。

## 5.2 Worker Executor Routing

在 `apps/worker/main.py` 的 governance executor 中新增显式分支：

- 若 `task.task_id == "governance.final_validation_selection"`
  - 要求 `source_run_id` 非空
  - 调用 `run_governance_final_validation_selection(...)`
  - 返回窄 `TaskResult.details`

推荐最小 `details` 投影：

- `source_run_id`
- `selected_validation_id`
- `baseline_run_id`
- `candidate_run_id`
- `outcome`
- `dry_run`

实现必须保持：

- 不影响既有 handoff / candidate outcome / reject / status transition 分流顺序
- 失败时继续沿用现有 governance executor 的 `RunStatus.FAILED` 与 message 风格

## 5.3 Orchestrator Fit Tests

新增 focused tests 只验证 on-demand adoption，不验证 docs/HTTP/CLI：

- success:
  - 已有 handoff
  - 已有唯一 candidate validation outcome
  - final validation selection on-demand task 可成功 materialize
- dry-run:
  - 返回 `RunStatus.OK`
  - 不落 final validation artifact / ledger
- failure:
  - 缺少 candidate validation outcome 时返回 `RunStatus.FAILED`

测试应复用已有的：

- benchmark materialization helper
- governance handoff helper
- candidate validation outcome materialization helper
- orchestrator execute_run_plan carrier

## 5.4 Boundary Guardrails

本切片要防止两个质量风险：

- 把 on-demand adoption 误做成 `daily` adoption
  - Guardrail：不改 `daily_master_orchestrator.json`
- 为了“顺手完整”而扩大到 CLI/API/docs
  - Guardrail：只改 worker 与 orchestrator-fit tests

# 6. File Boundary

本切片实现预计只修改：

- `apps/worker/main.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

明确不修改：

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `neotrade3/governance/cli.py`
- `apps/api/main.py`
- `apps/api/router.py`
- `docs/operations/bootstrap_runbook.md`
- `PROJECT_STATUS.md`

# 7. Verification

本切片最小验证：

- `python3 -m py_compile apps/worker/main.py tests/unit/test_m5_governance_orchestrator_fit.py`
- focused pytest:
  - `tests/unit/test_m5_governance_orchestrator_fit.py`

# 8. Dual-axis Audit

- `M5` 归属：为已存在的 final validation formal owner 补 worker/orchestrator adoption，不扩展治理语义
- `G5` 归属：让 final truth 可以通过正式 orchestration carrier 执行与回放
- 未触碰边界：
  - daily registration
  - CLI / API surface
  - docs/status sync
  - candidate comparison
