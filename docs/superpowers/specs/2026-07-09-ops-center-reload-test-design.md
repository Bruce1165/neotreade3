# OpsCenter 重拉测试设计

日期：2026-07-09

## 1. 目标

本切片只解决一个问题：

为 `OpsCenter` 增加一个独立测试载体，证明页面两个关键重拉入口都成立：

- 点击刷新会重新请求
- `selectedDate` 变化会重新请求

本切片的目标不是扩展页面功能，而是把“重拉行为”收口为独立回归保护。

## 2. 范围

包含：

- 一个新的聚焦测试文件，例如 `neotrade3-dashboard/src/pages/OpsCenter.reload.test.jsx`

如确有必要，才允许：

- `neotrade3-dashboard/src/pages/OpsCenter.jsx` 中最小、仅为可测试性服务的改动

不包含：

- `/ops` 路由
- `OpsCenter` 页尾 contract 收口
- `OpsCenter` 错误态样式统一
- `Overview` 或其他页面跳转
- `OpsCenter.test.jsx` 的大规模扩写

## 3. 现有证据

当前仓库中已有以下可验证证据：

- `OpsCenter` 页面已存在：`neotrade3-dashboard/src/pages/OpsCenter.jsx`
- 页面已通过 `getOpsCenterSummary(selectedDate)` 拉取数据
- 页面已有 `DateSelector`，且传入了 `onRefresh={load}`
- 现有 `OpsCenter.test.jsx` 已覆盖正常渲染、异常摘要、失败态，但尚未专门覆盖“刷新重拉”与“日期变化重拉”

这说明本切片属于对现有页面行为测试的补齐，而不是发明新能力。

## 4. 职责归属

本切片职责属于页面重拉行为验证。

它只回答两个问题：

- 手动刷新是否触发再次请求
- 日期切换是否触发针对新日期的再次请求

它不回答以下问题：

- 页面 contract 是否完整
- 页面区块文案是否逐项更新
- 路由是否命中

因此本切片应保持为“行为触发测试”，而不是“页面展示大全测试”。

## 5. 测试设计

### 5.1 测试载体

测试应新增独立文件，例如：

- `OpsCenter.reload.test.jsx`

不优先回写 `OpsCenter.test.jsx`，避免继续把该文件做大。

### 5.2 触发源

测试聚焦两个触发源：

1. `DateSelector` 的 `onRefresh`
2. `selectedDate` 从上层 context 发生变化

### 5.3 断言范围

推荐最小断言集合：

- 首次渲染时，请求一次初始日期
- 刷新后，再次请求同一个日期
- 日期变化后，再次请求新日期

断言重点应放在：

- `getOpsCenterSummary(selectedDate)` 的调用序列

而不是扩展为：

- 全部区块文案变化
- 所有卡片内容刷新后的 UI 细节

### 5.4 Mock 策略

推荐策略：

- mock `getOpsCenterSummary`
- mock `useApp()` 或提供一个最小测试 provider
- 必要时 mock `DateSelector`，把 `onRefresh` 暴露为可触发按钮

测试应尽量不依赖复杂真实上下文。

## 6. 非目标

本切片明确不处理：

- `OpsCenter` contract 收口
- 页面错误态样式
- `/ops` 路由
- 刷新后页面所有区块内容是否逐项变化
- 跨页面联动

这些都属于后续更宽的页面或路由主题。

## 7. 提交边界

目标实现提交只允许包含：

- 新增的 `OpsCenter.reload.test.jsx`

如确有必要，才允许包含：

- `OpsCenter.jsx` 中最小、仅为可测试性服务的改动

必须排除：

- `App.jsx`
- `OpsCenter.test.jsx` 的大规模扩写
- `Overview.jsx`
- 共享组件与样式重构

## 8. 验证要求

预期最小验证闭环：

- 运行 `OpsCenter.reload.test.jsx`
- 如触及 `OpsCenter.jsx`，补跑 `OpsCenter.test.jsx`
- 确认提交中不带其他页面或路由主题线

## 9. 结论

本切片的本质不是新增用户可见功能，而是给 `OpsCenter` 的两个关键重拉入口补上一层独立、稳定、低风险的行为回归保护。

只有先把这条最窄的测试线收口，后续 `OpsCenter` 的 contract 收口、错误态统一或更宽的页面治理，才更容易继续保持原子化推进。
