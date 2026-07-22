# App Unused Import Cleanup 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-app-unused-import-cleanup-design.md`

## 1. 目标

本计划只覆盖 `App.jsx` 中未使用的 `Filter` / `Search` import 清理，不扩展到路由结构、导航 IA、页面 wiring、样式或交互调整。

本轮目标只有三个：

1. 从 `App.jsx` 的 `lucide-react` import 行中移除未被消费的 `Filter` 与 `Search`。
2. 在不扩大测试范围的前提下，完成最小语法/结构安全验证。
3. 仅在相对 `HEAD` 能隔离该单点 cleanup 时提交。

本轮必须得到的核心结果：

- `App.jsx` 中 icon import 不再包含 `Filter` 与 `Search`
- 提交中不包含 `Route path="*"` 的缩进变化
- 提交中不包含路由、导航或其他文件改动

## 2. 不在本轮完成

- 路由兜底 contract
- 导航 IA 调整
- 页面 import / wiring
- `MarketIntelligence` / `Overview` / `vite.config.js`
- `Route path="*"` 行缩进变化
- 新增测试文件或断言
- 全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 当前相对 `HEAD` 的剩余漂移有两类：
  - 未使用 import 删除：`Filter`、`Search`
  - `Route path="*"` 行缩进变化
- 当前 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx#L1-L8) 中 `lucide-react` import 不再包含 `Filter` / `Search` 的实际消费场景
- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx#L263-L271) 的通配符路由结构与既有逻辑一致，当前差异仅表现为缩进

### 3.2 结构性风险

- 最大风险不是删除未使用 import 本身，而是把缩进噪音一起带入提交
- 如果顺手改动路由顺序、导航项或页面 wiring，本轮会从“整洁性清理”扩大成混合主题
- 如果为这条 import cleanup 增补无关测试，本轮会从 cleanup 扩大成测试主题

## 4. 实施原则

- 只改 `App.jsx`
- 只做 `Filter` / `Search` import cleanup
- 不改 JSX 结构
- 不改 `Route path="*"` 缩进
- 不改页面或配置文件
- 若验证暴露的是路由、页面或配置主题问题，应暂停并报告边界问题，不能静默扩大范围
- 若相对 `HEAD` 无法安全隔离 import cleanup hunk，本轮结论应是“不提交”，而不是扩大提交范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/src/App.jsx`

允许改动逻辑：

- `lucide-react` import 行：
  - 删除 `Filter`
  - 删除 `Search`

明确不改：

- `Route path="*"` 行缩进
- 路由定义顺序
- `navItems`
- 页面 import
- `neotrade3-dashboard/src/pages/*`
- `neotrade3-dashboard/vite.config.js`

## 6. 总体分段

本计划建议分为四段执行：

- `SAI-R1`：冻结 import cleanup 的精确边界
- `SAI-R2`：只实施未使用 import 删除
- `SAI-R3`：做最小语法/结构安全验证
- `SAI-R4`：隔离 import cleanup hunk 并提交

## 7. 分段实施计划

### SAI-R1：冻结 import cleanup 的精确边界

目标：

- 明确 `App.jsx` 中哪些点位属于本轮 import cleanup，哪些相邻改动必须排除。

任务：

- 读取 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 当前 import 区块
- 用 `git diff HEAD -- neotrade3-dashboard/src/App.jsx` 检查当前剩余 diff
- 只标记以下目标点位：
  - `Filter` import
  - `Search` import
- 显式排除：
  - `Route path="*"` 行缩进
  - 路由与导航结构
  - 页面 wiring

完成判定：

- include / exclude 列表明确
- `HEAD`-relative diff 中 import cleanup 与缩进噪音已清楚分开

### SAI-R2：只实施未使用 import 删除

目标：

- 在不改变壳层行为和结构的前提下，完成 `Filter` / `Search` import 清理。

任务：

- 从 `lucide-react` import 列表中移除 `Filter`
- 从 `lucide-react` import 列表中移除 `Search`

关键约束：

- 不修改任何 JSX
- 不修改通配符路由行缩进
- 不修改测试文件
- 不调整路由、导航或页面接线

完成判定：

- `App.jsx` import 不再包含 `Filter` / `Search`
- 生产代码其他区域无改动

### SAI-R3：做最小语法/结构安全验证

目标：

- 证明本轮只影响 import cleanup，不影响 `App` 壳层的语法与结构安全。

任务：

- 检查最近编辑文件是否存在明显语法或结构问题
- 如有必要，再运行最小前端验证
- 若失败原因来自缩进噪音、路由或页面主题，则停止并报告边界问题

完成判定：

- `App.jsx` 无明显语法或结构错误
- 未引入额外边界外修改

### SAI-R4：隔离 import cleanup hunk 并提交

目标：

- 生成一个单一目的的切片，只表达 `App.jsx` 的未使用 import 清理。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/App.jsx`
- 只暂存 import cleanup 的最小 hunk
- 排除 `Route path="*"` 行缩进变化
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 `Filter` / `Search` import 删除
- 提交中不包含缩进噪音
- 提交中不包含其他文件改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `App.jsx` import 区块并对照 `HEAD`
2. 确认 `HEAD`-relative diff 里 import cleanup 与缩进噪音的分界
3. 只改 import 行
4. 做最小语法/结构检查
5. 再检查 `HEAD`-relative diff
6. 只暂存 import cleanup hunk

原因：

- 先切主题再改代码，可以避免把缩进噪音一起带进提交
- 先确认结构安全，再决定是否提交，可以把边界失真风险控制在最小范围

## 9. 建议提交切分

建议单一提交：

### Commit SAI：App unused import cleanup

范围：

- `App.jsx` 中 `Filter` / `Search` import 删除的最小 hunk

目的：

- 移除 `App` 壳层中未使用的 icon 依赖

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 import cleanup + formatting 的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `App.jsx` import 不再包含 `Filter` / `Search`
2. `App.jsx` 无明显语法或结构错误
3. 提交中不包含 `Route path="*"` 行缩进变化
4. 提交中不包含路由、导航、页面或配置改动

## 11. 风险提示

- 主要风险是 `App.jsx` 当前 diff 中混有通配符路由缩进噪音，隔离时必须逐 hunk 对照 `HEAD`
- 第二风险是若顺手改动路由或导航，本轮提交目的会失真
- 第三风险是若为了“顺便整理”而混入其他文件，本轮会失去单点 cleanup 边界

## 12. 结论

本计划不是 `App` 壳层整理计划，而是一条更窄的单点 cleanup 线，目标只有三件事：

- 只删除未使用的 `Filter` / `Search` import
- 只做最小语法/结构安全验证
- 只在相对 `HEAD` 可安全隔离时提交
