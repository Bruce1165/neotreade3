# StockCheck Header Subtitle Copy Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-stockcheck-header-subtitle-copy-contract-design.md`

## 1. 目标

本计划只覆盖 `StockCheck` 页面的 `PageHeader.subtitle` copy contract 收口，不扩展到 import 整洁性、badge 状态契约、按钮文案、debug summary 或 API 行为。

本轮目标只有三个：

1. 将页头 subtitle 从旧版分隔写法统一为当前页面文案合同。
2. 在不扩大测试范围的前提下，为该单点 header copy contract 提供最小测试承接。
3. 仅在相对 `HEAD` 能隔离该单点 contract 时提交。

本轮必须得到的核心结果：

- `StockCheck.jsx` 中 `PageHeader.subtitle` 使用 `输入股票代码，核验筛选器、热门板块、形态与确定性`
- `StockCheck.test.jsx` 对应页面渲染用例承接该 subtitle 文案
- 提交中不包含 `AlertCircle` import 清理
- 提交中不包含 badge、按钮或 debug summary contract 变更

## 2. 不在本轮完成

- `AlertCircle` import 清理
- `STATUS_COPY.*`
- 热门板块 badge contract
- 搜索按钮文案
- debug `<summary>`
- `fetchApi` 调用
- 结果区结构或渲染逻辑
- `PageHeader` 组件本身
- 其他页面测试或全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前剩余 drift 已缩到两类：
  - `PageHeader.subtitle`
  - `AlertCircle` import
- 当前 subtitle 的目标差异明确：
  - `输入股票代码，核验筛选器 / 热门板块 / 老鸭头 / 确定性`
  - `输入股票代码，核验筛选器、热门板块、形态与确定性`
- [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 已覆盖页面主路径，但还没有直接断言 subtitle 文案
- `StockCheck` 的 shared-shell adoption、button copy contract、hot-sector badge status contract、debug summary copy contract 已分别独立提交

### 3.2 结构性风险

- 最大风险不是 subtitle 替换本身，而是从同一文件的混合 diff 中误带入 `AlertCircle` import 清理
- 如果完全不补测试承接，本轮会形成一个无显式验证的用户可见 copy contract
- 如果顺手改 title、按钮或结果区文案，本轮就会从“header subtitle copy contract”扩大成“整页 copy 清理”

## 4. 实施原则

- 只改 `StockCheck.jsx` 与 `StockCheck.test.jsx`
- 只做 `PageHeader.subtitle` copy contract 收口
- 不改 `PageHeader` 组件本身
- 不改 `statusCopy.js`
- 不改 badge contract
- 不改按钮 contract
- 不改 debug summary contract
- 不改 API 与交互逻辑
- 若验证暴露的是 import、其他 copy 或结构问题，应暂停并报告边界问题，不能静默扩大范围
- 若相对 `HEAD` 无法安全隔离 subtitle 相关 hunk，本轮结论应是“不提交”，而不是扩大提交范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`

允许改动逻辑：

- `PageHeader.subtitle`：
  - `输入股票代码，核验筛选器 / 热门板块 / 老鸭头 / 确定性`
  - `输入股票代码，核验筛选器、热门板块、形态与确定性`
- 在现有页面渲染用例中增加一条 subtitle 文案断言

明确不改：

- `AlertCircle` import
- `STATUS_COPY.*`
- 热门板块 badge 的 `semanticKey` 与 `label`
- 搜索按钮文案
- debug `<summary>`
- `fetchApi`
- 搜索逻辑和请求参数
- 结果区渲染结构
- 页头 title

## 6. 总体分段

本计划建议分为四段执行：

- `SCS-R1`：冻结 subtitle contract 的精确边界
- `SCS-R2`：只实施 subtitle 文案与最小测试断言
- `SCS-R3`：跑最小验证并检查语法/结构安全
- `SCS-R4`：隔离 subtitle hunk 并提交

## 7. 分段实施计划

### SCS-R1：冻结 subtitle contract 的精确边界

目标：

- 明确 `StockCheck.jsx` 和 `StockCheck.test.jsx` 中哪些点位属于本轮 subtitle contract，哪些相邻改动必须排除。

任务：

- 读取 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前 `PageHeader` 区块
- 读取 [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 当前页面渲染断言
- 对照 `HEAD` 检查当前剩余 diff
- 只标记以下目标点位：
  - `PageHeader.subtitle`
  - 对应最小测试断言
- 显式排除：
  - `AlertCircle` import
  - badge contract
  - 搜索按钮 copy
  - debug summary

完成判定：

- include / exclude 列表明确
- subtitle 与 `AlertCircle` import 两类 drift 已清楚分开

### SCS-R2：只实施 subtitle 文案与最小测试断言

目标：

- 在不改变业务逻辑和页面结构的前提下，完成 header subtitle 的生产与测试同步。

任务：

- 将 `PageHeader.subtitle` 改为 `输入股票代码，核验筛选器、热门板块、形态与确定性`
- 在现有页面渲染用例中补一条对应 subtitle 断言

关键约束：

- 不调整 `PageHeader.title`
- 不修改按钮文案
- 不修改 badge contract
- 不修改 debug summary
- 不调整 API 请求和结果渲染逻辑

完成判定：

- 生产 subtitle 文案收口到目标合同
- 测试对该文案有最小承接

### SCS-R3：跑最小验证并检查语法/结构安全

目标：

- 证明本轮只影响 header subtitle copy contract，不影响 `StockCheck` 既有核验路径。

任务：

- 运行 `npm test -- src/pages/StockCheck.test.jsx`
- 检查最近编辑文件是否存在明显语法或结构问题
- 若失败原因来自 import、其他 copy 或相邻 drift，则停止并报告边界问题

完成判定：

- `StockCheck.test.jsx` 通过
- 最近编辑文件无明显语法或结构错误

### SCS-R4：隔离 subtitle hunk 并提交

目标：

- 生成一个单一目的的切片，只表达 `StockCheck` 的 header subtitle copy contract 收口。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.jsx`
- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- 只暂存 subtitle 与对应测试断言 hunk
- 排除 `AlertCircle` 与其他相邻 drift
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 subtitle copy contract
- 提交中不包含 import 清理
- 提交中不包含 badge、按钮或 debug summary 改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `StockCheck.jsx` 的 `PageHeader` 区块与 `StockCheck.test.jsx` 现有页面断言
2. 对照 `HEAD` 切分 subtitle 与 `AlertCircle` import 两类 drift
3. 只改 subtitle contract 点位
4. 跑 `StockCheck.test.jsx`
5. 再检查 `HEAD`-relative diff
6. 只暂存 subtitle hunk

原因：

- 先切主题再改代码，可以避免把同文件中的 import 相邻改动一起带进提交
- 先验证现有 carrier，再决定是否提交，可以把边界失真风险控制在最小范围

## 9. 建议提交切分

建议单一提交：

### Commit SCS：StockCheck header subtitle copy contract

范围：

- `StockCheck.jsx` 中 `PageHeader.subtitle` 的最小 hunk
- `StockCheck.test.jsx` 中对应断言的最小 hunk

目的：

- 让 `StockCheck` 页头说明与当前页面 copy contract 保持一致

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 subtitle + import cleanup 的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `StockCheck.jsx` 页头 subtitle 为 `输入股票代码，核验筛选器、热门板块、形态与确定性`
2. `StockCheck.test.jsx` 对应文案断言通过
3. `StockCheck.test.jsx` 全部通过
4. 提交中不包含 `AlertCircle` import 清理
5. 提交中不包含 badge、按钮或 debug summary contract 变更

## 11. 风险提示

- 主要风险是 `StockCheck.jsx` 当前剩余 diff 中仍有 `AlertCircle` import，相邻隔离时必须逐 hunk 对照 `HEAD`
- 第二风险是若不补最小断言，这条用户可见 subtitle contract 在回归时缺少显式保护
- 第三风险是若为了减少剩余 diff 一次性带入 import 清理或其他 copy，本轮提交目的会失真

## 12. 结论

本计划不是 `StockCheck` 整页收口计划，而是一条更窄的单点 contract 线，目标只有三件事：

- 只统一 `PageHeader.subtitle`
- 只补现有 carrier 上的最小测试断言
- 只在相对 `HEAD` 可安全隔离时提交
