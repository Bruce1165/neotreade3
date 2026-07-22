# StockCheck Button Copy Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `StockCheck` 页面搜索按钮的 copy contract，不改状态标签、不改 debug 标题、不改 API 行为。

目标是：

- 将按钮静态文案从 `检查` 收口到 `开始核验`
- 将按钮 loading 文案从 `检查中...` 收口到 `核验中...`
- 将 `StockCheck.test.jsx` 中对应的按钮断言同步到相同 contract

本切片不是：

- `STATUS_COPY` 在 `StockCheck` 的接入
- 热门板块 badge 文案收口
- debug 折叠标题收口
- 结果区或输入区结构调整
- API 请求、结果解析或交互逻辑变更

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- 只针对搜索按钮的 copy contract 收口

Excluded:

- `neotrade3-dashboard/src/components/statusCopy.js`
- `STATUS_COPY.actionable / observing / followerObserving`
- `STATUS_COPY.debugData`
- `PageHeader`
- `BlockMessage`
- `fetchApi` 逻辑
- 热门板块 badge 的语义与 label
- 结果区渲染结构

## 3. Existing Context

当前 `StockCheck` 线经过前一条切片后，shared-shell adoption 已经独立提交，工作区剩余 diff 主要集中在两类内容：

1. 按钮文案 contract
   - `开始核验`
   - `核验中...`
   - `StockCheck.test.jsx` 的按钮查询断言
2. `STATUS_COPY` contract
   - 热门板块 badge label
   - debug 折叠标题

这两类内容虽然都属于“文案”，但职责并不相同：

- 按钮 copy 是页面入口交互 contract
- `STATUS_COPY` 是状态语义 contract

当前测试表面也证明了这两类内容不应混在一个切片里：

- `StockCheck.test.jsx` 直接查询按钮名称
- `StockCheck.test.jsx` 当前并不直接拥有 `STATUS_COPY.debugData` 或观察类 badge 的断言

现状风险：

- 如果把按钮 copy 和 `STATUS_COPY` 一起提交，切片目的会从“button copy contract”扩大成“button + status-copy contract”
- 如果只改生产按钮文案，不改测试断言，则当前 `StockCheck.test.jsx` 会失效
- 如果顺手改结果区、debug 标题或 badge，会把本轮从“入口按钮 copy 收口”扩大成页面级 copy 清理

## 4. Approach Options

### Option A: 只做按钮 copy contract（推荐）

仅处理：

- `检查 -> 开始核验`
- `检查中... -> 核验中...`
- 测试中对应按钮查询断言同步

Pros:

- 生产代码和测试形成最小闭环
- 边界最窄
- 不卷入 `STATUS_COPY`

Cons:

- 不会顺手减少 `StockCheck` 剩余的 `STATUS_COPY` diff

### Option B: 按钮 copy + `STATUS_COPY` 一起做

同时处理：

- 按钮文案
- badge label
- debug 标题

Pros:

- 一次减少更多页面 copy diff

Cons:

- 切片边界明显扩大
- `STATUS_COPY` 语义与按钮 copy 不是同一层 contract
- 后续难以解释该切片的唯一目的

### Option C: 只改测试断言，不改生产文案

Pros:

- 当前工作区中看起来更容易通过测试

Cons:

- 生产与测试 contract 不一致
- 不是实际产品语义收口

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `StockCheck.jsx`
  - 提供统一的按钮 copy contract
- `StockCheck.test.jsx`
  - 验证该按钮 copy contract
- `STATUS_COPY`
  - 继续留待下一条独立切片处理

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. 按钮静态文案
   - `检查` -> `开始核验`
2. 按钮 loading 文案
   - `检查中...` -> `核验中...`
3. 对应测试断言
   - `getByRole('button', { name: '检查' })`
   - 同步到 `getByRole('button', { name: '开始核验' })`

本轮不允许顺手改动：

- `STATUS_COPY.actionable / observing / followerObserving`
- `STATUS_COPY.debugData`
- 错误提示 `请输入股票代码`
- placeholder `例如：600000`
- 结果区标题与 badge
- API 请求参数

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不改 `PageHeader`
- 不改 `BlockMessage`
- 不改 `STATUS_COPY`
- 不改 `fetchApi` 调用和结果渲染逻辑
- 若测试暴露的是 `STATUS_COPY` 或其他页面 copy 问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证只需要覆盖：

1. `StockCheck.test.jsx` 通过

默认不要求：

- 其他页面测试
- 全量前端测试矩阵
- `STATUS_COPY` 相关额外测试

## 7. Validation

预期验证命令：

- `npm test -- src/pages/StockCheck.test.jsx`

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `StockCheck.jsx` 中按钮文案的最小 hunk
- `StockCheck.test.jsx` 中对应按钮断言的最小 hunk

必须排除：

- `STATUS_COPY` 相关变更
- `PageHeader`
- `BlockMessage`
- 结果区和 debug 区其他 copy
- API 逻辑

若相对 `HEAD` 无法从相邻 diff 中安全隔离 button copy contract，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
