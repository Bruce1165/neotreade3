# StockCheck Header Subtitle Copy Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `StockCheck` 页面 `PageHeader.subtitle` 的 copy contract，不改 import 整洁性、不改 badge 状态契约、不改按钮文案、不改 API 行为。

目标是：

- 将 `PageHeader.subtitle` 从旧版分隔写法收口到当前页面文案合同
- 让 `StockCheck` 页头说明与页面内其他已完成的文案收口保持一致
- 在现有测试 carrier 上补一条最小 subtitle 断言，形成可核验闭环

本切片不是：

- `AlertCircle` import 清理
- 搜索按钮 copy contract
- 热门板块 badge contract
- debug summary copy contract
- API 请求、结果解析或交互逻辑变更
- 页面结构、样式或交互行为调整

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- 只针对 `PageHeader.subtitle` 的 copy contract 收口

Excluded:

- `AlertCircle` import
- `STATUS_COPY.*`
- 热门板块 badge 区块
- debug `<summary>`
- 搜索按钮文案
- `fetchApi` 逻辑
- 结果区其余结构

## 3. Existing Context

当前 `StockCheck` 线已经完成：

1. shared-shell adoption
2. button copy contract
3. hot-sector badge status contract
4. debug summary copy contract

在这些切片之后，`StockCheck.jsx` 相对 `HEAD` 的剩余 drift 只剩两类：

1. 页头 subtitle 文案
   - `输入股票代码，核验筛选器 / 热门板块 / 老鸭头 / 确定性`
   - `输入股票代码，核验筛选器、热门板块、形态与确定性`
2. import 漂移
   - `AlertCircle`

这两类内容虽然都位于同一文件，但职责不同：

- subtitle 属于用户可见 header copy contract
- `AlertCircle` import 属于整洁性清理，不是用户可见 contract

当前代码与测试已经给出可核验事实：

- `PageHeader` 位于 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx#L50-L53)
- subtitle 当前剩余 drift 位于 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx#L53)
- 当前 [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 还没有直接断言 subtitle 文案

现状风险：

- 如果把 subtitle 与 `AlertCircle` import 一起提交，切片目的会从“header subtitle copy contract”扩大成“copy + cleanup”
- 如果只改生产文案不补测试承接，这条用户可见 copy contract 会缺少显式保护
- 如果顺手改标题、按钮或结果区文案，本轮会从页头 copy 收口扩大成页面级 copy 清理

## 4. Approach Options

### Option A: 只做 subtitle copy contract，并补最小断言（推荐）

仅处理：

- `PageHeader.subtitle` 文案
- `StockCheck.test.jsx` 中一条最小 subtitle 断言

Pros:

- 生产文案与测试形成最小闭环
- 边界足够窄且易于解释
- 不卷入 import 整洁性清理

Cons:

- 会让 `StockCheck.test.jsx` 多承接一条 header copy 断言

### Option B: 只改生产文案，不补测试

Pros:

- 改动最少
- 单点文案收口足够直接

Cons:

- 没有显式测试承接
- 后续难以判断 subtitle contract 是否仍被保护

### Option C: subtitle + `AlertCircle` import 一起做

Pros:

- 一次减少更多剩余 diff

Cons:

- 切片边界扩大
- 用户可见文案与整洁性清理不是同一职责面
- 后续难以解释该切片的唯一目的

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `StockCheck.jsx`
  - 提供页头 subtitle 的统一 copy contract
- `StockCheck.test.jsx`
  - 以最小断言验证 subtitle contract
- `PageHeader`
  - 继续作为既有共享壳层组件被消费，但不在本轮内修改
- `AlertCircle`
  - 继续留待下一条独立切片处理

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `PageHeader.subtitle`
   - `输入股票代码，核验筛选器 / 热门板块 / 老鸭头 / 确定性`
   - `输入股票代码，核验筛选器、热门板块、形态与确定性`
2. 对应测试断言
   - 在页面渲染后断言新 subtitle 存在

本轮不允许顺手改动：

- `AlertCircle` import
- 页头 title
- 搜索按钮文案
- 热门板块 badge
- debug summary
- `fetchApi` 请求参数
- 页面结构和交互逻辑

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不改 `PageHeader` 组件本身
- 不改 badge contract
- 不改按钮 contract
- 不改 debug summary contract
- 不改 API 调用和结果渲染逻辑
- 若测试暴露的是 import、其他 copy 或结构问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证优先采用：

1. `StockCheck.test.jsx` 通过
2. 在现有页面渲染用例中增加一条 subtitle 文案断言

默认不要求：

- 新增独立测试文件
- 其他页面测试
- 全量前端测试矩阵

原因：

- 当前 `StockCheck.test.jsx` 已覆盖页面主路径，复用现有 carrier 的成本最低
- subtitle 是单点文案，不值得为此新建独立 carrier

## 7. Validation

预期验证命令：

- `npm test -- src/pages/StockCheck.test.jsx`

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `StockCheck.jsx` 中 `PageHeader.subtitle` 的最小 hunk
- `StockCheck.test.jsx` 中对应断言的最小 hunk

必须排除：

- `AlertCircle` import
- 搜索按钮文案
- badge status contract
- debug summary contract
- API 逻辑

若相对 `HEAD` 无法从相邻 diff 中安全隔离 subtitle copy contract，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
