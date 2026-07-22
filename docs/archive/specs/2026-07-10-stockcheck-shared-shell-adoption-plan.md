# StockCheck Shared-Shell Adoption 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-stockcheck-shared-shell-adoption-design.md`

## 1. 目标

本计划只覆盖 `StockCheck.jsx` 的共享壳层复用，不扩展到按钮文案、状态契约、测试断言或 API 逻辑。

本轮目标只有三个：

1. 将页面本地 header 收口到共享组件 `PageHeader`。
2. 将页面本地错误块收口到共享组件 `BlockMessage`。
3. 在不卷入按钮文案和 `STATUS_COPY` 的前提下，形成一个可独立解释的 shared-shell 切片。

本轮必须产出的核心结果：

- `StockCheck.jsx` 使用 `PageHeader`
- `StockCheck.jsx` 使用 `BlockMessage`
- 提交中不包含按钮文案变化
- 提交中不包含 `STATUS_COPY` badge / debug 标题变化
- 提交中不包含 `StockCheck.test.jsx`

## 2. 不在本轮完成

- `开始核验 / 核验中...` 文案收口
- `STATUS_COPY.actionable / observing / followerObserving`
- `STATUS_COPY.debugData`
- `StockCheck.test.jsx` 断言更新
- `fetchApi` 调用
- 结果区、输入区和搜索交互逻辑改动
- 共享组件自身实现修改

## 3. 当前实施起点

### 3.1 已有现实基础

- [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 的剩余 diff 实际混有两组主题：
  - shared-shell adoption：`PageHeader`、`BlockMessage`
  - copy/state contract：按钮文案、`STATUS_COPY` badge、`STATUS_COPY.debugData`
- `PageHeader` 和 `BlockMessage` 已有稳定消费面：
  - [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx)
  - [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx)
  - [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx)
- [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 当前显式感知的更多是按钮文案，不是 shared-shell 自身

### 3.2 结构性风险

- 最大风险不是共享组件替换本身，而是把按钮文案和 `STATUS_COPY` 顺手一起带进提交
- 如果 shared-shell adoption 与 copy/state contract 混到一个 commit，后续无法清楚解释该切片目的
- 如果替换后测试表面发生变化，容易误把测试修正扩大成文案收口

## 4. 实施原则

- 只改 `StockCheck.jsx`
- 只做 `PageHeader` / `BlockMessage` 复用
- 不改 copy
- 不改 status contract
- 不改测试文件，除非出现由 shared-shell adoption 直接导致的最小必要修正，并需先重新评估边界
- 若无法从相邻 diff 中安全隔离 shared-shell adoption，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/StockCheck.jsx`

允许的逻辑：

- 用 `PageHeader` 替换页面顶部本地 `<h2> + <p>` 组合
- 用 `BlockMessage` 替换本地红色错误块

明确不改：

- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- `开始核验 / 核验中...`
- `STATUS_COPY.actionable / observing / followerObserving`
- `STATUS_COPY.debugData`
- `fetchApi`
- `handleCheck`
- `handleKeyPress`
- 搜索输入区与结果区的结构

## 6. 总体分段

本计划建议分为四段执行：

- `SCS-R1`：冻结 shared-shell adoption 切片边界
- `SCS-R2`：只替换 `PageHeader` 和 `BlockMessage`
- `SCS-R3`：跑最小验证并检查结构安全
- `SCS-R4`：隔离 shared-shell hunk 并提交

## 7. 分段实施计划

### SCS-R1：冻结 shared-shell adoption 切片边界

目标：

- 明确 `StockCheck.jsx` 中哪些改动属于共享壳层复用，哪些相邻改动必须排除。

任务：

- 读取 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前相关区块
- 对照 `HEAD` 检查剩余 diff
- 只标记以下目标点位：
  - 页面 header
  - 错误块
- 显式排除：
  - 按钮文案
  - `STATUS_COPY` badge
  - `STATUS_COPY.debugData`
  - `StockCheck.test.jsx`

完成判定：

- include / exclude 列表明确
- shared-shell adoption 与相邻 copy/state diff 已清楚分开

### SCS-R2：只替换 `PageHeader` 和 `BlockMessage`

目标：

- 在不改变业务行为和用户可见 copy 语义的前提下，完成 `StockCheck` 的共享壳层接入。

任务：

- 引入 `PageHeader`
- 引入 `BlockMessage`
- 删除本地 header 实现
- 删除本地错误块实现
- 保持其余 UI 文案与交互不动

关键约束：

- 不调整按钮文案
- 不调整 `STATUS_COPY`
- 不改结果区结构
- 不改 API 行为

完成判定：

- `StockCheck.jsx` 使用共享壳层组件
- 页面其余行为保持不变

### SCS-R3：跑最小验证并检查结构安全

目标：

- 证明 shared-shell adoption 不影响 `StockCheck` 现有交互契约。

任务：

- 运行 `npm test -- src/pages/StockCheck.test.jsx`
- 检查编辑区是否引入明显语法/结构问题
- 若测试暴露的变化属于 shared-shell adoption 直接影响，再回到边界判断；不能自动扩大到文案收口

完成判定：

- `StockCheck.test.jsx` 通过
- 编辑区无明显语法/结构问题

### SCS-R4：隔离 shared-shell hunk 并提交

目标：

- 生成一个单一目的的 production commit，只表达 `StockCheck` 的 shared-shell adoption。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.jsx`
- 只暂存 `PageHeader` / `BlockMessage` 对应 hunk
- 排除按钮文案和 `STATUS_COPY` 相邻 drift
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 shared-shell adoption
- 提交中不含 `StockCheck.test.jsx`
- 提交中不含 copy/state contract 变更

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `StockCheck.jsx` 当前 header / error 区块
2. 对照 `HEAD` 切分 shared-shell 与 copy/state 两类 drift
3. 只改共享壳层点位
4. 跑 `StockCheck.test.jsx`
5. 再检查 `HEAD`-relative diff
6. 只暂存 shared-shell hunk

原因：

- 先切主题再改代码，可以避免把相邻按钮文案和状态文案一起带进提交
- 先跑当前页面测试，再决定是否能安全提交，能把风险控制在最小范围

## 9. 建议提交切分

建议单一提交：

### Commit SCS：StockCheck shared-shell adoption

范围：

- 仅 `StockCheck.jsx` 中 `PageHeader` / `BlockMessage` 的复用 hunk

目的：

- 让 `StockCheck` 接入当前已存在的页面壳层共享体系

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成壳层 + 文案 + 状态契约的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `StockCheck.jsx` 使用 `PageHeader`
2. `StockCheck.jsx` 使用 `BlockMessage`
3. `StockCheck.test.jsx` 通过
4. 不修改 `StockCheck.test.jsx`
5. 提交中不包含按钮文案变化
6. 提交中不包含 `STATUS_COPY` 文案变化

## 11. 风险提示

- 最大风险是从 `StockCheck.jsx` 的混合 diff 中误带入按钮文案和 `STATUS_COPY`
- 第二风险是测试一旦失败，就把问题误判成“需要一起收口 copy”
- 第三风险是 shared-shell adoption 与 page copy 收口在同一文件里过近，隔离时需要更严格地比对 `HEAD`

## 12. 结论

本计划的核心不是“统一整个 `StockCheck` 页面”，而是先做一条可独立解释的 shared-shell 线：

- 只复用 `PageHeader`
- 只复用 `BlockMessage`
- 只在相对 `HEAD` 能保持原子性的前提下提交

这样后续按钮文案和 `STATUS_COPY` 收口仍可以作为下一条独立切片继续推进。
