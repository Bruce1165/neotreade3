# Lowfreq M4 B1/B2 Benchmark Seeds 实施计划

日期：2026-07-11

Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-m4-b1-b2-benchmark-seeds-design.md`

## 1. 计划目标

本计划只覆盖下一条最窄的 `B1/B2 M4 benchmark seeds` 切片。

本切片只处理：

- `B1_target_opportunity` 的正式 seed 语义落地
- `B2_control_failure` 的正式 seed 语义落地
- `B1/B2` 对应 fixture 的正式收口
- 一个独立的 `v2 manifest`
- 针对 registry / fixture / assessment / batch-run 的 focused coverage

本切片的目标是：

- 在 `M4` 内补齐最贴近 `G1/G5/G6` 的正负样本对
- 保持当前 `M2 shadow -> M4 benchmark` 的严格边界
- 不污染已经稳定的 `B3/B4 v1` 基线
- 用最小验证代价证明 `B1/B2` 已从桶名升级为正式验证语义

本切片不做：

- 不新增 `M2` 周期状态算法
- 不改写 `build_benchmark_assessment_from_m2_shadow(...)` 的总体评估框架
- 不把 `B1/B2` 提升为 `M3` 正式入场或退出动作
- 不重写 `artifact_writer`、`run_ledger`、`batch_runner` 基础设施

## 2. 起点证据

当前仓库证据表明：

- `B3/B4` 已存在正式 registry：
  - `config/benchmark/validation_seed_samples.json`
- `B3/B4` 已存在正式 manifest：
  - `config/benchmark/validation_seed_manifest.json`
- `fixture_catalog` 已存在正式 owner，但只覆盖：
  - `m2_advancing_reference`
  - `m2_local_global_guardrail_reference`
- `M4` focused tests 已覆盖：
  - seed
  - registry
  - fixture catalog
  - batch runner
  - artifact writer
  - run ledger

当前缺口是：

- `B1_target_opportunity` 和 `B2_control_failure` 只有桶定义，没有正式 seed 语义
- 当前没有 `B1/B2` 对应 fixture
- 当前没有独立的 `B1/B2 v2 manifest`
- 当前没有专门锁定 `G1/G5/G6` 的 `B1/B2` focused 验证

因此正确的下一刀是：

- 扩现有 `M4` 样本体系
- 不再扩 `M4` 基础设施
- 不跨到 `M3`

## 3. 双轴映射

### 3.1 主落层

本切片主落层冻结为：

- `M4`

### 3.2 目标映射

本切片主推进：

- `G1`
- `G5`
- `G6`

本切片辅证：

- `G2`
- `G3`
- `G4`

原因：

- `B1` 用于验证“小周期位置没有错位，并具备机会候选解释力”
- `B2` 用于验证“控制失败必须被拦住，不能误译为机会目标”
- 其他目标仍然只通过 `cycle_linkage_state / growth_potential_profile` 等字段承载结构化证据，不冒充新增正式能力

## 4. 实施策略

沿用现有 `M4` owner 结构，不新增新 package，也不拆新层。

本切片只触达以下正式文件集合：

- `config/benchmark/validation_seed_samples.json`
- `config/benchmark/validation_seed_v2_manifest.json`
- `neotrade3/benchmark/fixture_catalog.py`
- `tests/unit/test_m4_benchmark_sample_registry.py`
- `tests/unit/test_m4_benchmark_fixture_catalog.py`
- `tests/unit/test_m4_benchmark_seed.py`
- `tests/unit/test_m4_benchmark_batch_runner.py`

必要时补最小导出面：

- `neotrade3/benchmark/__init__.py`

原则：

- 能复用现有 loader / runner / owner，就不新增抽象
- 能通过补样本与补 fixture 闭环，就不改评估内核

## 5. 执行步骤

### B1B2-S1：冻结文件边界与行为合同

在实现前，先冻结本切片只允许触达的生产/测试文件：

- `config/benchmark/validation_seed_samples.json`
- `config/benchmark/validation_seed_v2_manifest.json`
- `neotrade3/benchmark/fixture_catalog.py`
- `tests/unit/test_m4_benchmark_sample_registry.py`
- `tests/unit/test_m4_benchmark_fixture_catalog.py`
- `tests/unit/test_m4_benchmark_seed.py`
- `tests/unit/test_m4_benchmark_batch_runner.py`

如必须补统一导出，则允许：

- `neotrade3/benchmark/__init__.py`

冻结的可观察合同：

- `B1` 必须表达“机会候选成立”，不是“交易动作成立”
- `B2` 必须表达“控制失败应被拦住”，不是“泛化坏样本”
- 现有 `B3/B4` 语义和 `v1 manifest` 不得被改写
- `batch_runner / artifact_writer / run_ledger` 的现有行为不得变化

完成检查：

- 这一步的文件集合和行为边界都可明确说清，不存在隐含越层修改

### B1B2-S2：扩充 registry 中的 `B1/B2` 正式 seeds

在 `config/benchmark/validation_seed_samples.json` 中新增：

- `b1_target_opportunity_seed`
- `b2_control_failure_seed`

字段冻结要求：

- `sample_bucket` 分别为 `B1_target_opportunity` 与 `B2_control_failure`
- `fixture_id` 分别指向：
  - `m2_target_opportunity_reference`
  - `m2_control_failure_reference`
- `target_state_type` 分别为：
  - `T3_strong_target`
  - `T1_prohibition_target`
- `expected_target_state` 只写最小必要条件
- `evidence_refs` 只标主锚点，不写动作结论

完成检查：

- `B1/B2` 已从桶名升级为正式可加载 seed
- 不存在“应买入/应卖出”这类越层 note

### B1B2-S3：在 fixture catalog 中补 `B1/B2` 正式夹具

在 `neotrade3/benchmark/fixture_catalog.py` 中新增：

- `m2_target_opportunity_reference`
- `m2_control_failure_reference`

实现规则：

- `B1` fixture 以正向机会候选语义为主：
  - `small_cycle_state` 不错位
  - `supports_continuation == true`
  - `risk_level <= watch`
  - `growth_potential_profile` 不为负向
- `B2` fixture 以单主失败锚点为主：
  - `supports_continuation == false`
  - 其他负向信号仅做辅助，不叠成混合失败样本

不得做的事：

- 不重写 `_sample_m1_objects(...)` 的公共基线形状
- 不把 `B2` 做成多失败原因叠加的大杂烩

完成检查：

- `fixture_catalog` 能正式构造 `B1/B2`
- `B1/B2` 的状态锚点能被单独解释

### B1B2-S4：新增独立 `v2 manifest`

新增：

- `config/benchmark/validation_seed_v2_manifest.json`

仅包含：

- `b1_target_opportunity_seed`
- `b2_control_failure_seed`

不得改动：

- `config/benchmark/validation_seed_manifest.json`

原因：

- `v1` 仍是 `B3/B4` 基线
- `v2` 用于单独回归 `G1/G5/G6` 的正负样本对

完成检查：

- `B1/B2` 可以被 batch runner 独立执行
- `v1` 和 `v2` 的验证主题彼此隔离

### B1B2-S5：补 focused tests

最少补齐四类验证：

1. `sample_registry`：
   - `B1/B2` 能被正式加载
2. `fixture_catalog`：
   - `B1` fixture 输出机会候选主锚
   - `B2` fixture 输出控制失败主锚
3. `benchmark_seed`：
   - `B1` 走 `pass + strong target`
   - `B2` 走 `fail + prohibition target`
4. `batch_runner`：
   - `v2 manifest` 可独立执行
   - summary 能区分 `B1/B2`

最小断言冻结为：

- `B1`
  - `assessment_grade == pass`
  - `hard_violation_count == 0`
  - `supports_continuation == true`
- `B2`
  - `assessment_grade == fail`
  - 存在至少一个高严重度 gap 或 hard violation
  - 主失败锚点能回链到 `supports_continuation == false`

完成检查：

- `B1/B2` 具备 direct focused coverage
- 当前 `B3/B4` 相关验证不被破坏

### B1B2-S6：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_m4_benchmark_sample_registry.py`
- `python3 -m pytest tests/unit/test_m4_benchmark_fixture_catalog.py`
- `python3 -m pytest tests/unit/test_m4_benchmark_seed.py`
- `python3 -m pytest tests/unit/test_m4_benchmark_batch_runner.py`

如实现触及导出面或其他文件，再加最小语法校验：

- `python3 -m py_compile neotrade3/benchmark/*.py`

完成检查：

- `B1/B2` 新测试通过
- `B3/B4` 现有路径未回归
- 语法校验通过

### B1B2-S7：窄提交

实现提交前，只暂存本切片目标文件：

- `config/benchmark/validation_seed_samples.json`
- `config/benchmark/validation_seed_v2_manifest.json`
- `neotrade3/benchmark/fixture_catalog.py`
- `tests/unit/test_m4_benchmark_sample_registry.py`
- `tests/unit/test_m4_benchmark_fixture_catalog.py`
- `tests/unit/test_m4_benchmark_seed.py`
- `tests/unit/test_m4_benchmark_batch_runner.py`

如确有必要，再包含：

- `neotrade3/benchmark/__init__.py`

必须排除：

- `artifact_writer.py`
- `run_ledger.py`
- `batch_runner.py` 的非必要行为修改
- 与本主题无关的工作区改动

## 6. 风险与防护

风险 1：

- 把 `B1` 偷偷写成 `M3` 入场动作语义

防护：

- 所有 seed / fixture / test 文案只表达“机会候选成立”，不表达“应买入”

风险 2：

- 把 `B2` 写成多失败原因混合样本，导致失败不可解释

防护：

- 首期固定单主锚点：`supports_continuation == false`

风险 3：

- 为接入 `B1/B2` 而回写 `v1 manifest`，污染 `B3/B4` 基线

防护：

- 强制新增独立 `v2 manifest`

风险 4：

- 为了适配 `B1/B2` 而修改评估内核，导致范围扩张

防护：

- 优先通过补 seed / fixture / test 闭环，除非出现真实 contract 缺口，否则不改 assembler 规则体

## 7. 成功标准

本切片完成时，应满足：

- `B1/B2` 已拥有正式可回放 seed
- `fixture_catalog` 已正式支持 `B1/B2`
- `validation_seed_v2_manifest.json` 已可独立驱动 batch run
- `B1` 能稳定表达机会候选通过语义
- `B2` 能稳定表达控制失败拦截语义
- `B1/B2` focused tests 通过
- `B3/B4 v1` 基线不被改写
- 全程不发生 `M4 -> M3` 越层漂移

## 8. 完整性 Audit 要求

本刀完成后必须输出双轴 audit：

- `M层`
  - 本步是否仍然只落在 `M4`
- `G目标`
  - `G1`：是否补上小周期位置正负样本验证
  - `G5`：是否补上机会候选 vs 错误候选的验证证据
  - `G6`：是否补上控制失败必须被拦住的负向证据
  - `G2/G3/G4`：是否仍只是辅助承载，而非夸大成新增正式能力

同时必须明确保留缺口：

- 尚未进入 `M3` 正式消费
- 尚未形成全量 `B1-B4` 统一批次
- 尚未对生产级收益或交易表现做任何承诺

## 9. 提交边界

本次 plan 文档提交只应包含：

- `docs/superpowers/specs/2026-07-11-lowfreq-m4-b1-b2-benchmark-seeds-plan.md`

必须排除：

- 任何生产代码
- 任何测试代码
- 任何配置 JSON
- 与本主题无关的工作区改动
