Status: Approved
Owner: cycle_intelligence
Scope: M4 replay m2_shadow_bundle_ref real truth-source minimal baseline
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-m4-m2-shadow-bundle-ref-truth-source-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# M4 m2_shadow_bundle_ref Real Truth-Source Minimal Baseline Design

## 背景

当前 `M4 replay resolver` 已完成三步演进：

- `inline replay manifest`
- `resolver_refs + resolver_stub`
- `m2_cycle_ref(real) + m1_context_ref(real)` 的 mixed mode

当前仍留在 stub 的输入块只有：

- `m2_shadow_bundle_ref`
- `m3_context_ref`

其中，`m2_shadow_bundle_ref` 比 `m3_context_ref` 更适合作为下一刀，原因是：

- 它仍属于 `M2 cycle_intelligence` 归口
- `benchmark` 当前已经稳定消费其 bundle 形状
- `cycle_intelligence` 当前已有 formal assembler，但尚无 bundle 级 persisted owner

因此，本刀采用最小收敛方案：**在 `neotrade3/cycle_intelligence/` 内新增 `m2_shadow_bundle` 的 bundle 级 artifact/ledger/readback owner，并仅把 `M4 replay resolver` 的 `m2_shadow_bundle_ref` 切到真实 source。**

## 目标

- 为 `m2_shadow_bundle_ref` 建立一条最小真实 truth-source 链
- truth-source 落在 `cycle_intelligence`，不落在 `benchmark` 私有投影层
- 保持 `M4 replay` 输出契约不变：
  - 仍输出 `BenchmarkBatchRunResult`
  - 仍复用现有 `benchmark` artifact/ledger/readback
- 保持 `G/M5` 完全无感知

## 非目标

- 不把 `m3_context_ref` 一起真实化
- 不把 `m2_shadow_bundle` 拆成 5 个独立 persisted owner
- 不改变 `BenchmarkBatchRunResult` schema
- 不改变 `M5 governance` handoff/bridge/selection/reject/status 语义
- 不扩 CLI/API/worker/daily surface
- 不把 `benchmark` stub payload 误写成正式 truth-source

## 方案对比

### P1) `cycle_intelligence` bundle owner（推荐）

- 在 `neotrade3/cycle_intelligence/` 内新增 `m2_shadow_bundle` 的 bundle 级 owner/readback
- 在 `benchmark replay resolver` 中仅为 `m2_shadow_bundle_ref` 增加真实 source 分支

优点：

- `M2` 归口清晰
- 边界最窄
- 顺着已落地的 `m2_cycle_ref(real)` 向前推进

缺点：

- 需要定义一个 bundle 级 contract，而不是直接复用已有单对象 owner

### P2) 5 个独立 owner

- 分别持久化：
  - `wave_hypothesis`
  - `mid_cycle_states`
  - `cycle_linkage_state`
  - `growth_potential_profile`
  - `top_risk_profile`

优点：

- 语义最细

缺点：

- 明显扩面
- 不符合当前原子切片目标

### P3) `benchmark` 局部 projection

- 仅在 `neotrade3/benchmark/` 内做局部 persisted projection

优点：

- 实现更快

缺点：

- 会把 `M2` truth-source 降格成 `benchmark` 私有真相源
- 后续若其他消费面要复用，会形成反向迁移成本

## 推荐方案

采用 `P1`：

- `m2_shadow_bundle_ref` 的真实 truth-source 归口在 `cycle_intelligence`
- `benchmark` 只负责 resolver 读取与 payload 归一化
- `m3_context_ref` 继续保留为 stub

## 数据形状

### 1) bundle payload

本刀不改变 `benchmark` 当前消费的 `m2_shadow_bundle` 形状。bundle payload 仍保持：

```json
{
  "object_type": "m2_shadow_bundle",
  "object_version": 1,
  "payload": {
    "wave_hypothesis": {},
    "mid_cycle_states": {
      "fund_cycle": {},
      "industry_cycle": {}
    },
    "cycle_linkage_state": {},
    "growth_potential_profile": {},
    "top_risk_profile": {}
  }
}
```

说明：

- `payload` 内 5 个组成块仍沿用当前 replay/assembler 已消费的最小形状
- `mid_cycle_states` 作为 bundle 的一个子块保留为映射，不额外拆 ref
- 本刀不重新设计 `benchmark assembler` 的输入 contract

### 2) bundle object

建议定义最小 typed object，例如：

```python
@dataclass(frozen=True)
class ShadowCycleIntelligenceBundle:
    wave_hypothesis: dict[str, Any]
    mid_cycle_states: dict[str, dict[str, Any]]
    cycle_linkage_state: dict[str, Any]
    growth_potential_profile: dict[str, Any]
    top_risk_profile: dict[str, Any]
    object_type: str = "m2_shadow_bundle"
    object_version: int = 1
```

要求：

- 提供 `to_payload()`
- 提供 `from_dict()`
- `from_dict()` 必须 fail-closed，不允许把缺块静默补空

## owner 设计

### 1) 持久化 owner 落点

仅允许落在 `neotrade3/cycle_intelligence/`，例如：

- 新增 bundle 级 `artifact_writer`
- 新增 bundle 级 `run_ledger`
- 新增 typed readback helper

### 2) 路径建议

建议采用与现有 `small_cycle` 一致的 owner 风格，例如：

- `var/artifacts/m2_shadow_bundles/<record_id>/shadow_bundle.json`
- `var/ledgers/m2_shadow_bundles/<record_id>/shadow_bundle.json`

要求：

- artifact / ledger 分离
- `ref_id` 不直接等于任意裸文件路径
- typed readback 必须稳定回读成 bundle object

### 3) record_id

建议先采用与 `small_cycle` 同级别的最小确定性 record_id 方案：

- 以 `stock_code + trade_date` 为主
- 若后续确需引入更强唯一性，再独立切片演进

本刀不要求一次解决跨版本多副本管理问题。

## resolver 接线

### 1) 本刀完成后的 mixed mode

允许以下组合：

- `m2_cycle_ref`：真实 persisted source
- `m2_shadow_bundle_ref`：真实 persisted source
- `m1_context_ref`：真实 persisted source
- `m3_context_ref`：stub

### 2) resolver 责任

resolver 对 `m2_shadow_bundle_ref` 只做四件事：

1. 读取 bundle persisted owner
2. 校验 `object_type`
3. 校验 `object_version`
4. 转成当前 replay 所需的 `m2_shadow_bundle` payload

不允许：

- 自动 fallback 到 stub
- 自动猜测缺块
- 直接越级读取 `decision_engine` 或其它域状态文件

## fail-closed

以下情况都必须显式失败：

- `m2_shadow_bundle_ref` 缺失
- `m2_shadow_bundle_ref.ref_id` 不存在
- `m2_shadow_bundle_ref.object_type` 不匹配
- `m2_shadow_bundle_ref.object_version` 缺失或不匹配
- bundle artifact 读取后不是合法 JSON object
- bundle payload 缺失任一必需组成块
- `mid_cycle_states` 不是合法 mapping
- typed readback 后的 bundle 与当前 replay 预期形状不兼容

这里的两个典型失败用例是**预期内的正确行为**，不视为实现 bug：

- 缺失真实 `m2_shadow_bundle_ref`
- `object_type` 或 `object_version` mismatch

只要失败命中上述 fail-closed 契约，就视为设计内验证通过。

## M/G 双轴审计

### M 轴

本刀必须满足：

- 只推进 `m2_shadow_bundle_ref` 真相源
- owner 落在 `M2 cycle_intelligence`
- 只改 `M4 replay` 输入解析层
- 不改变 `BenchmarkBatchRunResult` 输出契约

判定标准：

- replay 仍输出同形 `benchmark` artifact/ledger
- `seed / inline replay / resolver_stub / real m2_cycle_ref / real m1_context_ref` 回归不变

### G 轴

本刀必须满足：

- `G/M5` 仍只消费 persisted `M4` artifact
- `governance/runtime.py` 不改
- `daily_master_orchestrator.json` 不改
- `M5` persisted consumption schema 不改

### M/G 交叉印证

若本刀需要修改治理侧，说明边界已经漂移，应立即停止。

## Syntax / Semantic 补充验证

### Syntax

后续实现至少要做：

- 新增/修改 Python 文件 `py_compile`
- 新增 bundle owner 的 artifact/ledger/readback 路径可被 loader 正常读取

### Semantic

后续实现至少要做：

- `real m2_cycle_ref + real m2_shadow_bundle_ref + real m1_context_ref + stub m3_context_ref` 可成功 replay
- `m2_shadow_bundle_ref` 缺失/类型错/版本错 fail-closed
- `seed / inline replay / resolver_stub / real m2_cycle_ref / real m1_context_ref` 回归不受影响

## 测试策略

下一阶段最小测试集合：

1. `m2_shadow_bundle` 持久化测试
   - artifact 写入成功
   - ledger 写入成功
   - typed readback 成功
2. replay success 测试
   - `m2_cycle_ref(real) + m2_shadow_bundle_ref(real) + m1_context_ref(real) + m3_context_ref(stub)` 成功 materialize
3. replay failure 测试
   - `m2_shadow_bundle_ref` 缺失
   - `object_type mismatch`
   - `object_version mismatch`
4. regression 测试
   - seed 不变
   - inline replay 不变
   - resolver_stub 不变
   - real `m2_cycle_ref` 不变
   - real `m1_context_ref` 不变

## 实施边界

- 允许修改：
  - `neotrade3/cycle_intelligence/`
  - `neotrade3/benchmark/batch_runner.py`
  - `neotrade3/benchmark/__init__.py`
  - `tests/unit/test_m2_*`
  - `tests/unit/test_m4_benchmark_*`
- 不允许修改：
  - `neotrade3/decision_engine/*`
  - `neotrade3/governance/*`
  - `apps/api/*`
  - `apps/worker/*`
  - `config/orchestrator/daily_master_orchestrator.json`

## 验收标准

- `m2_shadow_bundle_ref` 拥有最小真实 truth-source
- mixed mode replay 成功
- fail-closed 行为稳定且预期失败被测试锁定
- `M/G` 边界不变

## 下一步接口

本 spec 批准后，下一步实现只应是：

- 新增 `cycle_intelligence` bundle 级 `m2_shadow_bundle` owner/readback
- 只把 `m2_shadow_bundle_ref` 切到真实 source
- 继续保持 `m3_context_ref` 为 stub
