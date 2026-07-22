# Lowfreq Engine Six-Layer Accounting Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `lowfreq_engine_v16_advanced.py` 及其直接 formal 依赖的全量拆账与 `M1-M6` 六层映射，目标是为后续低频引擎重组建立一份可复核、可冻结的结构基线，而不是直接进入代码迁移。

目标是：

- 明确 `lowfreq_engine_v16_advanced.py` 当前到底在同时扮演哪些层的角色
- 明确哪些对象属于 `M3` 决策主核，后续不得在重组时被误拆
- 明确哪些对象只是历史上暂住在 engine 文件里的邻层责任
- 为后续 rewrite / re-componentize 提供统一账本，避免“先切文件、后补语义”的反向工作方式

本设计不是：

- `lowfreq_engine_v16_advanced.py` 的实现计划
- 新目录结构或新文件树方案
- 第一刀迁移切片选择
- 任何生产代码、测试代码、API、脚本或前端改动
- 对 NeoTrade3 六层架构的重新定义

## 2. Scope

Included:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control`
- `neotrade3/cycle_intelligence`
- `neotrade3/decision_engine`
- 与上述对象直接相关的现有架构文档与项目状态文档

Excluded:

- `apps/api/main.py`
- `scripts/*`
- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `M4/M5/M6` 的实现层代码设计
- 任何文件迁移、模块拆分或代码重写

## 3. Existing Context

当前仓库已经给出三组关键事实：

- [lowfreq_code_wiki.md](file:///Users/mac/NeoTrade3/docs/architecture/lowfreq_code_wiki.md#L12-L149) 已确认：
  - active engine 是 `lowfreq_engine_v16_advanced.py`
  - active backtest owner 是 `LowFreqTradingEngineV16.run_backtest()`
  - 模型语义必须由 engine / backend 拥有，frontend / report 只能消费正式字段
- [2026-07-06-m1-fact-layer-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-06-m1-fact-layer-design.md#L41-L145) 已冻结：
  - `M1` 负责事实接入、标准化、派生事实、质量证明、任务契约
  - `M1` 不负责周期识别、交易决策、benchmark 评分和前端解释
- [PROJECT_STATUS.md](file:///Users/mac/NeoTrade3/PROJECT_STATUS.md#L333-L365) 已确认：
  - `M2 small_cycle`
  - `M3 identify_state`
  - `M3 tracking_state`
  - `M3 entry_state`
  已有正式承载包与最小消费切换实现

同时，当前 engine 文件本身已经形成以下现实结构：

- 顶部定义运行时 dataclass 与 config 对象，如 [SellSignal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L124-L133)、[LayerContract](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L136-L161)、[TradeRecord](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L165-L212)、[LowFreqV16Config](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L234-L330)
- 中部同时包含：
  - facts / history / fundamentals / formal front 接线
  - 周期与结构识别
  - tracking / execution / exit 决策
- 底部还包含：
  - 回测指标聚合
  - CLI 输出
  - JSON 结果落盘

现状风险：

- 若不先做拆账，后续重组会把“当前写在哪个文件”误当成“应归属哪一层”
- 若不先保护 `M3` 主核，后续拆文件很容易把决策状态机拆散
- 若不先把 `M1/M2` 邻层责任认账，后续很容易把事实适配和识别逻辑继续固化在 engine 中

## 4. Approach Options

### Option A: 按六层运行链拆账（推荐）

- 先按 `M1 -> M2 -> M3 -> M4 -> M5 -> M6` 建立正式判定标准
- 再把 engine 本体与直依赖中的对象逐项挂层
- 用 `当前作用 / 六层应归属 / 是否越层 / 是否核心 contract` 的方式输出账本

Pros:

- 与仓库已冻结的 `M1-M6` 架构直接对齐
- 可以先得到“语义账本”，再决定未来是否重写和如何拆文件
- 最适合作为后续所有重组工作的基线

Cons:

- 需要非常严格地区分“当前位置”和“正确 ownership”
- 初期判断成本高于纯代码 inventory

### Option B: 按代码簇拆账

- 先按函数和代码块分组
- 再对每组贴上六层标签

Pros:

- 最贴近现状
- 扫描速度快

Cons:

- 容易停留在“代码长什么样”
- 不足以回答“谁真正拥有这个语义”

### Option C: 按 contract / 输出物反推

- 从 `signals / trades / audits / config_snapshot / metrics` 等正式输出面反推 owner

Pros:

- 对 API / report / frontend 消费边界很有帮助

Cons:

- 容易忽略底层 facts adapter 与识别逻辑
- 不能完整描述 engine 内部的层混写

Decision:

- choose Option A
- 吸收 Option C 的输出面视角，但不以其作为主方法

## 5. Design

### 5.1 Layer Judgment Rules

本设计不以“代码当前写在哪个文件”判层，而以“谁应当拥有该行为”判层。

- `M1`
  - 事实接入、标准化、派生事实、质量状态、任务契约
- `M2`
  - 基于 `M1` 正式事实的周期 / 结构识别与状态抽象
- `M3`
  - `identify / tracking / entry / hold / exit / execution` 决策翻译与运行态状态机
- `M4`
  - benchmark / gap-check / independent evaluation
- `M5`
  - governance / feedback / evolution inputs
- `M6`
  - API 投影、报告、前端、CLI、结果交付

只有满足以下任一条件，才判定为越层：

- 同时拥有两个不同层的责任
- 直接产出不属于本层的正式语义对象
- 把消费者需求反向写回模型语义
- 绕过现有正式承载包，在 engine 内重复拥有 formal 语义

### 5.2 Object Grouping Strategy

本轮拆账不逐函数平铺，而先按语义簇分组：

- 配置与运行时基座
- 核心状态与契约对象
- facts 读取与 formal 输入接线
- 候选发现与评分
- signal 结构化与 formal front 装配
- tracking / entry / execution
- hold / exit / system exit
- backtest orchestration
- 结果输出与消费接口

记录粒度采用三档：

- 一级对象
  - dataclass、正式 payload builder、主流程入口、跨层枢纽函数
- 二级对象
  - 被多个主流程复用、可能独立迁移、或明显越层的 helper
- 三级对象
  - 纯局部 helper，不单独立项，只归入簇说明

### 5.3 File-Level Role Definition

本轮最关键的文件级结论是：

- `lowfreq_engine_v16_advanced.py` 不是一个纯 `M3` 文件
- 它当前更准确的定义是：
  - 以 `M3` 决策主核为主体
  - 混入 `M1` formal 输入适配
  - 混入 `M2` 识别遗留逻辑
  - 输出 `M4/M5` 所需的证据面
  - 直接承载部分 `M6` CLI / JSON 交付职责

因此，后续若进入重组，首要目标不是“切文件”，而是：

- 先认账
- 先保护 `M3 nucleus`
- 再剥离邻层责任

### 5.4 Layer Mapping Summary

#### M1

正式 owner 已在 `neotrade3/data_control`。

代表对象：

- [project_d1_daily_price_fact](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L42-L58)
- [project_d7_security_master_minimal](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L59-L84)
- [project_pf1_trading_profile](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L85-L117)

engine 内对应对象应视为 `M1 consumer adapter`，而不是 `M3` 决策本体，例如：

- `_get_formal_d1_facts_batch()`
- `_get_formal_security_master_batch()`
- `_build_formal_trading_day_status()`

#### M2

正式 owner 已开始由 `neotrade3/cycle_intelligence` 承载。

代表对象：

- [build_small_cycle_from_m1](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/assembler.py#L71-L126)

engine 内仍存在高密度 `M2` 倾向逻辑：

- `detect_wave_phase()`
- `_detect_wave_phase_from_series()`
- `check_weekly_duck_head()`
- `_structure_confirm()`
- `get_hot_sectors()`
- `detect_sector_cooldown()`

这些应被认定为：

- `M2 legacy recognition zone`

#### M3

当前文件的真实主体 owner 仍是 `M3`。

代表对象：

- [TradeRecord](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L165-L212)
- [SellSignal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L124-L133)
- [LayerContract](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L136-L161)
- [_tracking_snapshot_from_signal](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L751-L785)
- [_decorate_signal_with_phase1_contracts](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L787-L861)
- [_record_tracking_candidate_events](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L5126-L5268)
- [check_sell_signal_v2](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L5495-L5569)
- [run_backtest](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L5675-L6407)

并且 `M3` formal 组装入口已经存在于：

- [build_m1_constraints_ref](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L47-L83)
- [build_identify_state_from_formal_inputs](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L85-L119)
- [build_tracking_state_from_formal_inputs](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L121-L159)
- [build_entry_state_from_formal_inputs](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L161-L199)

#### M4

当前文件不是 `M4 owner`，但已产出高价值 benchmark 输入：

- `trade_blocks`
- `execution_action_summary`
- `buy_signal_audit`
- `sell_signal_audit`
- `drawdown_trace`

它们应标记为：

- `M4 pre-benchmark evidence feed`

#### M5

当前文件不是 `M5 owner`，但已产出治理候选证据：

- `coverage_gaps`
- `blocked_reason` 归一化
- `execution_block_reason`
- `system_exit_grace` 相关事件

它们应标记为：

- `M5 governance-input feeder`

#### M6

当前文件内存在明确 `M6` 混入职责：

- [_calc_metrics](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L6410-L6477) 的交付组织侧
- [main](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L6507-L6568)
- CLI 展示
- JSON 落盘

这部分应标记为：

- `M6 delivery mixin`

### 5.5 M3 Nucleus

后续所有重组都必须先保护以下 `M3 nucleus`，不得在未单独设计前先拆散：

- `TradeRecord`
- `SellSignal`
- `LayerContract`
- `_tracking_snapshot_from_signal()`
- `_decorate_signal_with_phase1_contracts()`
- `_record_tracking_candidate_events()`
- `_execution_signal_gate_snapshot()`
- `_elite_execution_candidate_snapshot()`
- `check_sell_signal_v2()`
- `run_backtest()` 中真正的 runtime decision / execution 推进段

### 5.6 Priority Accounting List

#### P1

最值得优先认账、后续最可能先从 engine 主核中剥离的区域：

- `M2` 识别遗留区
- `M1` formal 输入适配区
- `formal front` 装配接线区

#### P2

次级认账区：

- `_calc_metrics()` 的交付侧部分
- `main()`
- JSON 落盘
- 面向 report / UI 的结果组织逻辑

## 6. Deliverables

本轮设计最终只产出以下三类结果：

- `A. 文件级职责总图`
- `B. M1-M6 逐层映射表`
- `C. 越层清单与优先级清单`

本轮不产出：

- 新文件树
- 迁移步骤
- 第一刀实现边界

## 7. Validation

本设计的验证不依赖代码执行，而依赖证据闭合：

1. 所有层判断必须能回指到：
   - 已冻结的 `M1-M6` 架构文档
   - 当前仓库中的正式承载包
   - `lowfreq_engine_v16_advanced.py` 的真实调用链
2. 所有“越层”判断都必须基于 ownership，而不是基于当前文件位置
3. 所有“应归属某层”的表述都不得误写成“已完成迁移”
4. 最终结论必须同时满足：
   - `M3 nucleus` 被明确保护
   - `M1/M2/M6` 邻层责任被单独认账
   - `M4/M5` 只被认定为 evidence feed，而不是 owner

## 8. Commit Boundary

本轮提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-engine-six-layer-accounting-design.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/*`
- `neotrade3/cycle_intelligence/*`
- `neotrade3/decision_engine/*`
- `apps/api/main.py`
- `scripts/*`
- `neotrade3-dashboard/*`
- 其他任何工作区改动

若在文档撰写过程中发现必须先改代码才能维持结论一致，本轮结论应改为：

- “设计边界需要重新评估，不进入实现”
