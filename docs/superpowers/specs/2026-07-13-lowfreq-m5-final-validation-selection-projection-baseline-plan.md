Status: active
Owner: lowfreq / governance / orchestrator
Scope: `M5 final validation selection/projection baseline` 的最小实施计划
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Final Validation Selection / Projection Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-final-validation-selection-projection-baseline-design.md`

## 1. 目标

本切片只实现 `M5 final validation selection/projection` 的独立 owner 基线。

本切片必须：

- 新增按 `source_run_id` 枚举 persisted candidate validation outcomes 的正式读面
- 新增独立的 final validation artifact / ledger 命名空间
- 新增 `run_governance_final_validation_selection(...)` runtime owner
- 固定 `unique-only` 选择语义：恰好 1 条 finalized candidate validation outcome 才允许产出 final truth
- 新增 focused tests，锁定 materialization、dry-run 与 fail-closed 语义

本切片明确不做：

- 不修改 `ValidationResult` contract
- 不修改既有 `candidate_validation_outcome` artifact / ledger schema
- 不实现 worker / CLI / API 触发面
- 不修改 `daily_master_orchestrator.json`
- 不把该 owner 注册成 `daily` scheduled task
- 不引入多 candidate 的比较、评分或 winner-ranking 逻辑
- 不修改 `reject_execution` 与 `status_transition` 既有消费语义

## 2. 文件边界

Spec 文件：

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-final-validation-selection-projection-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-final-validation-selection-projection-baseline-plan.md`

生产文件：

- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/runtime.py`

Focused test 文件：

- `tests/unit/test_m5_governance_final_validation_selection.py`

明确不修改：

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `apps/api/main.py`
- `apps/api/router.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_bootstrap_skeleton.py`
- `tests/integration/test_http_smoke.py`

## 3. 实施步骤

### M5FVS-S1：补齐按 `source_run_id` 的 candidate validation listing / read-model

修改：

- `neotrade3/governance/run_ledger.py`

实现：

1. 新增按 `source_run_id` 枚举 persisted candidate validation records 的正式读面
2. 该读面只返回已经过 contract 反序列化的正式记录，不把文件系统扫描逻辑泄露给 runtime caller
3. 读面需要保留 `validation_id`、`baseline_run_id`、`candidate_run_id`、`outcome`、`artifact_path`、`ledger_path`
4. 该读面必须只覆盖 `governance_candidate_validations` 命名空间，不混入 handoff / reject / status transition

实现规则：

- 不修改现有 `read_governance_candidate_validation_result(...)`
- 不把 listing 逻辑写进 `runtime.py`
- 返回顺序应稳定可预测，避免测试依赖目录遍历偶然性

### M5FVS-S2：新增 final validation artifact / ledger owner

修改：

- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`

实现：

1. 在 `artifact_writer.py` 中新增 final validation artifact record
2. 在 `run_ledger.py` 中新增 final validation ledger dataclass
3. 固定新命名空间：
   - `var/artifacts/governance_final_validations/<source_run_id>/governance_final_validation.json`
   - `var/ledgers/governance_final_validations/<source_run_id>/governance_final_validation_run.json`
4. artifact payload 只写单一 projection truth，至少包含：
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
5. ledger payload 至少包含：
   - `source_run_id`
   - `status`
   - `selected_validation_id`
   - `baseline_run_id`
   - `candidate_run_id`
   - `outcome`
   - `artifact_path`
   - `ledger_path`
   - `written_at`
6. 新增对应 readback / materialize helper

实现规则：

- 不内嵌完整 `ValidationResult` payload
- 不改写既有 candidate validation artifact / ledger
- `selection_basis` 固定为 `unique_persisted_candidate_validation`

### M5FVS-S3：新增 final validation runtime owner

修改：

- `neotrade3/governance/runtime.py`

实现：

1. 新增 `run_governance_final_validation_selection(...)`
2. 输入只接受：
   - `project_root`
   - `source_run_id`
   - `dry_run`
3. runtime 先读取 persisted handoff bundle
4. runtime 再通过 S1 的 listing/read-model 读取同一 `source_run_id` 下的 candidate validation outcomes
5. 应用 `unique-only` 选择语义：
   - 0 条：失败
   - 1 条 finalized outcome：继续
   - 多条：失败
6. 对唯一候选做一致性校验：
   - `baseline_run_id == source_run_id`
   - `validation_id` 必须存在于 handoff baseline validation results
   - outcome 必须是 final 状态，不能是 pending / incomplete
7. 调用 S2 的 materialize helper 产出 final truth

失败规则：

- 明确报错，不允许 silent fallback
- 不允许按最新时间选一条
- 不允许按 outcome 值做隐式优先级
- 不允许自动回退到 handoff baseline validation

### M5FVS-S4：新增 focused tests

修改：

- `tests/unit/test_m5_governance_final_validation_selection.py`

必测覆盖：

1. `run_governance_final_validation_selection(...)` 在唯一 finalized outcome 时成功写入独立 projection
2. `dry_run=True` 时返回记录但不落盘
3. 缺少 candidate validation outcome 时失败
4. 存在多条 candidate validation outcomes 时失败
5. persisted candidate validation 的 `baseline_run_id` 与 `source_run_id` 不一致时失败
6. selected validation 不在 handoff baseline 中时失败
7. 既有 handoff artifact 不被改写
8. 既有 candidate validation artifact / ledger 不被改写

测试规则：

- 复用已有 handoff / candidate validation fixture 载体
- 保持单文件 focused，不把 worker / CLI / API 测试混入本切片
- 断言路径与 payload 字段都使用正式命名空间

## 4. 最小验证

实施完成后至少执行：

- `python3 -m py_compile neotrade3/governance/artifact_writer.py neotrade3/governance/run_ledger.py neotrade3/governance/runtime.py tests/unit/test_m5_governance_final_validation_selection.py`
- focused pytest：
  - `tests/unit/test_m5_governance_final_validation_selection.py`

若本地无 `pytest` 可用：

- 保底执行 `py_compile`
- 并在测试文件内保持可被后续环境直接运行的 focused 断言结构

## 5. 完成判据

- 已存在按 `source_run_id` 的 candidate validation listing / read-model
- 已存在独立的 final validation artifact / ledger 与 readback
- runtime owner 只依赖 persisted truth，不接收新的 `validation_result`
- `unique-only` 选择语义被 focused tests 锁定
- 本切片未引入 `daily` 注册、未改 worker/API/CLI

## 6. 双轴审计

- `M5` 归属：补齐治理层 scheduler-facing final truth owner 的最小正式实现，不扩展 trigger surface
- `G5` 归属：把 candidate validation persisted truth 收敛成单一 projection，避免多 consumer 各自拼装最终结论
- `G6` 归属：以独立 artifact / ledger 保持 selection basis、上游引用与回放审计能力
- 未触碰边界：
  - candidate comparison
  - daily registration
  - worker / API / CLI adoption
  - launchd scheduler wiring
  - M6 delivery
