# M2/M3 最小消费切换实施计划

日期：2026-07-07  
对应设计：

- `docs/superpowers/specs/2026-07-07-m2-m3-minimal-consumption-switch-design.md`
- `docs/superpowers/specs/2026-07-07-m2-cycle-intelligence-layer-design.md`
- `docs/superpowers/specs/2026-07-07-m3-decision-engine-design.md`

## 1. 目标

本计划只覆盖 `M2/M3` 的首轮最小正式消费切换，不扩展到后半段 `hold/exit` 正式化，也不扩展到仓库大扫除工程。

本轮目标只有四个：

1. 建立 `M2 small_cycle` 的最小正式对象与组装链。
2. 建立 `M3 identify_state / tracking_state / entry_state` 的最小正式对象与翻译链。
3. 让低频引擎并行输出 `legacy + formal`，但不推翻现有主流程。
4. 让 `API` 只负责投影正式对象，不继续生成正式语义。

本轮必须产出的核心结果：

- `neotrade3/cycle_intelligence/` 正式建立
- `neotrade3/decision_engine/` 正式建立
- `lowfreq_engine_v16_advanced.py` 能挂出 `formal.small_cycle`
- `lowfreq_engine_v16_advanced.py` 能挂出 `formal.identify_state`
- `lowfreq_engine_v16_advanced.py` 能挂出 `formal.tracking_state`
- `lowfreq_engine_v16_advanced.py` 能挂出 `formal.entry_state`
- `apps/api/main.py` 能并行投影旧字段与正式对象字段

## 2. 不在本轮完成

- `hold_state / exit_state` 正式对象化
- `mid_cycle / large_cycle / super_long_cycle` 正式对象化
- `analysis/*` 研究资产整体重构
- `screeners/*` 全量正式化
- 前端全面改造
- workbench / 报告脚本全量切到 `formal`
- 仓库清理、退役治理、目录瘦身工程

## 3. 当前实施起点

### 3.1 已有现实基础

- `M1` 首批正式对象已经存在，且 API 已能稳定投影：
  - `d1_daily_price_fact`
  - `d7_security_master_minimal`
  - `d7_trading_day_status`
  - `pf1_trading_profile`
- 当前 proto-`identify / tracking / entry` 语义已存在于 `lowfreq_engine_v16_advanced.py`
- 当前 `API` 已能消费部分旧字段并投影到候选池、workbench、持仓视图

### 3.2 当前结构性缺口

- 当前没有正式 `M2` 包
- 当前没有正式 `M3` 包
- `small_cycle` 还没有独立的正式对象
- `identify/tracking/entry` 仍主要依赖旧字段语义
- `API` 仍在消费旧字段而不是正式对象

## 4. 实施原则

- 先建正式承载结构，再挂接现有引擎，再做 API 投影。
- 先保证边界不漂移，再追求字段更丰富。
- 所有正式对象都必须只消费正式 `M1` 或正式 `M2` 输入。
- 不允许把 `theme_momentum`、候选标签、研究层临时信号重新引入正式主链。
- 不允许为了本轮切换而同时重写 `hold/exit`。
- 不允许在 `apps/api/main.py` 中生成正式对象。
- 不允许把正式对象定义继续堆回 `lowfreq_engine_v16_advanced.py`。

## 5. 建议改动边界

首批建议改动边界严格限制在以下位置：

- `neotrade3/cycle_intelligence/`
- `neotrade3/decision_engine/`
- `lowfreq_engine_v16_advanced.py`
- `apps/api/main.py`
- `tests/unit/`

首批不建议大改：

- `neotrade3/analysis/`
- `config/screeners/`
- `neotrade3-dashboard/`
- `scripts/`
- `hold/exit` 相关旧主链

## 6. 总体分段

本计划建议分为六段执行：

- `P2-A`：建立正式对象承载包
- `P2-B`：落 `small_cycle` 正式对象与组装链
- `P2-C`：落 `identify/tracking/entry` 正式对象与翻译链
- `P2-D`：引擎并行输出 `legacy + formal`
- `P2-E`：API 正式对象投影接线
- `P2-F`：测试、结构校验与收口

## 7. 分段实施计划

### P2-A：建立正式对象承载包

目标：

- 先把正式对象从巨型文件中物理分离出来，建立稳定落点。

任务：

- 新增 `neotrade3/cycle_intelligence/__init__.py`
- 新增 `neotrade3/cycle_intelligence/contracts.py`
- 新增 `neotrade3/cycle_intelligence/assembler.py`
- 新增 `neotrade3/decision_engine/__init__.py`
- 新增 `neotrade3/decision_engine/contracts.py`
- 新增 `neotrade3/decision_engine/assembler.py`
- 明确每个正式对象的 `object_type` 与 `object_version`

完成判定：

- 正式对象定义不再依附于引擎文件
- 后续生成链不再需要边拼 `dict` 边定义对象语义

### P2-B：落 `small_cycle` 正式对象与组装链

目标：

- 先让 `M2` 有一个最小正式对象，而不是继续停留在隐式旧字段阶段。

任务：

- 在 `cycle_intelligence/contracts.py` 中定义 `small_cycle`
- 在 `cycle_intelligence/assembler.py` 中建立最小组装入口
- 固定 `small_cycle` 首批字段：
  - `stock_code`
  - `trade_date`
  - `cycle_state`
  - `state_stability_level`
  - `evidence_bundle`
  - `confidence`
  - `invalidation`
  - `state_transition_log`
  - `input_data_version`
  - `rule_version`
- 明确输入只允许来自正式 `M1`
- 对 `M1` 证据不足场景建立显式降级表达

建议实现策略：

- 首批优先复用现有引擎中的可核实基础事实
- 但组装结果必须在新模块中完成，不直接把旧字段当正式对象返回

完成判定：

- 给定固定正式 `M1` 输入，能够稳定生成一个结构完整的 `small_cycle`
- `small_cycle` 不直接携带交易动作结论

### P2-C：落 `identify/tracking/entry` 正式对象与翻译链

目标：

- 让 `M3` 的前半段行为状态机从“旧字段集合”升级为“正式状态对象集合”。

任务：

- 在 `decision_engine/contracts.py` 中定义：
  - `identify_state`
  - `tracking_state`
  - `entry_state`
- 在 `decision_engine/assembler.py` 中建立最小翻译入口
- 固定三类对象的首批字段：
  - `stock_code`
  - `trade_date`
  - `status`
  - `reason / transition_reason / decision`
  - `evidence_ref`
  - `m2_cycle_ref`
  - `m1_constraints_ref`
- `tracking_state` 明确区分：
  - 继续观察
  - 达到 entry 成熟度
- `entry_state` 明确区分：
  - 允许动作
  - 因约束被阻断

建议实现策略：

- 首批允许复用旧引擎中的候选/跟踪/建仓现实能力
- 但必须在新模块中完成正式翻译
- 不允许 `API` 侧再做一遍语义生成

完成判定：

- 给定固定 `small_cycle + M1 constraints`，能稳定输出三类正式状态对象
- `entry_state` 不会被单日异动直接触发

### P2-D：引擎并行输出 `legacy + formal`

目标：

- 在不推翻既有消费面的前提下，先把正式真值源挂出来。

任务：

- 在 `lowfreq_engine_v16_advanced.py` 中引入新模块导出
- 选择最小调用点生成：
  - `formal.small_cycle`
  - `formal.identify_state`
  - `formal.tracking_state`
  - `formal.entry_state`
- 保留现有：
  - `candidate_signals`
  - `entry_signals`
  - `signal_summary`
- 对正式对象生成失败场景提供结构化失败信息

关键约束：

- 不在引擎文件中定义正式对象类型
- 不重写 `hold/exit`
- 不删除旧字段

完成判定：

- 引擎输出中已经同时存在 `legacy` 和 `formal`
- 后续消费方可以开始优先读取 `formal`

### P2-E：API 正式对象投影接线

目标：

- 让 `API` 只做读取与投影，不再承担正式语义生成职责。

任务：

- 在 `apps/api/main.py` 中读取引擎输出的 `formal` 区块
- 在相关视图中新增正式对象投影
- 保留原有旧字段
- 在 `_meta` 或同类说明字段中明确正式优先级
- 确保当前候选池 / workbench 相关视图不因本轮切换而断裂

建议接线范围：

- 先接与候选/跟踪/建仓直接相关的视图
- 本轮不强制全面改写持仓与离场投影
- 本轮不要求前端立即只消费 `formal`

完成判定：

- 现有 API 仍可返回旧字段
- 新增 `formal` 对象投影可读
- `main.py` 不新增正式语义生成逻辑

### P2-F：测试、结构校验与收口

目标：

- 验证正式对象链成立，且未破坏当前低频主链。

建议测试分组：

#### 对象与组装器测试

任务：

- 新增 `small_cycle` 对象字段测试
- 新增 `identify/tracking/entry` 对象字段测试
- 新增证据不足降级测试
- 新增 `decision_engine` 只消费正式输入的测试

#### 引擎并行输出测试

任务：

- 验证引擎输出新增 `formal` 区块
- 验证旧字段仍保持可读
- 验证正式对象失败时不会被静默吞掉

#### API 投影测试

任务：

- 验证 API 同时返回旧字段和正式对象区块
- 验证 `formal` 仅做投影，不做二次生成

#### 结构校验

任务：

- 对新增与修改的 Python 文件执行 `python3 -m py_compile`
- 对最近修改文件做最小诊断检查

完成判定：

- 新模块单测通过
- 低频回归测试通过
- API 投影测试通过
- 结构校验通过

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 新增 `cycle_intelligence` 包
2. 新增 `decision_engine` 包
3. 先写 `small_cycle` 正式对象与组装器
4. 再写 `identify/tracking/entry` 正式对象与翻译器
5. 再接 `lowfreq_engine_v16_advanced.py`
6. 最后接 `apps/api/main.py`
7. 收尾补测试与结构校验

原因：

- 先立正式对象，再接旧主链，风险最低
- 先把真值源做出来，再处理投影层，边界最清楚
- 如果先改 API，很容易再次把正式语义堆回 `main.py`

## 9. 建议提交切分

建议至少拆成三个窄提交：

### Commit A：正式对象与组装器

范围：

- `neotrade3/cycle_intelligence/*`
- `neotrade3/decision_engine/*`
- 对应单测

目标：

- 先冻结正式对象结构与最小翻译逻辑

### Commit B：引擎并行输出

范围：

- `lowfreq_engine_v16_advanced.py`
- 对应引擎回归测试

目标：

- 让引擎挂出 `formal` 区块，但不碰 API 投影

### Commit C：API 投影与回归

范围：

- `apps/api/main.py`
- 对应 API/视图测试

目标：

- 保留旧字段，新增正式对象投影

如果测试文件中混有既有无关改动，应继续使用窄暂存策略，不扩大提交边界。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `small_cycle` 只消费正式 `M1`
2. `identify/tracking/entry` 只消费正式 `M2 + M1 constraints`
3. 引擎输出存在稳定的 `formal` 区块
4. `API` 只做投影，不做正式语义生成
5. 旧字段仍兼容可读
6. `hold/exit` 现有主链未被本轮误伤

## 11. 风险提示

- 首批 `small_cycle` 仍运行于旧引擎生态内部，严格程度可能高于旧字段语义
- 并行期可能出现“旧字段更宽、正式对象更严”的表象，这属于预期而不是回归
- 若 `apps/api/main.py` 接线范围扩张过快，会重新放大 `main.py` 体积，因此本轮必须克制在候选/跟踪/建仓相关视图内

## 12. 结论

本计划的核心不是一次性完成完整 `M2/M3`，而是：

- 先建立正式对象承载结构
- 再把正式真值源挂到引擎输出
- 再让 API 并行投影
- 最后用窄测试和窄提交收口

这样可以在不推翻现有低频主链的前提下，把 `M2/M3` 的前半段正式消费切换稳住，并为后续 `workbench/report/hold/exit` 迁移留出清晰边界。
