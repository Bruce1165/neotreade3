# Lowfreq Candidates Carrier Realignment Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `Lowfreq` 候选工作台独立测试载体的职责重新对齐，不改任何生产代码。

目标是：

- 修正 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 与当前 `Lowfreq.jsx` 候选区语义之间的漂移
- 让 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 只承担“阅读区 / 动作区分离”这一主题
- 让 `Lowfreq.manualActionsContract.test.jsx` 继续作为人工动作 endpoint contract 的唯一权威测试载体
- 避免一个 focused carrier 同时承接布局职责和接口契约职责

本切片不是：

- `Lowfreq.jsx` 功能变更
- 候选区 UI 重做
- 人工动作 contract 变更
- `Lowfreq` 全量测试重构

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`
- 只针对候选工作台 focused carrier 的职责收口

Excluded:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- `Lowfreq.scorePoolBaseline.test.jsx`
- `Lowfreq.scorePoolRequestGuard.test.jsx`
- `Lowfreq.backtestUxDetailLink.test.jsx`
- `Lowfreq.toolsTab.test.jsx`
- 任意生产代码、路由或共享组件改动

## 3. Existing Context

当前 `Lowfreq.jsx` 中候选区的生产语义已经是：

1. tab 文案为 `候选与人工`
2. `CandidatesPanel` 分为 `候选阅读区` 与 `人工动作区`
3. `买进(T+1)` 调用 `POST /api/lowfreq-score/manual/buy-intent`
4. `放弃` 调用 `POST /api/lowfreq-score/manual/abandon`

现有 focused carriers 的职责分布已经部分稳定：

- `Lowfreq.manualActionsContract.test.jsx`
  - 覆盖 `lowfreq-score/manual/*` endpoint contract
  - 验证 payload 关键字段
  - 验证旧 endpoint 不再被调用
- `Lowfreq.candidatesWorkbenchSplit.test.jsx`
  - 原本应覆盖阅读区 / 动作区分离
  - 但当前仍包含旧 tab 文案 `候选池`
  - 仍断言旧 endpoint `/api/lowfreq/manual/*`

这意味着 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 已经发生两类漂移：

- 对生产 UI 入口文案的漂移
- 对 focused carrier 职责边界的漂移

现状风险：

- 同一人工动作 contract 同时在两个 focused carriers 中被断言，导致责任重叠
- 当 endpoint contract 变化时，会出现多文件同时失败，增加定位噪音
- `candidatesWorkbenchSplit` 主题本身反而失去“只验证布局分离”的清晰边界

## 4. Approach Options

### Option A: 只重对齐 `candidatesWorkbenchSplit` 职责（推荐）

更新 `Lowfreq.candidatesWorkbenchSplit.test.jsx`：

- 改成使用当前 tab 文案 `候选与人工`
- 保留“阅读区 / 动作区分离”断言
- 删除或收缩人工动作 endpoint contract 断言

Pros:

- 边界最窄
- 不触碰生产代码
- 与现有 focused carrier 分工一致
- 适合作为当前 `Lowfreq` 剩余 drift 的下一条最小测试线

Cons:

- 不能一次解决 `Lowfreq.jsx` 中其他生产 drift

### Option B: 同时改 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 与 `Lowfreq.manualActionsContract.test.jsx`

重新拆分两份 focused carrier，使两边的职责重新分摊。

Pros:

- 分工可以更彻底梳理

Cons:

- 会扩大边界
- 当前 `manualActionsContract` 已经稳定，无需再动

### Option C: 保留现状，等后续 `Lowfreq.jsx` 收口时一起处理

暂不修正 focused carrier 漂移。

Pros:

- 当前不需要改测试文件

Cons:

- 错误职责继续滞留
- focused carrier 的边界会越来越模糊
- 不符合阶段性去肥与职责唯一性原则

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后测试职责应明确为：

- `Lowfreq.candidatesWorkbenchSplit.test.jsx`
  - 只验证候选区是否仍然保持 `阅读区 + 动作区` 分栏结构
  - 只验证已排队 / 已放弃对象不进入待处理列表
  - 可以保留动作区按钮存在性断言
  - 不再验证 buy / abandon 的网络 contract
- `Lowfreq.manualActionsContract.test.jsx`
  - 继续独占 buy / abandon endpoint contract
  - 继续独占 payload 关键字段与旧 endpoint 排除断言

### 5.2 Realignment Strategy

本切片只允许对 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 做以下调整：

- 将 tab 入口从 `候选池` 更新为 `候选与人工`
- 保留 `候选阅读区` / `人工动作区` / `待处理列表` 的布局断言
- 保留队列项与放弃项不进入待处理列表的断言
- 删除或改写第二条用例中关于 `/api/lowfreq/manual/*` 的 endpoint contract 断言

推荐收口方式：

- 第一条用例保留为“布局 + 待处理过滤”权威断言
- 第二条用例若仍保留，仅验证动作区按钮在当前布局下仍可交互触发，不承担 endpoint payload contract
- 若第二条用例在收口后不再有独立价值，可直接删除，避免形成新的半重复职责

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `Lowfreq.manualActionsContract.test.jsx` 的断言范围
- 不修改 `Lowfreq.jsx`
- 不把本切片扩大成 `Lowfreq` 候选区 UI 调整
- 不把旧 endpoint contract 从一个错误 carrier 挪到另一个无关 carrier
- 若清理后出现显式未使用 mock / helper，可做最小附带清理，但不能顺手重写整个文件

## 6. Testing Design

验证只需要覆盖两件事：

1. `Lowfreq.candidatesWorkbenchSplit.test.jsx` 在收口后继续通过，证明候选工作台分栏职责仍被独立承接
2. `Lowfreq.manualActionsContract.test.jsx` 继续通过，证明人工动作 contract 仍由唯一权威 carrier 承接

不要求：

- 全量 `Lowfreq` 测试矩阵
- `Lowfreq.test.jsx` 回归
- 任意生产代码验证

## 7. Validation

预期验证命令：

- `npm test -- src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx`
- `npm test -- src/pages/Lowfreq.manualActionsContract.test.jsx`

## 8. Commit Boundary

目标提交应限制为：

- `Lowfreq.candidatesWorkbenchSplit.test.jsx` 的最小职责重对齐 hunk
- 如有必要，最小的未使用依赖清理

必须排除：

- `Lowfreq.jsx`
- `Lowfreq.manualActionsContract.test.jsx`
- `Lowfreq.test.jsx`
- 其他 focused carriers
- 任何生产行为改动
