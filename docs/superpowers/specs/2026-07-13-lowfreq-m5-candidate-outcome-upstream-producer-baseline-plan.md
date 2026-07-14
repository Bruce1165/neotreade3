Status: active
Owner: lowfreq / governance / runtime
Scope: `M5 candidate outcome upstream producer baseline` 的最小实施计划
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Candidate Outcome Upstream Producer Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-outcome-upstream-producer-baseline-design.md`

## 1. 目标

本切片只实现 `M5 candidate outcome upstream producer owner` 的最小基线。

本切片必须：

- 新增独立 runtime owner：
  - `run_governance_candidate_outcome_upstream_producer(...)`
- 输入只依赖 persisted governance truth
- 输出直接复用现有 `ValidationResult` contract
- 输出可被既有 `run_governance_candidate_validation_outcome(...)` 直接消费
- 新增 focused tests，锁定 success / fail-closed / immutable-boundary

本切片明确不做：

- 不修改 `ValidationResult` contract
- 不修改 handoff schema
- 不修改 candidate outcome artifact / ledger schema
- 不做 `daily_master_orchestrator.json` 注册
- 不做 worker / CLI / API adoption
- 不做 docs/status 同步
- 不做 multi-candidate comparison / ranking / winner selection

## 2. 文件边界

Spec 文件：

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-outcome-upstream-producer-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-candidate-outcome-upstream-producer-baseline-plan.md`

生产文件：

- `neotrade3/governance/runtime.py`
- 如有必要的同目录 helper owner 文件

Focused test 文件：

- `tests/unit/test_m5_governance_candidate_outcome_upstream_producer.py`

明确不修改：

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `config/orchestrator/daily_master_orchestrator.json`
- `apps/worker/main.py`
- `apps/api/main.py`
- `apps/api/router.py`
- `docs/operations/bootstrap_runbook.md`
- `PROJECT_STATUS.md`

## 3. 实施步骤

### M5COUP-S1：新增 upstream producer runtime owner

修改：

- `neotrade3/governance/runtime.py`

实现：

1. 新增 `run_governance_candidate_outcome_upstream_producer(...)`
2. 输入固定为：
   - `project_root`
   - `source_run_id`
3. 读取 persisted governance handoff bundle
4. 从 handoff bundle 中读取 pending `validation_results`
5. 基于已定义的正式 evidence sources，推导一个可成立的 final `ValidationResult`
6. 返回该 `ValidationResult`，但本步不持久化 candidate outcome artifact/ledger

实现规则：

- 不接受人工传入 `validation_result`
- 不改写 handoff bundle
- 不扫描未定义的新证据源
- 若证据不足，必须抛错，不得默认给 outcome

### M5COUP-S2：保持与既有 candidate outcome persistence owner 的薄耦合

修改：

- `neotrade3/governance/runtime.py`

实现：

1. 明确 producer owner 的输出 shape 与 `ValidationResult` 一致
2. 保证该结果可直接传给：
   - `run_governance_candidate_validation_outcome(...)`
3. 本切片不新增独立 persistence owner
4. 本切片不修改现有 `run_governance_candidate_validation_outcome(...)` 行为

实现规则：

- 不创建并行 schema
- 不创建中间 projection payload
- 不让 producer owner 兼任 persistence owner

### M5COUP-S3：新增 focused tests

修改：

- `tests/unit/test_m5_governance_candidate_outcome_upstream_producer.py`

必测覆盖：

1. success：
   - handoff 存在
   - pending validation 存在
   - evidence 足够
   - owner 成功返回合法 `ValidationResult`
2. compatibility：
   - producer 输出可被现有
     `run_governance_candidate_validation_outcome(...)` 直接消费
3. failure：
   - handoff 不存在时失败
   - pending validation 不存在时失败
   - evidence 不足时失败
4. immutable boundary：
   - handoff artifact 不被改写

测试规则：

- 复用已有 handoff / candidate outcome fixture 思路
- 保持 focused，不混 worker / API / daily / docs 测试
- 若需要构造 evidence，必须使用当前仓库已存在的正式证据载体

## 4. 最小验证

至少执行：

- `python3 -m py_compile neotrade3/governance/runtime.py tests/unit/test_m5_governance_candidate_outcome_upstream_producer.py`
- `python3 -m pytest tests/unit/test_m5_governance_candidate_outcome_upstream_producer.py`

## 5. 完成判据

- 已存在独立 upstream producer runtime owner
- 输出为合法 `ValidationResult`
- 输出可被现有 candidate outcome persistence runtime 直接消费
- focused tests 已锁定 success / failure / immutable-boundary
- 本切片未触碰 `daily` / worker / CLI / API / docs

## 6. 双轴审计

- `M5` 归属：补齐 governance candidate outcome 的非人工 upstream truth production owner
- `G5` 归属：为后续 scheduler-facing adoption 提供真实上游，而不是继续扩大人工触发面
- `G6` 归属：保持 truth production、truth persistence、truth selection 三层 owner 分离
- 未触碰边界：
  - daily adoption
  - CLI / API surface
  - candidate comparison
  - final selection daily registration
