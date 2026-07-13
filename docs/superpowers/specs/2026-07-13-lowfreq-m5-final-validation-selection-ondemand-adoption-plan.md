Status: active
Owner: lowfreq / governance / worker / orchestrator
Scope: `M5 final validation selection on-demand adoption baseline` 的最小实施计划
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Final Validation Selection On-Demand Adoption Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-final-validation-selection-ondemand-adoption-design.md`

## 1. 目标

本切片只实现 `M5 final validation selection` 的 worker/orchestrator explicit on-demand adoption。

本切片必须：

- 在 `apps/worker/main.py` 的 governance executor 中新增
  `governance.final_validation_selection` 分支
- 让 on-demand orchestration task 能显式承载该 task shape
- 返回窄 `TaskResult.details`
- 在 `tests/unit/test_m5_governance_orchestrator_fit.py` 中补 focused tests，锁定
  success / dry-run / failure

本切片明确不做：

- 不修改 `run_governance_final_validation_selection(...)`
- 不修改 final validation artifact / ledger schema
- 不做 `daily_master_orchestrator.json` 注册
- 不做 CLI / API adoption
- 不做 docs/status 同步

## 2. 文件边界

Spec 文件：

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-final-validation-selection-ondemand-adoption-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-final-validation-selection-ondemand-adoption-plan.md`

生产文件：

- `apps/worker/main.py`

Focused test 文件：

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

## 3. 实施步骤

### M5FVSOA-S1：在 governance worker executor 中新增 final selection 分支

修改：

- `apps/worker/main.py`

实现：

1. 引入 `run_governance_final_validation_selection`
2. 在现有 governance executor 分流中新增：
   - `task.task_id == "governance.final_validation_selection"`
3. 读取并校验 `source_run_id`
4. 调用 runtime owner：
   - `run_governance_final_validation_selection(project_root=..., source_run_id=..., dry_run=...)`
5. 返回窄 `TaskResult.details`，至少包含：
   - `source_run_id`
   - `selected_validation_id`
   - `baseline_run_id`
   - `candidate_run_id`
   - `outcome`
   - `dry_run`
6. 返回 artifact refs：
   - final validation artifact
   - final validation ledger

实现规则：

- 不影响 handoff / candidate outcome / reject / status transition 的既有分流
- 错误处理继续沿用现有 governance executor 风格
- 不新增新的 worker CLI mode

### M5FVSOA-S2：补齐 on-demand task carrier

修改：

- `tests/unit/test_m5_governance_orchestrator_fit.py`

实现：

1. 参考现有 `_run_governance_reject_task(...)` 与 `_run_governance_status_transition_task(...)`
   模式
2. 新增 `_run_governance_final_validation_selection_task(...)`
3. 固定 task shape：
   - `task_id = "governance.final_validation_selection"`
   - `phase = GOVERNANCE`
   - `source_run_id` 从 on-demand request 直接传入
4. 不引入 `validation_id` / `validation_result`

### M5FVSOA-S3：新增 focused orchestrator-fit tests

修改：

- `tests/unit/test_m5_governance_orchestrator_fit.py`

必测覆盖：

1. success：
   - benchmark 已 materialize
   - governance handoff 已 materialize
   - candidate validation outcome 已存在且唯一
   - final validation selection on-demand 执行成功
2. dry-run：
   - 返回 `RunStatus.OK`
   - final validation artifact / ledger 不落盘
3. failure：
   - 缺少 candidate validation outcome 时返回 `RunStatus.FAILED`

测试规则：

- 复用已有 benchmark / handoff / candidate outcome helpers
- 不新增 HTTP / CLI / docs 测试
- 断言路径应指向 `governance_final_validations` 命名空间

## 4. 最小验证

至少执行：

- `python3 -m py_compile apps/worker/main.py tests/unit/test_m5_governance_orchestrator_fit.py`
- `python3 -m pytest tests/unit/test_m5_governance_orchestrator_fit.py`

## 5. 完成判据

- governance worker executor 已支持 `governance.final_validation_selection`
- on-demand orchestration carrier 可执行该任务
- focused tests 已覆盖 success / dry-run / failure
- 本切片未触碰 `daily` / CLI / API / docs

## 6. 双轴审计

- `M5` 归属：为 final validation formal owner 补最小 orchestration execution surface
- `G5` 归属：让 final truth 能通过正式 on-demand carrier 被调用与回放
- 未触碰边界：
  - daily registration
  - CLI / API adoption
  - docs/status
  - candidate comparison
