Status: active
Owner: lowfreq / chaos-model
Scope: 混沌模型 v0 可执行任务清单（含证据与门禁）
Canonical: docs/superpowers/specs/2026-07-20-chaos-model-implementation-plan.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-20

# 混沌模型 v0 执行任务清单

日期：2026-07-20  
对应计划：`docs/superpowers/specs/2026-07-20-chaos-model-implementation-plan.md`

## 0. 清单目标

本清单用于把混沌模型的实施工作压缩到：

- 明确的文件级落点
- 明确的对象级交付物
- 明确的测试/门禁证据
- 明确的性能与磁盘容量基准

## 1. Task A：冻结对象契约与注册表（Phase 0）

### Task A1：冻结 chaos_snapshot 契约（M3 输出）

产出：

- `docs/architecture/lowfreq_v16_model_rulebook.md` 中存在 `chaos_snapshot` 的字段级描述与 fail-closed 语义（planned→implemented 时需补齐测试证据）。
- `docs/superpowers/specs/2026-07-20-chaos-model-design.md` 与 rulebook 一致。

证据：

- `docs/architecture/lowfreq_v16_model_rulebook.md`
- `docs/superpowers/specs/2026-07-20-chaos-model-design.md`

完成判定：

- `tests/unit/test_rulebook_contract_registry_gate.py` 通过

### Task A2：冻结 Factor Registry 的字段集合与分类权重调节器（3:4:3）

产出：

- Factor Registry 字段集合与分类权重语义写入 design/spec，并明确版本化策略。

证据：

- `docs/superpowers/specs/2026-07-20-chaos-model-design.md`

完成判定：

- 文档内不存在“按业务阶段切换阴阳刻度”的表述

## 2. Task B：M3 混沌快照输出（Phase 1）

### Task B1：在 position contract snapshot 中引入 chaos_snapshot 字段

产出：

- `chaos_snapshot` 与 `hazard_snapshot` 并行存在，且不相互污染。

建议落点：

- `neotrade3/decision_engine/position_contract_snapshot.py`
- `lowfreq_engine_v16_advanced.py`

证据：

- 单测：新增 `tests/unit/test_chaos_snapshot_contract_v0.py`（路径占位，实施阶段补齐）

完成判定：

- 新增单测通过
- `tests/unit/test_rulebook_contract_registry_gate.py` 继续通过

### Task B2：合规闸门（fail-closed）

产出：

- M3 混沌计算不得读取任何离线标签表/未来窗口真值表；违反即 fail。

证据：

- 单测：新增 `tests/unit/test_chaos_compliance_gate.py`（路径占位，实施阶段补齐）

完成判定：

- 合规闸门单测通过（fail-closed）

## 3. Task C：全市场日度矩阵落盘与基准（Phase 2）

### Task C1：落盘 DB 结构（EAV）

产出：

- `var/db/chaos_factor_matrix.db`（或等价路径）包含：
  - `chaos_factor_registry`
  - `chaos_factor_values`
  - `chaos_daily_snapshot`

证据：

- 迁移/建库脚本（实施阶段确定落点）
- 最小读回脚本（实施阶段确定落点）

完成判定：

- 小样本可复算（写入后可读回）

### Task C2：性能/容量基准（必须先测再扩）

产出：

- 基准脚本：`scripts/bench_chaos_factor_matrix_v0.py`（实施阶段补齐）
- 基准报告（可复现）：耗时、DB 增长速度、外推规模估算

完成判定：

- 基准结果可定位、可重复运行

## 4. Task D：M4 偏差监测与 M5 治理版本（Phase 3-4）

### Task D1：M4 偏差监测入口

产出：

- 监测脚本/任务入口可复现，并输出“混沌判断 vs 后验走势”的偏差归因报告（不进入 M3 输入）。

完成判定：

- 产物落盘可定位

### Task D2：M5 版本化回灌

产出：

- `factor_registry_version / weights_version / thresholds_version` 的治理对象与落盘策略（实现阶段确定）。

完成判定：

- M3 仅消费批准版本；无批准版本时 fail-closed（只观察、不得强动作）

