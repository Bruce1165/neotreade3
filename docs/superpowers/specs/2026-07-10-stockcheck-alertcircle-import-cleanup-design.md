# StockCheck AlertCircle Import Cleanup Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `StockCheck` 页面中未使用的 `AlertCircle` import 清理，不改页面文案、不改状态契约、不改 API 行为、不改结构与交互。

目标是：

- 清除 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx#L1-L3) 中未被消费的 `AlertCircle` import
- 让 `StockCheck.jsx` 的剩余工作区漂移从“功能/文案主题”收口到单点整洁性主题
- 以最小验证证明本轮没有引入行为变化

本切片不是：

- `PageHeader.subtitle` copy contract
- 搜索按钮 copy contract
- 热门板块 badge contract
- debug summary copy contract
- API 请求、结果解析或交互逻辑变更
- 页面结构、样式或交互行为调整

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- 只针对未使用的 `AlertCircle` import 清理

Excluded:

- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- `STATUS_COPY.*`
- 页头 subtitle
- 搜索按钮文案
- 热门板块 badge 区块
- debug `<summary>`
- `fetchApi` 逻辑
- 结果区其余结构

## 3. Existing Context

当前 `StockCheck` 线已经完成：

1. shared-shell adoption
2. button copy contract
3. hot-sector badge status contract
4. debug summary copy contract
5. header subtitle copy contract

在这些切片之后，`StockCheck.jsx` 相对 `HEAD` 的剩余 drift 只剩一类：

1. import 漂移
   - `AlertCircle`

当前代码与 diff 已给出可核验证据：

- [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx#L1-L3) 当前 import 为 `Search, AlertCircle, TrendingUp, Layers, Target`
- `AlertCircle` 在 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 中只出现一次，即 import 行
- `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.jsx` 当前只剩这一处 import 变化

现状风险：

- 如果把该 import 清理与其他页面文案或结构调整混做，会把“整洁性清理”扩大成混合主题提交
- 如果在清理 import 时顺手改 JSX、文案或逻辑，本轮将失去单一目的
- 如果为了给 import 清理补测试而改动无关测试载体，本轮会从整洁性主题扩大成测试主题

## 4. Approach Options

### Option A: 只删除未使用的 `AlertCircle` import（推荐）

仅处理：

- `StockCheck.jsx` import 行中移除 `AlertCircle`

Pros:

- 边界最窄，和当前剩余 drift 完全对齐
- 不引入新的测试或行为变更
- 易于从相对 `HEAD` 视角解释提交目的

Cons:

- 本轮没有新增测试承接，只依赖现有 focused test 回归验证

### Option B: 删除 import，并顺手做同文件整洁性整理

Pros:

- 一次清掉更多表层噪音

Cons:

- 超出已审计边界
- 容易把整洁性清理扩成“代码风格整理”
- 与当前相对 `HEAD` 的证据不匹配

### Option C: 保留 import，不单独处理

Pros:

- 不新增提交

Cons:

- 剩余 drift 长期滞留
- 当前 `StockCheck` 线无法完成工作区收口

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `StockCheck.jsx`
  - 只保留实际被页面消费的 icon import
- `AlertCircle`
  - 不再作为 `StockCheck` 页面的依赖出现
- 现有测试载体
  - 继续只做回归验证，不在本轮新增职责

### 5.2 Cleanup Strategy

本切片只允许对以下点位做改动：

1. `StockCheck.jsx` import 行
   - `Search, AlertCircle, TrendingUp, Layers, Target`
   - `Search, TrendingUp, Layers, Target`

本轮不允许顺手改动：

- 任何 JSX 渲染内容
- 页头 title / subtitle
- 搜索按钮文案
- 热门板块 badge
- debug summary
- `fetchApi` 请求参数
- 页面结构和交互逻辑

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不新增测试文件
- 不修改 `StockCheck.test.jsx`
- 不更换 icon、样式或组件结构
- 若验证暴露的是其他 copy、结构或逻辑问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证优先采用：

1. `StockCheck.test.jsx` 通过

默认不要求：

- 新增独立测试文件
- 补 import 清理专用断言
- 其他页面测试
- 全量前端测试矩阵

原因：

- 本轮是未使用 import 清理，不涉及用户可见 contract
- 当前 [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 已能回归页面主路径

## 7. Validation

预期验证命令：

- `npm test -- src/pages/StockCheck.test.jsx`

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `StockCheck.jsx` import 行的最小 hunk

必须排除：

- `StockCheck.test.jsx`
- subtitle、按钮、badge、debug summary
- API 逻辑
- 结构与样式改动

若相对 `HEAD` 无法把 import cleanup 安全隔离为单一目的提交，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
