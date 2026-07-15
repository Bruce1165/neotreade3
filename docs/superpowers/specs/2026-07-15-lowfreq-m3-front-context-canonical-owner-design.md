Status: Approved
Owner: decision_engine
Scope: M3 front-only canonical owner minimal baseline
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-m3-front-context-canonical-owner-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# M3 Front-Only Canonical Owner Minimal Design

## 背景

当前 `M4 replay resolver` 已完成四块真实路径收口，但其中 `m3_context_ref` 仍通过 `benchmark` 子域的 local projection 读取：

- `m2_cycle_ref(real)`
- `m2_shadow_bundle_ref(real)`
- `m1_context_ref(real-local)`
- `m3_context_ref(real-local)`

仓库审计确认：

- `decision_engine` 已拥有 front-only 正式对象与组装入口：
  - `IdentifyState`
  - `TrackingState`
  - `EntryState`
  - `build_m1_constraints_ref(...)`
- `decision_engine` 当前没有独立 persisted `artifact / ledger / readback` owner
- `benchmark/m3_context_projection.py` 当前只是 `M4 replay` 局部 persisted projection，不是 `M3` 全域 canonical truth-source

因此，本刀目标不是扩展新的消费面，而是把 `m3_context_ref` 的 truth-source 从 `benchmark local projection` 上提为 `decision_engine front-only canonical owner`，同时保留 `benchmark` 侧最小兼容接线。

## 目标

- 在 `decision_engine` 内新增 `front-only canonical owner`
- canonical payload 只承载：
  - `m1_constraints_ref`
  - `identify_state`
  - `tracking_state`
  - `entry_state`
- `benchmark` replay resolver 支持读取新的 canonical owner
- 保持 `BenchmarkBatchRunResult` 输出契约不变
- 保持 `G/M5` 完全无感知

## 非目标

- 不把 `hold_state / exit_state / position_status / hold_quality_signal` 纳入本刀 canonical payload
- 不改 `M5 governance` handoff / bridge / selection / reject / status
- 不扩 `API / worker / daily`
- 不在本刀删除 `benchmark_m3_context_projection` 兼容层
- 不把 `m1_context_ref` 一并上提

## 方案对比

### P1) decision_engine front-only canonical owner + benchmark 兼容接线（推荐）

- 在 `neotrade3/decision_engine/` 内新增 persisted owner/readback
- `benchmark` resolver 增加新的 canonical source_type 分支
- 保留原 `benchmark_m3_context_projection` 作为兼容层，不在本刀删除

优点：

- 语义 owner 与 truth owner 统一
- 范围仍收敛在 `M3/M4`，不影响治理侧
- 可在不破坏现有 replay 的前提下平滑迁移

缺点：

- 本刀后存在两条可读路径，需要在后续再决定是否废弃 local projection

### P2) 直接替换 benchmark local projection

- 不保留兼容层，`benchmark` 只允许新 canonical source

优点：

- 最终态更干净

缺点：

- 切换风险更高
- 不利于最小切片推进

### P3) full M3 canonical owner

- 一次性把 front-only + backhalf 一起纳入 persisted owner

优点：

- 理论上一步到位

缺点：

- 明显扩面
- 当前证据不足

## 推荐方案

采用 `P1`：

- 新增 `decision_engine front-only canonical owner`
- `benchmark` 新增 canonical source 读取分支
- 旧 `benchmark_m3_context_projection` 暂时保留，仅作兼容

## 数据形状

建议新增 canonical object，例如：

```python
@dataclass(frozen=True)
class DecisionM3FrontContext:
    m1_constraints_ref: dict[str, Any]
    identify_state: dict[str, Any]
    tracking_state: dict[str, Any]
    entry_state: dict[str, Any]
    object_type: str = "m3_front_context"
    object_version: int = 1
```

要求：

- `to_payload()` 输出固定 top-level payload
- `from_dict()` 必须 fail-closed
- 不允许静默补空
- top-level `object_type/object_version` 必须校验

## owner 设计

### 1) 落点

建议新增：

- `neotrade3/decision_engine/front_context_store.py`

### 2) 路径

建议采用独立 truth-source 路径：

- `var/artifacts/m3_front_contexts/<record_id>/front_context.json`
- `var/ledgers/m3_front_contexts/<record_id>/front_context.json`

### 3) record_id

继续采用最小确定性方案：

- `stock_code + trade_date`

本刀不处理多版本并存策略。

## benchmark 兼容接线

### 1) 新 source_type

建议新增：

- `DECISION_ENGINE_M3_FRONT_CONTEXT_SOURCE_TYPE = "decision_engine_m3_front_context"`

### 2) resolver 责任

resolver 对新 canonical source 只做：

1. 读取 canonical owner
2. 校验 `object_type/object_version`
3. 返回 replay 当前所需的 `m3_context` payload

### 3) 兼容策略

本刀后允许两条读路径并存：

- `decision_engine_m3_front_context`
- `benchmark_m3_context_projection`

但新测试与新推荐用法应优先使用 canonical source。

## fail-closed

以下情况都必须显式失败：

- `ref_id` 不存在
- `object_type` 不匹配
- `object_version` 不匹配
- artifact 读取后不是合法 JSON object
- payload 缺失任一必需块：
  - `m1_constraints_ref`
  - `identify_state`
  - `tracking_state`
  - `entry_state`

以下失败是预期内正确行为，不视为 bug：

- 缺失真实 canonical ref
- `object_type` mismatch
- `object_version` mismatch

## M/G 双轴审计

### M 轴

本刀必须满足：

- 只推进 `m3_context_ref` canonical owner
- payload 只保留 front-only 形状
- 不改 `BenchmarkBatchRunResult` 输出契约

### G 轴

本刀必须满足：

- `G/M5` 继续无感知
- 不改 `governance/runtime.py`
- 不改 `daily_master_orchestrator.json`
- 不改 `M5` persisted consumption schema

### M/G 交叉印证

若实施中需要改治理侧，说明边界漂移，应立即停止。

## Syntax / Semantic 补充验证

### Syntax

- 新增/修改 Python 文件 `py_compile`
- artifact / ledger / readback 路径可正常读写

### Semantic

- canonical owner round-trip 成功
- replay 可通过 canonical source 成功 materialize
- 缺失 ref / 类型错 / 版本错 fail-closed
- 旧 local projection 路径不被本刀意外破坏

## 测试策略

最小测试集合：

1. `decision_engine` canonical owner round-trip
2. replay success：
   - `real m2_cycle_ref + real m2_shadow_bundle_ref + real m1_context_ref + real canonical m3_context_ref`
3. replay failure：
   - canonical `m3_context_ref` 缺失
   - canonical `object_type mismatch`
   - canonical `object_version mismatch`
4. 兼容回归：
   - 旧 `benchmark_m3_context_projection` round-trip 仍可通过

## 实施边界

- 允许修改：
  - `neotrade3/decision_engine/`
  - `neotrade3/benchmark/batch_runner.py`
  - `neotrade3/benchmark/__init__.py`
  - `tests/unit/test_m3_*`
  - `tests/unit/test_m4_benchmark_*`
- 不允许修改：
  - `neotrade3/governance/*`
  - `apps/api/*`
  - `apps/worker/*`
  - `config/orchestrator/daily_master_orchestrator.json`

## 验收标准

- `decision_engine` 已拥有 front-only canonical owner
- `benchmark` replay 可消费 canonical source
- fail-closed 行为稳定
- `M/G` 边界不变

## 下一步接口

本 spec 批准后，下一步实现只应是：

- 新增 `decision_engine front-only canonical owner`
- 给 `benchmark` 增加 canonical source 兼容读取
- 不扩 backhalf
