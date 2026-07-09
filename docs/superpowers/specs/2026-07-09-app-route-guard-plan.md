# App 未知路径与缺参路由保护实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-app-route-guard-design.md`

## 1. 目标

本计划只覆盖 `App` 路由层的未知路径与缺参路径保护落地，不扩展到详情页组件逻辑、导航 IA 调整或其他页面主题线。

本轮目标只有三个：

1. 为 `App` 增加最小的未知路径兜底。
2. 让 `/lowfreq/backtest-reports/` 这类缺少必要路径参数的详情路径，同样得到明确兜底。
3. 用独立测试载体为这条入口保护线建立回归验证。

本轮必须产出的核心结果：

- 未知路径不会落入“壳层存在但主内容空白”的状态
- 缺参详情路径有明确兜底结果
- 提交中不包含 `LowfreqBacktestReport` 页面逻辑与 IA 主题线

## 2. 不在本轮完成

- `LowfreqBacktestReport.jsx` 页面逻辑修改
- `LowfreqBacktestReport.test.jsx`
- `/screeners`、`/stock-check` IA 策略
- 侧边栏结构改造
- 导航激活态调整
- 404 页面视觉升级

## 3. 当前实施起点

### 3.1 已有现实基础

- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 已注册多条明确路由：
  - `/`
  - `/ops`
  - `/market-intelligence`
  - `/screeners`
  - `/stock-check`
  - `/lowfreq`
  - `/lowfreq/backtest-reports/:reportId`
- 当前 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 没有 `*` 兜底路由
- 当前 App 级测试已存在：
  - [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)
  - [App.opsCenterRoute.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.opsCenterRoute.test.jsx)
  - [App.lowfreqBacktestReportRoute.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.lowfreqBacktestReportRoute.test.jsx)
- [LowfreqBacktestReport.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx) 内部已有 `reportId` 缺失处理，但属于组件级保护

### 3.2 当前结构性风险

- 当前最大风险在 App 路由入口层，而不是详情页组件内部
- 若继续依赖组件级缺参保护，真实异常路径仍可能在 App 层表现为空白主区域
- 若直接把问题改成重定向或 IA 调整，会把本刀从“入口保护”扩大成“导航策略改造”

## 4. 实施原则

- 只处理 App 路由层的最小兜底语义
- 采用统一 404 占位，而非静默重定向
- 优先新增独立测试文件，不扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)
- 不修改 [LowfreqBacktestReport.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx)
- 若实现需要扩大到 IA 或页面逻辑，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/App.routeGuard.test.jsx`

建议只包含以下逻辑：

- 增加 `*` 路由最小兜底
- 提供最小“页面不存在/路径无效”占位
- 新增独立 App 级测试，覆盖未知路径与缺参路径

明确不改：

- `neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx`
- `neotrade3-dashboard/src/pages/LowfreqBacktestReport.test.jsx`
- `neotrade3-dashboard/src/App.test.jsx`
- `neotrade3-dashboard/src/App.lowfreqBacktestReportRoute.test.jsx`
- 其他页面文件

## 6. 总体分段

本计划建议分为四段执行：

- `P0-R1`：冻结路由保护切片边界
- `P0-R2`：在 `App.jsx` 增加最小兜底
- `P0-R3`：新增独立路由保护测试载体
- `P0-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### P0-R1：冻结路由保护切片边界

目标：

- 在动手前确认未知路径与缺参路径的统一语义，以及哪些主题线必须排除。

任务：

- 审计 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 当前路由集合
- 确认采用统一 404 占位语义
- 审计现有 App 级路由测试，避免重复扩写
- 记录必须排除的 IA、详情页组件和其他页面主题线

完成判定：

- 已形成明确的 include / exclude 清单
- 路由保护语义已经固定

### P0-R2：在 `App.jsx` 增加最小兜底

目标：

- 让 App 对未知路径和缺参路径给出明确入口保护结果。

任务：

- 在 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 中增加最小 404 占位
- 增加 `*` 路由作为兜底
- 保持现有明确路由不变

关键约束：

- 不调整侧边栏
- 不改详情页组件逻辑
- 不扩展为完整 NotFound 页面系统

完成判定：

- 未知路径进入 App 时有明确占位
- 缺参详情路径同样进入统一兜底

### P0-R3：新增独立路由保护测试载体

目标：

- 为 App 路由保护补上一层独立回归验证。

任务：

- 新增 `App.routeGuard.test.jsx`
- mock 现有页面为最小占位
- 用独立用例覆盖：
  - 未知路径进入 App 时显示兜底内容
  - `/lowfreq/backtest-reports/` 缺参路径进入 App 时显示同样的兜底内容
- 断言 App 壳层基础结构仍存在

关键约束：

- 不复验详情页组件内部错误态
- 不加入导航激活态断言
- 不扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)

完成判定：

- 新测试文件可以独立保护路由入口 contract

### P0-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `App.routeGuard.test.jsx`
- 如触及 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx)，补跑相关独立 App 路由测试
- 检查暂存区 diff，只保留：
  - `App.jsx` 中最小兜底 hunk
  - `App.routeGuard.test.jsx`
- 提交前确认不带入 IA 或其他页面主题线

完成判定：

- 测试通过
- 提交边界干净
- 本刀仍然是“路由保护”，不是“App 改版”

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先确认路由保护语义与排除边界
2. 再在 `App.jsx` 中增加最小兜底
3. 然后新增 `App.routeGuard.test.jsx`
4. 最后做验证、精确暂存与提交

原因：

- 先定语义，再写实现，能避免临时把 404 与重定向混用
- 先稳定 `App.jsx` 的入口语义，再写测试，断言对象更清晰
- 把边界检查放到最后，可最大限度避免把 IA 漂移带入

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit P0：App 路由保护

范围：

- `App.jsx` 中最小 404 兜底 hunk
- `App.routeGuard.test.jsx`

目标：

- 为未知路径与缺参路径建立统一入口保护

如果该提交无法与 IA 或其他页面主题线安全分离，则应停止实现并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 未知路径进入 App 时有明确兜底内容
2. `/lowfreq/backtest-reports/` 缺参路径同样有明确兜底内容
3. 使用独立测试载体，不扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)
4. 提交中不包含 [LowfreqBacktestReport.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx) 改动
5. 提交中不包含 IA 调整或其他页面主题线

## 11. 风险提示

- 当前最大风险不是实现难度，而是容易把路由保护顺手扩成 IA 策略调整
- 若改成静默重定向，会削弱错误路径的诊断语义
- 若把详情页组件级错误态一并纳入，会破坏这条线的原子性

## 12. 结论

本计划的核心不是“补一个 404 页面”，而是：

- 给 App 路由层加上明确的未知路径与缺参路径保护
- 保持测试文件物理独立
- 不触碰详情页组件本体

只有这样，后续更宽的导航 IA、详情页链路和入口策略，才能继续保持原子化推进。
