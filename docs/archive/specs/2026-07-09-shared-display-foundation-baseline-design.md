# 共享展示骨架组件基线设计

日期：2026-07-09

## 1. 目标

本切片只解决一个问题：

把当前多个前端页面已经共同依赖、但尚未进入 `HEAD` 基线的一组共享展示骨架组件，作为独立主题线收口进仓库基线。

本切片的目标不是改页面功能，也不是为某一个页面单独让路，而是明确补齐“共享展示层基线”。

## 2. 范围

包含：

- `neotrade3-dashboard/src/components/BlockMessage.jsx`
- `neotrade3-dashboard/src/components/MetricCard.jsx`
- `neotrade3-dashboard/src/components/PageHeader.jsx`
- `neotrade3-dashboard/src/components/StatusPill.jsx`
- `neotrade3-dashboard/src/components/statusCopy.js`

如确有必要，才允许：

- 仅为基线整洁性服务的最小清理，例如删除未使用 import

不包含：

- `OpsCenter.jsx` 页面逻辑
- `OpsCenter.test.jsx`
- `OpsCenter.footerContract.test.jsx`
- `Lowfreq`、`Overview`、`Screeners`、`StockCheck`、`MarketIntelligence` 的功能改动
- 共享组件 API 扩展
- 新增共享组件测试

## 3. 现有证据

当前仓库中已有以下可验证证据：

- 当前 `HEAD` 已跟踪：
  - `neotrade3-dashboard/src/context/AppContext.jsx`
  - `neotrade3-dashboard/src/services/api.js`
  - `neotrade3-dashboard/src/services/asyncBlocks.js`
- 但以下共享组件当前仍未进入 `HEAD`：
  - `BlockMessage.jsx`
  - `MetricCard.jsx`
  - `PageHeader.jsx`
  - `StatusPill.jsx`
  - `statusCopy.js`
- 这些共享组件已经被多个已跟踪页面直接消费：
  - `Lowfreq.jsx`
  - `Overview.jsx`
  - `Screeners.jsx`
  - `StockCheck.jsx`
  - `MarketIntelligence.jsx`
  - `OpsCenter.jsx`
- `statusCopy.js` 当前还被 `Lowfreq.jsx`、`Screeners.jsx`、`StockCheck.jsx` 等页面直接引用

这说明它们的真实职责是“共享展示骨架层”，而不是单页私有文件。

## 4. 职责归属

本切片职责属于前端共享展示骨架层基线收口。

它只回答两个问题：

- 当前多页面共用的展示骨架组件是否正式进入仓库基线
- 当前共享文案常量是否以独立模块形式进入仓库基线

它不回答以下问题：

- 某个页面的业务功能是否正确
- 页面 contract 是否完整
- 路由是否命中
- 共享组件是否需要扩展新能力

因此本切片应保持为“共享骨架基线收口”，而不是“页面功能迭代”。

## 5. 组件设计

### 5.1 组件集合

本切片只补齐当前已经存在的 4 个共享组件和 1 个共享文案模块：

1. `BlockMessage`
2. `MetricCard`
3. `PageHeader`
4. `StatusPill`
5. `STATUS_COPY`

### 5.2 设计定位

这组对象的共同特征是：

- 已经存在可工作的实现
- 已被多个页面消费
- 当前不在 `HEAD` 中

因此本切片不是“设计新组件”，而是“确认它们已经成为正式共享层对象”。

### 5.3 收口要求

本切片应保持收敛：

- 保持现有组件对外 props 语义不变
- 保持现有共享文案键名不变
- 不新增视觉主题层
- 不把页面级逻辑回流到共享组件

如需要清理，只允许做“基线整洁性最小清理”，例如：

- 删除消费者页面中的未使用 import
- 删除组件文件中的显然未使用符号

但不允许借机重构组件 API。

## 6. 消费边界

### 6.1 允许的消费者关系

当前已观察到的消费者关系包括：

- `BlockMessage` 被 `Lowfreq.jsx`、`Overview.jsx`、`Screeners.jsx`、`StockCheck.jsx`、`MarketIntelligence.jsx`、`OpsCenter.jsx` 引用
- `MetricCard` 被 `Lowfreq.jsx`、`Overview.jsx`、`MarketIntelligence.jsx`、`OpsCenter.jsx` 引用
- `PageHeader` 被 `Lowfreq.jsx`、`Overview.jsx`、`StockCheck.jsx`、`MarketIntelligence.jsx`、`OpsCenter.jsx` 引用
- `StatusPill` 被 `Overview.jsx`、`OpsCenter.jsx` 引用
- `STATUS_COPY` 被 `Lowfreq.jsx`、`Screeners.jsx`、`StockCheck.jsx`、`BlockMessage.jsx` 引用

### 6.2 当前结论

这意味着 `A` 线不能再被表述成“OpsCenter 附属提交”。

它的正确定位必须是：

- 先收口共享骨架层
- 再收口 `OpsCenter` 页面层
- 最后再做 `O2` 页尾 contract 线

## 7. 非目标

本切片明确不处理：

- 页面功能修复
- 共享组件视觉重做
- 共享组件行为扩展
- `OpsCenter` 页面基线
- `OpsCenter` 页尾“运行证据”区块
- 页面级测试补齐

这些都属于后续更具体的页面或测试主题线。

## 8. 提交边界

目标实现提交只允许包含：

- `BlockMessage.jsx`
- `MetricCard.jsx`
- `PageHeader.jsx`
- `StatusPill.jsx`
- `statusCopy.js`

如确有必要，才允许包含：

- 仅为基线整洁性服务的最小消费者清理

必须排除：

- `OpsCenter.jsx`
- `OpsCenter.test.jsx`
- `OpsCenter.footerContract.test.jsx`
- `Lowfreq.jsx` 的功能改动
- `Overview.jsx`、`Screeners.jsx`、`StockCheck.jsx`、`MarketIntelligence.jsx` 的功能改动
- 共享组件测试扩展

## 9. 验证要求

预期最小验证闭环：

- 确认这 5 个共享对象进入提交边界
- 如发生最小消费者清理，只验证语法/结构完整性
- 确认提交中不带页面功能线

## 10. 结论

本切片的本质不是“为 `OpsCenter` 让路”，而是给当前已经被多个页面共同消费的展示骨架层补上一层正式基线。

只有先把共享展示骨架层从工作区漂移中独立收口，后续 `OpsCenter` 页面基线以及 `O2` 页尾 contract 收口，才有可能继续保持原子化推进。
