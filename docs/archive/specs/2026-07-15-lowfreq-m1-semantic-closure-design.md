Status: Approved
Owner: cross-domain
Scope: M1 semantic closure without canonical owner implementation
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-m1-semantic-closure-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# M1 Semantic Closure Design

## 背景

当前 `resolver_refs` 主线已经完成以下收口：

- `m2_cycle_ref(real)`
- `m2_shadow_bundle_ref(real)`
- `m3_context_ref(canonical owner)`

但 `m1_context_ref` 的现状与上述三者不同：

- `benchmark_m1_context_projection` 当前只保存极小 payload：
  - `source`
  - `object_type`
  - `object_version`
- 该对象不承载稳定业务语义，也不是跨域真相源
- `benchmark` 对 `m1_context` 的消费当前主要只是 replay / trace 辅助载荷

仓库审计同时确认：

- `data_control` 的真实归口是 `M1 formal inputs`
- `decision_engine` 的真实归口是 `m1_constraints_ref`
- 当前并不存在一个已经成型、可直接上提的正式 `m1_context` 对象

因此，本刀不应继续把 `m1_context` 推成 canonical owner。正确方向是：**废弃 `m1_context` 作为正式对象，保留 `benchmark_m1_context_projection` 仅作兼容层，并把未来正式语义收口到更真实的上游对象。**

## 目标

- 废弃 `m1_context` 作为正式对象的演进方向
- 明确 `benchmark_m1_context_projection` 只是兼容层
- 用设计语言把未来正式语义收口到：
  - `data_control formal inputs snapshot`
  - 或 `decision_engine m1_constraints_ref`
- 仅补最小代码/测试加固，不实现新的 canonical owner

## 非目标

- 不实现新的 `m1 canonical owner`
- 不删除现有 `benchmark_m1_context_projection`
- 不改变 `BenchmarkBatchRunResult` schema
- 不改变 `M5 governance` handoff/bridge/selection/reject/status 语义
- 不扩 CLI/API/daily trigger surface
- 不顺手改动 `m2/m3` 已收口主线

## 方案对比

### P1) 废弃 `m1_context`，保留兼容层（推荐）

- 不再把 `m1_context` 当正式对象推进
- `benchmark_m1_context_projection` 明确定义为 replay 兼容层
- 未来正式语义按用途分别挂到上游真对象

优点：

- 最符合当前证据
- 可以终止“同名异义”扩张
- 不会把局部占位对象误固化成真相源

缺点：

- 需要接受 `m1_context` 这个名字未来只保留兼容意义

### P2) 重定义 `m1_context`

- 保留 `m1_context` 名称，但重新定义正式 payload 与 owner

优点：

- 命名连续性更强

缺点：

- 历史歧义会继续积累
- 当前证据不足以支撑一个统一正式语义

### P3) 直接实现 `m1 canonical owner`

- 不先收口语义，直接新建 owner

优点：

- 表面推进更快

缺点：

- 高概率把兼容壳对象误变成正式真相源

## 推荐方案

采用 `P1`：

- `m1_context` 不再作为正式对象演进
- `benchmark_m1_context_projection` 保留，但只作为兼容层
- 未来正式替代方向按用途拆分

## 语义收口

### 1) 当前对象重新定性

`BenchmarkM1ContextProjection` 当前只应被表述为：

- `benchmark replay compatibility projection`
- `trace / replay 辅助载荷`
- `非 canonical owner`

不允许继续表述为：

- `M1 canonical object`
- `data_control formal truth-source`
- `可跨域复用的正式 m1_context`

### 2) 未来正式替代方向

本设计不立即选定唯一替代对象，但明确只允许从以下两类中选：

- `data_control formal inputs snapshot`
  - 适用于“输入事实 replay / readback”
- `decision_engine m1_constraints_ref`
  - 适用于“M3 front 决策约束”

### 3) 命名策略

从本设计开始，`m1_context` 只保留兼容命名，不再新增任何“正式 `m1_context`”实现。

若未来确需新对象，必须采用更真实的语义名，例如：

- `m1_fact_snapshot`
- `m1_constraints_snapshot`

## 最小实现范围

本轮允许的实现只包括：

- 在代码中显式标注 `BenchmarkM1ContextProjection` 是兼容层
- 补齐 `m1_context_ref` 的 fail-closed 缺失测试
- 在必要处收紧最小对象校验，避免把兼容壳对象表述得比事实更强

本轮不允许：

- 新增任何 `m1 canonical owner`
- 引入新的 `source_type`
- 修改 `data_control` persisted owner 体系
- 修改 `decision_engine` persisted owner 体系

## fail-closed

当前 `m1_context_ref` 至少应稳定覆盖以下失败路径：

- `ref_id` 不存在
- `object_type` mismatch
- `object_version` mismatch
- persisted artifact 不是合法 JSON object
- persisted payload 缺失 `source`

这些失败都属于预期内正确行为，不视为 bug。

## M/G 双轴审计

### M 轴

本刀必须满足：

- 不新增 `m1 canonical owner`
- 只推进 `m1` 语义收口与兼容层加固
- 不改变 `BenchmarkBatchRunResult` 输出契约

### G 轴

本刀必须满足：

- `G/M5` 继续无感知
- 不改 `governance/runtime.py`
- 不改 `daily_master_orchestrator.json`
- 不改 `M5` persisted consumption schema

### M/G 交叉印证

若本刀需要修改治理侧，说明已经偏离“语义收口”边界，应立即停止。

## Syntax / Semantic 补充验证

### Syntax

- 新增/修改 Python 文件 `py_compile`

### Semantic

- `m1_context_ref` 现有成功路径保持不变
- `object_type mismatch` / `object_version mismatch` 失败路径被测试锁定
- `benchmark_m1_context_projection` round-trip 仍通过

## 测试策略

最小测试集合：

1. 现有 `m1_context_projection` round-trip 回归保持通过
2. replay failure：
   - `m1_context_ref` `object_type mismatch`
   - `m1_context_ref` `object_version mismatch`
3. 不破坏：
   - `m2/m3` 已有真实路径
   - mixed mode replay

## 实施边界

- 允许修改：
  - `neotrade3/benchmark/m1_context_projection.py`
  - `neotrade3/benchmark/batch_runner.py`
  - `tests/unit/test_m4_benchmark_m1_context_projection.py`
  - `tests/unit/test_m4_benchmark_replay_manifest.py`
- 不允许修改：
  - `neotrade3/data_control/*`
  - `neotrade3/decision_engine/*`
  - `neotrade3/governance/*`
  - `apps/api/*`
  - `apps/worker/*`

## 验收标准

- `m1_context` 已被文档与实现层明确降级为兼容语义
- `m1_context_ref` fail-closed 缺口补齐
- `M/G` 边界不变

## 下一步接口

本 spec 完成后，本轮只应实施：

- 兼容层边界显式化
- `m1_context_ref` fail-closed 测试补齐
