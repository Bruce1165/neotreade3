# M4 m2_shadow_bundle_ref 实现计划

日期：2026-07-15  
对应文档：

- `docs/superpowers/specs/2026-07-15-lowfreq-m4-m2-shadow-bundle-ref-truth-source-design.md`
- `docs/superpowers/specs/2026-07-15-lowfreq-m4-m2-shadow-bundle-ref-implementation-plan.md`

## 1. 目标

本计划只覆盖 `m2_shadow_bundle_ref` 真实 truth-source 的最小实现，不扩展到 `m3_context_ref` 或更宽的 persisted refs 建设。

本轮目标只有四个：

1. 在 `neotrade3/cycle_intelligence/` 内建立 `m2_shadow_bundle` 的最小 bundle 级 owner/readback。
2. 在 `M4 replay resolver` 中为 `m2_shadow_bundle_ref` 接入真实 source 分支。
3. 用聚焦回归锁定 mixed mode 成功路径与 fail-closed 失败路径。
4. 在不改变 `M/G` 边界的前提下完成最小验证与提交边界收口。

本轮必须产出的核心结果：

- `m2_shadow_bundle` 有最小 typed object
- `m2_shadow_bundle` 有 `artifact + ledger + typed readback`
- replay mixed mode 可消费真实 `m2_shadow_bundle_ref`
- 缺失 ref / 类型错 / 版本错按预期 fail-closed

## 2. 不在本轮完成

- `m3_context_ref` 真实化
- `m2_shadow_bundle` 拆成 5 个独立 owner
- `decision_engine` persisted owner 建设
- `apps/api/*`、`apps/worker/*`、`governance/*` 改动
- `daily` 调度改动
- `BenchmarkBatchRunResult` schema 调整

## 3. 当前实施起点

### 3.1 已有基础

- `m2_cycle_ref(real)` 已完成 `artifact + ledger + typed readback`
- `m1_context_ref(real)` 已完成 benchmark-local projection owner/readback
- `resolver_refs + resolver_stub` 已证明 replay 输入层落点正确
- `benchmark assembler` 已稳定消费 `m2_shadow_bundle` 的 bundle 形状

### 3.2 当前缺口

- `cycle_intelligence` 只有 `small_cycle` persisted owner，没有 `m2_shadow_bundle` owner
- `benchmark batch_runner` 对 `m2_shadow_bundle_ref` 仍只支持 stub
- 缺少 bundle 级 readback round-trip 测试
- mixed mode 尚未覆盖 `real m2_shadow_bundle_ref`

## 4. 实施原则

- 先 owner，再 resolver，再测试，再验证，再收口。
- 只新增一个 bundle 级 truth-source，不拆子对象 owner。
- 不允许自动 fallback 到 stub。
- 不允许因实现方便而把 truth-source 下沉到 `benchmark` 私有层。
- 不允许修改治理、调度、API、worker。

## 5. 建议改动落点

允许改动的文件范围严格限制在：

- `neotrade3/cycle_intelligence/`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/__init__.py`
- `tests/unit/test_m2_*`
- `tests/unit/test_m4_benchmark_*`

首批建议新增或扩展的文件：

- `neotrade3/cycle_intelligence/shadow_bundle.py` 或同级最小承载文件
- `neotrade3/cycle_intelligence/__init__.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/__init__.py`
- `tests/unit/test_m2_shadow_bundle_persistence.py`
- `tests/unit/test_m4_benchmark_replay_manifest.py`

## 6. 总体分段

本计划建议分为五段执行：

- `P1-A`：bundle object 与 owner 落点建立
- `P1-B`：artifact/ledger/readback 收口
- `P1-C`：resolver 接线
- `P1-D`：success/fail-closed 回归补齐
- `P1-E`：最小验证与提交边界审计

## 7. 分段实施计划

### P1-A：bundle object 与 owner 落点建立

目标：

- 在 `cycle_intelligence` 中给 `m2_shadow_bundle` 建立稳定代码承载位点。

任务：

- 定义 bundle object 常量：
  - `M2_SHADOW_BUNDLE_OBJECT_TYPE`
  - `M2_SHADOW_BUNDLE_OBJECT_VERSION`
- 定义 bundle typed object
- 为 `from_dict()` 明确 fail-closed 校验：
  - 必需组成块齐全
  - `mid_cycle_states` 为合法映射
  - `object_type/object_version` 合法
- 定义 `to_payload()` 输出形状

完成判定：

- 代码中已经存在 bundle typed object
- 不再需要在 resolver 或测试里直接手工拼完整 bundle 形状作为“对象替代品”

### P1-B：artifact/ledger/readback 收口

目标：

- 为 bundle object 建立与 `small_cycle` 同级别的最小 persisted owner。

任务：

- 定义 `record_id` 生成函数
- 定义 artifact 写入函数
- 定义 ledger 写入函数
- 定义 materialize 函数
- 定义 typed readback 函数
- 在 `__init__.py` 中做最小导出

建议路径：

- `var/artifacts/m2_shadow_bundles/<record_id>/shadow_bundle.json`
- `var/ledgers/m2_shadow_bundles/<record_id>/shadow_bundle.json`

完成判定：

- 可从 typed object materialize 到 artifact/ledger
- 可从 `record_id` 稳定回读 typed object

### P1-C：resolver 接线

目标：

- 让 `benchmark replay` 能消费真实 `m2_shadow_bundle_ref`。

任务：

- 在 `batch_runner.py` 中新增真实 source 常量
- 在 `ALLOWED_PERSISTED_REF_SOURCE_TYPES` 中登记新 source
- 新增 `_resolve_m2_shadow_bundle_ref_payload(...)`
- 在 `_resolve_replay_stub_payloads(...)` 中仅替换 `m2_shadow_bundle_ref` 的读取分支

关键约束：

- `m2_cycle_ref`、`m1_context_ref` 现有真实分支不改语义
- `m3_context_ref` 继续 stub
- 不改 `_run_benchmark_replay_manifest(...)` 输出路径

完成判定：

- mixed mode 下 `m2_shadow_bundle_ref` 可走真实 source
- 其余分支行为不变

### P1-D：success/fail-closed 回归补齐

目标：

- 用最小单测覆盖 owner round-trip 与 replay mixed mode。

任务：

- 新增 `test_m2_shadow_bundle_persistence.py`
- 在 `test_m4_benchmark_replay_manifest.py` 中新增 success 用例：
  - `real m2_cycle_ref + real m2_shadow_bundle_ref + real m1_context_ref + stub m3_context_ref`
- 新增 failure 用例：
  - 缺失真实 `m2_shadow_bundle_ref`
  - `object_type mismatch`
  - `object_version mismatch`

说明：

- 上述失败若命中 fail-closed 预期，应判定为测试通过，不视为实现 bug。

完成判定：

- success 路径可通过
- 预期失败路径可稳定复现并被断言锁定

### P1-E：最小验证与提交边界审计

目标：

- 在提交前完成 Syntax/Semantic 最小验证，并确认提交仍是原子切片。

验证动作：

- `python3 -m py_compile` 覆盖新增/修改文件
- `python3 -m pytest -q` 覆盖：
  - bundle persistence
  - replay manifest
  - 已有关联回归

提交前审计：

- `git status --short`
- `git diff --stat`
- 指定文件 `git diff`

完成判定：

- 工作区只包含本刀相关文件
- 验证全部通过
- 无文档、治理、调度、API、worker 混入

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 新增 bundle typed object 与常量
2. 落 artifact/ledger/readback
3. 导出 `cycle_intelligence` 对外接口
4. 接线 `benchmark replay resolver`
5. 补 persistence 测试
6. 补 replay mixed-mode 测试
7. 运行最小验证
8. 做提交边界审计

原因：

- resolver 依赖 typed readback
- 测试应在 owner 与 resolver 完成后一次性收口
- 先完成 owner 再接线，最不容易在 `batch_runner.py` 内堆积临时逻辑

## 9. 风险点

### 风险 1：bundle object 形状漂移

表现：

- 为了“通用性”改写 `benchmark assembler` 当前消费形状

控制：

- bundle payload 完全保持现有 replay/assembler 预期形状

### 风险 2：owner 归口漂移到 benchmark

表现：

- 把 bundle readback 写进 `neotrade3/benchmark/`

控制：

- truth-source 只允许落在 `cycle_intelligence`

### 风险 3：失败闭合被偷偷放宽

表现：

- 缺失 `m2_shadow_bundle_ref` 时自动 fallback 到 stub

控制：

- failure 用例必须显式断言错误消息

### 风险 4：顺手扩到 m3_context

表现：

- 在接线时顺手为 `m3_context_ref` 设计 owner

控制：

- 本轮明确禁止修改 `decision_engine/*`

## 10. 验收标准

本计划完成后，应满足以下标准：

1. `m2_shadow_bundle_ref` 已有最小真实 truth-source。
2. replay mixed mode 已支持 `real m2_cycle + real m2_shadow_bundle + real m1_context + stub m3_context`。
3. 缺失 ref / 类型错 / 版本错按预期 fail-closed。
4. `M/G` 边界保持不变。
5. 提交边界仍是原子切片。

## 11. 下一步

本计划确认后，下一步应直接进入实现，不再重复做设计扩展。实施过程中仅在以下情况下暂停：

- 发现 `benchmark assembler` 实际消费形状与 spec 不一致
- 发现 `cycle_intelligence` 现有 formal object 无法支撑 bundle typed readback
- 发现要改 `governance`、`daily`、`API`、`worker` 才能继续

若以上情况未出现，则按本计划直接完成实现、验证、提交边界审计。
