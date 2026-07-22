# App `/ops` 路由独立测试设计

日期：2026-07-09

## 1. 目标

本切片只解决一个问题：

当前端直接访问 `/ops` 时，`App` 路由层需要稳定命中 `OpsCenter` 页面，并通过一个独立测试载体形成 App 级回归保护。

本切片的目标不是扩展 `OpsCenter` 页面能力，而是收口 `/ops` 路由的验证链路。

## 2. 范围

包含：

- 一个新的独立测试文件，例如 `neotrade3-dashboard/src/App.opsCenterRoute.test.jsx`
- 如确有必要，`neotrade3-dashboard/src/App.jsx` 中与 `/ops` 路由直接相关的最小改动

不包含：

- `OpsCenter.jsx` 页面 UI 或 contract 调整
- `OpsCenter` 刷新/日期切换测试
- 首页跳转 `/ops` 的交互验证
- `App` 导航 IA 调整
- Header 文案
- 其他路由主题线

## 3. 现有证据

当前工作区中已有以下可验证证据：

- `OpsCenter` 页面文件已存在：`neotrade3-dashboard/src/pages/OpsCenter.jsx`
- 首页风险卡片已指向 `/ops`
- `App.jsx` 工作树中已存在 `/ops` 路由与导航接线
- 现有测试模式中，回测详情页路由已经采用独立测试载体收口：
  - `neotrade3-dashboard/src/App.lowfreqBacktestReportRoute.test.jsx`

这说明 `/ops` 路由测试切片属于对现有结构的补齐，而不是发明新产品方向。

## 4. 职责归属

本切片职责属于 `App` 路由层。

它只回答一个问题：

- 访问 `/ops` 时，`App` 是否把用户带到 `OpsCenter`

它不回答以下问题：

- `OpsCenter` 内容是否正确完整
- `OpsCenter` API 是否正确请求
- `OpsCenter` 是否支持刷新或日期切换

因此本切片应保持为“路由验证”，而不是“页面功能验证”。

## 5. 测试设计

### 5.1 测试入口

测试通过直接设置浏览器地址到 `/ops`，然后渲染 `App`。

这比从首页点击导航进入更窄，也更能直接保护路由 contract。

### 5.2 最小断言集合

推荐最小断言集合只保留以下三类：

1. `OpsCenter` 页面桩内容被命中渲染
2. `App` 壳层基础结构仍存在
3. 如当前实现能稳定断言，再补一条与 `/ops` 对应的壳层文案存在

本切片不要求强制验证侧边栏 active 态；若断言成本偏高，可延后到更大的导航 IA 测试线。

### 5.3 Mock 策略

测试应采用最小 mock：

- mock `OpsCenter`
- mock 其他页面为简单占位组件
- mock `getDataStatus()` 到稳定返回

这样可以把测试聚焦在“路由命中”，而不是页面内部数据流。

## 6. 非目标

本切片明确不处理：

- `OpsCenter` 组件内部 API 请求行为
- `GlobalBanner`
- `GlobalApiErrorBanner`
- 首页到 `/ops` 的点击跳转
- App 导航激活样式精确验证

这些都属于后续更宽的测试主题。

## 7. 提交边界

目标实现提交只允许包含：

- 新增的 `App.opsCenterRoute.test.jsx`
- 如确有必要，`App.jsx` 中 `/ops` route 的最小相关 hunk

必须排除：

- `OpsCenter.jsx`
- `Overview.jsx`
- `App.test.jsx`
- Header 文案调整
- 导航 IA 调整

## 8. 验证要求

预期最小验证闭环：

- 运行 `App.opsCenterRoute.test.jsx`
- 如触及 `App.jsx`，补跑该测试即可
- 确认提交中不带其他 `App` 漂移

## 9. 结论

本切片的本质不是为 `OpsCenter` 加新能力，而是给 `/ops` 这条已有路由补上一层独立、稳定、低风险的 App 级回归保护。

只有先把这条最窄的路由验证线收口，后续 `OpsCenter` 页面 contract、刷新行为、乃至更大的 `App` 导航主题线，才更容易继续保持原子化推进。
