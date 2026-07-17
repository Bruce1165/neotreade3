Status: Approved
Owner: benchmark
Scope: M4 benchmark run evidence traceability (API evidence bundle)
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-17-m4-benchmark-evidence-traceability-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-17

# M4 Benchmark Evidence Traceability Design

## 背景

当前 M4 benchmark run 已具备对外读回三件套（list/read/download/download-ledger），但对“解释与证据引用可追溯”的支持不足：消费者无法从 run 读回结果直接定位到 seed registry 的样本元信息与样本级 evidence_refs，也无法直接定位到与样本关联的 M1/M3 本地 projection 产物（若存在）。

仓库中已存在两类与 benchmark replay 相关的本地 persisted projection owner：

- `benchmark_m1_contexts`：`var/{artifacts,ledgers}/benchmark_m1_contexts/<record_id>/m1_context_projection.json`
- `benchmark_m3_contexts`：`var/{artifacts,ledgers}/benchmark_m3_contexts/<record_id>/m3_context_projection.json`

其中 `<record_id>` 的生成规则为：`<stock_code>-<trade_date>`。

## 目标

- 在不新增额外 API surface 的前提下，使 `GET /api/m4/benchmark-runs/<run_id>` 返回“证据束（evidence bundle）”。
- 证据束可追溯到：
  - seed registry（`registry_path`）中的样本注册信息（sample_id、stock_code、trade_date、evidence_refs 等）
  - 与样本关联的 M1/M3 benchmark local projection（仅当文件实际存在时输出路径）
- 解析失败语义清晰且 fail-closed：seed registry 缺失 / 解析失败 / 样本缺失，一律返回 500（不静默降级）。

## 非目标

- 不新增 `registry/projection` 的独立 read/download 端点。
- 不改变 benchmark run artifact / ledger 的落盘 schema。
- 不生成或补齐 projection 文件（仅做“存在性检查 + 路径回传”）。

## API 变更

### Endpoint

- `GET /api/m4/benchmark-runs/<run_id>`

### 响应扩展

在现有返回结构基础上新增 `evidence` 字段：

```json
{
  "_meta": { "status": "ok" },
  "benchmark_run": {},
  "benchmark_run_artifact": {},
  "evidence": {
    "seed_registry": {
      "registry_path": "config/benchmark/validation_seed_samples.json"
    },
    "samples": [
      {
        "sample_id": "sample-1",
        "stock_code": "600000",
        "trade_date": "2026-07-11",
        "fixture_id": "fixture-1",
        "sample_bucket": "seed",
        "target_state_type": "front_state",
        "evidence_refs": [],
        "scenario_tags": [],
        "note": "",
        "input_data_version": "m1_phase1.v1",
        "rule_version": "m4_benchmark_seed.v1alpha1",
        "m1_context_projection": {
          "record_id": "600000-2026-07-11",
          "artifact_path": "var/artifacts/benchmark_m1_contexts/600000-2026-07-11/m1_context_projection.json",
          "ledger_path": "var/ledgers/benchmark_m1_contexts/600000-2026-07-11/m1_context_projection.json"
        },
        "m3_context_projection": {
          "record_id": "600000-2026-07-11",
          "artifact_path": "var/artifacts/benchmark_m3_contexts/600000-2026-07-11/m3_context_projection.json",
          "ledger_path": "var/ledgers/benchmark_m3_contexts/600000-2026-07-11/m3_context_projection.json"
        }
      }
    ]
  }
}
```

说明：

- `samples` 的顺序与 `benchmark_run.executed_sample_ids` 一致。
- `m1_context_projection` / `m3_context_projection` 仅在对应 artifact/ledger 文件均存在时输出；否则输出 `null`。

## 证据组装逻辑

### 1) 解析执行样本

输入来源：

- `benchmark_run.executed_sample_ids`（来自 run ledger）
- `benchmark_run.registry_path`（来自 run ledger）

解析方式：

- 从 `registry_path` 加载 seed registry 文件，按 `executed_sample_ids` 抽取对应样本注册信息。
- 将样本注册信息映射为 API 输出 `samples[]` 项，并透传 `evidence_refs`（registry 内的样本级证据引用）。

### 2) 关联 M1/M3 projection（存在性检查）

对每个样本：

- 计算 `projection_record_id = f"{stock_code}-{trade_date}"`
- 检查以下四个文件是否存在（存在则回传相对路径）：
  - `var/artifacts/benchmark_m1_contexts/<record_id>/m1_context_projection.json`
  - `var/ledgers/benchmark_m1_contexts/<record_id>/m1_context_projection.json`
  - `var/artifacts/benchmark_m3_contexts/<record_id>/m3_context_projection.json`
  - `var/ledgers/benchmark_m3_contexts/<record_id>/m3_context_projection.json`

## fail-closed 与错误码

当且仅当 `benchmark_run` ledger/artifact 均成功读回后，才进入证据束解析；证据束解析失败按 500 处理：

- seed registry 文件不存在：`benchmark_seed_registry_not_found`
- seed registry JSON/结构非法：`benchmark_seed_registry_invalid`
- executed_sample_ids 中存在 sample_id 未在 registry 内注册：`benchmark_seed_sample_not_found`
- registry_path 越界（不允许读取 project_root 之外的文件）：`benchmark_seed_registry_path_escape`

## 测试

新增 / 扩展单测（端到端路由层）：

- view happy-path：断言 evidence.samples 能正确回传样本信息与 evidence_refs，并在 projection 文件存在时回传路径
- view fail-closed：
  - registry 缺失 → 500 `benchmark_seed_registry_not_found`
  - registry 存在但 sample_id 缺失 → 500 `benchmark_seed_sample_not_found`

## Checklist 回写目标

- `docs/superpowers/specs/2026-07-16-m1-m6-checklist-current-status.md`
  - `M4 5.1 解释与证据引用可追溯` 置 `[x]`
  - 证据链接至少包含：
    - API 实现（service）
    - 单测文件（端到端）
    - 本设计文档
