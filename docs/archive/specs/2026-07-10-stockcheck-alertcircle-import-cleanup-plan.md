# StockCheck AlertCircle Import Cleanup 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-stockcheck-alertcircle-import-cleanup-design.md`

## 1. 目标

本计划只覆盖 `StockCheck` 页面中未使用的 `AlertCircle` import 清理，不扩展到页面文案、状态契约、API 行为、结构或交互调整。

本轮目标只有三个：

1. 从 `StockCheck.jsx` import 行中移除未被消费的 `AlertCircle`。
2. 在不扩大测试范围的前提下，用现有 focused test 证明本轮没有引入行为回归。
3. 仅在相对 `HEAD` 能隔离该单点 cleanup 时提交。

本轮必须得到的核心结果：

- `StockCheck.jsx` 中 icon import 不再包含 `AlertCircle`
- `StockCheck.test.jsx` 继续通过，证明页面主路径未被影响
- 提交中不包含 subtitle、按钮、badge、debug summary 或 API 相关变更

## 2. 不在本轮完成

- `PageHeader.subtitle` copy contract
- `STATUS_COPY.*`
- 热门板块 badge contract
- 搜索按钮文案
- debug `<summary>`
- `fetchApi` 调用
- 结果区结构或渲染逻辑
- `StockCheck.test.jsx` 内容改动
- 其他页面测试或全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前相对 `HEAD` 的剩余 drift 只剩 import 行：
  - `Search, AlertCircle, TrendingUp, Layers, Target`
- `AlertCircle` 在 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 中只出现一次，即 import 语句
- [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 已能回归页面主路径，本轮无需新增断言
- `StockCheck` 的 shared-shell adoption、button copy contract、badge status contract、debug summary copy contract、header subtitle copy contract 已分别独立提交

### 3.2 结构性风险

- 最大风险不是删除未使用 import 本身，而是从同一文件的剩余 drift 中误带入其他 JSX、文案或逻辑改动
- 如果为 import cleanup 顺手调整测试或结构，本轮会从“整洁性清理”扩大成混合主题
- 如果不复用现有 focused test 做最小回归验证，本轮虽然是 cleanup，但仍缺少执行证据

## 4. 实施原则

- 只改 `StockCheck.jsx`
- 只做 `AlertCircle` import cleanup
- 不改 `StockCheck.test.jsx`
- 不改 JSX、文案、状态契约与 API
- 若验证暴露的是其他 copy、结构或逻辑问题，应暂停并报告边界问题，不能静默扩大范围
- 若相对 `HEAD` 无法安全隔离 import cleanup 相关 hunk，本轮结论应是“不提交”，而不是扩大提交范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/src/pages/StockCheck.jsx`

允许改动逻辑：

- import 行：
  - `Search, AlertCircle, TrendingUp, Layers, Target`
  - `Search, TrendingUp, Layers, Target`

明确不改：

- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- `STATUS_COPY.*`
- `PageHeader` title / subtitle
- 热门板块 badge 的 `semanticKey` 与 `label`
- 搜索按钮文案
- debug `<summary>`
- `fetchApi`
- 搜索逻辑和请求参数
- 结果区渲染结构

## 6. 总体分段

本计划建议分为四段执行：

- `SCI-R1`：冻结 import cleanup 的精确边界
- `SCI-R2`：只实施未使用 import 删除
- `SCI-R3`：跑最小验证并检查语法/结构安全
- `SCI-R4`：隔离 import cleanup hunk 并提交

## 7. 分段实施计划

### SCI-R1：冻结 import cleanup 的精确边界

目标：

- 明确 `StockCheck.jsx` 中哪些点位属于本轮 import cleanup，哪些相邻改动必须排除。

任务：

- 读取 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前 import 区块
- 用 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.jsx` 检查当前剩余 diff
- 只标记以下目标点位：
  - `AlertCircle` import
- 显式排除：
  - JSX 内容
  - subtitle、按钮、badge、debug summary
  - API 与结构逻辑

完成判定：

- include / exclude 列表明确
- `HEAD`-relative diff 确认只剩 import 主题

### SCI-R2：只实施未使用 import 删除

目标：

- 在不改变页面行为和结构的前提下，完成 `AlertCircle` import 清理。

任务：

- 从 `lucide-react` import 列表中移除 `AlertCircle`

关键约束：

- 不修改任何 JSX
- 不替换其他 icon
- 不修改测试文件
- 不调整页面文案和 API 逻辑

完成判定：

- `StockCheck.jsx` import 不再包含 `AlertCircle`
- 生产代码其他区域无改动

### SCI-R3：跑最小验证并检查语法/结构安全

目标：

- 证明本轮只影响 import cleanup，不影响 `StockCheck` 既有主路径。

任务：

- 运行 `npm test -- src/pages/StockCheck.test.jsx`
- 检查最近编辑文件是否存在明显语法或结构问题
- 若失败原因来自其他漂移或无关主题，则停止并报告边界问题

完成判定：

- `StockCheck.test.jsx` 通过
- 最近编辑文件无明显语法或结构错误

### SCI-R4：隔离 import cleanup hunk 并提交

目标：

- 生成一个单一目的的切片，只表达 `StockCheck` 的未使用 import 清理。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.jsx`
- 只暂存 import cleanup 的最小 hunk
- 排除其他无关改动
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 import cleanup
- 提交中不包含测试改动
- 提交中不包含 subtitle、按钮、badge、debug summary 或 API 改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `StockCheck.jsx` import 区块并对照 `HEAD`
2. 确认相对 `HEAD` 只剩 import cleanup 主题
3. 只改 import 行
4. 跑 `StockCheck.test.jsx`
5. 再检查 `HEAD`-relative diff
6. 只暂存 import cleanup hunk

原因：

- 先确认主题纯度，再改代码，可以避免把 cleanup 扩大成同文件整理
- 先验证现有 carrier，再决定是否提交，可以把边界失真风险控制在最小范围

## 9. 建议提交切分

建议单一提交：

### Commit SCI：StockCheck AlertCircle import cleanup

范围：

- `StockCheck.jsx` import 行的最小 hunk

目的：

- 移除 `StockCheck` 页面中未使用的 `AlertCircle` 依赖

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 import cleanup + 结构整理的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `StockCheck.jsx` import 不再包含 `AlertCircle`
2. `StockCheck.test.jsx` 全部通过
3. 提交中不包含测试改动
4. 提交中不包含 subtitle、按钮、badge、debug summary 或 API 相关变更

## 11. 风险提示

- 主要风险是若顺手改动同文件其他内容，会把单点 cleanup 扩成混合主题
- 第二风险是若不跑最小验证，cleanup 提交缺少执行证据
- 第三风险是若为了“顺便收口”而补改测试或页面结构，本轮提交目的会失真

## 12. 结论

本计划不是 `StockCheck` 整页整理计划，而是一条更窄的单点 cleanup 线，目标只有三件事：

- 只删除未使用的 `AlertCircle` import
- 只复用现有 focused test 做最小回归验证
- 只在相对 `HEAD` 可安全隔离时提交
