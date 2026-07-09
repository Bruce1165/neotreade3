# OpsCenter 页尾 Contract 收口设计

日期：2026-07-09

## 1. 目标

本切片只解决一个问题：

把 `OpsCenter` 页面底部当前平铺展示的 `meta + evidence` 信息，收口为一个独立、可识别、可测试的只读“运行证据”区块。

本切片的目标不是新增运维能力，也不是扩展后端 contract，而是把页尾这组已有事实字段从“散落展示”收口为稳定前端展示 contract。

## 2. 范围

包含：

- 在 `neotrade3-dashboard/src/pages/OpsCenter.jsx` 中，将当前页尾平铺信息整理为独立只读区块
- 一个新的聚焦测试文件，例如 `neotrade3-dashboard/src/pages/OpsCenter.footerContract.test.jsx`

不包含：

- 后端字段增删
- `/ops` 路由
- `OpsCenter` 主区块文案改写
- `OpsCenter` 错误态样式统一
- `OpsCenter.test.jsx` 的继续扩写
- `App.jsx` 或其他页面改动

## 3. 现有证据

当前仓库中已有以下可验证证据：

- `OpsCenter` 页面已存在：`neotrade3-dashboard/src/pages/OpsCenter.jsx`
- 页尾当前已直接消费：
  - `meta.snapshot_generated_at`
  - `evidence.latest_run_date`
  - `evidence.expected_trade_date`
  - `evidence.overdue_shifted_count`
  - `evidence.inconsistency_count`
  - `evidence.pending_intents_after`
- 上述字段目前以一组平铺 `span` 的形式直接展示在页面底部
- 现有 `OpsCenter.test.jsx` 只覆盖主区块渲染、异常摘要和失败态，尚未对页尾字段建立独立 contract 保护

这说明本切片属于对现有页面展示 contract 的收口，而不是发明新字段或新业务流程。

## 4. 职责归属

本切片职责属于 `OpsCenter` 页面内部的只读展示 contract 收口。

它只回答两个问题：

- 页面底部是否存在一个稳定的“运行证据”区块
- 当前已有 6 个证据字段是否按既有 contract 被展示出来

它不回答以下问题：

- 运维聚合接口是否新增字段
- 页面主区块是否重排
- `/ops` 路由是否命中
- 刷新或日期切换行为是否正确

因此本切片应保持为“页尾 contract 收口”，而不是“页面功能升级”。

## 5. 展示设计

### 5.1 区块定位

当前页尾已经承载一组运行事实，但缺少明确的区块边界。

本切片应把它整理为一个独立只读区块，建议命名为“运行证据”。

### 5.2 字段集合

本切片只保留现有 6 个字段，不新增业务字段：

1. `快照生成` ← `meta.snapshot_generated_at`
2. `最近任务` ← `evidence.latest_run_date`
3. `目标交易日` ← `evidence.expected_trade_date`
4. `顺延待处理` ← `evidence.overdue_shifted_count`
5. `收口异常` ← `evidence.inconsistency_count`
6. `日后待执行` ← `evidence.pending_intents_after`

### 5.3 展示要求

展示层要求保持收敛：

- 继续使用现有 `displayText()` 做缺失值回退
- 不改变字段语义
- 不引入折叠、筛选、点击跳转或交互动作
- 不新增解释性副文案

因此本切片只是“重新组织已有事实”，不是“增加解释层”。

## 6. 测试设计

### 6.1 测试载体

测试应新增独立文件，例如：

- `OpsCenter.footerContract.test.jsx`

不优先回写 `OpsCenter.test.jsx`，避免继续把该文件做大。

### 6.2 最小断言集合

推荐最小断言集合：

- “运行证据”区块存在
- 6 个标签都存在
- 6 个字段值按当前 contract 正常渲染
- 缺失值仍回退到 `--`

断言重点应放在：

- 页尾字段集合与标签映射
- 缺失值回退行为

而不是扩展为：

- 主区块内容重验
- 页面样式像素级检查
- 整页布局快照

### 6.3 Mock 策略

推荐策略：

- mock `getOpsCenterSummary`
- mock `useApp()`
- 如现有测试已有稳定 `DateSelector` stub，可沿用最小替身

测试应尽量聚焦页尾区块本身，不把断言扩散到刷新、路由或其他主题。

## 7. 非目标

本切片明确不处理：

- 后端 contract 调整
- `OpsCenter` 主卡片或表格区块重排
- `OpsCenter` 错误态样式统一
- `/ops` 路由
- `OpsCenter` 刷新/日期切换行为

这些都属于其他已拆分或待拆分的主题线。

## 8. 提交边界

目标实现提交只允许包含：

- `OpsCenter.footerContract.test.jsx`
- `OpsCenter.jsx` 中与页尾“运行证据”区块直接相关的最小改动

必须排除：

- `App.jsx`
- `OpsCenter.test.jsx` 的继续扩写
- `Overview.jsx`
- `DateSelector`、`PageHeader` 等共享组件重构
- 后端接口或 contract 改动

## 9. 验证要求

预期最小验证闭环：

- 运行 `OpsCenter.footerContract.test.jsx`
- 如触及 `OpsCenter.jsx`，补跑 `OpsCenter.test.jsx`
- 确认提交中不带其他页面、路由或样式主题线

## 10. 结论

本切片的本质不是新增用户能力，而是给 `OpsCenter` 页尾这组已有事实字段补上一层独立、稳定、低风险的展示 contract 保护。

只有先把这条最窄的页尾收口线完成，后续 `OpsCenter` 的更宽展示治理或错误态统一，才更容易继续保持原子化推进。
