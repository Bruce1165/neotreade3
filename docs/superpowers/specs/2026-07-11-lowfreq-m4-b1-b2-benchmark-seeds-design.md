# Lowfreq M4 B1/B2 Benchmark Seeds 设计

日期：2026-07-11

关联文档：

- [2026-07-11-lowfreq-six-layer-model-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-11-lowfreq-six-layer-model-design.md)
- [2026-07-11-lowfreq-six-layer-model-plan.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-11-lowfreq-six-layer-model-plan.md)
- [2026-07-11-lowfreq-m4-benchmark-validation-seed-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-11-lowfreq-m4-benchmark-validation-seed-design.md)

## 1. 文档目标

本文档用于定义 `P2 / M4` 的下一条窄切片：为 `B1/B2` 建立正式 benchmark seed 语义，而不是继续停留在样本桶占位。

本切片只解决一个问题：

- 如何在不越过 `M4` 边界的前提下，为 `B1/B2` 建立可回放、可审计、可被 focused tests 锁定的正式验证语义。

本文档不做：

- 不新增 `M2` 周期识别算法
- 不把 `B1/B2` 直接提升为 `M3` 正式入场或退出动作
- 不承诺真实收益、胜率或交易表现
- 不修改当前 `B3/B4` 的已通过基线

项目阶段说明：

- domain: `lowfreq M4 B1/B2 benchmark seeds`
- change type: `validation seed semantic extension`
- NeoTrade2 仅作为思路参考，不是活动依赖

## 2. 双轴映射

### 2.1 主落层

本切片主落层冻结为：

- `M4 Benchmark`

原因：

- 当前任务的目标是补验证语义与样本载体，而不是新增事实层、周期层或动作层能力
- `B1/B2` 必须先在 `M4` 可证伪，后续才有资格被 `M3` 正式消费

### 2.2 目标映射

本切片直接对应：

- `G1`：补齐“小周期位置正确/错误”的正负样本验证
- `G5`：补齐“机会候选 vs 错误候选”的最小验证证据
- `G6`：补齐“控制失败必须被拦住”的负向验证证据

间接支撑：

- `G2`：通过 `cycle_linkage_state` 和中周期上下文，承载中周期位置的背景证据
- `G3`：通过 `supports_continuation` 等字段，承载周期衔接的最小约束
- `G4`：通过 `growth_potential_profile` 的允许/禁止状态，承载潜力判断的最小结构化证据

边界声明：

- 本切片不声称已经完成 `G5` 的正式入场识别
- 本切片只证明 `G5` 已经开始拥有验证载体，而不是已经完成生产级决策翻译

## 3. 当前证据与缺口

当前仓库已具备的正式证据：

- 已有 `B3/B4` seed registry：
  - [validation_seed_samples.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_samples.json)
- 已有 `B3/B4` manifest 基线：
  - [validation_seed_manifest.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_manifest.json)
- 已有 `M4` owner 与评估路径：
  - [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py)
  - [fixture_catalog.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/fixture_catalog.py)
- 已有 `B1/B2` 常量冻结，但尚无正式语义：
  - [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/benchmark/assembler.py#L20-L27)

当前缺口：

- `B1_target_opportunity` 只有桶名，没有正式验证语义
- `B2_control_failure` 只有桶名，没有正式失败锚点
- 当前 fixture catalog 只覆盖 `B3/B4`
- 当前 manifest 只覆盖 `B3/B4`

结论：

- 当前 `M4` 已有基础设施，但仍未覆盖最贴近 `G1/G5/G6` 的正负样本对
- 因此下一刀应优先补 `B1/B2` 语义，而不是继续扩基础设施或提前接 `M3`

## 4. 方案选择

### Option A: 机会候选 / 控制失败双样本对（推荐）

- `B1` 定义为目标机会样本
- `B2` 定义为控制失败样本
- 二者都只验证 `M2 shadow` 输出是否满足最小状态语义，不直接表达交易动作

优点：

- 与 `G1/G5/G6` 对齐最直接
- 保持在 `M4` 内部，不越层进入 `M3`
- 可以形成最小正负对照，避免只有复杂边界样本而没有基础机会样本

缺点：

- `B1` 只能表达“机会候选成立”，不能冒充“入场已确认”

### Option B: 成长潜力 / 顶部风险双样本对

- `B1` 主锚 `G4`
- `B2` 主锚 `G6`

缺点：

- 对当前最缺的 `G1/G5` 证据补强不够直接
- 会把 `B1` 过度偏向潜力样本，而弱化机会候选语义

Decision:

- 选择 `Option A`

## 5. 正式语义冻结

### 5.1 `B1_target_opportunity`

`B1` 冻结为：

- 目标机会样本

其正式含义不是：

- “这里已经可以买入”
- “这里一定会涨”
- “这里已经完成 `M3 entry_state` 判定”

其正式含义是：

- 当前 `M2 shadow` 输出已经具备“可继续、非高风险、具有起点候选解释力”的最小正向状态组合

因此，`B1` 的任务是验证：

- 系统能否把“应被识别为机会候选”的状态识别出来

### 5.2 `B2_control_failure`

`B2` 冻结为：

- 控制失败样本

其正式含义不是：

- 泛化的坏样本集合
- 任意负收益样本
- “已经确认卖出”的动作样本

其正式含义是：

- 即使局部存在亮点，但整体不应继续推进的状态组合，必须被系统拦住，不能误译为机会目标

因此，`B2` 的任务是验证：

- 系统能否把“本不该继续”的状态稳定识别为禁止目标

## 6. 最小判定语义

### 6.1 `B1` 通过语义

`B1` 的通过条件冻结为最小正向状态组合：

- `small_cycle_state` 落在允许推进的状态集合
- `cycle_linkage_state.supports_continuation == true`
- `top_risk_profile.risk_level` 不高于 `watch`
- `growth_potential_profile.status` 不落入明确负向状态

这些条件的含义是：

- 周期位置不能错位
- 周期衔接不能直接指向中断
- 风险不能已经进入高危
- 潜力结构不能已经明显破坏

保守约束：

- `B1` 不要求证明“最佳入场点已经成立”
- `B1` 只要求证明“应被识别为机会候选”

### 6.2 `B2` 失败语义

`B2` 的失败条件冻结为最小负向控制组合：

- `cycle_linkage_state.supports_continuation == false`

并允许以下字段作为辅助失败证据，但不作为必须叠加条件：

- `top_risk_profile.risk_level` 达到高风险
- `growth_potential_profile.status` 落入明确负向状态
- `small_cycle_state` 与机会解释冲突

保守约束：

- `B2` 必须有一个主失败锚点
- 首期主失败锚点固定选择 `supports_continuation == false`
- 不在首期同时叠加多种失败原因，避免样本解释漂移

## 7. `target_state_type` 冻结

为保证验证语义稳定，本切片冻结如下映射：

- `B1_target_opportunity` -> `T3_strong_target`
- `B2_control_failure` -> `T1_prohibition_target`

原因：

- `B1` 是正向机会候选，语义上应要求“强目标成立”，而不是宽松范围匹配
- `B2` 是控制失败样本，语义上应要求“必须拦住”，而不是仅给 warn

由此得到的验证语义：

- `B1` 失败：系统没有识别出本应成立的机会候选条件
- `B2` 失败：系统没有拦住本不应推进的状态

## 8. Fixture 设计

本切片新增两个正式 fixture：

- `m2_target_opportunity_reference`
- `m2_control_failure_reference`

### 8.1 `m2_target_opportunity_reference`

该 fixture 用于稳定产出 `B1` 正向样本。

最小状态要求：

- `small_cycle_state` 处于允许推进的区间
- `cycle_linkage_state.supports_continuation == true`
- `growth_potential_profile.status` 非负向
- `top_risk_profile.risk_level <= watch`

边界：

- 不要求它证明交易动作已经成立
- 只要求它能稳定承载“机会候选成立”的最小验证语义

### 8.2 `m2_control_failure_reference`

该 fixture 用于稳定产出 `B2` 负向样本。

最小状态要求：

- 主锚点：`cycle_linkage_state.supports_continuation == false`
- 辅助证据可包含高风险或负向潜力，但不作为首期必须条件

边界：

- 不把 `B2` 设计成“全面失败的混合样本”
- 保持单主锚点，确保评估失败原因可以被精确追溯

## 9. Registry 与 Manifest 边界

### 9.1 Registry

本切片将在现有 registry 中新增两个正式 seed：

- `b1_target_opportunity_seed`
- `b2_control_failure_seed`

建议字段口径：

- `sample_id`：稳定且可回放
- `fixture_id`：分别指向 `m2_target_opportunity_reference` 与 `m2_control_failure_reference`
- `sample_bucket`：分别为 `B1_target_opportunity` 与 `B2_control_failure`
- `target_state_type`：分别为 `T3_strong_target` 与 `T1_prohibition_target`
- `expected_target_state`：只写最小必要判定条件
- `evidence_refs`：只标主验证落点
- `scenario_tags`：短而稳定，不混入结论性文案

硬约束：

- 不在 `expected_target_state` 中写未来收益承诺
- 不在 `note` 中写“应买入”“应卖出”
- 只表达状态语义，不表达动作结论

### 9.2 Manifest

本切片不修改现有 [validation_seed_manifest.json](file:///Users/mac/NeoTrade3/config/benchmark/validation_seed_manifest.json)。

原因：

- 当前 `B3/B4` 已构成稳定基线
- 直接修改 `v1 manifest` 会污染既有回归基线

因此新增独立批次：

- `validation_seed_v2_manifest.json`

其作用仅限于：

- 承载 `B1/B2` 两个新 seed 的独立回归

后续若需要全量 `B1-B4` 批次，应新增更高版本 manifest，而不是回写 `v1`

## 10. Focused Tests 口径

本切片应新增或扩充三类 focused tests：

1. `sample_registry` 测试：
   - 证明 `B1/B2` 已被正式加载
2. `fixture_catalog` 测试：
   - 证明 `B1/B2 fixture` 输出的 shadow 组合符合主锚点
3. `benchmark_seed` 或 `batch_runner` 测试：
   - 证明 `B1/B2` 分别走到强目标通过与禁止目标失败路径

### 10.1 `B1` 最小断言

- `assessment_grade == pass`
- `hard_violation_count == 0`
- `supports_continuation == true`
- `top_risk_profile.risk_level <= watch`

### 10.2 `B2` 最小断言

- `assessment_grade == fail`
- 至少存在 1 个 hard violation 或等价高严重度 gap
- 主失败锚点可追溯到 `supports_continuation == false`

测试边界：

- 不写收益更高、命中率更高之类的断言
- 不把测试提升为 `M3 entry/exit` 行为测试
- 只锁定 `M4` 对 `M2 shadow` 的验证语义

## 11. 成功标准

本切片完成时，应满足：

- `B1/B2` 从桶名升级为正式验证语义
- `fixture_catalog` 正式支持 `B1/B2`
- `sample_registry` 正式支持 `B1/B2`
- 新增独立 `v2 manifest`，不破坏 `B3/B4` 基线
- `B1/B2` 拥有 focused tests，且能稳定验证正向候选与负向拦截语义
- 不发生 `M4` 越层冒充 `M3` 动作翻译

## 12. 完整性 Audit 标准

本刀完成后，必须用双轴口径审计：

- `M层`：主落层是否仍然是 `M4`
- `G1`：是否补上了小周期位置正确/错误的正负验证
- `G5`：是否补上了机会候选 vs 错误候选的最小验证证据
- `G6`：是否补上了控制失败必须被拦住的负向验证证据
- `G2/G3/G4`：是否只是承载辅助证据，而没有被夸大为新增正式能力

同时必须明确剩余缺口：

- 仍未进入 `M3` 正式消费
- 仍未覆盖全量样本池
- 仍未对生产级收益表现做任何承诺

## 13. 当前结论

这条切片的正确推进方式不是继续扩基础设施，也不是提前跨到动作层，而是：

- 在 `M4` 内为 `B1/B2` 建立正式验证语义
- 用最小正负样本对补齐 `G1/G5/G6` 的验证缺口
- 保持 `M2 shadow -> M4 benchmark` 的严格边界

这样推进，才符合“保守、可审计、对目标负责”的当前主线。
