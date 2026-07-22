# StockCheck Debug Summary Copy Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `StockCheck` 页面 debug 折叠区 `<summary>` 的 copy contract，不改 badge 状态契约、不改按钮文案、不改 API 行为。

目标是：

- 将 debug 折叠区标题从硬编码文案收口到 `STATUS_COPY.debugData`
- 让 `StockCheck` 页面内与 debug 数据区相关的 copy 来源和其他状态文案来源保持一致
- 根据现有测试承接面，决定是否补一条最小断言来覆盖该 copy contract

本切片不是：

- 热门板块 badge 的 `semanticKey` / `label`
- `PageHeader` subtitle 文案调整
- `AlertCircle` import 清理
- 搜索按钮 copy contract
- API 请求、结果解析或交互逻辑变更
- debug 区结构、样式或展开行为调整

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- 仅在确有必要时，最小调整 `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- 只针对 debug 折叠区 `<summary>` 的 copy contract 收口

Excluded:

- `neotrade3-dashboard/src/components/statusCopy.js`
- `STATUS_COPY.actionable / observing / followerObserving`
- 热门板块 badge 区块
- `PageHeader`
- 搜索按钮文案
- `fetchApi` 逻辑
- debug 区 `<pre>` 内容
- 结果区其余结构

## 3. Existing Context

当前 `StockCheck` 线已经完成：

1. shared-shell adoption
2. button copy contract
3. hot-sector badge status contract

在这些切片之后，`StockCheck.jsx` 相对 `HEAD` 的剩余 drift 主要还有三类：

1. debug 折叠区标题
   - `原始返回数据` -> `STATUS_COPY.debugData`
2. 页面相邻 copy 漂移
   - `PageHeader` subtitle
3. import 漂移
   - `AlertCircle`

这些内容虽然都在同一文件中，但职责不同：

- debug 折叠区标题属于单点 copy contract
- subtitle 属于页面头部文案 contract
- `AlertCircle` import 属于整洁性清理，不是用户可见 contract

当前代码与测试已经给出可核验事实：

- debug 折叠区位于 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx#L246-L248)
- `STATUS_COPY.debugData` 常量已存在于 [statusCopy.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/statusCopy.js#L12-L14)
- 当前 [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 还没有直接断言 debug `<summary>` 文案

现状风险：

- 如果把 debug 标题与 subtitle 一起提交，切片目的会从“debug summary copy contract”扩大成“页面 copy 清理”
- 如果顺手带入 `AlertCircle` import 清理，本轮会从用户可见 copy 收口偏移成混合主题提交
- 如果完全不考虑测试承接，可能留下一个无显式验证的 copy contract

## 4. Approach Options

### Option A: 只做 debug summary copy contract，并补最小断言（推荐）

仅处理：

- `<summary>` 文案改为 `STATUS_COPY.debugData`
- 在现有 `StockCheck.test.jsx` 中增加一条最小断言

Pros:

- 生产 copy 与测试形成最小闭环
- 边界仍然足够窄
- 不卷入 subtitle 与 import 漂移

Cons:

- 会让 `StockCheck.test.jsx` 承担一条新的非核心断言

### Option B: 只改生产文案，不补测试

Pros:

- 改动最少
- 单点文案收口足够直接

Cons:

- 没有显式测试承接
- 后续难以区分这条 copy 是否仍被页面 contract 保护

### Option C: debug summary + subtitle 一起做

Pros:

- 一次减少更多剩余 copy diff

Cons:

- 切片边界明显扩大
- debug summary 与页面头部 subtitle 不是同一职责面
- 后续难以解释该切片的唯一目的

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `StockCheck.jsx`
  - 提供 debug 折叠区 `<summary>` 的统一 copy contract
- `StockCheck.test.jsx`
  - 以最小断言验证该 copy contract
- `STATUS_COPY`
  - 作为现有文案源被消费，但不在本轮内修改
- subtitle / `AlertCircle`
  - 继续留待下一条独立切片处理

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. debug `<summary>` 文案
   - `原始返回数据` -> `STATUS_COPY.debugData`
2. 对应测试断言
   - 在结果区已渲染的前提下，断言 `详细数据（排查用）` 存在

本轮不允许顺手改动：

- `STATUS_COPY.actionable / observing / followerObserving`
- 热门板块 badge
- `PageHeader` subtitle
- 搜索按钮文案
- `AlertCircle` import
- debug 区 `<pre>` 内容或结构
- `fetchApi` 请求参数

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不改 `statusCopy.js`
- 不改 `PageHeader`
- 不改 badge contract
- 不改按钮 contract
- 不改 API 调用和结果渲染逻辑
- 若测试暴露的是 subtitle、import 或其他页面 copy 问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证优先采用：

1. `StockCheck.test.jsx` 通过
2. 在已有结果渲染用例中增加一条 `<summary>` 文案断言

默认不要求：

- 新增独立测试文件
- 其他页面测试
- 全量前端测试矩阵

原因：

- 当前 `StockCheck.test.jsx` 已经覆盖结果区渲染，复用现有 carrier 的成本最低
- 该文案是单点 copy，不值得为此新建独立 carrier

## 7. Validation

预期验证命令：

- `npm test -- src/pages/StockCheck.test.jsx`

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `StockCheck.jsx` 中 debug `<summary>` 文案的最小 hunk
- 若采用测试闭环，则包含 `StockCheck.test.jsx` 中对应断言的最小 hunk

必须排除：

- `PageHeader` subtitle
- `AlertCircle` import
- 搜索按钮文案
- badge status contract
- API 逻辑

若相对 `HEAD` 无法从相邻 diff 中安全隔离 debug summary copy contract，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
