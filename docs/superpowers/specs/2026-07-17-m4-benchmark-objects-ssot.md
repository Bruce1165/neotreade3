# M4 Benchmark 对象契约（单一真相源）

日期：2026-07-17

## 1. 范围与边界

本文件冻结并声明 `M4` 基准评估层（Benchmark Layer）的核心对象契约（字段、语义、版本、命名策略与落盘形态），作为单一真相源（SSOT）。

边界：

- 本文件冻结的是“对象契约与落盘形态”，不是“评分策略或 guardrail 规则是否正确”。
- 以 `neotrade3/benchmark/` 下的 contracts/manifest/batch_result/ledger/artifact 代码为实现态真相源；新增/变更必须伴随本文件更新。

## 2. 版本与命名策略（实现态）

### 2.1 object_type / object_version

Benchmark 合同对象通过 `object_type`（snake_case 字符串）与 `object_version`（int）标记契约身份与版本。

证据（常量定义）：[contracts.py:L9-L23](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L9-L23)

### 2.2 rule_version / input_data_version

- `rule_version`：业务规则版本，默认 `m4_benchmark_seed.v1alpha1`（也可由样本注册表/manifest 覆盖）。
- `input_data_version`：输入数据版本，默认 `m1_phase1.v1`。

证据：

- `BenchmarkSample` 默认值：[contracts.py:L64-L78](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L64-L78)
- 样本注册表到 BenchmarkSample 的映射（可覆盖 rule_version/input_data_version）：[sample_registry.py:L42-L105](file:///Users/mac/NeoTrade3/neotrade3/benchmark/sample_registry.py#L42-L105)

### 2.3 benchmark_run_id / run_id

- `benchmark_run_id`：由单个样本派生出的“样本级运行标识”，用于 Summary 与 Trace 的关联；格式由 `_make_benchmark_run_id(sample)` 冻结。
- `run_id`：批跑（manifest）级运行标识，用于落盘目录与 ledger/artifact 命名。

证据：

- `benchmark_run_id` 生成函数（格式冻结）：[assembler.py:L174-L179](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py#L174-L179)
- manifest 的 `run_id` 契约（必须非空）：[batch_runner.py:L337-L357](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py#L337-L357)

## 3. 核心对象清单（冻结）

本节冻结 `M4` 的对象集合与字段形态（只列“contract 级对象”；不枚举每条 gap/trace 内部字段的业务解释）。

### 3.1 BenchmarkSample（输入样本）

- 对象：`BenchmarkSample`
- 关键字段：`stock_code, trade_date, sample_bucket, target_state_type, expected_target_state, evidence_refs, scenario_tags, note, input_data_version, rule_version, object_type, object_version`

证据：[contracts.py:L64-L94](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L64-L94)

### 3.2 AssessmentSummary（评估摘要）

- 对象：`AssessmentSummary`
- 关键字段：`benchmark_run_id, symbol, trade_date, assessment_grade, hard_violation_count, warn_count, *_risk_summary, sample_bucket_summary, gap_group_distribution, rule_version, object_type, object_version`
- 反序列化入口：`AssessmentSummary.from_dict`

证据：[contracts.py:L96-L184](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L96-L184)

### 3.3 GapRecord / TraceBundle / InteractionGuardrailBreach（评估明细）

- `GapRecord`：用于表达差异/缺口记录（包含 `gap_id, layer_scope, gap_group, gap_label, severity, expected_target_state, actual_state, evidence_refs` 等）
- `TraceBundle`：用于表达可追溯的上下文引用/摘要（包含 `trace_id, benchmark_run_id, resolver_refs` 等）
- `InteractionGuardrailBreach`：用于表达交互 guardrail breach 明细（包含 `breach_id, guardrail_code, severity, evidence_refs` 等）

证据：

- `GapRecord`：[contracts.py:L186-L289](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L186-L289)
- `TraceBundle`：[contracts.py:L291-L362](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L291-L362)
- `InteractionGuardrailBreach`：[contracts.py:L364-L448](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L364-L448)

### 3.4 BenchmarkAssessmentResult（单样本评估结果）

- 对象：`BenchmarkAssessmentResult`
- 结构：`summary: AssessmentSummary` + `gap_records` + `trace_bundle` + `interaction_guardrail_breaches`
- 反序列化入口：`BenchmarkAssessmentResult.from_dict`

证据：[contracts.py:L451-L502](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L451-L502)

### 3.5 BenchmarkRunManifest（批跑入口契约）

- 对象：`BenchmarkRunManifest`
- 关键字段：`run_id, registry_path, sample_ids, description, candidate_run_context, replay_sample`

证据：[batch_runner.py:L337-L382](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py#L337-L382)

### 3.6 BenchmarkBatchRunResult（批跑产物契约）

- 对象：`BenchmarkBatchRunResult`
- 关键字段：`run_id, registry_path, executed_sample_ids, grade_summary, bucket_summary, results, candidate_run_context`
- 反序列化入口：`BenchmarkBatchRunResult.from_dict`

证据：[batch_runner.py:L384-L450](file:///Users/mac/NeoTrade3/neotrade3/benchmark/batch_runner.py#L384-L450)

## 4. 落盘形态（artifact + ledger）

### 4.1 artifact（批跑结果）

- 位置：`var/artifacts/benchmark_runs/{run_id}/benchmark_batch_result.json`
- 内容：`BenchmarkBatchRunResult.to_payload()` + `written_at` + `sample_count`

证据：[artifact_writer.py:L25-L54](file:///Users/mac/NeoTrade3/neotrade3/benchmark/artifact_writer.py#L25-L54)

### 4.2 ledger（运行索引）

- 位置：`var/ledgers/benchmark_runs/{run_id}/benchmark_batch_run.json`
- 内容：`BenchmarkRunLedgerRecord`（包含 artifact_path/ledger_path、grade_summary、bucket_summary 等）

证据：

- ledger record 与写入：[run_ledger.py:L14-L156](file:///Users/mac/NeoTrade3/neotrade3/benchmark/run_ledger.py#L14-L156)
- ledger/artifact 文件路径函数：[run_ledger.py:L78-L94](file:///Users/mac/NeoTrade3/neotrade3/benchmark/run_ledger.py#L78-L94)

## 5. 运行入口（只声明入口，不扩展执行语义）

- runtime owner：`run_benchmark_for_manifest(project_root, manifest)`，负责加载 manifest、运行 batch、物化 artifact+ledger。
- worker 阶段：BENCHMARK executor 调用 `run_benchmark_for_manifest`，并回传 artifact_refs。

证据：

- runtime owner：[runtime.py:L27-L49](file:///Users/mac/NeoTrade3/neotrade3/benchmark/runtime.py#L27-L49)
- worker executor：[main.py:L304-L338](file:///Users/mac/NeoTrade3/apps/worker/main.py#L304-L338)

## 6. 变更流程（新增或变更 Benchmark 契约的最小门禁）

新增/变更 Benchmark 契约必须同时满足：

1. 更新本文件中的“冻结清单与路径/标识符”。
2. 更新 `contracts.py` / `batch_runner.py` / `run_ledger.py` / `artifact_writer.py` 的契约与读写逻辑。
3. 补齐单测，锁定对象反序列化与落盘读回（typed readback）行为。
