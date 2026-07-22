# Overview Workbench Endpoint Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-overview-workbench-endpoint-contract-design.md`

## 1. 目标

本计划只覆盖 `Overview` 页的 workbench endpoint contract：将页面数据来源收口到单一 `/api/lowfreq/workbench` 聚合端点，并让测试载体同步到单一 payload contract，不扩展到页面结构重排、表格重构、文案改写或其他页面主题。

本轮目标只有三个：

1. 在 `Overview.jsx` 中只保留单一 `/api/lowfreq/workbench` 请求入口。
2. 在 `Overview.test.jsx` 中只保留与该单端点对应的最小 payload/mock/断言。
3. 在不扩大到 UI 结构主题的前提下，完成最小验证，并仅在相对 `HEAD` 可安全隔离 endpoint contract 相关 hunk 时提交。

本轮必须得到的核心结果：

- `Overview.jsx` 的数据读取路径只围绕 `/api/lowfreq/workbench`
- `Overview.test.jsx` 的 mock 与断言只围绕单一 workbench payload
- 提交中不包含整页区块重构、表格列改写、视觉文案与布局重排
- 提交中不包含其他页面、后端、网关或文档改动

## 2. 不在本轮完成

- `Overview` 整页 UI/信息架构重构
- 卡片、表格、区块标题、说明文案、排版与样式重构
- `MarketIntelligence.jsx` 改动
- `App.jsx` 改动
- `src/services/api.js` 改动
- `/api/lowfreq/workbench` 后端实现改动
- 文档与部署说明改动
- 全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- 当前 [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx) 工作区相对 `HEAD` 的 diff 同时混有两层主题：
  - 更窄层：数据入口收口到 `/api/lowfreq/workbench`
  - 更宽层：整页区块、表格与文案/布局重构
- 当前 [Overview.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.test.jsx) 工作区相对 `HEAD` 的 diff 也同时混有两层主题：
  - 更窄层：`buildWorkbenchPayload()` 与单端点请求断言
  - 更宽层：为新 UI 结构服务的断言与旧多端点场景删除
- [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx#L76-L88) 已出现单一 `/api/lowfreq/workbench?date=...&ensure_generated=false` 请求
- [Overview.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.test.jsx#L166-L228) 已出现单端点加载、失败展示与刷新请求的 contract 测试形态

### 3.2 结构性风险

- 最大风险不是端点收口本身，而是把 UI 结构重构一起带进提交
- 如果只改生产代码不改测试载体，contract 无法闭环
- 如果整文件直接提交，极易把 endpoint contract 与表格/文案重排混成一个不可解释的 commit

## 4. 实施原则

- 只改 `neotrade3-dashboard/src/pages/Overview.jsx`
- 只改 `neotrade3-dashboard/src/pages/Overview.test.jsx`
- 只做单一 workbench endpoint contract
- 不改页面结构、表格列、卡片层次、文案重排
- 不改其他页面、共享组件、后端、网关与文档
- 若相对 `HEAD` 无法安全隔离 endpoint contract 相关 hunk，本轮结论应为“不提交”，不能静默扩大范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/src/pages/Overview.jsx`
- `neotrade3-dashboard/src/pages/Overview.test.jsx`

允许改动逻辑：

- `Overview.jsx`：
  - 单一 `fetchApi('/api/lowfreq/workbench?...')`
  - 与该单端点直接对应的数据解构/状态承接
  - 与该单端点直接对应的错误与刷新路径
- `Overview.test.jsx`：
  - `buildWorkbenchPayload()`
  - 单端点请求断言
  - 单端点失败断言
  - 触发刷新后的二次请求断言

明确不改：

- 交易台账表格列结构
- 建仓池/跟踪池/板块卡片的 UI 细节
- 页面区块标题、文案与视觉层级
- `MarketIntelligence.jsx`
- `App.jsx`
- 后端 `/api/lowfreq/workbench` 实现

## 6. 总体分段

本计划建议分为四段执行：

- `OWE-R1`：冻结 endpoint contract 的精确边界
- `OWE-R2`：只实施单端点生产与测试 contract
- `OWE-R3`：做最小语法/测试验证
- `OWE-R4`：隔离 contract hunk 并提交

## 7. 分段实施计划

### OWE-R1：冻结 endpoint contract 的精确边界

目标：

- 明确 `Overview.jsx` 与 `Overview.test.jsx` 中哪些点位属于本轮 endpoint contract，哪些相邻改动必须排除。

任务：

- 读取当前 [Overview.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.jsx)
- 读取当前 [Overview.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Overview.test.jsx)
- 用 `git diff HEAD -- ...` 检查当前剩余 diff
- 只标记以下目标点位：
  - `/api/lowfreq/workbench` 请求入口
  - 该请求返回 payload 的最小状态承接
  - `buildWorkbenchPayload()`
  - 单端点加载/失败/刷新请求断言
- 显式排除：
  - 表格列变化
  - 区块结构重排
  - 标题/说明文案变化
  - 其他页面与后端主题

完成判定：

- include / exclude 列表明确
- `HEAD`-relative diff 中 endpoint contract 与 UI 结构层已被清楚分开

### OWE-R2：只实施单端点生产与测试 contract

目标：

- 在不扩大到页面结构主题的前提下，让 `Overview` 的生产与测试都围绕单一 workbench 端点工作。

任务：

- 在 `Overview.jsx` 中只保留单一 `/api/lowfreq/workbench` 请求逻辑
- 删除或避开与历史多端点 contract 直接相关的读取路径
- 在 `Overview.test.jsx` 中只保留单端点 payload 载体与对应断言
- 删除或避开与历史多端点 contract 直接相关的 mock/断言

关键约束：

- 不因单端点引入而顺手改表格、卡片或区块布局
- 不为 UI 结构层补新的断言
- 不修改其他文件

完成判定：

- `Overview.jsx` 只围绕单端点工作
- `Overview.test.jsx` 只围绕单端点 contract 工作
- 文件其他区域无边界外改动

### OWE-R3：做最小语法/测试验证

目标：

- 证明本轮只影响数据入口 contract，不引入语法错误或 contract 级回归。

任务：

- 检查最近编辑文件是否存在明显语法或结构问题
- 运行 `Overview.test.jsx` 的 focused test 或最小相关验证
- 若失败原因暴露的是 UI 结构层或后端接口语义问题，则停止并报告边界问题

完成判定：

- `Overview.jsx` / `Overview.test.jsx` 无明显语法错误
- focused test 能证明单端点 contract 成立
- 未引入额外边界外修改

### OWE-R4：隔离 contract hunk 并提交

目标：

- 生成一个单一目的的切片，只表达 `Overview` 的 workbench endpoint contract。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/Overview.jsx neotrade3-dashboard/src/pages/Overview.test.jsx`
- 只暂存 endpoint contract 相关 hunk
- 排除 UI 结构与文案重排相关 hunk
- 仅在 staged diff 纯度满足时提交

完成判定：

- staged diff 只包含：
  - 单端点请求入口
  - 单端点 payload/mock
  - 单端点加载/失败/刷新 contract 断言
- staged diff 不包含页面结构重排
- staged diff 不包含其他页面、后端、网关与文档改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先对照 `Overview.jsx` 与 `Overview.test.jsx` 的当前 diff
2. 明确 endpoint contract 与 UI 结构层的分界
3. 只收口 endpoint contract 所需最小代码
4. 做 focused test 与最小语法检查
5. 复核 staged diff 纯度
6. 再决定是否提交

原因：

- 先冻结边界再改代码，可以避免把整页重构顺手带入
- 先验证 contract 再提交，可以把这条线保持在“数据来源收口”而不是“页面翻修”

## 9. 建议提交切分

建议单一提交：

### Commit OWE：overview workbench endpoint contract

范围：

- `Overview.jsx` 与 `Overview.test.jsx` 中单端点 contract 的最小 hunk

目的：

- 让 `Overview` 页面与其测试载体围绕单一 `/api/lowfreq/workbench` 聚合端点保持一致

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 endpoint + UI 重构混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `Overview.jsx` 只请求 `/api/lowfreq/workbench`
2. `Overview.test.jsx` 只围绕单端点 payload 与请求断言
3. focused test 通过或至少能证明该 contract 成立
4. 提交中不包含页面结构重排与文案重排
5. 提交中不包含其他页面、后端、网关或文档改动

## 11. 风险提示

- 主要风险是当前 diff 中 UI 结构层与 endpoint contract 混在同一文件，隔离时必须逐 hunk 对照 `HEAD`
- 第二风险是测试侧很容易顺手接受新 UI 断言，导致 contract 与视觉层一起入提交
- 第三风险是如果因为测试失败去补后端或共享组件，会越过当前批准边界

## 12. 结论

本计划不是 `Overview` 页面重构计划，而是一条更窄的 contract 收口线，目标只有三件事：

- 只收口到单一 `/api/lowfreq/workbench` 请求入口
- 只同步最小测试载体到单端点 payload
- 只做最小语法/focused test 验证，并在可安全隔离时提交
