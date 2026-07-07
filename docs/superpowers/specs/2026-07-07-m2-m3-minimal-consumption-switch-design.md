# 2026-07-07 M2/M3 最小消费切换设计

## 1. 背景与目标

当前仓库已完成 `M1 Phase 1` 的首批正式对象落地，正式输入面已经明确为：

- `d1_daily_price_fact`
- `d7_security_master_minimal`
- `d7_trading_day_status`
- `pf1_trading_profile`

但当前 proto-`M2/M3` 语义仍主要散落在：

- `lowfreq_engine_v16_advanced.py`
- `apps/api/main.py`
- 少量报告与工作台投影逻辑

现状问题不是“没有语义”，而是“正式对象未独立，真值源与投影层耦合”。继续直接在 `main.py` 或大型引擎文件中堆叠新语义，会进一步放大以下风险：

- 正式层与兼容层边界继续混杂
- API 聚合层继续膨胀
- 后续清理时难以识别哪些字段仍是活跃真值

本设计的目标是：在不扩大范围的前提下，完成 `M2/M3` 的第一轮最小正式消费切换。

本轮只做：

- `M2 small_cycle`
- `M3 identify_state`
- `M3 tracking_state`
- `M3 entry_state`

本轮明确不做：

- `hold_state`
- `exit_state`
- `mid_cycle / large_cycle / super_long_cycle`
- 全仓库清理或退役治理
- 研究层资产整体重构

## 2. 范围冻结

### 2.1 本轮范围

本轮实现范围冻结为“前半段最小正式链”：

1. 只新增 `M2 small_cycle` 正式对象链
2. 只新增 `M3 identify/tracking/entry` 正式对象链
3. 由低频引擎生成正式对象
4. 由 API 做只读投影
5. 保留旧字段，同时新增正式对象字段

### 2.2 本轮边界外

以下内容不纳入本轮：

- `hold_state / exit_state` 正式化
- `M4 / M5 / M6` 消费切换
- `analysis/*` 研究资产统一正式化
- `screeners/*` 全量改造
- 前端全面改造
- 仓库大扫除和退役资产归档

### 2.3 兼容原则

本轮采用“并行暴露，正式优先”的兼容策略：

- 旧字段继续保留，用于兼容现有消费面
- 新增 `formal` 区块承载正式对象
- 若旧字段与正式对象语义发生冲突，以正式对象为准
- 旧字段不得继续作为新的正式真值源

## 3. 设计依据

### 3.1 来自 M2 设计的硬边界

`M2` 首期正式生产主链只允许 `small_cycle`，并且只允许消费 `M1` 首批正式对象，不得回流使用研究层临时标签、主题热度加成、候选标签等兼容信号。

因此，本轮 `small_cycle` 必须满足：

- 输入源严格来自正式 `M1`
- 输出具备正式状态语义
- 不直接生成交易动作
- 不将单日异动直接写成正式周期结论

### 3.2 来自 M3 设计的硬边界

`M3` 只能消费：

- `M1` 的正式执行约束与可交易事实
- `M2` 的正式周期状态对象

因此，本轮 `identify/tracking/entry` 必须是对：

- `small_cycle`
- `M1 constraints`

的正式翻译，而不是继续直接消费旧的：

- `buy_signal`
- `candidate_tier`
- `theme_momentum`
- 各类研究型标签

### 3.3 来自当前代码现实的边界

当前 proto-`M2/M3` 语义主承载点仍在：

- 候选/跟踪/建仓语义：`lowfreq_engine_v16_advanced.py`
- 持有/退出语义：`lowfreq_engine_v16_advanced.py`
- workbench 与候选池投影：`apps/api/main.py`

当前仓库中不存在正式的 `neotrade3/m2` 或 `neotrade3/m3` 包，因此本轮必须先建立最小正式承载结构，避免继续把正式语义堆回既有巨型文件。

## 4. 总体方案

本轮采用以下正式切换方案：

1. 新建轻量正式包：
   - `neotrade3/cycle_intelligence/`
   - `neotrade3/decision_engine/`
2. 在低频引擎内部调用正式组装器，生成 `formal` 对象链
3. API 保留旧字段，并新增正式对象投影
4. 旧字段降级为兼容口径，后续逐步退役

该方案的核心原则是：

- 正式对象独立承载
- 真值源尽量靠近引擎
- API 只承担读取与投影职责
- 先建立正式链，再做后续消费切换

## 5. 模块与文件职责

### 5.1 新增模块

新增 `neotrade3/cycle_intelligence/`：

- `contracts.py`
  - 定义 `small_cycle` 正式对象
- `assembler.py`
  - 将正式 `M1` 输入组装为 `small_cycle`
- `__init__.py`
  - 导出首批正式对象与组装入口

新增 `neotrade3/decision_engine/`：

- `contracts.py`
  - 定义 `identify_state`
  - 定义 `tracking_state`
  - 定义 `entry_state`
- `assembler.py`
  - 将 `small_cycle + M1 constraints` 翻译为三类正式状态
- `__init__.py`
  - 导出正式对象与组装入口

### 5.2 现有文件最小改动职责

`lowfreq_engine_v16_advanced.py`

- 保留现有主流程
- 新增最小调用点以生成正式对象
- 挂出并行 `formal` 结构
- 不在其中定义正式对象类型

`apps/api/main.py`

- 继续返回现有兼容字段
- 新增正式对象投影区块
- 不承担正式语义生成职责

相关测试文件

- 新增对象级测试
- 补充引擎并行输出测试
- 补充 API 投影回归测试

## 6. 正式对象链

### 6.1 M2 `small_cycle`

`small_cycle` 负责回答：

- 当前是否形成可正式消费的 `small_cycle`
- 当前属于哪个正式状态
- 当前判断为何成立
- 当前失效或衰竭风险是什么

首批最小字段要求：

- `object_type`
- `object_version`
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

### 6.2 M3 `identify_state`

`identify_state` 负责回答：

- 是否进入正式候选视野
- 进入视野的主要依据是什么
- 引用的是哪一个正式周期对象
- 当前是否受到 `M1` 约束阻断

首批最小字段要求：

- `object_type`
- `object_version`
- `stock_code`
- `trade_date`
- `status`
- `reason`
- `evidence_ref`
- `m2_cycle_ref`
- `m1_constraints_ref`

### 6.3 M3 `tracking_state`

`tracking_state` 负责回答：

- 是否进入持续观察
- 当前观察成熟度处于何种阶段
- 是否仍应继续观察而非直接进入建仓

首批最小字段要求：

- `object_type`
- `object_version`
- `stock_code`
- `trade_date`
- `status`
- `maturity`
- `transition_reason`
- `evidence_ref`
- `m2_cycle_ref`
- `m1_constraints_ref`

### 6.4 M3 `entry_state`

`entry_state` 负责回答：

- 当前是否满足正式建仓条件
- 当前是否可执行
- 若不可执行，阻断原因是什么

首批最小字段要求：

- `object_type`
- `object_version`
- `stock_code`
- `trade_date`
- `status`
- `decision`
- `actionable`
- `blocking_reasons`
- `evidence_ref`
- `m2_cycle_ref`
- `m1_constraints_ref`

## 7. 最小数据流

### 7.1 输入阶段

低频引擎从正式 `M1` 输入面取值，首批只允许使用：

- `D1`
- `D7`
- `PF1`

本轮不得绕过正式对象，直接把以下内容当作正式输入：

- `theme_momentum`
- `candidate tags`
- `factor_matrix`
- 研究层临时标签

### 7.2 M2 生成阶段

引擎调用 `cycle_intelligence.assembler`，基于正式 `M1` 输入生成 `small_cycle`。

此阶段只做识别，不做交易动作翻译。

### 7.3 M3 翻译阶段

引擎调用 `decision_engine.assembler`，基于：

- `small_cycle`
- `M1 constraints`

生成：

- `identify_state`
- `tracking_state`
- `entry_state`

### 7.4 输出阶段

引擎输出应采用并行结构：

```python
{
    "legacy": {...},
    "formal": {
        "small_cycle": {...},
        "identify_state": {...},
        "tracking_state": {...},
        "entry_state": {...},
    },
}
```

要求：

- 保留旧字段兼容面
- 新增正式对象区块
- 旧字段后续只能作为兼容投影，不再作为真值源

## 8. API 暴露策略

本轮 `API` 对外策略为：

- 保留旧字段
- 同步新增正式对象字段
- 明确旧字段是兼容口径
- 正式对象是新真值面

建议的 API 暴露方式：

1. 在现有相关视图中新增 `formal` 区块
2. 不删除现有 `legacy` 字段
3. 在 `_meta` 或说明字段中明确正式优先级

workbench、候选池、报告脚本等现有消费方，本轮不要求全面改写，但新增结构后应允许后续逐步迁移到 `formal`。

## 9. 禁止事项

本轮禁止：

- 把 `hold/exit` 一并塞进本轮切换
- 把 `mid_cycle / large_cycle` 升格进正式主链
- 在 `main.py` 中继续编写正式语义生成逻辑
- 把正式对象定义放回低频引擎主文件
- 由单日异动直接触发 `entry_state`
- 当 `M1` 正式证据不足时，偷偷回填旧分析字段以伪装正式结果
- 让 `theme_momentum` 等兼容信号重新影响 `small_cycle` 或 `entry_state`

## 10. 验证与验收口径

### 10.1 验收目标

本轮验收目标不是收益优化，而是：

- 正式对象链成立
- 正式输入边界成立
- 并行输出结构成立
- API 只投影、不造新语义

### 10.2 最小测试集

对象测试：

- `small_cycle` 字段完整
- `identify/tracking/entry` 字段完整
- 证据不足时显式降级，而不是静默补齐

组装器测试：

- 相同 `M1` 输入可稳定生成相同 `small_cycle`
- `decision_engine` 只能基于正式输入翻译三类状态

引擎测试：

- 输出新增 `formal` 区块
- 保留现有 `candidate_signals / entry_signals / signal_summary`
- 正式对象生成失败时必须显式暴露失败信息

API 测试：

- 旧字段继续可读
- 新增正式对象投影区块可读
- API 不承担正式语义生成

### 10.3 硬性验收条目

- `A1` `small_cycle` 只消费正式 `M1`
- `A2` `entry_state` 不能由单日异动直接触发
- `A3` `tracking_state` 必须区分“继续观察”和“达到 entry 成熟度”
- `A4` 旧字段与正式对象冲突时，以正式对象为准
- `A5` 本轮不得改写 `hold/exit` 现有语义

### 10.4 最小结构校验

至少执行：

- 新增对象/组装器相关单测
- 低频引擎回归单测
- API 投影相关单测
- `python3 -m py_compile` 覆盖新改文件
- 最近编辑文件诊断检查

## 11. 风险与后续

### 11.1 本轮残余风险

- `small_cycle` 首批仍运行于旧引擎生态内部，因此底层生成逻辑尚未完全脱离历史字段环境
- 并行期可能出现“旧字段更宽松、正式对象更严格”的表象，这是预期现象，不应视为回归
- 旧消费面短期仍会继续读取兼容字段，因此正式对象上线后不会立即带来全面消费切换

### 11.2 本轮完成后的下一步

本轮完成后，建议下一步按顺序推进：

1. workbench 优先改读 `formal`
2. 报告脚本优先改读 `formal`
3. 评估 `hold/exit` 正式对象化
4. 启动独立的仓库清理与退役治理项目

## 12. 结论

本设计收口的不是完整 `M2/M3` 大体系，而是一个最小、正式、可验证的切换边界：

- 新增轻量正式模块
- 由引擎生成正式对象
- 由 API 只做投影
- 保留旧字段兼容面
- 首批只完成 `small_cycle -> identify/tracking/entry`

该边界既满足当前正式设计要求，也能避免继续放大 `main.py` 与巨型引擎文件的语义堆积问题。
