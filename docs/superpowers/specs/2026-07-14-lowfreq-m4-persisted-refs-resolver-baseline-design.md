Status: Approved
Owner: benchmark
Scope: M4 persisted refs resolver baseline for replay manifest evolution
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-14-lowfreq-m4-persisted-refs-resolver-baseline-design.md
Supersedes: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-14-lowfreq-m4-replay-manifest-minimal-slice-design.md
Superseded_by:
Last_reviewed: 2026-07-14

# M4 Persisted Refs Resolver Baseline Design

## 背景

当前 `M4` 已具备：

- `validation_seed` manifest 基线
- `inline replay manifest` 最小切片
- `BenchmarkBatchRunResult` artifact/ledger/readback 基线

但仓库审计结果也明确：

- 当前不存在可直接供 `M4 replay refs` 使用的 `persisted M2/M3 formal artifact` 真相源
- 当前唯一稳定的 persisted truth-source/readback 基线位于 `M4 benchmark` 与 `M5 governance`
- `M3 formal_front` 现有落盘仅是 lowfreq sim state 中的压缩投影，不是 canonical formal object truth-source

因此，下一刀不能直接把 replay 从 inline payload 改成“随便读 persisted refs”；必须先定义一个最小 **resolver baseline**，明确 refs 指向什么、如何 fail-closed、以及如何不扰动 `M/G` 现有稳定消费面。

## 目标

- 为 `M4 replay manifest` 设计下一阶段的 `persisted refs resolver` 基线
- 保持 `M4` 当前 materialized output 契约完全不变：
  - 仍输出 `BenchmarkBatchRunResult`
  - 仍复用现有 artifact/ledger/readback
- 保持 `M5/G` 当前消费 persisted `M4` artifact 的语义完全不变
- 让 persisted refs 接入仅发生在 `M4 replay` 输入解析层

## 非目标

- 不在本刀建设独立的 `M2 artifact_writer/run_ledger/readback` 生产实现
- 不在本刀建设独立的 `M3 artifact_writer/run_ledger/readback` 生产实现
- 不改变 `BenchmarkBatchRunResult` schema
- 不改变 `M5 governance` handoff/bridge/selection/reject/status 语义
- 不扩 CLI/API/daily trigger surface
- 不把 lowfreq sim state 投影误标为正式 truth-source

## 审计结论前提

本 spec 基于以下事实：

- `M4 replay` 当前只支持 `inline replay_sample`
- `M4` assembler 的直接输入仍是：
  - `SmallCycle`
  - `m2_shadow_bundle`
  - `m1_context`
  - `m3_context`
- `M5/G` 当前只消费 persisted typed `M4` artifact
- 当前仓库内没有独立、稳定、可 typed readback 的 `M2/M3 persisted formal artifact` 真相源

因此，本刀设计的 resolver baseline 不是“直接接现成 refs”，而是：

1. 明确 **未来 refs 的 contract 形状**
2. 明确 **resolver 的最小落点**
3. 明确 **在 truth-source 未建设完成前必须 fail-closed**

## 方案概述

### 1) resolver 只位于 M4 replay 输入层

最小接入位点固定在：

- `BenchmarkRunManifest`
- `BenchmarkReplaySample`
- `_run_benchmark_replay_manifest(...)`

即：

`manifest -> replay_sample -> refs resolver -> inline-equivalent payloads -> existing assembler`

而不是：

- 改 `artifact_writer.py`
- 改 `run_ledger.py`
- 改 `governance/runtime.py`
- 改 `daily` 注册

这样可以保证 `M4/M5` 下游不感知 replay 输入来源变化。

### 2) persisted refs 的目标不是直接替换 assembler

resolver 的职责仅是把 refs 解成与当前 inline replay 完全同形的 4 份内存载荷：

- `m2_cycle`
- `m2_shadow_bundle`
- `m1_context`
- `m3_context`

assembler 继续只认现有输入，不接受 refs 本身。

这保证：

- replay 输入变化
- benchmark 输出不变化
- `G/M5` 消费面不变化

### 3) refs contract 采用显式分块，而不是单一 opaque path

推荐下一阶段 replay manifest 采用如下扩展方向：

```json
{
  "run_id": "formal_replay_v2_batch",
  "description": "NeoTrade3 M4 replay manifest with persisted refs baseline.",
  "replay_sample": {
    "sample_id": "formal_front_replay_seed_v2",
    "sample_bucket": "R2_formal_refs_replay",
    "stock_code": "600000",
    "trade_date": "2026-07-07",
    "target_state_type": "T3_strong_target",
    "expected_target_state": {},
    "resolver_refs": {
      "m2_cycle_ref": {},
      "m2_shadow_bundle_ref": {},
      "m1_context_ref": {},
      "m3_context_ref": {}
    }
  }
}
```

说明：

- 不用单一 `artifact_path` 一把梭
- 不把所有对象揉成一个 opaque blob
- 每个输入块独立引用，便于 fail-closed 与分段审计

## 推荐 refs 形状

当前阶段只定义最小抽象 contract，不绑定具体持久化 owner 实现：

```python
@dataclass(frozen=True)
class BenchmarkPersistedRef:
    source_type: str
    ref_kind: str
    ref_id: str
    object_type: str = ""
    object_version: int | None = None
```

字段语义：

- `source_type`
  - 引用来自哪个 truth-source 家族
  - 当前允许值应非常保守，不能开放式乱填
- `ref_kind`
  - `artifact`
  - `ledger_projection`
  - `inline_fallback`（仅测试/迁移过渡时可考虑）
- `ref_id`
  - 解析所需的唯一标识，不一定等于文件路径
- `object_type/object_version`
  - 用于 resolver 做最小类型核验

本刀不确定最终 `source_type` 具体枚举值，因为仓库当前尚无现成独立 truth-source；但要求后续实现时必须固定枚举，禁止自由文本。

## resolver 行为

### 1) 输入解析顺序

resolver 应按以下优先级执行：

1. 若 `replay_sample` 含完整 inline payload
   - 走现有 inline 路径
2. 若 `replay_sample` 含 `resolver_refs`
   - 走 persisted refs 路径
3. 两者都没有
   - 显式失败

### 2) persisted refs 路径

resolver 必须：

1. 逐块读取 `m2_cycle_ref/m2_shadow_bundle_ref/m1_context_ref/m3_context_ref`
2. 对每一块做最小类型校验
3. 归一化成当前 inline replay 同形 payload
4. 调用现有 `_build_small_cycle_from_payload(...)` 与 assembler

### 3) fail-closed

任一情况都必须显式失败：

- 缺少任一必需 ref
- ref 指向对象不存在
- ref 对应对象类型不匹配
- ref 对应对象版本不匹配
- ref 解析出的 payload 与当前 inline contract 不兼容
- `candidate_run_context` 未来若要求进入 replay 链，但 ref 未提供时

不允许：

- 自动降级为 seed
- 自动忽略缺块
- 自动从 lowfreq sim state 投影“猜”数据

## 真相源边界

### 1) 当前允许写入 spec 的事实

- `M4 benchmark artifact/ledger/readback` 是稳定真相源
- `M5 governance` 只消费 persisted typed `M4` artifact
- `lowfreq sim state.formal_front` 只是投影，不是 canonical truth-source

### 2) 当前不能写成已存在的事实

- 不能写“仓库已具备 M2 persisted artifact truth-source”
- 不能写“仓库已具备 M3 persisted artifact truth-source”
- 不能写“下刀只需简单接 path”

### 3) 未来实现原则

若后续要正式启用 persisted refs，必须满足至少其一：

- 新建独立的 `M2/M3` artifact + ledger + typed readback 基线
- 或定义一个经过审计的中间 truth-source owner，把 canonical formal objects 投影为可稳定回读的 benchmark resolver source

## M/G 双轴审计

### M 轴

本刀必须回答：

- `M4 replay` 的输入真相源从哪里来
- 该真相源是否比当前 inline payload 更稳定
- resolver 是否只改变输入层，而不改变 `M4` 输出契约

判定标准：

- `M4` materialized output 不变
- `M4` tests 只新增 refs 路径，不重写现有 replay/seed 基线

### G 轴

本刀必须回答：

- `G/M5` 是否仍只消费 persisted `M4` artifact
- resolver 引入后，`G` 是否完全无感知
- `candidate_run_context` 是否仍来自 benchmark persisted truth，而非治理层发明

判定标准：

- 不修改 `governance/runtime.py`
- 不修改 `daily_master_orchestrator.json`
- 不修改 `M5` persisted consumption schema

### M/G 交叉印证

只有同时满足以下条件，persisted refs 才算边界正确：

- `M` 轴：refs 只改变 replay 输入层
- `G` 轴：治理消费层完全不变

若任一条件不满足，则说明实现范围已漂移。

## Syntax / Semantic 补充验证

### Syntax

后续实现时至少要做：

- 新增/修改 Python 文件 `py_compile`
- 新增/修改 JSON manifest 可被 loader 正常解析

### Semantic

后续实现时至少要做：

- persisted refs 成功解引用后，与当前 inline replay 产出同形 `BenchmarkBatchRunResult`
- refs 缺失/类型错/版本错时 fail-closed
- seed 路径与 inline replay 路径回归不受影响
- `G/M5` 聚焦回归不因 persisted refs 接入而发生行为变化

## 测试策略

下一阶段最小测试集合应为：

1. resolver contract 解析测试
   - `resolver_refs` 结构解析成功
   - 缺任一分块 ref 显式失败
2. resolver success 测试
   - persisted refs 解出 payload 后可成功 materialize benchmark artifact
3. resolver failure 测试
   - object_type mismatch
   - object_version mismatch
   - ref target missing
4. regression 测试
   - seed benchmark 不变
   - inline replay 不变
   - 如有必要，再加一条 `M5` handoff smoke 确认下游无感知

## 实施边界

- 允许修改：
  - `neotrade3/benchmark/batch_runner.py`
  - `config/benchmark/`
  - `tests/unit/test_m4_benchmark_*`
- 有条件允许：
  - 新增一个极小的 `resolver` helper 文件，但仅限 `neotrade3/benchmark/` 子域
- 不允许修改：
  - `neotrade3/governance/*`
  - `apps/worker/*`
  - `apps/api/*`
  - `config/orchestrator/daily_master_orchestrator.json`
  - `BenchmarkBatchRunResult` output schema

## 验收标准

- spec 层面明确：
  - refs contract
  - resolver 落点
  - fail-closed 规则
  - `M/G` 双轴边界
  - `Syntax/Semantic` 补充验证要求
- 后续实现若通过：
  - seed / inline replay / persisted refs 三者共存
  - `M4` 输出不变
  - `G/M5` 下游不变

## 下一步接口

本 spec 批准后，下一步不是直接大面积编码，而是先做一个更窄的实现切片：

- 在 `benchmark` 子域内新增 `resolver_refs` contract
- 先用 mock/stub resolver 验证 resolver 位置与 fail-closed 行为
- 真正的 `M2/M3 truth-source` 建设若缺失，则应拆为后续独立切片，不在同一刀透支
