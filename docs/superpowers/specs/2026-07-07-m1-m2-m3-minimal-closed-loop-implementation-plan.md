# M1 第一阶段 + M2/M3 最小闭环实施计划

日期：2026-07-07  
对应设计：

- `docs/superpowers/specs/2026-07-06-m1-fact-layer-design.md`
- `docs/superpowers/specs/2026-07-07-m2-cycle-intelligence-layer-design.md`
- `docs/superpowers/specs/2026-07-07-m3-decision-engine-design.md`
- 参照总蓝图：`docs/superpowers/specs/2026-07-06-quant-model-top-level-architecture-design.md`

## 1. 目标

本计划的目标不是一次性实现 `M1-M6` 全栈，而是先建立一条最小但正式的生产主链：

1. `M1` 提供可正式消费的 `D1 + D7 + D8`
2. `M2` 基于正式事实产出 `small_cycle` 主链
3. `M3` 将 `M2` 周期语义翻译为 `identify -> tracking -> entry -> hold -> exit`
4. 为 `M4/M5/M6` 预留正式消费面，但不在首批做重实现

本计划必须实现的核心结果：

- 上游事实与下游状态之间有明确契约
- `small_cycle` 成为正式可回放周期对象
- `M3` 低频行为链成为正式对象，而不是引擎内部隐式状态
- 局部退出与全局终局退出严格分离
- 失败案例至少能被后续 `M4/M5` 归到 `Recognition / Translation / Interaction` 这类正式问题语义

本计划不在本轮完成：

- `mid_cycle / large_cycle / super_long_cycle` 的正式实现
- `M4` 的完整 Benchmark 工程
- `M5` 的完整治理工作流
- `M6` 的完整交付页面和观测平台
- 复杂仓位管理、组合级风控和自动调参

## 2. 当前现实与实施起点

### 2.1 当前真相源

- 现有引擎主文件：`lowfreq_engine_v16_advanced.py`
- API 主入口：`apps/api/main.py`
- 当前调度/数据流现实：`neotrade3/data_control/pipeline.py`、`neotrade3/scheduler/task_scheduler.py`
- 当前主要前端承载页：`neotrade3-dashboard/src/pages/Lowfreq.jsx` 及相关页面

### 2.2 已有可复用资产

- `M1` 方向已有较强现实基础：`daily_prices / stocks` 及日线更新链
- 现有低频引擎已存在：
  - `identify -> tracking -> entry -> hold -> exit` 的局部雏形
  - tracking 相关增量改造结果
  - 基础持有/退出审计
- 现有测试已覆盖部分低频行为与退出逻辑：
  - `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
  - `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
  - `tests/unit/test_lowfreq_intent_conflicts.py`

### 2.3 当前结构性缺口

- `M1` 还没有把 `D1 + D7 + D8` 作为正式供给契约落到统一对象边界
- `M2` 还没有独立于引擎存在的 `small_cycle` 正式对象与回放治理边界
- `M3` 的正式行为对象、退出语义分类与生命周期审计仍未独立落地
- `M4/M5` 当前无法稳定消费 `M2/M3` 的正式对象链

## 3. 实施原则

- 先立契约，再立对象，再立状态机，再接回现有引擎。
- 先保证 `M1 -> M2 -> M3` 语义主链成立，再讨论 `M4/M5/M6` 的完整消费。
- 先做“正式对象化”，再做“表现优化”。
- 先让失败可归因，再追求收益改善。
- 不允许 `M3` 重新吞回 `M2` 的周期职责。
- 不允许 `M2` 越过 `M1` 当前一阶段供给边界。
- 不允许前端或报告先发明新语义，再倒逼后端补字段。

## 4. 总体分期

本计划建议分为六个阶段：

- `Phase 0`：现实盘点与契约冻结
- `Phase 1`：M1 第一阶段正式供给最小闭环
- `Phase 2`：M2 small_cycle 正式对象与回放主链
- `Phase 3`：M3 正式行为状态机与低频纪律主链
- `Phase 4`：M1-M2-M3 集成回放与最小接口投影
- `Phase 5`：测试、回归与验收收口

## 5. 分阶段计划

### Phase 0：现实盘点与契约冻结

目标：

- 在不改逻辑的前提下，冻结首批要落地的对象边界、文件落点和输入输出契约。

任务：

- 盘点现有 `M1` 现实供给链中，哪些字段已经足够支持 `D1 / D7 / D8`
- 盘点现有引擎中可映射到 `M2` 的周期候选、状态迁移、退出语义资产
- 盘点现有引擎中可映射到 `M3` 的 `tracking / hold / exit` 行为对象资产
- 确认首批正式对象最小集合：
  - `M1`：事实对象、质量状态、Freshness Proof、Attention Item
  - `M2`：`cycle_state / evidence_bundle / confidence / invalidation / state_transition_log`
  - `M3`：`identify_state / tracking_state / entry_state / hold_state / exit_state / decision_lifecycle_log`
- 确认哪些对象先在引擎内部落地，哪些先以 API/schema 形式冻结

完成判定：

- 形成一份“现有资产 -> M1/M2/M3 正式对象”映射表
- 明确第一批会改的模块和不会动的模块

### Phase 1：M1 第一阶段正式供给最小闭环

目标：

- 将 `D1 + D7 + D8` 收口为首批可正式消费的 `M1` 输出。

任务：

- 明确 `D1` 的正式事实对象边界：
  - 个股日线行情
  - 最小必要字段契约
  - 对应刷新要求
- 明确 `D7` 的正式事实对象边界：
  - 元数据
  - 交易日历
  - 映射/状态信息
- 明确 `D8` 的正式派生与标准化视图边界：
  - 仅保留 `M2/M3` 当前一阶段真正需要的派生事实
  - 不提前发明未来才会用到的大量派生
- 为首批对象建立最小质量门禁：
  - `Source Status`
  - `Freshness Proof`
  - `Coverage Status`
  - `Replay Status`
- 为关键问题建立第一批 `Attention Item`
- 禁止在质量不达标时静默降级为“照样给下游消费”

建议落点：

- `neotrade3/data_control/`
- `apps/api/main.py`
- `config/data_control/`
- 必要时新增 `contracts` 或 `schemas` 位置用于正式对象定义

完成判定：

- `M2/M3` 可以只消费正式 `D1/D7/D8`，不再依赖混杂字段
- 首批 `M1` 问题可以通过 `Attention Item` 明确暴露
- 历史回放时，`M1` 至少能提供版本可追溯的最小事实面

### Phase 2：M2 small_cycle 正式对象与回放主链

目标：

- 将 `small_cycle` 从引擎启发式标签提升为正式周期对象。

任务：

- 落地 `M2` 首批正式对象：
  - `cycle_state`
  - `state_transition_log`
  - `evidence_bundle`
  - `confidence`
  - `invalidation`
  - `state_stability_level`
- 建立首版 `small_cycle` 中性状态机：
  - `Neutral`
  - `Emerging`
  - `Advancing`
  - `Maturing`
  - `Exhausting_or_Invalidated`
- 建立 `minimum_structural_span` 与 `minimum_evidence_span`
- 将 `small_cycle` 的长度定义落实为：
  - 结构充分性优先
  - 最小时间跨度辅助
- 建立回放与重算边界：
  - `open_window`
  - `semi_frozen_window`
  - `frozen_window`
- 记录：
  - `rule_version`
  - `input_data_version`
  - `recompute_reason`
- 首批只支持 `small_cycle`，不把 `mid_cycle` 升格为正式主链

建议落点：

- 新增或收口 `neotrade3/.../m2` 相关模块
- 如需先过渡，可在现有引擎旁建立 `M2` 对象生成与投影模块，而不是立即大拆引擎

完成判定：

- `M2` 能独立产出正式 `small_cycle` 对象，而不是只在引擎内部存在波段标签
- 同一数据快照与规则版本下，`M2` 输出可稳定复现
- `M3` 可仅消费正式 `M2` 对象，而不读 `M2` 内部临时变量

### Phase 3：M3 正式行为状态机与低频纪律主链

目标：

- 将现有低频引擎里的行为链收口为正式 `M3` 对象与状态迁移纪律。

任务：

- 落地 `M3` 首批正式行为对象：
  - `identify_state`
  - `tracking_state`
  - `entry_state`
  - `hold_state`
  - `exit_state`
  - `decision_lifecycle_log`
- 落地首版行为状态机：
  - `Identify`
  - `Tracking`
  - `Entry`
  - `Hold`
  - `Exit`
- 将 low-frequency discipline 写成正式迁移条件：
  - tracking 成熟度
  - entry 耐心
  - hold 抗噪
  - exit 成熟度
- 为关键迁移建立正式归因对象：
  - `transition_reason`
  - `action_justification`
  - `invalidation_context`
- 为退出落地正式分类：
  - `Local Exhaustion Exit`
  - `Invalidation Exit`
  - `Execution Risk Exit`
  - `Governance-Constrained Exit`
  - `Global Thesis End Exit`
- 将局部/全局退出语义强制分离：
  - `local_exit_semantics`
  - `global_thesis_end_semantics`
- 明确首批保护规则：
  - 单个 `small_cycle` 的局部后段不得机械翻译成整轮结束
  - tracking 不得被系统性绕过
  - `hold` 必须是主动语义，不是“还没卖”

建议落点：

- 现有 `lowfreq_engine_v16_advanced.py`
- 必要时新增 `contracts/schemas` 或行为对象模块
- API 投影层同步收口

完成判定：

- `M3` 可独立输出正式行为对象
- `M4/M5` 后续所需的行为链、归因链和局部/全局语义字段已具备
- 前端或报告不再需要自己推测“为什么买/为什么持有/为什么卖”

### Phase 4：M1-M2-M3 集成回放与最小接口投影

目标：

- 让 `M1 -> M2 -> M3` 成为一条可跑、可回放、可最小消费的闭环。

任务：

- 将 `M2` 正式对象接入 `M3`
- 将 `M3` 正式对象接入 API/最小输出结构
- 为 `M4/M5/M6` 预留最小消费面：
  - `M4` 未来需要的 `identify / tracking / hold / exit` 与理由对象
  - `M5` 未来需要的 trace/ref/version 对象
  - `M6` 未来需要的正式权威输出字段
- 建立单股最小回放链：
  - 某日 `M1` 事实
  - 某日 `M2` 周期状态
  - 某日 `M3` 行为状态
- 明确不在本阶段做完整前端重构，只做最小字段投影与稳定输出

完成判定：

- 同一只股票可回放 `M1 -> M2 -> M3` 的最小逻辑链
- API 能输出最小完备正式对象，而不是混杂旧字段
- 后续 `M4/M5/M6` 可以在不重写上游语义的前提下接入

### Phase 5：测试、回归与验收收口

目标：

- 验证最小闭环真的成立，而不是只在文档上成立。

任务：

- 为 `M1` 增加首批契约与门禁验证测试
- 为 `M2` 增加：
  - 状态机测试
  - evidence bundle 结构测试
  - replay/recompute 边界测试
- 为 `M3` 增加：
  - `Identify -> Tracking -> Entry -> Hold -> Exit` 状态迁移测试
  - tracking 不得被系统性绕过
  - `hold` 理由对象与退出分类测试
  - 局部/全局退出语义分离测试
- 回归现有低频测试，确认没有破坏已存在的基础能力
- 做一轮双轨对比：
  - 旧行为口径
  - 新正式对象化口径

完成判定：

- `M1` 的首批正式供给可被验证
- `M2` 的 `small_cycle` 可被回放与重算
- `M3` 的低频纪律可被测试而不是靠肉眼复盘
- 最小闭环在代码、API、测试三侧同时成立

## 6. 模块与文件建议

建议不要一开始就大拆仓库，而是优先按“对象与契约先独立、逻辑再迁移”的方式推进。

建议优先落点：

- `M1`
  - `neotrade3/data_control/`
  - `config/data_control/`
  - 必要的 facts/contracts/schema 模块
- `M2`
  - 新增或收口 `m2` 相关模块
  - 先以对象生成层形式挂接现有引擎/回放链
- `M3`
  - 现有 `lowfreq_engine_v16_advanced.py`
  - 配套正式行为对象与审计对象模块
- API
  - `apps/api/main.py`
  - 必要的 view/schema/serializer 位置
- 测试
  - 现有 lowfreq 单测文件
  - 新增 `M1/M2/M3` 正式对象与契约测试

## 7. 关键依赖关系

- `M1` 不先收口，`M2` 没有正式事实基底。
- `M2` 不先正式化，`M3` 会继续消费隐式周期语义。
- `M3` 不先对象化，`M4/M5/M6` 后续只能继续猜测行为原因。

所以严格顺序应是：

1. `M1` 首批正式供给
2. `M2` small_cycle 正式对象
3. `M3` 行为状态机与低频纪律
4. 最小 API/回放投影
5. 测试与回归收口

## 8. 风险控制

- 不允许一开始就大规模重写引擎主体，优先通过正式对象与契约收口。
- 不允许 `M2` 越过 `M1` 当前供给边界去假装完整周期宇宙已可用。
- 不允许 `M3` 为了“更聪明”重新做周期识别。
- 不允许前端先形成新语义再倒逼后端适配。
- 不允许用收益改善掩盖语义、回放或归因退化。

## 9. 本计划的完成标志

满足以下条件时，视为本轮 `M1 第一阶段 + M2/M3 最小闭环` 实施计划闭环：

- `M1` 已正式供给 `D1 + D7 + D8` 的最小可消费对象
- `M2` 已正式输出 `small_cycle` 对象，并具备回放边界
- `M3` 已正式输出 `identify / tracking / entry / hold / exit` 行为对象
- `M3` 已正式区分局部退出与全局终局退出
- `M1 -> M2 -> M3` 可被单股回放
- API 与测试已能消费这条最小正式主链

## 10. 下一步建议

本计划写完后，建议不要立即全量开做，而是再做一步更细的执行拆解：

- `Phase 0-1` 的任务清单与文件级落点
- 首批具体要改的模块顺序
- 首批测试清单
- 首批阻塞项清单

也就是说：

- 本文档是“实施蓝图”
- 下一份文档应是“执行任务清单”
