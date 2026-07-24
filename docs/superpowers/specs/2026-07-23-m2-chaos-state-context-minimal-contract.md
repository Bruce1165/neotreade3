Status: active
Owner: lowfreq / chaos-model
Scope: M2 混沌三层状态上下文最小对象契约
Canonical: PROJECT_STATUS.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-23

# 2026-07-23 M2 混沌三层状态上下文最小对象契约

## 0. 目的

本文件只定义 `M2` 混沌三层状态上下文的最小对象契约：

- 对象名
- 对象定位
- 字段类别
- 对象边界
- 消费关系

本文件不定义：

- 计算公式
- 阈值参数
- 落盘路径
- API 端点
- 代码结构

## 1. 适用边界

本契约只服务当前阶段已冻结的专项基线：

- 混沌模型当前阶段先作为状态上下文主变量体系推进
- `M2` 是正式主归属
- `M4/M6` 只读消费
- 当前阶段先证 `20D/40D/60D` 中期有效
- 当前阶段不直接切换到混沌动作主线

本契约不替代当前已存在的 `M2 small_cycle` 与 `m2_shadow_bundle` 对象，只定义混沌专项当前阶段新增的最小状态对象。

## 2. 与现有 M2 对象的关系

### 2.1 已有对象

当前仓库已存在的 `M2` 正式对象与 persisted truth-source 包括：

- `small_cycle`
- `m2_shadow_bundle`

它们当前服务的主要是：

- formal front
- lowfreq 前半段消费
- benchmark replay / readback

### 2.2 本次新增对象的定位

本次冻结的混沌状态上下文对象与已有 `small_cycle / shadow_bundle` 的关系是：

- 不是替代关系
- 不是兼容壳关系
- 是并行的 M2 状态对象关系

更准确地说：

- `small_cycle / shadow_bundle` 继续服务现有 formal front 与 benchmark 体系
- `stock_state_context / theme_state_context / market_state_context / state_context_link` 服务混沌专项当前阶段的状态上下文表达

### 2.3 当前阶段禁止事项

当前阶段禁止：

- 把新对象误表述为“已经替代 existing M2 formal objects”
- 在没有中期验证与消费切换结论前，把新对象强行接成完整动作主线
- 在 `M6` 或 `M4` 中自行定义对象主语义

## 3. 对象总览

`M2` 混沌状态上下文 v1 只冻结 4 个对象：

1. `stock_state_context`
2. `theme_state_context`
3. `market_state_context`
4. `state_context_link`

版本策略：

- 本文档只冻结对象名与语义
- 对象版本统一从 `v1` 开始
- 字段扩展采用向后兼容方式，不在本轮讨论

## 4. 对象契约

### 4.1 stock_state_context

**定位**

- `L1` 个股自身状态对象
- 个股主语义对象

**回答的问题**

- 这只股票当日自身阴阳关系如何
- 它当前驱动段是否成立
- 相对自身历史，驱动段是增强、衰减还是噪声切换

**最小身份字段**

- `object_type`
- `object_version`
- `stock_code`
- `trade_date`
- `rule_version`
- `input_data_version`

**最小字段类别**

- `core_energy`
- `regime`
- `dynamics`
- `coverage_quality`
- `audit_ref`

**必须不包含**

- 动作建议字段
- 未来收益预测字段
- 板块/概念解释字段
- 全市场解释字段

**边界**

- `stock_state_context` 只描述个股自身状态
- 它是个股判断的主语义中心
- 它不被 `theme_state_context` 或 `market_state_context` 直接覆盖

### 4.2 theme_state_context

**定位**

- `L2` 板块/概念统一上下文对象
- 个股所处局部生态的关键上下文

**回答的问题**

- 该股所在主题当前是在支持它还是削弱它
- 该主题自身是启动、扩散、分歧还是退潮
- 个股相对该主题是同步、超强还是掉队

**最小身份字段**

- `object_type`
- `object_version`
- `theme_id`
- `theme_type`
- `trade_date`
- `rule_version`
- `input_data_version`

**最小字段类别**

- `core_energy`
- `regime`
- `dynamics`
- `coverage_quality`
- `audit_ref`

**必须不包含**

- 直接个股动作建议
- 未来收益预测字段
- 对单只个股主状态的覆盖字段
- 复杂传播图或多主题融合字段

**边界**

- `theme_state_context` 是关键上下文，不是主语义
- v1 统一承载“板块/概念”上下文，不拆行业对象与概念对象
- 当前阶段只定义最小对象，不引入传播图和多主题融合算法

### 4.3 market_state_context

**定位**

- `L3` 全市场背景约束对象
- 整体市场天气对象

**回答的问题**

- 当前全市场整体是阳主导、阴主导还是高噪声
- 当前市场背景是在给顺风、给逆风，还是不稳定

**最小身份字段**

- `object_type`
- `object_version`
- `trade_date`
- `rule_version`
- `input_data_version`

**最小字段类别**

- `core_energy`
- `regime`
- `dynamics`
- `coverage_quality`
- `audit_ref`

**必须不包含**

- 个股主状态字段
- 板块主状态字段
- 直接动作建议字段
- 未来收益预测字段

**边界**

- `market_state_context` 只做背景约束
- 它不能直接替代个股和主题上下文
- 它不能直接成为个股动作的第一决定项

### 4.4 state_context_link

**定位**

- 三层状态上下文的显式关联对象

**回答的问题**

- 某只股票在某个交易日，关联到哪些主题上下文和哪一个市场背景
- 三层对象的解释优先级是什么
- 当前三层对象哪些可用、哪些不可用

**最小身份字段**

- `object_type`
- `object_version`
- `stock_code`
- `trade_date`
- `rule_version`

**最小字段类别**

- `stock_state_ref`
- `theme_state_refs`
- `market_state_ref`
- `context_priority`
- `context_validity`
- `audit_ref`

**必须不包含**

- 复制上层大对象内容
- 动作建议字段
- 未来收益预测字段

**边界**

- `state_context_link` 只表达引用关系和优先级
- 不承载主状态语义
- 不重复上层对象 payload

## 5. 统一字段类别约束

四个对象当前阶段只允许使用以下字段类别：

- `identity`
- `core_energy`
- `regime`
- `dynamics`
- `coverage_quality`
- `audit_ref`
- `version_ref`
- `*_ref` / `*_refs`（仅 link 对象）

当前阶段明确禁止：

- `action_suggestion`
- `entry_decision`
- `exit_decision`
- `predicted_return`
- `future_window_label`
- 任意带交易指令含义的字段

## 6. 解释顺序

三层状态上下文的正式解释顺序固定为：

1. 先读 `stock_state_context`
2. 再读 `theme_state_context`
3. 最后读 `market_state_context`

禁止：

- 用 `market_state_context` 直接覆盖 `stock_state_context`
- 用 `theme_state_context` 直接改写 `stock_state_context`
- 在下游消费层重新发明另一套解释顺序

## 7. 消费关系

### 7.1 M2

职责：

- 定义并输出 4 个对象
- 保持对象语义一致性

### 7.2 M3

职责：

- 只读消费状态上下文对象，作为未来动作链上下文

边界：

- 当前阶段不把这些对象直接上升为完整动作主线
- 不反向定义对象语义

### 7.3 M4

职责：

- 只读消费对象
- 在不同 `theme/market` 背景下验证 `stock_state_context` 的中期有效性

边界：

- 不把评估标签回灌为在线对象字段
- 不把 M4 评估结果上提为 M2 主语义

### 7.4 M5

职责：

- 治理版本推进
- 治理对象、权重、阈值的版本化调整

边界：

- 不静默在线改写当日状态对象

### 7.5 M6

职责：

- 展示对象
- 形成共享观察入口

边界：

- 只读消费
- 不创造新语义
- 不把状态字段渲染成动作建议

## 8. 当前阶段不展开的内容

本契约当前阶段不展开：

- `theme_id` 的最终编码方案
- 多主题加权融合策略
- 相关主题传播图
- 行业对象与概念对象拆分
- 各字段具体取值公式
- 存储路径与 API 路由

## 9. 通过条件

本契约在当前阶段视为通过，需同时满足：

- 4 个对象的定位清晰
- 4 个对象的边界清晰
- 消费关系清晰
- 当前阶段明确禁止项清晰
- 与现有 `small_cycle / m2_shadow_bundle` 的关系清晰

如果以上任一项仍模糊，则不进入更深实现或更细字段设计。

