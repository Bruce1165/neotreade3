# MarketIntelligence BlockMessage Adoption 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-marketintelligence-blockmessage-adoption-design.md`

## 1. 目标

本计划只覆盖 `MarketIntelligence.jsx` 中加载占位块的共享壳层收口：引入共享 `BlockMessage`，删除本地 `BlockMessage` helper，并让两个加载态消费点继续透传原有 message，不扩展到 `MetricCard`、`SummaryCard`、`ErrorPanel`、测试断言或 API 逻辑。

本轮目标只有三个：

1. 将页面本地 `BlockMessage` helper 收口到共享组件 `BlockMessage`。
2. 保持 `决策摘要加载中...` 与 `主线审阅加载中...` 两个加载 message 不变。
3. 在不卷入 `MetricCard` 与 `SummaryCard` 的前提下，形成一个可独立解释的加载占位 shared-shell 切片。

本轮必须产出的核心结果：

- `MarketIntelligence.jsx` 使用共享 `BlockMessage`
- `MarketIntelligence.jsx` 不再保留本地 `BlockMessage` helper
- 两个加载态 message 保持不变
- 提交中不包含 `MetricCard` 相关 hunk
- 提交中不包含 `SummaryCard` 相关 hunk
- 提交中不包含测试文件或其他页面改动

## 2. 不在本轮完成

- `MetricCard` adoption
- `SummaryCard` 删除
- `ErrorPanel` 结构或文案调整
- `MarketIntelligence.test.jsx`
- `fetchData`、`loading`、请求时序逻辑改动
- 加载文案改写
- 共享组件自身实现修改

## 3. 当前实施起点

### 3.1 已有现实基础

- 当前 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 的剩余 diff 实际混有两组主题：
  - shared-shell adoption：`BlockMessage` import、本地 helper 删除、两个加载态消费点
  - stats card adoption：`MetricCard` import、`SummaryCard` 删除、四张统计卡替换
- 共享 [BlockMessage.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/BlockMessage.jsx) 已有稳定契约：
  - 默认 `tone='gray'`
  - `message`
  - 可选 `onRetry`
  - 可选 `retryLabel`
- `HEAD` 中本地 `BlockMessage` helper 的默认灰色视觉语义，与共享组件当前默认契约一致
- [MarketIntelligence.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx) 当前显式感知的是加载文案，不是本地 helper 的实现细节

### 3.2 结构性风险

- 最大风险不是共享组件替换本身，而是把相邻的 `MetricCard` / `SummaryCard` 一起带进提交
- 如果 shared-shell adoption 与 stats card adoption 混到一个 commit，后续无法清楚解释该切片目的
- 如果验证失败后顺手去调整 `ErrorPanel` 或加载文案，本轮会从“加载占位共享化”扩大成 error/copy 主题

## 4. 实施原则

- 只改 `MarketIntelligence.jsx`
- 只做 `BlockMessage` 复用
- 不改 `MetricCard` / `SummaryCard`
- 不改 `ErrorPanel`
- 不改测试文件，除非出现由 `BlockMessage` adoption 直接导致的最小必要修正，并需先重新评估边界
- 若无法从相邻 diff 中安全隔离 `BlockMessage` adoption，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`

允许的逻辑：

- 引入 `BlockMessage`
- 删除本地 `BlockMessage` helper
- 保持两个加载态继续渲染 `BlockMessage`
- 保持两个加载态 `message` 字面量不变

明确不改：

- `MetricCard` import
- 本地 `SummaryCard`
- 四张统计卡区块
- `ErrorPanel`
- `neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx`
- 其他页面、共享组件、API 文件与文档

## 6. 总体分段

本计划建议分为四段执行：

- `MIB-R1`：冻结 `BlockMessage` adoption 的精确边界
- `MIB-R2`：只替换共享 `BlockMessage` 并删除本地 helper
- `MIB-R3`：做最小语法/结构安全验证
- `MIB-R4`：隔离 `BlockMessage` hunk 并提交

## 7. 分段实施计划

### MIB-R1：冻结 `BlockMessage` adoption 的精确边界

目标：

- 明确 `MarketIntelligence.jsx` 中哪些改动属于加载占位 shared-shell adoption，哪些相邻改动必须排除。

任务：

- 读取 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 当前 import 区、`BlockMessage` helper 区和相邻统计卡区块
- 对照 `HEAD` 检查剩余 diff
- 只标记以下目标点位：
  - `BlockMessage` import
  - 本地 `BlockMessage` helper 删除
  - 两个加载态消费点
- 显式排除：
  - `MetricCard` import / 消费点
  - 本地 `SummaryCard` 删除
  - `ErrorPanel`
  - 测试文件与其他页面

完成判定：

- include / exclude 列表明确
- `BlockMessage` 与 `MetricCard` / `SummaryCard` 的边界清楚分开

### MIB-R2：只替换共享 `BlockMessage` 并删除本地 helper

目标：

- 在不改变页面行为和加载文案语义的前提下，完成 `MarketIntelligence` 加载占位的共享壳层接入。

任务：

- 引入共享 `BlockMessage`
- 删除本地 `BlockMessage` helper
- 保持 `决策摘要加载中...` 与 `主线审阅加载中...` 不变
- 保持其余区块与请求行为不动

关键约束：

- 不调整加载文案
- 不调整 `fetchData`
- 不调整 `loading`
- 不修改 `ErrorPanel`
- 不修改统计卡、badge 或 value 语义

完成判定：

- `MarketIntelligence.jsx` 只消费共享 `BlockMessage`
- 页面其他区域和语义保持不变

### MIB-R3：做最小语法/结构安全验证

目标：

- 证明加载占位 shared-shell adoption 不引入语法或明显结构问题。

任务：

- 对最近编辑文件做最小语法/结构检查
- 运行 `npm test -- src/pages/MarketIntelligence.test.jsx`
- 若验证暴露的是 `MetricCard` 或 `SummaryCard` 相关问题，回到边界判断，不能自动扩大到统计卡主题

完成判定：

- `MarketIntelligence.jsx` 无明显语法或结构错误
- `MarketIntelligence.test.jsx` 通过

### MIB-R4：隔离 `BlockMessage` hunk 并提交

目标：

- 生成一个单一目的的 production commit，只表达 `MarketIntelligence` 的加载占位 shared-shell adoption。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- 只暂存 `BlockMessage` 对应 hunk
- 排除 `MetricCard` 与 `SummaryCard` 相邻 drift
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 `BlockMessage` adoption
- staged diff 不含 `MetricCard` 相关 hunk
- staged diff 不含 `SummaryCard` 相关 hunk
- staged diff 不含测试、文档或其他页面改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `MarketIntelligence.jsx` 当前 import、helper 区和统计卡区块
2. 对照 `HEAD` 切分 `BlockMessage` 与 `MetricCard` / `SummaryCard` 两类 drift
3. 只改加载占位点位
4. 跑 `MarketIntelligence.test.jsx`
5. 再检查 `HEAD`-relative diff
6. 只暂存 `BlockMessage` hunk

原因：

- 先切主题再改代码，可以避免把同文件里的统计卡主题一起带进提交
- 先跑当前页面测试，再决定是否能安全提交，能把风险控制在单文件、单消费面范围内

## 9. 建议提交切分

建议单一提交：

### Commit MIB：MarketIntelligence BlockMessage adoption

范围：

- 仅 `MarketIntelligence.jsx` 中 `BlockMessage` 的复用 hunk

目的：

- 让 `MarketIntelligence` 的加载占位接入当前已存在的共享占位体系

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 `BlockMessage + MetricCard` 的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `MarketIntelligence.jsx` 使用共享 `BlockMessage`
2. `MarketIntelligence.jsx` 不再保留本地 `BlockMessage` helper
3. 两个加载态 message 保持不变
4. `MarketIntelligence.test.jsx` 通过
5. 不修改 `MarketIntelligence.test.jsx`
6. 提交中不包含 `MetricCard` 相关改动
7. 提交中不包含 `SummaryCard` 相关改动

## 11. 风险提示

- 最大风险是从 `MarketIntelligence.jsx` 的混合 diff 中误带入 `MetricCard` / `SummaryCard`
- 第二风险是测试一旦失败，就把问题误判成“需要一起收口统计卡”
- 第三风险是共享 `BlockMessage` adoption 与现有 error/loading 结构在同一文件里较近，隔离时需要更严格地比对 `HEAD`

## 12. 结论

本计划的核心不是“统一整个 `MarketIntelligence` 页面”，而是先做一条可独立解释的加载占位 shared-shell 线：

- 只复用 `BlockMessage`
- 只删除本地 `BlockMessage` helper
- 只在相对 `HEAD` 能保持原子性的前提下提交

这样后续 `MetricCard` / `SummaryCard` 收口仍可以作为下一条独立切片继续推进。
