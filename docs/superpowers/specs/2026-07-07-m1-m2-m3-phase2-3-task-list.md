# M1 第一阶段 + M2/M3 最小闭环 Phase 2-3 执行任务清单

日期：2026-07-07  
对应计划：`docs/superpowers/specs/2026-07-07-m1-m2-m3-minimal-closed-loop-implementation-plan.md`

## 1. 任务清单目标

本清单只覆盖实施蓝图中的：

- `Phase 2`：M2 `small_cycle` 正式对象与回放主链
- `Phase 3`：M3 正式行为状态机与低频纪律主链

本清单的目标不是直接大面积改写引擎，而是把第二批核心工作压缩到：

- 明确的模块落点
- 明确的对象级交付物
- 明确的状态机与语义边界
- 明确的测试与回归动作
- 明确的阻塞项与决策点

本清单不覆盖：

- `Phase 4` 的完整 API/回放投影接线
- `Phase 5` 的完整回归收口
- `M4/M5/M6` 的正式工程实现
- 中周期/大周期正式实现
- 复杂仓位管理与组合级风控

## 2. Phase 2：M2 small_cycle 正式对象与回放主链

### 2.1 目标

- 将 `small_cycle` 从现有引擎启发式标签提升为正式周期对象。
- 建立首版 `M2` 正式对象、证据束、状态机与回放边界。
- 让 `M3` 可以只消费 `M2` 正式对象，而不再依赖 `M2` 内部临时判断。

### 2.2 任务组 A：M2 模块落点与对象骨架

#### Task A1：冻结 `M2` 模块落点

目标：

- 确认 `M2` 首批工程不直接吞回现有引擎主文件，而是建立独立对象生成与投影落点。

建议落点：

- 新增或收口 `neotrade3/.../m2/` 相关模块
- 如当前仓库缺少明确位置，可先建立：
  - `neotrade3/m2/objects.py`
  - `neotrade3/m2/state_machine.py`
  - `neotrade3/m2/evidence.py`
  - `neotrade3/m2/replay.py`

完成判定：

- `M2` 首批不再只是 `lowfreq_engine_v16_advanced.py` 内的隐式判断块。

#### Task A2：冻结 `M2` 正式对象骨架

目标：

- 为首批正式对象建立最小结构定义。

首批对象：

- `cycle_state`
- `state_transition_log`
- `evidence_bundle`
- `confidence`
- `invalidation`
- `state_stability_level`
- `rule_version`
- `input_data_version`
- `recompute_reason`

完成判定：

- 首批对象已能用 schema/dataclass/model 形式稳定表达。

### 2.3 任务组 B：small_cycle 状态机

#### Task B1：冻结首版中性状态机

目标：

- 以中性状态语义落地 `small_cycle` 状态机。

首版状态：

- `Neutral`
- `Emerging`
- `Advancing`
- `Maturing`
- `Exhausting_or_Invalidated`

产出：

- 状态定义表
- 状态迁移表
- 不允许迁移表

完成判定：

- 不再依赖引擎中的松散标签推断“现在到底处于哪个阶段”。

#### Task B2：冻结迁移条件最小集

目标：

- 为每条关键迁移定义首版正式条件。

至少明确：

- `Neutral -> Emerging`
- `Emerging -> Advancing`
- `Advancing -> Maturing`
- `Maturing -> Exhausting_or_Invalidated`
- 回落/重算时允许的特殊迁移

要求：

- 迁移条件必须以 `M1 D1/D7/D8` 的正式对象为输入
- 不得引入研究级外部信号

完成判定：

- 状态迁移规则可单独被测试，而不是埋在引擎流程中靠结果验证。

### 2.4 任务组 C：evidence / confidence / invalidation

#### Task C1：冻结 evidence_bundle 首版结构

目标：

- 将首批证据束变成正式可落盘对象。

首批证据类型：

- 价格结构证据
- 成交与活跃度证据
- 波动与稳定性证据
- 横截面对比证据
- 交易可用性证据

完成判定：

- `evidence_bundle` 已是正式结构，而不是特征临时集合。

#### Task C2：冻结 confidence 首版结构

目标：

- 将 `confidence` 从“单一分数”固定为正式可解释对象。

至少包括：

- 来源充分性
- 方向一致性
- 时间连续性
- 结构稳定性
- 数据可靠性

完成判定：

- `confidence` 能被下游解释，而不是神秘综合分。

#### Task C3：冻结 invalidation 首版结构

目标：

- 将 `invalidation` 变成正式失效条件集合。

至少包括：

- 结构破坏
- 连续性破坏
- 相对性破坏
- 数据可用性破坏
- 反向证据压倒

完成判定：

- `M2` 不再只是“感觉状态没了”，而是正式知道为什么失效。

### 2.5 任务组 D：回放与重算边界

#### Task D1：冻结 replay/recompute 最小治理结构

目标：

- 建立 `M2` 首批回放与重算治理对象。

至少包括：

- `open_window`
- `semi_frozen_window`
- `frozen_window`
- `rule_version`
- `input_data_version`
- `recompute_reason`

完成判定：

- `M2` 可区分允许修正与不可接受漂移。

#### Task D2：冻结历史改写边界测试要求

目标：

- 在编码前就明确哪些历史改写是允许的，哪些是禁止的。

必须覆盖：

- 近端确认性修正
- 半冻结窗口内的有限细化
- 冻结窗口后的禁止重写

完成判定：

- `M2` 不会在后续实现中默默滑向“后视镜美化”。

### 2.6 任务组 E：M2 -> M3 最小消费面

#### Task E1：冻结 `M3` 首批所需 `M2` 输出字段

目标：

- 防止 `M3` 继续读取 `M2` 内部变量。

至少输出：

- `cycle_state`
- `state_stability_level`
- `state_transition_log`
- `confidence`
- `invalidation`
- 必要的 `phase_candidate / transition_candidate`

完成判定：

- `M3` 的输入契约已与 `M2` 正式对齐。

### 2.7 Phase 2 测试清单

#### Task F1：M2 首批测试冻结

首批至少包括：

- 状态机迁移测试
- evidence_bundle 结构测试
- confidence 结构测试
- invalidation 结构测试
- replay/recompute 边界测试
- 版本字段与重算原因测试

完成判定：

- `M2` 首批对象与边界可被测试直接验证。

### 2.8 Phase 2 阻塞项

- `B1`：`D8` 首批派生字段若不稳定，`evidence_bundle` 容易反复改口径
- `B2`：现有引擎中周期启发式若高度耦合，`M2` 抽离可能需要先做投影层过渡
- `B3`：若回放版本字段当前无稳定来源，`recompute_reason / input_data_version` 可能先需要占位接口

### 2.9 Phase 2 完成标志

- `M2` 首批正式对象骨架已建立
- `small_cycle` 首版状态机已冻结
- `evidence_bundle / confidence / invalidation` 已正式对象化
- 回放与重算边界已定义
- `M3` 可仅消费 `M2` 正式对象最小集合

## 3. Phase 3：M3 正式行为状态机与低频纪律主链

### 3.1 目标

- 将现有引擎中的行为链收口为正式 `M3` 对象。
- 把 tracking、hold、exit 的低频纪律与语义保护写成正式状态迁移规则。
- 为 `M4/M5` 准备正式可评估、可治理的行为对象链。

### 3.2 任务组 G：M3 模块落点与行为对象

#### Task G1：冻结 `M3` 行为对象落点

目标：

- 明确 `M3` 首批对象优先挂接现有引擎，但对象定义独立。

建议落点：

- 现有 `lowfreq_engine_v16_advanced.py`
- 配套新增：
  - 行为对象模块
  - 归因对象模块
  - 生命周期审计模块

完成判定：

- `M3` 不是只在引擎流程里隐式存在，而是有正式对象承载。

#### Task G2：冻结 `M3` 首批行为对象骨架

目标：

- 为首批行为状态建立最小结构定义。

首批对象：

- `identify_state`
- `tracking_state`
- `entry_state`
- `hold_state`
- `exit_state`
- `decision_lifecycle_log`

完成判定：

- `M3` 首批对象已能稳定挂接到引擎与 API 输出链。

### 3.3 任务组 H：行为状态机与低频纪律

#### Task H1：冻结五阶段行为状态机

目标：

- 正式建立：
  - `Identify`
  - `Tracking`
  - `Entry`
  - `Hold`
  - `Exit`

产出：

- 状态定义表
- 状态迁移表
- 不允许迁移表

完成判定：

- `M3` 行为语义不再只靠“买卖信号函数”拼出来。

#### Task H2：冻结低频纪律迁移条件

目标：

- 将 tracking 成熟度、entry 耐心、hold 抗噪、exit 成熟度写成首版正式门槛。

至少明确：

- 什么情况下 `Identify` 不得直接跳 `Entry`
- tracking 至少满足什么条件才可转 `Entry`
- `Hold` 在什么条件下仍可继续抗噪
- `Exit` 在什么条件下才算正式成熟退出

完成判定：

- `M3` 不再只是“有状态名”，而是有低频纪律约束。

### 3.4 任务组 I：持有/退出语义保护

#### Task I1：冻结 exit 分类最小集合

目标：

- 将退出正式分为：
  - `Local Exhaustion Exit`
  - `Invalidation Exit`
  - `Execution Risk Exit`
  - `Governance-Constrained Exit`
  - `Global Thesis End Exit`

完成判定：

- `exit_state` 不再是单一卖点结果。

#### Task I2：冻结局部/全局退出语义分离

目标：

- 将以下字段正式化：
  - `local_exit_semantics`
  - `global_thesis_end_semantics`

同时写死保护规则：

- 单个 `small_cycle` 的局部后段不得机械翻译成整轮结束
- 当仅有 `small_cycle` 主链时，默认保留趋势延续解释空间

完成判定：

- 后续 `M4/M5/M6` 可直接消费局部/全局分离字段，而不再靠复盘猜测。

### 3.5 任务组 J：正式归因对象与生命周期审计

#### Task J1：冻结首批归因对象

目标：

- 为关键迁移建立正式归因对象：
  - `transition_reason`
  - `action_justification`
  - `invalidation_context`

完成判定：

- 每次关键动作都能回答“为什么成立”“什么时候失效”。

#### Task J2：冻结生命周期审计对象

目标：

- 将 `decision_lifecycle_log` 写成正式审计链，而不是零散 event log。

至少包括：

- `state_entered_at`
- `state_exited_at`
- `transition_reason_ref`
- `action_justification_ref`
- `invalidation_context_ref`
- `m2_state_ref`
- `m1_constraint_ref`
- `trace_id`
- `rule_version`
- `input_data_version`

完成判定：

- 单股行为链可被后续 `M4/M5` 直接回链。

### 3.6 任务组 K：M3 -> M4/M5 最小接口

#### Task K1：冻结 `M4` 所需最小消费面

目标：

- 让 `M4` 后续可正式评估 `Timing / Holding / Exit / Interaction`。

至少输出：

- 行为状态序列
- 退出分类字段
- 持有质量语义字段
- 协同风险标记

完成判定：

- `M4` 不再需要拼日志才能评估 `M3`。

#### Task K2：冻结 `M5` 所需最小消费面

目标：

- 让 `M5` 后续可正式做 `Translation / Interaction` 归因。

至少输出：

- 生命周期链
- 低频纪律命中/违反记录
- 局部/全局语义区分标记
- guardrail 触发记录
- trace 引用

完成判定：

- `M5` 不再需要靠人工复盘猜 `M3` 问题。

### 3.7 Phase 3 测试清单

#### Task L1：M3 首批测试冻结

首批至少包括：

- 五阶段行为状态机测试
- tracking 不得被系统性绕过测试
- hold 理由对象测试
- exit 分类测试
- 局部/全局退出语义分离测试
- 归因对象与生命周期审计对象测试
- 低频纪律 guardrail 测试

完成判定：

- `M3` 低频纪律不再只是设计要求，而是测试可验证约束。

### 3.8 Phase 3 阻塞项

- `B4`：现有引擎中的 entry/hold/exit 逻辑若与新状态机深度交织，可能需要过渡适配层
- `B5`：若 `M2` 首批正式输出字段不稳定，`M3` 输入契约会持续漂移
- `B6`：现有页面/API 若仍消费旧 buy/sell 信号口径，可能需要先做兼容字段映射

### 3.9 Phase 3 完成标志

- `M3` 首批正式行为对象已建立
- 五阶段行为状态机已冻结
- tracking / hold / exit 的低频纪律规则已正式化
- 局部/全局退出语义已严格分离
- 生命周期审计与归因对象已具备
- `M4/M5` 可获得最小完备消费面

## 4. Phase 2-3 共同阻塞项

- `C1`：`M1` 若未先完成首批正式供给，`M2/M3` 对象会继续漂浮在旧字段上
- `C2`：若 schema/contracts 放置位置未统一，`M2/M3` 对象定义会再次分散
- `C3`：若继续同时大改前端/API/引擎主体，第二批实施会迅速失控

## 5. Phase 2-3 完成标志

满足以下条件时，视为 `Phase 2-3` 可以结束并进入 `Phase 4`：

- `M2` 已正式产出 `small_cycle` 主链对象
- `M2` 已具备首版回放与重算治理边界
- `M3` 已正式产出 `identify / tracking / entry / hold / exit` 行为对象
- `M3` 已正式区分局部退出与全局终局退出
- `M3` 已输出正式归因对象与生命周期审计链
- `M4/M5` 后续接入所需的最小消费面已经具备

## 6. 下一步建议

这份清单确认后，下一步最合理的是继续拆：

- `Phase 4-5` 执行任务清单

也就是：

- `M1-M2-M3` 最小 API/回放投影接线
- 测试、回归与验收收口

这样可以把第一批真正要落地的实施顺序，从“蓝图 -> 阶段任务 -> 工程任务 -> 接线与验收”完整闭合。
