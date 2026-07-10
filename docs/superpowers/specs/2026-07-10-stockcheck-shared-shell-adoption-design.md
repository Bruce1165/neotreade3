# StockCheck Shared-Shell Adoption Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `StockCheck.jsx` 的共享壳层复用，不改数据请求、不改结果结构、不改状态文案契约。

目标是：

- 用共享组件 `PageHeader` 替换 `StockCheck` 页面的本地 header 实现
- 用共享组件 `BlockMessage` 替换 `StockCheck` 页面的本地错误块实现
- 让 `StockCheck` 与 `Overview`、`OpsCenter`、`MarketIntelligence` 保持同一壳层表达方式

本切片不是：

- `StockCheck` 的按钮文案收口
- `STATUS_COPY` 文案/状态契约收口
- `StockCheck.test.jsx` 断言调整
- API contract 或请求链路变更
- 搜索输入区或结果区的结构重排

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- 只针对页面 header 和错误块的共享组件复用

Excluded:

- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- `neotrade3-dashboard/src/components/PageHeader.jsx`
- `neotrade3-dashboard/src/components/BlockMessage.jsx`
- `neotrade3-dashboard/src/components/statusCopy.js`
- 按钮文案 `检查 / 检查中...`
- `STATUS_COPY.actionable / observing / followerObserving`
- `STATUS_COPY.debugData`
- 任意 API 请求、响应解析和结果渲染逻辑

## 3. Existing Context

当前 `StockCheck.jsx` 的剩余 diff 实际混有两组主题：

1. 共享壳层复用
   - `PageHeader`
   - `BlockMessage`
2. 文案/状态契约收口
   - 按钮文案 `开始核验 / 核验中...`
   - `STATUS_COPY` badge 文案
   - `STATUS_COPY.debugData`

共享壳层不是新模式，现有代码库已经存在稳定消费面：

- `Overview.jsx` 使用 `PageHeader` 和 `BlockMessage`
- `OpsCenter.jsx` 使用 `PageHeader` 和 `BlockMessage`
- `MarketIntelligence.jsx` 使用 `PageHeader` 和 `BlockMessage`

这说明把 `StockCheck` 接到同一壳层体系，是可核验的延续性改动，而不是新增设计方向。

相反，按钮文案与 `STATUS_COPY` 属于另一组语义：

- 它们改变的是用户可见 copy 和状态标签语义
- `StockCheck.test.jsx` 当前也只显式承接了按钮文案变化
- 如果把这组内容和共享壳层复用一起提交，切片目的会从“共享壳层 adoption”扩大成“壳层 + copy + 状态契约”

现状风险：

- `StockCheck` 页面壳层仍保留本地实现，而其他页面已经进入共享组件体系
- 若继续混合推进，后续很难解释某次提交到底是在做共享壳层复用，还是在做状态文案收口
- 若顺手把按钮文案与 `STATUS_COPY` 一并纳入，本轮就不再是纯粹的 shared-shell 切片

## 4. Approach Options

### Option A: 只做 shared-shell adoption（推荐）

仅处理：

- 本地 header -> `PageHeader`
- 本地错误块 -> `BlockMessage`

Pros:

- 与现有共享组件消费模式对齐
- 提交目的单一清晰
- 不卷入按钮文案和状态语义

Cons:

- 不能顺手减少 `StockCheck` 里其他文案/状态 diff

### Option B: shared-shell + 文案/状态契约一起做

同时处理：

- `PageHeader`
- `BlockMessage`
- 按钮文案
- `STATUS_COPY` badge / debug 标题

Pros:

- 一次减少更多 drift

Cons:

- 切片边界显著扩大
- 提交目的不再单纯
- `StockCheck.test.jsx` 也会被卷入文案层变化

### Option C: 只做文案/状态契约收口

保持本地 header / 错误块不动，只处理：

- 按钮文案
- `STATUS_COPY`

Pros:

- 与当前测试表面更贴近

Cons:

- `StockCheck` 会继续保留与其他页面不一致的本地壳层实现
- 共享壳层复用继续拖延

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `PageHeader`
  - 负责页面标题与副标题壳层表达
- `BlockMessage`
  - 负责错误块的统一展示
- `StockCheck.jsx`
  - 消费共享壳层组件
  - 不在本轮修改按钮 copy、状态 copy 或结果语义

### 5.2 Adoption Strategy

本切片只允许对 `StockCheck.jsx` 做以下替换：

1. 页面 header
   - 删除本地 `<h2> + <p>` 组合
   - 替换为 `<PageHeader title="单股核验" subtitle="..." />`
2. 错误显示区
   - 删除本地红色错误容器
   - 替换为 `<BlockMessage tone="red" message={error} />`

本轮不允许顺手改动：

- 搜索按钮文案
- 搜索按钮 loading 文案
- 热门板块 badge label
- debug 折叠标题
- 结果区卡片结构
- 搜索输入区样式

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不改 `StockCheck.test.jsx`
- 不改 `PageHeader.jsx` / `BlockMessage.jsx`
- 不改 `STATUS_COPY`
- 不改 `fetchApi` 调用
- 不改 `handleCheck`、`handleKeyPress` 行为
- 若发现 shared-shell adoption 不能单独通过现有测试/结构校验，应先报告边界问题，而不是静默把按钮文案或状态 copy 一起带进提交

## 6. Testing Design

验证只需要覆盖：

1. `StockCheck.test.jsx` 继续通过
2. 若页面 header 替换引发测试表面变化，再基于最小必要原则判断是否补充断言

默认不要求：

- 其他页面测试
- 全量前端测试矩阵
- API 层验证

## 7. Validation

预期验证命令：

- `npm test -- src/pages/StockCheck.test.jsx`

如替换后出现明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `StockCheck.jsx` 中 `PageHeader` 和 `BlockMessage` 的 shared-shell adoption 最小 hunk

必须排除：

- `StockCheck.test.jsx`
- 按钮文案变更
- `STATUS_COPY` badge / debug 文案
- 任何 API 或结果结构改动

若相对 `HEAD` 无法从相邻 diff 中安全隔离 shared-shell adoption，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
