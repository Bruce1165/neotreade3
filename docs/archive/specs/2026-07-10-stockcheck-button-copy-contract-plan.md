# StockCheck Button Copy Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-stockcheck-button-copy-contract-design.md`

## 1. 目标

本计划只覆盖 `StockCheck` 页面的按钮 copy contract 收口，不扩展到 `STATUS_COPY`、debug 标题、共享壳层或 API 行为。

本轮目标只有三个：

1. 将搜索按钮静态文案统一为 `开始核验`。
2. 将按钮 loading 文案统一为 `核验中...`。
3. 将 `StockCheck.test.jsx` 中对应按钮断言同步到同一 contract。

本轮必须得到的核心结果：

- `StockCheck.jsx` 中按钮空闲态文案为 `开始核验`
- `StockCheck.jsx` 中按钮 loading 态文案为 `核验中...`
- `StockCheck.test.jsx` 使用相同按钮名称断言
- 提交中不包含 `STATUS_COPY` 相关文案
- 提交中不包含 `PageHeader`、`BlockMessage` 或其他结构性改动

## 2. 不在本轮完成

- `STATUS_COPY.actionable / observing / followerObserving`
- `STATUS_COPY.debugData`
- 热门板块 badge label
- debug 折叠标题
- `PageHeader`
- `BlockMessage`
- `fetchApi` 调用
- `handleCheck` 逻辑
- 结果区与输入区结构调整
- 其他页面测试或全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前剩余 drift 同时包含两类主题：
  - 按钮 copy contract：`开始核验`、`核验中...`
  - `STATUS_COPY` contract：badge label、debug 标题
- [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 当前直接查询按钮名称，因此是本轮最直接的 focused carrier
- `StockCheck` 的 shared-shell adoption 已经作为独立切片提交，本轮不需要再触碰 `PageHeader` 或 `BlockMessage`

### 3.2 结构性风险

- 最大风险不是按钮文案修改本身，而是从同一文件的混合 diff 中误带入 `STATUS_COPY` 相关改动
- 如果只改生产文案不改测试断言，按钮 contract 会在生产与测试之间失配
- 如果顺手修改 debug 标题、badge 或结果区 copy，本轮就会从“按钮 contract”扩大成“页面 copy 清理”

## 4. 实施原则

- 只改 `StockCheck.jsx` 与 `StockCheck.test.jsx`
- 只做按钮 copy contract 收口
- 不改 `STATUS_COPY`
- 不改共享壳层
- 不改 API 与交互逻辑
- 若验证暴露的是 `STATUS_COPY` 或其他页面 copy 问题，应暂停并报告边界问题，不能静默扩大范围
- 若相对 `HEAD` 无法安全隔离按钮相关 hunk，本轮结论应是“不提交”，而不是扩大提交范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`

允许改动逻辑：

- 按钮静态文案：`检查` -> `开始核验`
- 按钮 loading 文案：`检查中...` -> `核验中...`
- 对应测试按钮查询断言同步到 `开始核验`

明确不改：

- `STATUS_COPY.actionable / observing / followerObserving`
- `STATUS_COPY.debugData`
- 热门板块 badge 的 `semanticKey` 与 `label`
- debug 折叠区 `<summary>`
- `PageHeader`
- `BlockMessage`
- `fetchApi`
- 搜索逻辑和请求参数
- 结果区渲染结构

## 6. 总体分段

本计划建议分为四段执行：

- `SCB-R1`：冻结按钮 contract 的精确边界
- `SCB-R2`：只实施按钮 copy 与对应测试断言
- `SCB-R3`：跑最小验证并检查语法/结构安全
- `SCB-R4`：隔离 button-copy hunk 并提交

## 7. 分段实施计划

### SCB-R1：冻结按钮 contract 的精确边界

目标：

- 明确 `StockCheck.jsx` 和 `StockCheck.test.jsx` 中哪些点位属于本轮按钮 contract，哪些相邻改动必须排除。

任务：

- 读取 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前按钮区块
- 读取 [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 当前按钮查询断言
- 对照 `HEAD` 检查当前剩余 diff
- 只标记以下目标点位：
  - 按钮空闲态文本
  - 按钮 loading 文本
  - 对应 `getByRole('button', { name: ... })` 断言
- 显式排除：
  - `STATUS_COPY` badge
  - `STATUS_COPY.debugData`
  - `PageHeader`
  - `BlockMessage`
  - 结果区其他 copy

完成判定：

- include / exclude 列表明确
- 按钮 contract 与 `STATUS_COPY` 相邻 drift 已清楚分开

### SCB-R2：只实施按钮 copy 与对应测试断言

目标：

- 在不改变业务逻辑和页面结构的前提下，完成按钮文案 contract 的生产与测试同步。

任务：

- 将按钮静态文本改为 `开始核验`
- 将按钮 loading 文本改为 `核验中...`
- 将测试中的按钮查询断言同步到 `开始核验`

关键约束：

- 不调整按钮触发逻辑
- 不调整按钮禁用条件
- 不引入 `STATUS_COPY`
- 不修改结果区、badge 或 debug 区文案

完成判定：

- 生产与测试按钮名称 contract 对齐
- 页面结构与交互逻辑保持不变

### SCB-R3：跑最小验证并检查语法/结构安全

目标：

- 证明本轮只影响按钮文案 contract，不影响 `StockCheck` 既有核验流程。

任务：

- 运行 `npm test -- src/pages/StockCheck.test.jsx`
- 检查最近编辑文件是否存在明显语法或结构问题
- 对最近编辑文件执行诊断检查
- 若失败原因来自 `STATUS_COPY` 或其他相邻 drift，则停止并报告边界问题

完成判定：

- `StockCheck.test.jsx` 通过
- 最近编辑文件无明显语法或结构错误

### SCB-R4：隔离 button-copy hunk 并提交

目标：

- 生成一个单一目的的切片，只表达 `StockCheck` 的按钮 copy contract 收口。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.jsx`
- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- 只暂存按钮文案与对应测试断言 hunk
- 排除 `STATUS_COPY`、debug 标题与其他相邻 drift
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含按钮 copy contract
- 提交中不包含 `STATUS_COPY` 相关改动
- 提交中不包含 shared-shell 或结构性改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `StockCheck.jsx` 按钮区块与 `StockCheck.test.jsx` 按钮断言
2. 对照 `HEAD` 切分 button copy 与 `STATUS_COPY` 两类 drift
3. 只改按钮 contract 点位
4. 跑 `StockCheck.test.jsx`
5. 检查最近编辑文件诊断
6. 再检查 `HEAD`-relative diff
7. 只暂存 button-copy hunk

原因：

- 先切主题再改代码，可以避免把同文件中的 `STATUS_COPY` 相邻改动一起带进提交
- 先验证 focused carrier，再决定是否提交，可以把边界失真风险控制在最小范围

## 9. 建议提交切分

建议单一提交：

### Commit SCB：StockCheck button copy contract

范围：

- `StockCheck.jsx` 中按钮静态文案与 loading 文案的最小 hunk
- `StockCheck.test.jsx` 中对应按钮断言的最小 hunk

目的：

- 让 `StockCheck` 的入口按钮 copy 在生产与测试之间使用同一 contract

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成按钮 + `STATUS_COPY` 的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `StockCheck.jsx` 按钮空闲态文案为 `开始核验`
2. `StockCheck.jsx` 按钮 loading 文案为 `核验中...`
3. `StockCheck.test.jsx` 对应按钮断言通过
4. `StockCheck.test.jsx` 全部通过
5. 提交中不包含 `STATUS_COPY` badge 或 debug 标题变更
6. 提交中不包含 shared-shell 或 API 逻辑改动

## 11. 风险提示

- 主要风险是 `StockCheck.jsx` 当前剩余 diff 混有 `STATUS_COPY` 相关改动，隔离时必须逐 hunk 对照 `HEAD`
- 第二风险是测试若失败，容易误判为“顺手一起收口其他 copy”
- 第三风险是同一按钮附近若存在格式整理差异，容易在暂存时误带入无关 hunk

## 12. 结论

本计划不是 `StockCheck` 整页 copy 清理计划，而是一条更窄的 contract 线，目标只有三件事：

- 只统一按钮静态文案
- 只统一按钮 loading 文案
- 只同步对应测试断言，并仅在相对 `HEAD` 可安全隔离时提交
