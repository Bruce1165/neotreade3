# 共享展示骨架组件基线实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-shared-display-foundation-baseline-design.md`

## 1. 目标

本计划只覆盖共享展示骨架组件基线落地，不扩展到 `OpsCenter` 页面基线、`O2` 页尾 contract 收口、页面功能调整或共享组件能力扩展。

本轮目标只有三个：

1. 把当前已被多个页面共同消费、但尚未进入 `HEAD` 的共享展示骨架组件正式纳入仓库基线。
2. 把共享文案模块 `statusCopy.js` 正式纳入仓库基线。
3. 用最小验证与最小提交边界收口，不带入页面功能线。

本轮必须产出的核心结果：

- 共享展示骨架层正式进入提交历史
- 当前共享组件对外 props 语义保持不变
- 提交中不包含 `OpsCenter` 或其他页面功能改动

## 2. 不在本轮完成

- `OpsCenter.jsx` 页面基线
- `OpsCenter.test.jsx`
- `OpsCenter.footerContract.test.jsx`
- `Lowfreq`、`Overview`、`Screeners`、`StockCheck`、`MarketIntelligence` 的功能改动
- 共享组件 API 扩展
- 共享组件测试补齐

## 3. 当前实施起点

### 3.1 已有现实基础

- 以下文件当前已存在于工作区：
  - [BlockMessage.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/BlockMessage.jsx)
  - [MetricCard.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/MetricCard.jsx)
  - [PageHeader.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/PageHeader.jsx)
  - [StatusPill.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/StatusPill.jsx)
  - [statusCopy.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/statusCopy.js)
- 当前 `HEAD` 已跟踪：
  - [AppContext.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/context/AppContext.jsx)
  - [api.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/api.js)
  - [asyncBlocks.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/services/asyncBlocks.js)
- 上述共享组件已经被多个已跟踪页面共同消费：
  - [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx)
  - [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx)
  - [Screeners.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Screeners.jsx)
  - [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx)
  - [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx)
  - [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx)

### 3.2 当前结构性风险

- 这些共享组件当前尚未进入 `HEAD`，导致后续 `OpsCenter` 页面基线无法独立收口
- 它们已被多个页面复用，如果直接和某个页面一起提交，会破坏“共享层先于页面层”的边界
- 若借此机会扩展组件 API 或补页面功能，会把“基线收口”扩大成“组件治理”

## 4. 实施原则

- 只纳入共享展示骨架组件与共享文案模块本身
- 组件对外 props 语义保持不变
- 允许的代码清理仅限“基线整洁性最小清理”
- 不顺手做页面逻辑修改
- 若发现必须改页面功能才能让基线成立，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/components/BlockMessage.jsx`
- `neotrade3-dashboard/src/components/MetricCard.jsx`
- `neotrade3-dashboard/src/components/PageHeader.jsx`
- `neotrade3-dashboard/src/components/StatusPill.jsx`
- `neotrade3-dashboard/src/components/statusCopy.js`

如确有必要，才允许包含：

- 仅为基线整洁性服务的最小消费者清理

建议只包含以下逻辑：

- 把当前已有实现正式纳入基线
- 保持现有 props / 常量键名不变
- 如存在显然未使用符号，只做最小清理

明确不改：

- `neotrade3-dashboard/src/pages/OpsCenter.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.test.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.footerContract.test.jsx`
- 其他页面的功能逻辑
- 共享组件测试文件

## 6. 总体分段

本计划建议分为四段执行：

- `A-R1`：冻结共享骨架层切片边界
- `A-R2`：纳入共享组件与共享文案模块
- `A-R3`：如有必要，做最小整洁性清理
- `A-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### A-R1：冻结共享骨架层切片边界

目标：

- 在动手前确认共享组件集合、消费者范围，以及哪些页面主题线必须排除。

任务：

- 审计 5 个共享对象当前实现
- 审计它们在多个页面中的消费关系
- 记录必须排除的页面功能主题线
- 确认本刀不进入 `OpsCenter` 页面层

完成判定：

- 已形成明确的 include / exclude 清单
- 可以确认本刀属于共享层，而不是页面层

### A-R2：纳入共享组件与共享文案模块

目标：

- 让共享展示骨架层正式进入仓库基线。

任务：

- 纳入 [BlockMessage.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/BlockMessage.jsx)
- 纳入 [MetricCard.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/MetricCard.jsx)
- 纳入 [PageHeader.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/PageHeader.jsx)
- 纳入 [StatusPill.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/StatusPill.jsx)
- 纳入 [statusCopy.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/statusCopy.js)

关键约束：

- 不扩展组件 API
- 不新增共享状态或上下文依赖
- 不顺手调整消费者页面行为

完成判定：

- 5 个共享对象都在提交边界内
- 对外接口语义保持不变

### A-R3：如有必要，做最小整洁性清理

目标：

- 只有在基线整洁性确有需要时，才做最小清理。

任务：

- 判断是否存在显然未使用 import 或未使用符号
- 如确需清理，只处理“不会改变功能”的最小项

关键约束：

- 不修改页面功能逻辑
- 不改变组件对外 API
- 不扩写为共享组件重构

完成判定：

- 清理范围可以用一句话解释为“仅为基线整洁性服务”

### A-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 检查提交边界只包含共享层对象
- 如发生最小消费者清理，补做语法/结构校验
- 检查暂存区 diff，不带页面功能线
- 提交前确认 `OpsCenter` 页面层与 `O2` 页尾线未混入

完成判定：

- 提交边界干净
- 本刀仍然是“共享骨架层基线”，不是“页面功能迭代”

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先审计共享组件集合与消费者关系
2. 再纳入 5 个共享对象
3. 如有必要，最后才做最小整洁性清理
4. 收尾验证并提交

原因：

- 先定共享层边界，能避免误把页面层混进来
- 先纳入基线，再考虑清理，能避免“清理”反过来扩大范围
- 把边界检查放到最后，可最大限度保持原子化

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit A：共享展示骨架组件基线

范围：

- `BlockMessage.jsx`
- `MetricCard.jsx`
- `PageHeader.jsx`
- `StatusPill.jsx`
- `statusCopy.js`
- 如确有必要，再加最小消费者整洁性清理

目标：

- 为多页面共用的展示骨架层建立正式基线

如果该提交无法与页面功能线安全分离，则应停止实现并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 5 个共享对象正式进入基线
2. 共享组件对外 props 语义不变
3. `statusCopy.js` 的现有键名保持不变
4. 提交中不包含 `OpsCenter` 页面层与 `O2` 页尾线
5. 如有最小清理，也不改变页面功能行为

## 11. 风险提示

- 当前最大风险不在文件数量，而在于这些共享组件已被多个页面共同消费，稍有不慎就会把页面功能线混进来
- 如果借这刀扩展组件 API，会把“基线收口”扩大成“共享组件治理”
- 如果顺手修页面显示问题，会破坏后续 `B/C` 两刀的独立性

## 12. 结论

本计划的核心不是“补几个组件文件”，而是：

- 把已经被多个页面共用的展示骨架层正式纳入基线
- 保持共享层与页面层的物理边界清晰
- 只允许最小整洁性清理，不做功能扩张

只有这样，后续 `OpsCenter` 页面基线和 `O2` 页尾 contract 收口，才能继续保持原子化推进。
