Status: Approved
Owner: benchmark
Scope: M4 replay refs official fixture baseline alignment
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-m4-replay-refs-real-fixture-baseline-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# M4 Replay Refs Real Fixture Baseline Design

## 背景

当前 `M4 replay` 已经具备真实 `resolver_refs` 路径：

- `m2_cycle_ref` -> `M2 small_cycle persisted truth-source`
- `m2_shadow_bundle_ref` -> `M2 shadow_bundle persisted truth-source`
- `m1_context_ref` -> `benchmark_m1_context_projection`
- `m3_context_ref` -> `benchmark_m3_context_projection` 或 `decision_engine_m3_front_context`

但官方示例文件 `config/benchmark/formal_replay_refs_manifest.json` 仍停留在 `resolver_stub` 口径，导致公开 fixture 与当前真实能力不一致。

## 目标

- 将官方 replay refs fixture 从 `resolver_stub` 收口到真实可运行基线
- 保持本刀为“保守 local 口径”
- 让 fixture 与当前实现态一致，但不借机扩大为 canonical owner 宣示

## 非目标

- 不把 `m3_context_ref` 官方 fixture 切到 `decision_engine_m3_front_context`
- 不修改 `batch_runner.py` 或 `runtime.py`
- 不扩 CLI / API / worker / governance
- 不推进“完整 benchmark 层”

## 方案

采用“保守 local 基线”：

- `m2_cycle_ref` 使用真实 persisted `source_type`
- `m2_shadow_bundle_ref` 使用真实 persisted `source_type`
- `m1_context_ref` 使用 `benchmark` compatibility projection 的真实 `source_type`
- `m3_context_ref` 保持 `benchmark local projection` 的真实 `source_type`

同时把 manifest 描述从 `contract stub` 改为体现“real fixture baseline”。

## 实现范围

仅允许修改：

- `config/benchmark/formal_replay_refs_manifest.json`
- `tests/unit/test_m4_benchmark_replay_manifest.py`

## 验证

最小验证集合：

1. 官方 fixture manifest 可按保守 local 真实路径跑通
2. 既有 replay success / fail-closed 回归保持通过

## M/G 双轴审计

### M 轴

- 仅修正 `M4 replay refs` 官方 fixture 基线
- 不新增对象、不改变输出契约

### G 轴

- 不触碰 `M5 governance`
- 不触碰 `daily`、API、worker 与任何生产写路径
