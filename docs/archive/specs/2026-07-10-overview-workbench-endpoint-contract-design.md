# Overview Workbench Endpoint Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `Overview` 页的数据来源 contract：从多接口并行请求收口到单一 `/api/lowfreq/workbench` 聚合端点，并让测试载体同步到该单端点 contract，不改整页视觉结构、不改区块布局主题、不改其他页面或后端实现。

目标是：

- 为 [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx) 建立单一 workbench 聚合请求入口
- 为 [Overview.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.test.jsx) 建立与之对应的单一 payload contract
- 将当前 `Overview` 相关 diff 中最窄、最可解释的一条线收口为“endpoint contract”主题

本切片不是：

- `Overview` 整页信息架构重构
- 卡片、表格、锚点导航、区块命名与视觉排布治理
- `MarketIntelligence.jsx` 或其他页面改动
- 后端接口实现或网关改动
- 文档与部署说明改写

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Overview.jsx`
- `neotrade3-dashboard/src/pages/Overview.test.jsx`
- 单一 `/api/lowfreq/workbench` 请求 contract
- 测试侧单一 `buildWorkbenchPayload()` 载体

Excluded:

- `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/services/api.js`
- 后端 `/api/lowfreq/workbench` 实现
- 页面视觉与布局微调

## 3. Existing Context

当前代码已给出可核验证据：

- [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx#L76-L88) 当前只通过一次 `fetchApi()` 请求 `/api/lowfreq/workbench?date=...&ensure_generated=false`
- [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx#L94-L101) 当前页面消费的数据已集中在：
  - `meta`
  - `market_summary`
  - `daily_ops`
  - `hot_sectors`
  - `tracking_list`
  - `positions`
  - `trade_ledger`
- [Overview.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.test.jsx#L33-L155) 当前测试已用 `buildWorkbenchPayload()` 收口为单一 payload
- [Overview.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.test.jsx#L169-L228) 当前测试主题集中在：
  - 单端点加载
  - 请求失败错误展示
  - `DateSelector` 刷新再次请求

现状风险：

- 如果把单端点 contract 与整页区块重构一起处理，本轮会从“数据来源收口”扩大成整页翻修
- 如果只改生产代码不改测试载体，contract 证据链会断裂
- 如果继续保留对多端点历史行为的测试，本轮会失去单一入口语义

## 4. Approach Options

### Option A: 只收口到单一 workbench 端点，并同步测试载体（推荐）

仅处理：

- `Overview.jsx` 的请求入口
- `Overview.test.jsx` 的 payload/mock 入口

Pros:

- 边界最窄，直接围绕 endpoint contract
- 生产与测试载体语义一致
- 与当前 diff 中最容易解释的一层完全对齐

Cons:

- 页面结构层的变化需留到后续独立主题

### Option B: endpoint contract + 整页 UI 重构一起做

Pros:

- 一次看起来“完整”

Cons:

- 混合了数据 contract 与页面结构两类主题
- 不符合窄切片原则

### Option C: 暂不处理 Overview，转回其他页面

Pros:

- 可以继续寻找更显眼的页面主题

Cons:

- 放弃当前 `Overview` 中最可解释的一条独立线
- `Overview` 测试与生产数据来源收口继续处于混合状态

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `Overview.jsx`
  - 只从单一 `/api/lowfreq/workbench` 读取页面所需聚合数据
- `Overview.test.jsx`
  - 用单一 `buildWorkbenchPayload()` 描述该 contract 的最小测试载体
- UI 结构层
  - 继续视作独立主题，不在本轮处理

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `Overview.jsx` 的请求入口与错误/刷新路径
2. `Overview.test.jsx` 的 mock payload 与请求断言
3. 与单端点 contract 直接相关的最小断言

本轮不允许顺手改动：

- 页面区块拆分
- 样式细节与命名文案微调
- 其他页面或共享组件行为
- 后端接口实现

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `MarketIntelligence.jsx`
- 不修改 `App.jsx`
- 不修改 `src/services/api.js`
- 不修改后端 `/api/lowfreq/workbench` 实现
- 若验证暴露的是页面结构、共享组件或后端契约问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证优先采用：

1. `Overview.test.jsx` 的单端点 contract 断言
2. 生产文件最近改动后的最小语法/结构检查

默认不要求：

- 新增 UI 快照测试
- 为视觉层变更补断言
- 跨页面联动测试

原因：

- 本轮是 endpoint contract 收口，关键在请求入口与测试载体一致性

## 7. Validation

预期验证方式：

- 确认 `Overview.jsx` 只请求 `/api/lowfreq/workbench`
- 确认 `Overview.test.jsx` 只围绕单端点 payload 做断言
- 如实施后有改动，再做最小测试与语法检查

## 8. Commit Boundary

目标提交应限制为：

- `Overview.jsx` 与 `Overview.test.jsx` 中单一 workbench endpoint contract 的最小 hunk

必须排除：

- 纯 UI 结构重排
- 其他页面与共享组件改动
- 后端与文档改动

若相对 `HEAD` 无法将 endpoint contract 与 UI 结构层安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
