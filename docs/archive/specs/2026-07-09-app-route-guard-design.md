# App 未知路径与缺参路由保护设计

日期：2026-07-09

## 1. 目标

本切片只解决一个问题：

为 `App` 路由层补上一层最小入口保护，使未知路径以及缺少必要路径参数的详情路径，不会落入“壳层存在但主内容空白”的状态。

本切片的目标不是改造页面逻辑，也不是扩大 App 信息架构，而是补齐路由入口兜底 contract。

## 2. 范围

包含：

- `neotrade3-dashboard/src/App.jsx` 中与路由兜底直接相关的最小改动
- 一个新的独立测试文件，例如 `neotrade3-dashboard/src/App.routeGuard.test.jsx`

不包含：

- `LowfreqBacktestReport.jsx` 页面逻辑修改
- `/screeners`、`/stock-check` 的 IA 调整
- 侧边栏结构改造
- `Lowfreq` 页面改动
- 其他页面行为调整

## 3. 现有证据

当前仓库中已有以下可验证证据：

- `App.jsx` 已注册以下明确路由：
  - `/`
  - `/ops`
  - `/market-intelligence`
  - `/screeners`
  - `/stock-check`
  - `/lowfreq`
  - `/lowfreq/backtest-reports/:reportId`
- 当前 `App.jsx` 没有 `*` 兜底路由
- 当前 App 级测试只覆盖：
  - 壳层文案
  - `/ops`
  - `/lowfreq/backtest-reports/:reportId`
- `LowfreqBacktestReport.jsx` 组件内部确实处理了 `reportId` 缺失，但这是组件级保护，不是 App 路由级保护
- `LowfreqBacktestReport.test.jsx` 中的“报告编号缺失”用例通过独立 `MemoryRouter` 人工构造，不代表真实 App 路由链路

这说明当前缺口属于 App 入口保护，而不是详情页组件能力不足。

## 4. 职责归属

本切片职责属于 `App` 路由层。

它只回答两个问题：

- 未知路径进入 App 时，是否有明确兜底结果
- 缺少必要路径参数的详情路径，是否在 App 层有明确兜底结果

它不回答以下问题：

- 详情页数据请求是否成功
- `LowfreqBacktestReport` 页面结构是否完整
- 侧边栏信息架构是否最优
- 详情页返回链接是否合理

因此本切片应保持为“路由保护”，而不是“页面增强”。

## 5. 方案选择

### 5.1 备选方案

存在 3 种语义方案：

1. 未知路径与缺参路径统一进入 404 占位
2. 未知路径与缺参路径统一重定向到已有页面
3. 未知路径 404，缺参路径重定向

### 5.2 选择

本切片建议采用方案 1：

- 未知路径进入 404 占位
- `/lowfreq/backtest-reports/` 这类缺参路径同样进入 404 占位

### 5.3 选择理由

原因如下：

- 当前缺口在 App 入口层，应由 App 层直接给出明确失败语义
- 若静默重定向，会把错误链接伪装成正常导航，不利于诊断
- 404 占位最符合“入口保护”这条线的边界，不需要改动详情页组件

## 6. 展示设计

### 6.1 最小展示要求

路由兜底页面只需要承担最小说明职责：

- 明确告知“页面不存在”或“路径无效”
- 提供返回主工作台或首页的入口

### 6.2 边界要求

本切片不做：

- 独立 NotFound 页面系统化设计
- 丰富插图或复杂空态
- 额外导航逻辑

因此实现应保持为最小占位，不扩展为新的页面主题线。

## 7. 测试设计

### 7.1 测试载体

测试应新增独立文件，例如：

- `App.routeGuard.test.jsx`

不扩写：

- `App.test.jsx`
- `App.lowfreqBacktestReportRoute.test.jsx`

### 7.2 最小断言集合

推荐最小断言集合：

- 未知路径进入 App 时显示兜底内容
- 缺参详情路径进入 App 时显示同样的兜底内容
- App 壳层基础结构仍存在

断言重点应放在：

- 路由保护结果是否明确
- 壳层是否仍稳定挂载

而不是扩展为：

- 详情页组件内部错误态
- 导航激活态
- 其他页面跳转行为

## 8. 非目标

本切片明确不处理：

- `LowfreqBacktestReport.jsx` 组件逻辑
- 详情页下载链路
- App 导航 IA 调整
- `/screeners` 与 `/stock-check` 的入口策略
- 404 页面视觉升级

这些都属于其他主题线。

## 9. 提交边界

目标实现提交只允许包含：

- `App.jsx` 中与 `*` 路由或最小兜底占位相关的最小 hunk
- 新增 `App.routeGuard.test.jsx`

必须排除：

- `LowfreqBacktestReport.jsx`
- `LowfreqBacktestReport.test.jsx`
- `App.test.jsx`
- `App.lowfreqBacktestReportRoute.test.jsx`
- 其他页面文件

## 10. 验证要求

预期最小验证闭环：

- 运行 `App.routeGuard.test.jsx`
- 如触及 `App.jsx`，补跑与路由直接相关的独立 App 测试
- 确认提交中不带入其他导航或页面主题线

## 11. 结论

本切片的本质不是再做一个新页面，而是给 `App` 路由层补上一条明确、稳定、低成本的入口保护线。

只有先把未知路径和缺参路径的语义收口，后续 `App` 的导航 IA、详情页链路和更多路由保护，才更容易继续保持原子化推进。
