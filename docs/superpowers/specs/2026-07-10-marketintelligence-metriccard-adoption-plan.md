# MarketIntelligence MetricCard Adoption 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-marketintelligence-metriccard-adoption-design.md`

## 1. 目标

本计划只覆盖 `MarketIntelligence.jsx` 中四张统计卡的共享壳层收口：引入共享 `MetricCard`，删除本地 `SummaryCard`，并完成与 `MetricCard` 形态直接相关的 `value` / `badge` 适配，不扩展到 `BlockMessage`、`ErrorPanel`、测试断言或共享组件实现。

本轮目标只有三个：

1. 将页面本地 `SummaryCard` 收口到共享组件 `MetricCard`。
2. 保持四张统计卡的标题与 subtitle 语义不变。
3. 在不卷入共享组件实现修改的前提下，形成一个可独立解释的统计卡 shared-shell 切片。

本轮必须产出的核心结果：

- `MarketIntelligence.jsx` 使用共享 `MetricCard`
- `MarketIntelligence.jsx` 不再保留本地 `SummaryCard`
- 四张统计卡的标题与 subtitle 语义保持不变
- 页面侧完成最小 `value` / `badge` 适配
- 提交中不包含 `BlockMessage` / `ErrorPanel` / 测试文件改动

## 2. 不在本轮完成

- `BlockMessage`
- `ErrorPanel` 结构或文案调整
- `MarketIntelligence.test.jsx`
- `summaryStateText()` / `summaryStateClass()` 内部逻辑重构
- `MetricCard.jsx` 共享组件实现修改
- 四张统计卡文案改写
- 页面其他区块重排

## 3. 当前实施起点

### 3.1 已有现实基础

- 当前 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 的剩余 diff 已只剩一组主题：
  - `MetricCard` import
  - 本地 `SummaryCard` 删除
  - 四张统计卡消费点替换
- 本地 `SummaryCard` 的旧契约会在组件内部完成状态文案与胶囊渲染
- 共享 [MetricCard.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/MetricCard.jsx) 的现有契约要求页面侧显式传入 `value` 和可选 `badge`
- 因此本轮不能只做 import 替换，还必须让页面承担最小的展示适配
- [MarketIntelligence.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx) 当前感知的是卡片标题，而非 `value` / `badge` 细节，可继续作为最小验证载体

### 3.2 结构性风险

- 最大风险不是共享组件替换本身，而是把页面侧最小适配误扩大成 helper 重构或共享组件实现改动
- 如果把 `summaryStateText()` / `summaryStateClass()` 重整一起带进来，本轮会从“统计卡 shared-shell adoption”扩大成展示逻辑主题
- 如果顺手修改四张卡片 copy，本轮会从 shared-shell adoption 扩大成文案主题

## 4. 实施原则

- 只改 `MarketIntelligence.jsx`
- 只做 `MetricCard` 复用与最小页面侧适配
- 不改 `MetricCard.jsx`
- 不改测试文件，除非出现由 `MetricCard` adoption 直接导致的最小必要修正，并需先重新评估边界
- 若无法从相邻代码中安全隔离 `MetricCard` adoption，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`

允许的逻辑：

- 引入 `MetricCard`
- 删除本地 `SummaryCard`
- 让四张统计卡切换到 `MetricCard`
- 将 `value` 切为 `summaryStateText(...)`
- 显式传入 `badge`，并继续复用 `summaryStateClass(...)`

明确不改：

- `MetricCard.jsx`
- `BlockMessage`
- `ErrorPanel`
- `neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx`
- 其他页面、共享组件、API 文件与文档

## 6. 总体分段

本计划建议分为四段执行：

- `MIM-R1`：冻结 `MetricCard` adoption 的精确边界
- `MIM-R2`：只替换四张统计卡并删除本地 `SummaryCard`
- `MIM-R3`：做最小语法/结构安全验证
- `MIM-R4`：隔离 `MetricCard` hunk 并提交

## 7. 分段实施计划

### MIM-R1：冻结 `MetricCard` adoption 的精确边界

目标：

- 明确 `MarketIntelligence.jsx` 中哪些改动属于统计卡 shared-shell adoption，哪些改动必须排除。

任务：

- 读取 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 当前 import 区、`SummaryCard` helper 区和四张统计卡区块
- 对照 `HEAD` 检查剩余 diff
- 只标记以下目标点位：
  - `MetricCard` import
  - 本地 `SummaryCard` 删除
  - 四张统计卡消费点
  - 直接服务于 `MetricCard` 的 `value` / `badge` 适配
- 显式排除：
  - `BlockMessage`
  - `ErrorPanel`
  - 测试文件
  - 共享组件实现

完成判定：

- include / exclude 列表明确
- `MetricCard` adoption 与其他主题边界清楚分开

### MIM-R2：只替换四张统计卡并删除本地 `SummaryCard`

目标：

- 在不改变统计卡标题和 subtitle 语义的前提下，完成 `MarketIntelligence` 统计卡的共享壳层接入。

任务：

- 引入共享 `MetricCard`
- 删除本地 `SummaryCard`
- 保持四张卡片标题不变：
  - `主线集中度`
  - `AI 聚焦`
  - `K 型干扰`
  - `推荐集中度`
- 保持 subtitle 语义不变
- 将 `value` 与 `badge` 调整为 `MetricCard` 需要的最小显式传参

关键约束：

- 不调整四张卡片标题
- 不调整四张卡片 subtitle 文案
- 不修改 `summaryStateText()` / `summaryStateClass()` 内部逻辑
- 不修改 `MetricCard.jsx`
- 不修改页面其他区块

完成判定：

- `MarketIntelligence.jsx` 只消费共享 `MetricCard`
- 页面其他区域和语义保持不变

### MIM-R3：做最小语法/结构安全验证

目标：

- 证明统计卡 shared-shell adoption 不引入语法或明显结构问题。

任务：

- 对最近编辑文件做最小语法/结构检查
- 运行 `npm test -- src/pages/MarketIntelligence.test.jsx`
- 若验证暴露的是共享组件实现或 helper 重构需求，回到边界判断，不能自动扩大范围

完成判定：

- `MarketIntelligence.jsx` 无明显语法或结构错误
- `MarketIntelligence.test.jsx` 通过

### MIM-R4：隔离 `MetricCard` hunk 并提交

目标：

- 生成一个单一目的的 production commit，只表达 `MarketIntelligence` 的统计卡 shared-shell adoption。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- 只暂存 `MetricCard` 对应 hunk
- 排除 `BlockMessage`、`ErrorPanel`、测试文件与其他页面 drift
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 `MetricCard` adoption
- staged diff 不含 `BlockMessage` 相关 hunk
- staged diff 不含 `ErrorPanel` 相关 hunk
- staged diff 不含测试、文档或其他页面改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `MarketIntelligence.jsx` 当前 import、`SummaryCard` helper 区和四张统计卡区块
2. 对照 `HEAD` 切分 `MetricCard` adoption 的最小点位
3. 只改四张统计卡与本地 `SummaryCard`
4. 跑 `MarketIntelligence.test.jsx`
5. 再检查 `HEAD`-relative diff
6. 只暂存 `MetricCard` hunk

原因：

- 先冻结边界再改代码，可以避免把统计卡之外的页面主题带进提交
- 先跑现有页面测试，再决定是否能安全提交，可以把风险控制在单文件、单消费面范围内

## 9. 建议提交切分

建议单一提交：

### Commit MIM：MarketIntelligence MetricCard adoption

范围：

- 仅 `MarketIntelligence.jsx` 中 `MetricCard` 的复用 hunk

目的：

- 让 `MarketIntelligence` 的四张统计卡接入当前已存在的共享统计卡体系

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成“消费点替换 + helper 重构 + 共享组件实现修改”的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `MarketIntelligence.jsx` 使用共享 `MetricCard`
2. `MarketIntelligence.jsx` 不再保留本地 `SummaryCard`
3. 四张统计卡标题与 subtitle 语义保持不变
4. 页面侧完成最小 `value` / `badge` 适配
5. `MarketIntelligence.test.jsx` 通过
6. 不修改 `MarketIntelligence.test.jsx`
7. 提交中不包含 `BlockMessage`、`ErrorPanel` 或共享组件实现改动

## 11. 风险提示

- 最大风险是把页面侧最小适配误扩大成展示 helper 重构
- 第二风险是测试一旦失败，就把问题误判成“必须去改共享 `MetricCard` 实现”
- 第三风险是四张卡片同时切换，若 staged diff 没有严格对照 `HEAD`，容易带入无关格式或文案噪音

## 12. 结论

本计划的核心不是“统一整个 `MarketIntelligence` 页面”，而是完成最后一条剩余的统计卡 shared-shell 线：

- 只复用 `MetricCard`
- 只删除本地 `SummaryCard`
- 只做共享壳层所需的最小页面侧适配
- 只在相对 `HEAD` 能保持原子性的前提下提交

这样 `MarketIntelligence.jsx` 当前这轮 shared-shell 收口才算闭环完成。
