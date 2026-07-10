# Lowfreq Candidates Status-Copy Alignment Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `Lowfreq.jsx` 中 `CandidatesPanel` 的状态文案来源收口，不改页面壳层、不改回测区、不改数据流。

目标是：

- 将 `CandidatesPanel` 内已经属于候选状态语义的文案统一收口到 `STATUS_COPY` 契约
- 让统计卡、待处理列表 badge、跟随角色禁用提示使用同一状态文案来源
- 在不卷入 `PageHeader`、`ModeOverviewPanel` 或其他相邻 drift 的前提下，完成一个最小生产切片

本切片不是：

- `Lowfreq` 整页文案统一
- `PageHeader` 接入或页面壳层升级
- `ModeOverviewPanel` 引入或说明文案调整
- `BacktestPanel` 或 `scorePool` 改动
- `CandidatesPanel` 结构重排、样式整理或交互逻辑变更

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `CandidatesPanel` 内与以下状态文案点位直接相关的最小 hunk
  - 统计卡标题
  - 待处理列表 badge 文案
  - 跟随角色按钮禁用提示
- 只针对 `STATUS_COPY` 状态文案契约收口

Excluded:

- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- `PageHeader`
- `ModeOverviewPanel`
- `BacktestPanel`
- `scorePool` 请求链路与展示
- `CandidatesPanel` 的 JSX 结构整理、class 顺序调整、格式化重排

## 3. Existing Context

当前 `Lowfreq.jsx` 中，候选状态语义已经存在统一常量契约：

- `STATUS_COPY.actionable`
- `STATUS_COPY.observing`
- `STATUS_COPY.queued`
- `STATUS_COPY.abandoned`
- `STATUS_COPY.followerObserving`

而 `Lowfreq.jsx` 内部现状是“部分已收口，部分仍使用字面量”的混合状态：

1. 候选状态映射函数已经使用 `STATUS_COPY.*`
2. 候选阅读区的状态 badge 已经使用 `STATUS_COPY.*`
3. 人工动作区统计卡仍是局部独立标题
4. 待处理列表 badge 已部分切换到 `STATUS_COPY.*`
5. 跟随角色按钮的禁用提示仍需要与统一状态契约保持同源

focused carrier 的现有锚点已经足够支撑这条收口边界：

- `Lowfreq.manualActionsContract.test.jsx`
  - 断言 `候选与人工` 页签
  - 断言 `人工动作区`
  - 断言人工动作网络 contract
- `Lowfreq.candidatesWorkbenchSplit.test.jsx`
  - 断言 `候选阅读区` / `人工动作区` 分离
  - 断言待处理列表过滤语义

这意味着当前最真实、最小的 production drift 不是页面壳层升级，而是 `CandidatesPanel` 内同一状态语义来源没有完全统一。

现状风险：

- 同一候选状态在同一面板内同时出现常量文案与局部字面量，后续继续演化时容易出现语义漂移
- 若把 `PageHeader` / `ModeOverviewPanel` 一并纳入，会把“状态文案收口”扩大成“页面壳层改造”
- 若等待未来整页收口，本轮已经存在的统一契约就会继续半落地

## 4. Approach Options

### Option A: 只收口 `CandidatesPanel` 状态文案来源（推荐）

仅修改：

- 统计卡标题改为 `STATUS_COPY.actionable / observing / queued / abandoned`
- 待处理列表 badge 改为 `STATUS_COPY.actionable / observing`
- 跟随角色按钮禁用提示改为 `STATUS_COPY.followerObserving`

Pros:

- 与现有 `STATUS_COPY` 契约直接对齐
- 与 focused carrier 的现有断言边界一致
- 边界最窄
- 不触碰页面壳层主题

Cons:

- 不会顺手减少 `Lowfreq.jsx` 中其他主题的 drift

### Option B: 连同 `PageHeader` / `ModeOverviewPanel` 一起收口

把页头标题、模式概览和候选状态文案一起处理。

Pros:

- 一次消化更多工作区 drift

Cons:

- 边界从“状态文案收口”扩大成“页面壳层升级”
- 现有 focused carrier 并未直接承接这组壳层语义
- 提交目的会变得不纯

### Option C: 暂不处理，等待未来整页整理

保留当前混合状态。

Pros:

- 当前不需要修改生产代码

Cons:

- `CandidatesPanel` 内状态文案继续保持双来源
- 已有 `STATUS_COPY` 契约无法在该区域完全落地
- 后续更难解释哪些文案属于统一状态语义，哪些只是局部 UI copy

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `STATUS_COPY`
  - 继续作为候选状态文案的统一来源
- `CandidatesPanel`
  - 只消费 `STATUS_COPY`，不再在同一状态语义上保留独立标题字面量
- focused carriers
  - 继续验证候选页签、布局分区与人工动作 contract
  - 不需要因为本轮文案来源收口而改变职责

### 5.2 Alignment Strategy

本切片只允许修改 `CandidatesPanel` 中以下点位：

1. 人工动作区统计卡标题
   - `可出手` -> `STATUS_COPY.actionable`
   - `观察` -> `STATUS_COPY.observing`
   - `已排队` -> `STATUS_COPY.queued`
   - `已放弃` -> `STATUS_COPY.abandoned`
2. 待处理列表状态 badge
   - `可出手` -> `STATUS_COPY.actionable`
   - `观察` -> `STATUS_COPY.observing`
3. 跟随角色按钮禁用提示
   - `跟随仅观察` -> `STATUS_COPY.followerObserving`

除了上述点位，本轮不允许顺手改动：

- `CandidatesPanel` JSX 结构
- 布局栅格、spacing、className 顺序
- 按钮文案 `买进(T+1)` / `放弃`
- 副标题说明，如 `满足条件且非跟随`
- 页头标题与模式说明文案

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `PageHeader`
- 不修改 `ModeOverviewPanel`
- 不修改 `BacktestPanel`
- 不修改 `manual actions` 的请求 contract 与 payload
- 不修改 focused carrier 的职责范围，除非出现由本轮语法/结构问题导致的必要修复
- 若目标点位与相邻 drift 共处同一混合 hunk，必须先判断是否可安全隔离；不能隔离则暂停提交判断，而不是静默扩大范围

## 6. Testing Design

验证只需要覆盖：

1. `Lowfreq.manualActionsContract.test.jsx` 继续通过，证明人工动作区交互与 contract 未受影响
2. `Lowfreq.candidatesWorkbenchSplit.test.jsx` 继续通过，证明阅读区 / 动作区分离职责未受影响

默认不要求：

- 全量 `Lowfreq` 测试矩阵
- `Lowfreq.test.jsx` 全文件回归
- `App` 层回归

## 7. Validation

预期验证命令：

- `npm test -- src/pages/Lowfreq.manualActionsContract.test.jsx`
- `npm test -- src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx`

若实现后判断首页基础装载区域存在意外耦合，可增加：

- `npm test -- src/pages/Lowfreq.test.jsx`

但这不是默认必跑项。

## 8. Commit Boundary

目标提交应限制为：

- `Lowfreq.jsx` 中 `CandidatesPanel` 状态文案来源收口的最小 hunk

允许的最小附带项：

- 若同一逻辑块内存在必须一起修改的同源 `STATUS_COPY` 点位，可一并纳入

必须排除：

- `PageHeader`
- `ModeOverviewPanel`
- `BacktestPanel`
- `scorePool` 请求保护或展示改动
- `CandidatesPanel` 结构整理与格式化重排
- 其他文件

若相对 `HEAD` 无法从邻近 drift 中安全隔离该 hunk，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
