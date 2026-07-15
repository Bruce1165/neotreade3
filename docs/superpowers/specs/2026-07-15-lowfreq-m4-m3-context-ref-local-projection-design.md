Status: Approved
Owner: benchmark
Scope: M4 replay m3_context_ref benchmark local persisted projection baseline
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-m4-m3-context-ref-local-projection-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# M4 m3_context_ref Local Projection Design

## 背景

当前 `M4 replay resolver` 已完成以下三条真实 truth-source：

- `m2_cycle_ref(real)`
- `m2_shadow_bundle_ref(real)`
- `m1_context_ref(real-local)`

当前 `resolver_refs` 中唯一仍保留为 stub 的输入块是：

- `m3_context_ref`

仓库审计同时确认：

- `benchmark` 当前只稳定消费 `front-only` 的 `m3_context` 形状
- 该形状只包含：
  - `m1_constraints_ref`
  - `identify_state`
  - `tracking_state`
  - `entry_state`
- `decision_engine` 当前已有 formal contracts 与 assembler，但没有独立的 `artifact/ledger/readback` owner 基线

因此，本刀不适合直接建设 `decision_engine canonical owner`。本刀采用最小收敛方案：**仅在 `benchmark` 子域内新增 `m3_context_ref` 的局部 persisted projection owner/readback，只服务 `M4 replay resolver`，不把它升级成全局正式真相源。**

## 目标

- 为 `m3_context_ref` 建立最小真实 truth-source 链
- truth-source 仅服务 `benchmark replay resolver`
- payload 严格限制为当前 `front-only` 最小形状
- 保持 `M4` 输出契约不变：
  - 仍输出 `BenchmarkBatchRunResult`
  - 仍复用现有 artifact/ledger/readback
- 保持 `G/M5` 完全无感知

## 非目标

- 不把 `m3_context` 上提到 `decision_engine` 全域 canonical owner
- 不把 `hold_state / exit_state / position_status / hold_quality_signal` 纳入本刀 payload
- 不改变 `BenchmarkBatchRunResult` schema
- 不改变 `M5 governance` handoff/bridge/selection/reject/status 语义
- 不扩 CLI/API/daily trigger surface
- 不顺手推进 `decision_engine` persisted owner 体系

## 方案对比

### P1) benchmark 局部 persisted projection + front-only 最小形状（推荐）

- 在 `neotrade3/benchmark/` 内新增 `m3_context_projection` owner/readback
- 只固化 `front-only` 最小 payload
- resolver 只对 `m3_context_ref` 切到真实 source，其余已有真实/ stub 分支不动

优点：

- 边界最小
- 与当前 replay stub、fixture 和 assembler 消费面一致
- 不需要先补 `decision_engine` 全域 persisted owner

缺点：

- 若后续要让更多域复用，可能需要再评估是否上提

### P2) benchmark projection + hold/exit 扩展

- 在局部 projection 中同时带入 `hold_state / exit_state` 等 backhalf 字段

优点：

- 单次信息覆盖更全

缺点：

- 会把本刀从 `formal front` 扩到 `backhalf`
- 明显超出当前原子切片

### P3) decision_engine canonical owner

- 在 `decision_engine` 子域建立独立 persisted owner/readback

优点：

- 长期语义更纯

缺点：

- 当前仓库没有现成 owner 基线
- 范围显著扩大

## 推荐方案

采用 `P1`：

- `m3_context_ref` 只建设 `benchmark` 局部 persisted projection
- projection payload 只保留 `front-only` 最小形状
- 不抬升为全局 canonical owner

## 数据形状

当前 `benchmark` 对 `m3_context` 的最小稳定消费形状为：

```json
{
  "object_type": "m3_context_projection",
  "object_version": 1,
  "m1_constraints_ref": {},
  "identify_state": {},
  "tracking_state": {},
  "entry_state": {}
}
```

说明：

- 本刀不把 `hold_state / exit_state` 放进 projection
- 本刀不重写 `benchmark assembler` 对 `m3_context` 的前半段消费契约
- 若后续确需扩展 backhalf 字段，应独立切片推进

## owner 设计

### 1) 持久化 owner 落点

仅允许放在 `neotrade3/benchmark/` 子域内，例如：

- `m3_context_projection.py`

### 2) 建议对象

可采用如下最小对象：

```python
@dataclass(frozen=True)
class BenchmarkM3ContextProjection:
    m1_constraints_ref: dict[str, Any]
    identify_state: dict[str, Any]
    tracking_state: dict[str, Any]
    entry_state: dict[str, Any]
    object_type: str = "m3_context_projection"
    object_version: int = 1
```

要求：

- 提供 `to_payload()`
- 提供 `from_dict()`
- `from_dict()` 必须 fail-closed，不允许把缺块静默补空

### 3) 持久化路径

建议采用与现有 `m1_context_projection` 同风格的局部路径，例如：

- `var/artifacts/benchmark_m3_contexts/<record_id>/m3_context_projection.json`
- `var/ledgers/benchmark_m3_contexts/<record_id>/m3_context_projection.json`

要求：

- artifact / ledger 分离
- typed readback 可稳定回读
- `ref_id` 不直接等同于任意裸文件路径

## resolver 接线

### 1) 当前 mixed mode

本刀完成后，resolver 允许以下组合：

- `m2_cycle_ref`：真实 persisted source
- `m2_shadow_bundle_ref`：真实 persisted source
- `m1_context_ref`：真实 local projection source
- `m3_context_ref`：真实 local projection source

### 2) resolver 责任

resolver 对 `m3_context_ref` 只做三件事：

1. 读取 persisted projection
2. 做 `object_type/object_version` 校验
3. 转成当前 replay 所需的 `m3_context` payload

不允许：

- 自动 fallback 到 stub
- 自动猜测缺字段
- 直接越级读取 `decision_engine` 运行时状态文件

## fail-closed

以下情况都必须显式失败：

- `m3_context_ref` 缺失
- `m3_context_ref.ref_id` 不存在
- `m3_context_ref.object_type` 不匹配
- `m3_context_ref.object_version` 不匹配
- persisted projection 读取后不是合法 JSON object
- payload 缺失任一必需块：
  - `m1_constraints_ref`
  - `identify_state`
  - `tracking_state`
  - `entry_state`
- persisted projection 与当前 replay 预期的 `front-only` 形状不兼容

这里的两个典型失败用例是**预期内的正确行为**，不视为实现 bug：

- 缺失真实 `m3_context_ref`
- `object_type` 或 `object_version` mismatch

只要失败命中上述 fail-closed 契约，就视为设计内验证通过。

## M/G 双轴审计

### M 轴

本刀必须满足：

- 只推进 `m3_context_ref` 真相源
- 只改 `M4 replay` 输入层
- 不改变 `BenchmarkBatchRunResult` 输出契约
- payload 只保留 `front-only` 最小形状

判定标准：

- replay 仍输出同形 benchmark artifact/ledger
- `seed / inline replay / resolver_stub / real m2_cycle_ref / real m2_shadow_bundle_ref / real m1_context_ref` 回归不变

### G 轴

本刀必须满足：

- `G/M5` 仍只消费 persisted `M4` artifact
- `governance/runtime.py` 不改
- `daily_master_orchestrator.json` 不改
- `M5` persisted consumption schema 不改

### M/G 交叉印证

若本刀需要修改治理侧，说明范围已经漂移，应立即停止。

## Syntax / Semantic 补充验证

### Syntax

后续实现至少要做：

- 新增/修改 Python 文件 `py_compile`
- 新增 artifact/ledger/readback 路径可被 loader 正常读取

### Semantic

后续实现至少要做：

- `real m2_cycle_ref + real m2_shadow_bundle_ref + real m1_context_ref + real m3_context_ref` 可成功 replay
- `m3_context_ref` 缺失/类型错/版本错 fail-closed
- `seed / inline replay / resolver_stub / real m2_cycle_ref / real m2_shadow_bundle_ref / real m1_context_ref` 回归不受影响

## 测试策略

下一阶段最小测试集合：

1. `m3_context_projection` 持久化测试
   - artifact 写入成功
   - ledger 写入成功
   - typed readback 成功
2. replay success 测试
   - `m2_cycle_ref(real) + m2_shadow_bundle_ref(real) + m1_context_ref(real) + m3_context_ref(real)` 成功 materialize
3. replay failure 测试
   - `m3_context_ref` 缺失
   - `object_type mismatch`
   - `object_version mismatch`
4. regression 测试
   - seed 不变
   - inline replay 不变
   - resolver_stub 不变
   - real `m2_cycle_ref` 不变
   - real `m2_shadow_bundle_ref` 不变
   - real `m1_context_ref` 不变

## 实施边界

- 允许修改：
  - `neotrade3/benchmark/`
  - `tests/unit/test_m4_benchmark_*`
- 不允许修改：
  - `neotrade3/decision_engine/*`
  - `neotrade3/governance/*`
  - `apps/api/*`
  - `apps/worker/*`
  - `config/orchestrator/daily_master_orchestrator.json`

## 验收标准

- `m3_context_ref` 拥有最小真实 truth-source
- replay mixed mode 成功
- fail-closed 行为稳定且预期失败被测试锁定
- `M/G` 边界不变

## 下一步接口

本 spec 批准后，下一步实现只应是：

- 新增 `benchmark` 局部 `m3_context_projection` owner/readback
- 只把 `m3_context_ref` 切到真实 source
- 不扩 `decision_engine canonical owner`
