Status: Approved
Owner: benchmark
Scope: M4 m1_context_ref local persisted projection baseline
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-14-lowfreq-m4-m1-context-ref-local-projection-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-14

# M4 m1_context_ref Local Projection Design

## 背景

当前 `M4 replay resolver` 已完成两层推进：

- `inline replay manifest`
- `resolver_refs + mock/stub resolver`

随后又完成了 `m2_cycle_ref` 的第一条真实 truth-source 最小链：

- `SmallCycle` 已具备独立 `artifact + ledger + typed readback`
- replay resolver 已能消费真实 `m2_cycle_ref`

当前剩余 stub 输入块还有：

- `m2_shadow_bundle_ref`
- `m1_context_ref`
- `m3_context_ref`

其中，`m1_context_ref` 当前是最窄的一块：它不是 formal object，也不是现成的全局 persisted truth-source；若直接把它抬升为 `data_control` 或全局 canonical object，这刀范围会显著变宽。

因此，本刀采用最小收敛方案：**仅在 `benchmark` 子域内新增 `m1_context_ref` 的局部 persisted projection owner/readback**，只为 `M4 replay resolver` 服务，不把它升级成全局正式对象。

## 目标

- 为 `m1_context_ref` 建立一条最小真实 truth-source 链
- truth-source 仅服务 `benchmark replay resolver`
- 保持 `M4` 输出契约不变：
  - 仍输出 `BenchmarkBatchRunResult`
  - 仍复用现有 artifact/ledger/readback
- 保持 `G/M5` 完全无感知

## 非目标

- 不把 `m1_context` 定义为 `data_control` 正式对象
- 不建设跨域通用的 `m1_context` truth-source
- 不改变 `BenchmarkBatchRunResult` schema
- 不改变 `M5 governance` handoff/bridge/selection/reject/status 语义
- 不扩 CLI/API/daily trigger surface
- 不顺手推进 `m2_shadow_bundle_ref` 或 `m3_context_ref` 的真实化

## 方案对比

### P1) benchmark 局部 persisted projection（推荐）

- 在 `neotrade3/benchmark/` 内新增最小 `m1_context_projection` owner/readback
- 只提供 replay resolver 所需最小字段
- resolver 只对 `m1_context_ref` 切到真实 source，其余 refs 不动

优点：

- 边界最小
- 不引入新的全局语义
- 与当前 `m2_cycle_ref` 真相源推进方式兼容

缺点：

- 若后续其它域也要复用，可能需要再评估是否上提

### P2) data_control 正式对象

- 把 `m1_context` 上提到更通用的正式对象层

优点：

- 理论复用性更强

缺点：

- 范围显著扩大
- 需要定义新的跨域语义和消费边界

### P3) 保持 stub

- 继续不真实化

结论：

- 与当前目标不符，不采用

## 推荐方案

采用 `P1`：

- `m1_context_ref` 只建设 `benchmark` 局部 persisted projection
- truth-source 只为 replay resolver 服务
- 不抬升为全局 canonical object

## 数据形状

当前 `m1_context` 在 replay 中只承担极小输入作用，因此本刀的 persisted projection 也只保留最小字段。

推荐最小 payload：

```json
{
  "object_type": "m1_context_projection",
  "object_version": 1,
  "source": "benchmark_local_projection"
}
```

说明：

- 这不是正式 `M1` 对象
- 它只是 `benchmark` 局部投影
- 若后续 replay 真正需要更多字段，再以独立切片扩展

## owner 设计

### 1) 持久化 owner 落点

仅允许放在 `neotrade3/benchmark/` 子域内，例如：

- `artifact_writer` 风格 helper
- `run_ledger` 风格 helper
- typed readback helper

### 2) 建议对象

可采用如下最小对象：

```python
@dataclass(frozen=True)
class BenchmarkM1ContextProjection:
    source: str
    object_type: str = "m1_context_projection"
    object_version: int = 1
```

并提供：

- `to_payload()`
- `from_dict()`

### 3) 持久化路径

建议采用与现有 owner 一致的局部路径风格，例如：

- `var/artifacts/benchmark_m1_contexts/<record_id>/m1_context_projection.json`
- `var/ledgers/benchmark_m1_contexts/<record_id>/m1_context_projection.json`

本刀不要求路径最终一定永久保留，但要求：

- artifact / ledger 分离
- typed readback 可稳定回读
- `ref_id` 不直接等同于任意裸文件路径

## resolver 接线

### 1) 当前 mixed mode

本刀完成后，resolver 允许以下组合：

- `m2_cycle_ref`：真实 persisted source
- `m1_context_ref`：真实 local projection source
- `m2_shadow_bundle_ref`：stub
- `m3_context_ref`：stub

### 2) resolver 责任

resolver 对 `m1_context_ref` 只做三件事：

1. 读取 persisted projection
2. 做 `object_type/object_version` 校验
3. 转成当前 replay 所需的 `m1_context` payload

不允许：

- 自动 fallback 到 stub
- 自动猜测缺字段
- 直接越级读取其它域状态文件

## fail-closed

以下情况都必须显式失败：

- `m1_context_ref` 缺失
- `m1_context_ref.ref_id` 不存在
- `m1_context_ref.object_type` 不匹配
- `m1_context_ref.object_version` 不匹配
- persisted projection 读取后不是合法 JSON object
- persisted projection 与当前 replay 预期的 `m1_context` 形状不兼容

## M/G 双轴审计

### M 轴

本刀必须满足：

- 只推进 `m1_context_ref` 真相源
- 只改 `M4 replay` 输入层
- 不改变 `BenchmarkBatchRunResult` 输出契约

判定标准：

- replay 仍输出同形 benchmark artifact/ledger
- 现有 seed / inline replay / stub resolver / real `m2_cycle_ref` 回归不变

### G 轴

本刀必须满足：

- `G/M5` 仍只消费 persisted `M4` artifact
- `governance/runtime.py` 不改
- `daily_master_orchestrator.json` 不改
- `M5` persisted consumption schema 不改

### M/G 交叉印证

若本刀需要修改治理侧，说明范围已经漂移，应停止。

## Syntax / Semantic 补充验证

### Syntax

后续实现至少要做：

- 新增/修改 Python 文件 `py_compile`
- 新增 artifact/ledger/readback 路径可被 loader 正常读取

### Semantic

后续实现至少要做：

- `real m2_cycle_ref + real m1_context_ref + stub others` 可成功 replay
- `m1_context_ref` 缺失/类型错/版本错 fail-closed
- `seed / inline replay / resolver_stub / real m2_cycle_ref` 回归不受影响

## 测试策略

下一阶段最小测试集合：

1. `m1_context_projection` 持久化测试
   - artifact 写入成功
   - ledger 写入成功
   - typed readback 成功
2. replay success 测试
   - `m2_cycle_ref(real) + m1_context_ref(real) + stub others` 成功 materialize
3. replay failure 测试
   - `m1_context_ref` 缺失
   - `object_type mismatch`
   - `object_version mismatch`
4. regression 测试
   - seed 不变
   - inline replay 不变
   - resolver_stub 不变
   - real `m2_cycle_ref` 不变

## 实施边界

- 允许修改：
  - `neotrade3/benchmark/`
  - `tests/unit/test_m4_benchmark_*`
- 不允许修改：
  - `neotrade3/data_control/*`
  - `neotrade3/governance/*`
  - `apps/api/*`
  - `apps/worker/*`
  - `config/orchestrator/daily_master_orchestrator.json`

## 验收标准

- `m1_context_ref` 拥有最小真实 truth-source
- mixed mode replay 成功
- fail-closed 行为稳定
- `M/G` 边界不变

## 下一步接口

本 spec 批准后，下一步实现只应是：

- 新增 `benchmark` 局部 `m1_context_projection` owner/readback
- 只把 `m1_context_ref` 切到真实 source
- 继续保持 `m2_shadow_bundle_ref / m3_context_ref` 为 stub
