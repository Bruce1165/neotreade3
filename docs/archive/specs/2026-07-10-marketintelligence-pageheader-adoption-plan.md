# MarketIntelligence PageHeader Adoption 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-marketintelligence-pageheader-adoption-design.md`

## 1. 目标

本计划只覆盖 `MarketIntelligence.jsx` 顶部标题区的共享壳层收口：将页面内联标题块与刷新按钮替换为共享 `PageHeader`，并完成与之直接相关的 import 清理，不扩展到 `BlockMessage`、`MetricCard`、测试断言或 API 逻辑。

本轮目标只有三个：

1. 将页面顶部的本地 `<div> + <button>` 标题区收口到 `PageHeader`。
2. 保持现有标题、subtitle、刷新触发和 loading 语义不变。
3. 在不卷入 `BlockMessage` 与 `MetricCard` 的前提下，形成一个可独立解释的顶部壳层 adoption 切片。

本轮必须产出的核心结果：

- `MarketIntelligence.jsx` 使用 `PageHeader`
- `PageHeader` 透传 `title`、`subtitle`、`onRefresh`、`loading`
- `RefreshCw` 不再由本页消费并从 import 中移除
- 提交中不包含 `BlockMessage` 相关 hunk
- 提交中不包含 `MetricCard` 相关 hunk
- 提交中不包含测试文件或其他页面改动

## 2. 不在本轮完成

- `BlockMessage` 共享组件 adoption
- `MetricCard` adoption
- 本地 `BlockMessage` helper 删除
- 本地 `SummaryCard` 删除
- `MarketIntelligence.test.jsx`（若存在）
- `fetchData` 行为改动
- 标题文案、subtitle 文案变更
- 统计卡、区块加载态、错误态结构调整
- 共享组件自身实现修改

## 3. 当前实施起点

### 3.1 已知事实

- 当前 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 相对 `HEAD` 的剩余 diff 混有三组主题：
  - `PageHeader` 顶部标题区替换
  - `BlockMessage` 共享错误/加载块 adoption
  - `SummaryCard -> MetricCard` 统计卡替换
- 顶部标题区的目标形态已经在当前工作区可见：
  - `title="主线审阅"`
  - `subtitle="先看赛道，再看候选，再核对主线与候选之间的联动关系"`
  - `onRefresh={fetchData}`
  - `loading={loading}`
- 旧形态是页面内联标题区与刷新按钮，刷新按钮依赖 `RefreshCw`
- `RefreshCw` import 清理与 `PageHeader` 替换存在直接因果关系
- `BlockMessage` 与 `MetricCard` 有各自独立 import 与消费点，因此具备独立成线条件，不应混入本轮

### 3.2 结构性风险

- 最大风险不是 `PageHeader` 替换本身，而是把同文件里相邻的 `BlockMessage`、`MetricCard` 一并带进提交
- 如果顺手调整标题 copy、刷新行为或 loading 语义，本轮会从“壳层 adoption”扩大成 copy/behavior 主题
- 如果把 `RefreshCw` 清理拆成另一条线，会制造低价值碎提交

## 4. 实施原则

- 只改 `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- 只处理顶部标题区与 `RefreshCw` import 清理
- 不改 `BlockMessage` 相关 import、helper 和消费点
- 不改 `MetricCard` / `SummaryCard` 相关 import、实现和消费点
- 不改测试文件，除非出现由 `PageHeader` adoption 直接导致的最小必要修正，并需先重新评估边界
- 若相对 `HEAD` 无法安全隔离 `PageHeader` hunk，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`

允许的逻辑：

- 引入 `PageHeader`
- 删除 `RefreshCw` import
- 用 `PageHeader` 替换顶部标题区的本地 `<div> + <button>` 结构
- 透传 `title`、`subtitle`、`onRefresh`、`loading`

明确不改：

- `BlockMessage` import
- 本地 `BlockMessage` helper
- `MetricCard` import
- 本地 `SummaryCard`
- 统计卡区块
- 其余加载块、错误块与内容区
- `MarketIntelligence.test.jsx`
- 其他页面、共享组件、API 文件与文档

## 6. 总体分段

本计划建议分为四段执行：

- `MIP-R1`：冻结 `PageHeader` adoption 的精确边界
- `MIP-R2`：只替换顶部标题区并清理 `RefreshCw`
- `MIP-R3`：做最小语法/结构安全验证
- `MIP-R4`：隔离 `PageHeader` hunk 并提交

## 7. 分段实施计划

### MIP-R1：冻结 `PageHeader` adoption 的精确边界

目标：

- 明确 `MarketIntelligence.jsx` 中哪些改动属于顶部壳层 adoption，哪些相邻改动必须排除。

任务：

- 读取 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 当前顶部标题区、import 区和相邻统计卡区块
- 对照 `HEAD` 检查剩余 diff
- 只标记以下目标点位：
  - `PageHeader` import
  - `RefreshCw` import 清理
  - 顶部标题区从内联结构替换为 `PageHeader`
- 显式排除：
  - `BlockMessage` import / helper / 消费点
  - `MetricCard` import / 消费点
  - 本地 `SummaryCard` 删除
  - 测试文件与其他页面

完成判定：

- include / exclude 列表明确
- `PageHeader` 与 `BlockMessage`、`MetricCard` 的边界清楚分开

### MIP-R2：只替换顶部标题区并清理 `RefreshCw`

目标：

- 在不改变页面行为和文案语义的前提下，完成 `MarketIntelligence` 顶部标题区的共享壳层接入。

任务：

- 引入 `PageHeader`
- 删除 `RefreshCw`
- 删除顶部标题区本地 `<div> + <button>` 结构
- 保持 `title`、`subtitle`、`onRefresh={fetchData}`、`loading={loading}` 不变

关键约束：

- 不调整标题文案
- 不调整 subtitle 文案
- 不调整 `fetchData`
- 不调整 `loading`
- 不修改统计卡、错误块和加载块

完成判定：

- `MarketIntelligence.jsx` 顶部标题区由 `PageHeader` 承载
- 页面其他区域和语义保持不变

### MIP-R3：做最小语法/结构安全验证

目标：

- 证明顶部壳层 adoption 不引入语法或明显结构问题。

任务：

- 对最近编辑文件做最小语法/结构检查
- 确认 `PageHeader` 传参与当前页面语义一致
- 确认 `RefreshCw` 已无本页消费点
- 若验证暴露的是 `BlockMessage` 或 `MetricCard` 相关问题，回到边界判断，不能自动扩大到其他共享组件主题

完成判定：

- `MarketIntelligence.jsx` 无明显语法或结构错误
- 顶部标题区的 refresh / loading 语义仍成立

### MIP-R4：隔离 `PageHeader` hunk 并提交

目标：

- 生成一个单一目的的 production commit，只表达 `MarketIntelligence` 顶部标题区的 `PageHeader` adoption。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- 只暂存 `PageHeader` 与 `RefreshCw` 对应 hunk
- 排除 `BlockMessage` 与 `MetricCard` 相邻 drift
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 `PageHeader` adoption
- staged diff 不含 `BlockMessage` 相关 hunk
- staged diff 不含 `MetricCard` 相关 hunk
- staged diff 不含测试、文档或其他页面改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `MarketIntelligence.jsx` 当前 import、标题区和统计卡区块
2. 对照 `HEAD` 切分 `PageHeader`、`BlockMessage`、`MetricCard` 三类 drift
3. 只改顶部标题区与 `RefreshCw`
4. 做最小语法/结构检查
5. 再检查 `HEAD`-relative diff
6. 只暂存 `PageHeader` hunk

原因：

- 先冻结边界再改代码，可以避免把同文件里的另外两条共享组件线误带进提交
- 先做最小结构验证，再决定是否提交，可以把风险控制在单文件单消费点范围内

## 9. 建议提交切分

建议单一提交：

### Commit MIP：MarketIntelligence PageHeader adoption

范围：

- 仅 `MarketIntelligence.jsx` 中顶部标题区的 `PageHeader` 替换 hunk
- `RefreshCw` import 清理

目的：

- 让 `MarketIntelligence` 顶部标题区接入共享页面壳层体系

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 `PageHeader + BlockMessage + MetricCard` 的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `MarketIntelligence.jsx` 使用 `PageHeader`
2. `PageHeader` 保持 `title`、`subtitle`、`onRefresh`、`loading` 语义
3. `RefreshCw` 不再由本页消费
4. `MarketIntelligence.jsx` 无明显语法或结构错误
5. staged diff 不包含 `BlockMessage` 相关改动
6. staged diff 不包含 `MetricCard` 相关改动
7. staged diff 不包含测试、文档或其他页面改动

## 11. 风险提示

- 最大风险是同文件三条共享组件线彼此靠近，隔离时必须严格比对 `HEAD`
- 第二风险是验证过程中若暴露其他组件问题，容易误判成“顺手一起收口更省事”，但这会破坏原子边界
- 第三风险是若 `PageHeader` 当前 API 不能承载页面现有 refresh / loading 语义，本轮必须停下重新评估，而不是扩大到共享组件实现

## 12. 结论

本计划的核心不是“统一整个 `MarketIntelligence` 页面”，而是先切出一条更窄、可独立解释的顶部壳层线：

- 只接入 `PageHeader`
- 只清理 `RefreshCw`
- 只在相对 `HEAD` 可安全隔离时提交

这样 `BlockMessage` 与 `MetricCard` 仍能保留为后续独立切片继续推进。
