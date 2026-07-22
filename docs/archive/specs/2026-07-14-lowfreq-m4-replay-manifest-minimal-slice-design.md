Status: Approved
Owner: benchmark
Scope: M4 replay manifest minimal slice for inline formal snapshot consumption
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-14-lowfreq-m4-replay-manifest-minimal-slice-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-14

# M4 Replay Manifest Minimal Slice Design

## 背景

当前 `M4` benchmark 已具备：

- `manifest -> runtime -> artifact/ledger` 的最小执行路径
- `validation_seed` registry + fixture catalog 驱动的 repeatable benchmark seeds
- `BenchmarkBatchRunResult` typed readback 与 `worker/orchestrator` 基线

当前缺口是：`M4` 仍主要消费静态 seed fixture，而不是面向 `M2/M3` 正式输出形状的 replay 输入。直接切到“读取 persisted formal artifacts”会扩大范围，因为当前仓库中尚未形成与 `M4` 对齐的独立 formal artifact truth-source/readback 基线。

因此，本刀采用最小收敛方案：先新增一种 **inline replay manifest**，允许在 manifest 内显式提供最小 `M2/M3 formal snapshot` 载荷，让 `M4` 能以正式对象形状运行 replay benchmark，同时不引入新的持久化真相源建设。

## 目标

- 为 `M4` 新增第二种最小输入模式：`replay manifest`
- 保持现有 `validation_seed` manifest 完全不变
- 让 replay manifest 复用现有 benchmark assembler 与 artifact/ledger 写入链路
- 将 `M4` 输入 contract 从 `fixture-only` 推进一步，变成“可接收正式对象形状的 benchmark replay”

## 非目标

- 不建设新的 `M2/M3 formal artifact` 持久化写入链
- 不让 replay manifest 直接读取外部 artifact refs
- 不改 CLI/API mode
- 不改 `daily` orchestrator task 注册
- 不改 `M5` handoff、governance 语义与调度边界
- 不扩多样本批量 replay，只先支持单个最小 replay sample

## 关键约束

- `validation_seed` 仍是当前 `M4` 基线，replay 只是新增并行输入模式
- replay manifest 必须 fail-closed：关键 replay 字段缺失时，manifest 解析或运行必须显式失败
- replay manifest 的输入形状以 `M2/M3 formal outputs` 为目标，不再依赖 `fixture_id`
- 输出仍统一为 `BenchmarkBatchRunResult`，不得发明第二套 benchmark 结果契约

## 方案概述

### 1) 新增 replay manifest 形状

新增一种最小 manifest 变体，建议形状如下：

```json
{
  "run_id": "formal_replay_v1_batch",
  "description": "NeoTrade3 M4 replay manifest minimal slice for inline formal snapshot benchmark.",
  "replay_sample": {
    "sample_id": "formal_front_replay_seed_v1",
    "sample_bucket": "R1_formal_front_replay",
    "stock_code": "600000",
    "trade_date": "2026-07-07",
    "target_state_type": "T3_strong_target",
    "expected_target_state": {},
    "m2_cycle": {},
    "m2_shadow_bundle": {},
    "m3_context": {}
  }
}
```

说明：

- `run_id`、`description` 继续保持现有 manifest 顶层风格
- `replay_sample` 是 replay 模式的唯一输入块
- `sample_id/sample_bucket/stock_code/trade_date/target_state_type/expected_target_state` 对齐现有 benchmark sample contract 的最小身份字段
- `m2_cycle`、`m2_shadow_bundle`、`m3_context` 是最小 inline formal snapshot

本刀不要求 `candidate_run_context`；如后续需要与 `M5` 对接，再作为下一刀补充。

### 2) runner 增加双分支

当前 `run_benchmark_manifest(...)` 保持入口不变，但内部按 manifest 类型分流：

1. 若 manifest 含 `replay_sample`
   - 走 replay 分支
   - 直接把 inline snapshot 转为 assembler 需要的 `cycle/shadow_bundle/m3_context`
   - 生成单个 `BenchmarkAssessmentResult`
2. 否则
   - 继续走现有 seed registry + fixture provider 分支

这样可保证：

- 现有 seed manifest 不受影响
- replay manifest 不依赖 registry/fixure catalog
- artifact/ledger/materialize/readback 全部复用现有路径

### 3) 最小内部对象建议

建议新增一个最小 dataclass，例如：

```python
@dataclass(frozen=True)
class BenchmarkReplaySample:
    sample_id: str
    sample_bucket: str
    stock_code: str
    trade_date: str
    target_state_type: str
    expected_target_state: dict[str, Any]
    m2_cycle: dict[str, Any]
    m2_shadow_bundle: dict[str, Any]
    m3_context: dict[str, Any]
```

并在 `BenchmarkRunManifest` 中新增可选字段：

```python
replay_sample: BenchmarkReplaySample | None = None
```

manifest 解析规则：

- 有 `replay_sample` 时，允许省略 `registry_path` 与 `sample_ids`
- 无 `replay_sample` 时，维持现有 `registry_path` 必填约束

这能让 seed 与 replay 共存于同一个 manifest root contract 中，而无需发明第二个 runtime entrypoint。

## 数据流

### seed 模式

`manifest -> registry -> fixture_provider -> assembler -> BenchmarkBatchRunResult -> artifact/ledger`

### replay 模式

`manifest.replay_sample -> inline formal snapshot -> assembler -> BenchmarkBatchRunResult -> artifact/ledger`

两条路径最终在 `BenchmarkBatchRunResult` 收口。

## 错误与 fail-closed 语义

以下情况必须显式失败：

- `replay_sample` 不是 JSON object
- `sample_id/sample_bucket/stock_code/trade_date/target_state_type` 任一为空
- `expected_target_state` 不是 JSON object
- `m2_cycle` 不是 JSON object
- `m2_shadow_bundle` 不是 JSON object
- `m3_context` 不是 JSON object

本刀不在 runtime 中兜底修复 replay 数据，也不允许静默回退到 seed 模式。

## 测试策略

最小测试集合：

1. manifest 解析测试
   - replay manifest 能成功解析
   - replay 模式下允许省略 `registry_path`
2. runtime/materialize 测试
   - replay manifest 能输出 artifact/ledger
   - `run_id`、`sample_count`、`executed_sample_ids` 形状正确
3. fail-closed 测试
   - 缺 `m2_shadow_bundle` 或其类型错误时显式失败

不新增 HTTP smoke；当前只需把 replay contract 在 `benchmark` 子域内部锁住。

## 实施边界

- 允许修改：
  - `neotrade3/benchmark/batch_runner.py`
  - `neotrade3/benchmark/runtime.py`（仅在必要时做最小兼容）
  - `config/benchmark/` 下新增 replay manifest 样例
  - `tests/unit/test_m4_benchmark_*`
- 不允许修改：
  - `apps/worker/main.py`
  - `apps/api/*`
  - `config/orchestrator/daily_master_orchestrator.json`
  - `neotrade3/governance/*`

## 验收标准

- 现有 seed benchmark 测试继续通过
- 新增 replay manifest 测试通过
- replay manifest 能 materialize 出标准 `BenchmarkBatchRunResult` artifact/ledger
- 未引入新的 trigger surface 或调度行为变化

## 下一刀接口

本刀完成后，下一刀才考虑把 `replay_sample` 的 inline formal snapshot 替换为真正的 persisted formal artifact refs。届时应新增独立的 formal artifact truth-source/readback 基线，而不是在本刀中提前透支实现范围。
