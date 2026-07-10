# StockCheck Hot-Sector Badge Status Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `StockCheck` 页面的热门板块命中区 badge status contract，不改按钮文案、不改 debug 折叠标题、不改 API 行为。

目标是：

- 将热门板块命中区的 badge `label` 统一收口到 `STATUS_COPY.actionable / observing / followerObserving`
- 将热门板块命中区的 badge `semanticKey` 同步收口到与上述状态语义一致的 contract
- 将 `StockCheck.test.jsx` 中对应 badge 的断言同步到相同 contract

本切片不是：

- `STATUS_COPY.debugData` 在 `StockCheck` 的接入
- debug 折叠标题收口
- `PageHeader` subtitle 文案调整
- 搜索按钮 copy contract
- API 请求、结果解析或交互逻辑变更
- 热门板块结果区之外的 copy 清理

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- 只针对热门板块命中区 badge 的状态语义 contract 收口

Excluded:

- `neotrade3-dashboard/src/components/statusCopy.js`
- `STATUS_COPY.debugData`
- `PageHeader`
- 搜索按钮文案
- `fetchApi` 逻辑
- 热门板块 message 正文
- debug 折叠区 `<summary>`
- 结果区其余结构

## 3. Existing Context

当前 `StockCheck` 线在完成 shared-shell adoption 和 button copy contract 后，剩余 `HEAD` 相对 drift 主要集中在三类内容：

1. `STATUS_COPY` import 与热门板块 badge contract
   - `STATUS_COPY.actionable`
   - `STATUS_COPY.observing`
   - `STATUS_COPY.followerObserving`
   - `watch_general / watch_follower`
2. debug 折叠标题
   - `STATUS_COPY.debugData`
3. 页面相邻 copy / import 漂移
   - `PageHeader` subtitle
   - `AlertCircle` import

其中第 1 类与第 2 类虽然都和 `STATUS_COPY` 有关，但职责并不相同：

- 热门板块 badge contract 是状态语义 contract，包含展示文案与语义 key 两个层面
- debug 折叠标题只是一个独立的 copy 点位，不承接 badge 状态语义

当前代码与测试已经给出可核验事实：

- badge 区块当前位于 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx#L141-L167)
- debug 折叠标题位于 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx#L246-L248)
- 现有测试已直接承接 `可出手` badge 的结果断言，但未承接 debug 标题，在 [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx#L105-L109)
- `STATUS_COPY` 常量中已具备本轮所需文案，在 [statusCopy.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/statusCopy.js#L1-L14)

现状风险：

- 如果把 badge contract 与 debug 标题一起提交，切片目的会从“badge status contract”扩大成“badge + debug copy”
- 如果只改 badge 的 `label`，不改 `semanticKey`，则展示文案与状态语义会继续失配
- 如果顺手带入 subtitle 或 import 清理，本轮会从状态契约收口扩大成页面级整理

## 4. Approach Options

### Option A: 只做热门板块 badge status contract（推荐）

仅处理：

- 热门板块命中区 badge 的 `semanticKey`
- 热门板块命中区 badge 的 `label`
- 对应 focused test 断言

Pros:

- 与测试承接面最接近
- 生产语义和可见文案形成最小闭环
- 不卷入 debug 标题与相邻 copy

Cons:

- 不会顺手减少 `StockCheck` 剩余的 debug 标题 diff

### Option B: badge contract + debug 标题一起做

同时处理：

- 热门板块 badge 的 `semanticKey`
- 热门板块 badge 的 `label`
- debug 折叠标题

Pros:

- 一次减少更多 `STATUS_COPY` 相关 diff

Cons:

- badge 语义 contract 与 debug 标题不是同一职责面
- 当前测试不直接承接 debug 标题，切片闭环会变弱
- 后续难以解释该切片的唯一目的

### Option C: 只改 badge label，不改 semanticKey

Pros:

- 代码改动看起来更少

Cons:

- 仅统一表层文案，未统一状态语义
- 会留下 `leaders/leader` 仍映射到错误观察层级的问题

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `StockCheck.jsx`
  - 提供热门板块命中区 badge 的统一状态语义 contract
- `StockCheck.test.jsx`
  - 验证热门板块命中区 badge 的状态 contract
- `STATUS_COPY`
  - 作为现有状态文案源被消费，但不在本轮内修改
- debug 折叠标题
  - 继续留待下一条独立切片处理

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `buy_signal === true`
   - `semanticKey` 对齐 `entry_ready`
   - `label` 对齐 `STATUS_COPY.actionable`
2. `buy_signal !== true && role in ['leaders', 'leader']`
   - `semanticKey` 对齐 `watch_general`
   - `label` 对齐 `STATUS_COPY.observing`
3. 其他观察类角色
   - `semanticKey` 保持 `watch_follower`
   - `label` 对齐 `STATUS_COPY.followerObserving`
4. 对应测试断言
   - 增补对 leader / follower 观察态的断言
   - 保留 `可出手` contract 的显式验证

本轮不允许顺手改动：

- `STATUS_COPY.debugData`
- debug `<summary>` 文案
- `PageHeader` subtitle
- 搜索按钮文案
- 热门板块正文 message
- `fetchApi` 请求参数

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不改 `statusCopy.js`
- 不改 `PageHeader`
- 不改按钮 contract
- 不改 API 调用和结果渲染逻辑
- 若测试暴露的是 debug 标题、subtitle 或其他页面 copy 问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证只需要覆盖：

1. `StockCheck.test.jsx` 通过
2. 热门板块 badge 至少覆盖以下 contract：
   - `buy_signal=true` -> `可出手`
   - `role=leaders` 或 `role=leader` 且 `buy_signal!==true` -> `观察中`
   - 其他观察角色 -> `跟随观察`

默认不要求：

- debug 标题额外测试
- 其他页面测试
- 全量前端测试矩阵

## 7. Validation

预期验证命令：

- `npm test -- src/pages/StockCheck.test.jsx`

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `StockCheck.jsx` 中热门板块 badge contract 的最小 hunk
- `StockCheck.test.jsx` 中对应 badge 断言的最小 hunk

必须排除：

- `STATUS_COPY.debugData`
- debug 折叠标题
- `PageHeader` subtitle
- 搜索按钮文案
- `AlertCircle` import
- API 逻辑

若相对 `HEAD` 无法从相邻 diff 中安全隔离 badge status contract，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
