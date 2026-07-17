Status: Approved
Owner: benchmark
Scope: M4 benchmark run degraded failure policy on run view
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-17-m4-benchmark-degraded-failure-policy-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-17

# M4 Benchmark Degraded Failure Policy Design

## 背景

当前 `GET /api/m4/benchmark-runs/<run_id>` 已能稳定返回：

- `benchmark_run`
- `benchmark_run_artifact`
- `evidence`

其中 `benchmark_run` 与 `benchmark_run_artifact` 是 M4 run view 的主体读回对象；`evidence` 是在主体读回成功后，进一步解析 seed registry 与本地 M1/M3 projection 路径生成的辅助证据束。

现状问题是：`evidence` 解析阶段仍采用全量 fail-closed。一旦发生如下问题，整个 run view 会直接返回 500：

- seed registry 缺失
- seed registry 非法
- executed sample 不存在
- registry_path 越界

这会导致“主体结果可读、但证据束不可用”的场景无法以降级方式展示，不满足 M4 checklist 中“失败策略明确：契约与解析 fail-closed；展示可降级 degraded”的要求。

## 目标

- 明确 M4 run view 的失败分层：
  - 主体对象失败：继续 fail-closed
  - evidence 子模块失败：允许 degraded 展示
- 在不新增 API surface 的前提下，为 `GET /api/m4/benchmark-runs/<run_id>` 增加结构化 degraded 输出。
- 使 degraded 行为可通过单测和 checklist 证据锁定。

## 非目标

- 不改变 benchmark run ledger/artifact 的落盘契约。
- 不改变 list/download/download-ledger 端点行为。
- 不把所有错误都改成 degraded。
- 不在本刀新增 M6 汇总面或独立诊断端点。

## 方案对比

### P1) 顶层 `_meta.status = degraded`，evidence 置空（采用）

- 主体对象 `benchmark_run` / `benchmark_run_artifact` 读回成功后，再尝试组装 `evidence`
- 若 evidence 阶段失败：
  - 不抛 500
  - 返回 `_meta.status = "degraded"`
  - 返回 `_meta.degraded_reasons`
  - 返回 `evidence = null`

优点：

- 对外语义最清晰
- 与 checklist 中“展示可降级 degraded”最直接对齐
- 不影响主体对象的稳定消费

缺点：

- 调用方需要接受 `evidence = null`

### P2) 顶层仍 `ok`，仅 `evidence._meta.status = degraded`

优点：

- 对主体调用方最温和

缺点：

- degraded 容易被忽略
- 对 checklist 的“展示可降级”支撑偏弱

### P3) 所有错误都 degraded

优点：

- 表面上更“可用”

缺点：

- 会破坏 fail-closed 范式
- 主体对象契约失败不应被伪装成可继续消费

## 最终决策

采用 `P1`：

- `benchmark_run` / `benchmark_run_artifact` 继续严格 fail-closed
- `evidence` 子模块允许 degraded
- degraded 信息放在顶层 `_meta`

## 失败分层

### 1) 继续 fail-closed 的错误

以下错误仍保持现状，不降级：

- `benchmark_run_not_found`
- `benchmark_run_artifact_not_found`
- `benchmark_run_ledger_invalid`
- `benchmark_run_artifact_invalid`
- `benchmark_run_invalid`
- `invalid_run_id`

理由：

- 这些错误说明主体对象本身不可安全消费
- 不应把主体契约失败伪装成“部分可用”

### 2) 允许 degraded 的错误

仅 evidence 子模块的如下错误允许 degraded：

- `benchmark_seed_registry_not_found`
- `benchmark_seed_registry_invalid`
- `benchmark_seed_sample_not_found`
- `benchmark_seed_registry_path_escape`

理由：

- 主体 benchmark run 仍已成功读回
- evidence 只是解释/追溯增强，不是主体事实本身

## 对外响应契约

### 正常返回

```json
{
  "_meta": {
    "status": "ok"
  },
  "benchmark_run": {},
  "benchmark_run_artifact": {},
  "evidence": {
    "seed_registry": {},
    "samples": []
  }
}
```

### degraded 返回

```json
{
  "_meta": {
    "status": "degraded",
    "degraded_reasons": [
      {
        "code": "benchmark_seed_registry_not_found",
        "message": "benchmark seed registry not found",
        "details": {
          "registry_path": "config/benchmark/validation_seed_samples.json"
        }
      }
    ]
  },
  "benchmark_run": {},
  "benchmark_run_artifact": {},
  "evidence": null
}
```

约束：

- `degraded_reasons` 必须是非空数组
- 数组元素保留 `code / message / details`
- 当前切片只允许写入一条 degraded reason；若未来 evidence 子模块拆成多步骤，可再扩展为多条

## 实现边界

在 `benchmark_run_view(...)` 内部，将逻辑拆为两层：

1. 读回主体对象：
   - ledger path
   - artifact path
   - JSON 解析
   - 主体 payload 校验
2. 组装 evidence：
   - 解析 registry_path
   - 读取 seed registry
   - 解析 executed_sample_ids
   - 组装 sample evidence
   - 检查 M1/M3 projection refs

实现要求：

- 第 1 层异常继续直接抛 `ApiError`
- 第 2 层异常若命中 degraded 白名单，则捕获并转写为 degraded 响应
- 第 2 层异常若不是白名单错误，仍继续抛出

## 测试

新增 / 调整端到端单测：

- happy-path：`_meta.status == "ok"` 且 `evidence` 为对象
- registry 缺失：`_meta.status == "degraded"`，`evidence is None`
- sample 缺失：`_meta.status == "degraded"`，`degraded_reasons[0].code == "benchmark_seed_sample_not_found"`
- path escape：`_meta.status == "degraded"`，`degraded_reasons[0].code == "benchmark_seed_registry_path_escape"`
- 主体对象失败保持不变：
  - invalid_run_id 仍 400
  - run not found 仍 404
  - ledger/artifact 非法仍 500

## Checklist 回写目标

- `docs/superpowers/specs/2026-07-16-m1-m6-checklist-current-status.md`
  - `M4 5.1 失败策略明确：契约与解析 fail-closed；展示可降级 degraded` 置 `[x]`
  - 证据链接至少包含：
    - 本设计文档
    - `benchmark_run_view(...)` 的 degraded/fail-closed 分层实现
    - 端到端单测
