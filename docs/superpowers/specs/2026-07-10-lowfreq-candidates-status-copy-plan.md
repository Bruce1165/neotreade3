# Lowfreq Candidates Status-Copy Alignment Plan

Date: 2026-07-10  
Related design: `docs/superpowers/specs/2026-07-10-lowfreq-candidates-status-copy-design.md`

## 1. Goal

本计划只覆盖 `Lowfreq.jsx` 中 `CandidatesPanel` 的状态文案来源收口，不扩展到页面壳层、回测区、`scorePool` 或其他 `Lowfreq` 主题。

本轮只有三个目标：

1. 将 `CandidatesPanel` 中属于候选状态语义的目标点位统一切换到 `STATUS_COPY` 契约。
2. 将实现边界限制在状态文案来源本身，排除相邻的格式整理、结构整理和壳层升级。
3. 通过 focused carriers 验证行为未受影响，并且只在相对 `HEAD` 的 hunk 可安全隔离时才提交。

本轮必须得到的核心结果：

- 人工动作区统计卡标题使用 `STATUS_COPY.actionable / observing / queued / abandoned`
- 待处理列表 badge 使用 `STATUS_COPY.actionable / observing`
- 跟随角色按钮禁用提示使用 `STATUS_COPY.followerObserving`
- 提交中不包含 `PageHeader`、`ModeOverviewPanel` 或其他相邻 UI 整理

## 2. Out Of Scope

- `PageHeader` 标题与副标题替换
- `ModeOverviewPanel` 的引入与文案
- `BacktestPanel` 的任何逻辑、文案或布局
- `scorePool` 请求保护、数据流与展示
- `CandidatesPanel` 的 JSX 结构重排
- `CandidatesPanel` 的 class 顺序、spacing、格式化重排
- `买进(T+1)` / `放弃` 按钮行为或文案变更
- focused test carrier 的职责调整，除非出现真实语法/结构问题

## 3. Current Starting Point

### 3.1 已知事实

- [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 中前部状态映射已经使用 `STATUS_COPY.actionable / observing / queued / abandoned / followerObserving`
- 同文件的 `CandidatesPanel` 中，候选阅读区状态 badge 已部分切换到 `STATUS_COPY.*`
- 仍存在未完全统一的状态文案点位：
  - 统计卡标题
  - 待处理列表 badge
  - 跟随角色按钮禁用提示
- focused carriers 已覆盖该面板的核心契约：
  - [Lowfreq.manualActionsContract.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx)
  - [Lowfreq.candidatesWorkbenchSplit.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx)

### 3.2 结构风险

- 最大风险不是文案替换本身，而是在同一混合 diff 区域中误带入 `PageHeader`、`ModeOverviewPanel` 或格式整理改动
- 如果为了一次多收口而把相邻壳层改造一起提交，本切片就不再是清晰的“状态文案来源收口”
- 如果相对 `HEAD` 不能安全隔离目标点位，强行提交会制造一个目的不纯的 mixed commit

## 4. Implementation Principles

- 只改 `CandidatesPanel` 中已经被 design 明确列出的状态文案点位
- 不改数据流，不改按钮行为，不改 payload，不改网络 contract
- 把相邻的格式化差异视为排除项，即使它们位于同一可视区域
- 优先保持最小生产 hunk，而不是顺手“顺便整理”
- 如果隔离不安全，停止提交判断并汇报边界失败，而不是静默扩大范围

## 5. Allowed Change Boundary

Allowed file:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`

Allowed logic:

- 将统计卡标题替换为：
  - `STATUS_COPY.actionable`
  - `STATUS_COPY.observing`
  - `STATUS_COPY.queued`
  - `STATUS_COPY.abandoned`
- 将待处理列表 badge 替换为：
  - `STATUS_COPY.actionable`
  - `STATUS_COPY.observing`
- 将跟随角色按钮禁用提示替换为：
  - `STATUS_COPY.followerObserving`

Explicitly disallowed:

- 修改 `PageHeader`
- 修改 `ModeOverviewPanel`
- 修改 `BacktestPanel`
- 修改 `scorePool` 逻辑
- 修改 `CandidatesPanel` 布局结构
- 修改按钮文案或点击行为
- 修改 `manual actions` contract
- 修改其他文件

## 6. Execution Stages

本计划分为四个阶段执行：

- `LCS-R1`: 冻结精确目标点位
- `LCS-R2`: 只实施状态文案来源替换
- `LCS-R3`: 跑 focused 验证并检查文件安全
- `LCS-R4`: 只暂存隔离后的 hunk 并提交

## 7. Stage Plan

### LCS-R1: 冻结精确目标点位

Goal:

- 明确 `CandidatesPanel` 中哪些行属于本轮状态文案契约，哪些相邻改动必须排除。

Tasks:

- 读取当前 `CandidatesPanel` 相关区块
- 对照 `HEAD` 检查当前剩余 diff
- 只标记以下目标点位：
  - 四个统计卡标题
  - 两个待处理列表 badge
  - 跟随角色禁用提示
- 显式排除：
  - `PageHeader`
  - `ModeOverviewPanel`
  - 格式化重排
  - 结构变化

Done when:

- include / exclude 列表明确
- 本轮目标点位与相邻 drift 已被清楚分开

### LCS-R2: 只实施状态文案来源替换

Goal:

- 在不改变 `CandidatesPanel` 结构和行为的前提下，将目标点位统一对齐到 `STATUS_COPY`。

Tasks:

- 更新四个统计卡标题到 `STATUS_COPY.*`
- 更新待处理列表 badge 到 `STATUS_COPY.*`
- 更新跟随角色按钮禁用提示到 `STATUS_COPY.followerObserving`

Constraints:

- 不调整 JSX 结构
- 不调整 className 或 spacing
- 不修改按钮可用性逻辑
- 不触碰人工动作请求逻辑

Done when:

- 所有目标点位都切换到 `STATUS_COPY`
- 周围结构与行为保持不变

### LCS-R3: 跑 focused 验证并检查文件安全

Goal:

- 证明本轮仅影响状态文案来源，不影响候选区布局与人工动作 contract。

Tasks:

- 运行 `npm test -- src/pages/Lowfreq.manualActionsContract.test.jsx`
- 运行 `npm test -- src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx`
- 人工检查编辑区是否引入明显语法或结构问题
- 如出现意外耦合，再补跑 `npm test -- src/pages/Lowfreq.test.jsx`

Done when:

- 两个 focused carriers 通过
- 编辑区无明显语法/结构问题

### LCS-R4: 只暂存隔离后的 hunk 并提交

Goal:

- 生成一个单一目的的 production commit，只表达 `CandidatesPanel` 状态文案来源收口。

Tasks:

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 只暂存目标状态文案 hunk
- 排除壳层升级和相邻格式整理
- 仅在 hunk 可安全隔离时提交

Done when:

- staged diff 只包含 `CandidatesPanel` 状态文案来源收口
- 提交中不包含 `PageHeader`、`ModeOverviewPanel` 或其他无关整理

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. File Order

建议执行顺序：

1. 读取当前 `CandidatesPanel` live block
2. 对照 `HEAD` 检查同区块 diff
3. 只改目标状态文案点位
4. 跑两个 focused carriers
5. 再次检查 `HEAD`-relative diff
6. 只暂存有效 hunk

Reason:

- 这样可以先锁定本轮唯一主题，再避免把相邻页面壳层 drift 混入切片
- 先用 focused carriers 验证，再决定是否提交，可以降低 mixed commit 风险

## 9. Proposed Commit Shape

建议单一提交：

### Commit LCS: Lowfreq candidates status-copy alignment

Scope:

- 仅 `Lowfreq.jsx` 中 `CandidatesPanel` 的状态文案来源收口

Purpose:

- 让候选区状态语义统一落到 `STATUS_COPY` 契约

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成壳层+文案的混合提交。

## 10. Minimum Acceptance

本轮完成的最小验收标准：

1. `CandidatesPanel` 统计卡标题使用 `STATUS_COPY.actionable / observing / queued / abandoned`
2. `CandidatesPanel` 待处理列表 badge 使用 `STATUS_COPY.actionable / observing`
3. 跟随角色按钮禁用提示使用 `STATUS_COPY.followerObserving`
4. `Lowfreq.manualActionsContract.test.jsx` 通过
5. `Lowfreq.candidatesWorkbenchSplit.test.jsx` 通过
6. 提交中不包含 `PageHeader`、`ModeOverviewPanel` 或相邻格式整理

## 11. Risks

- 主要风险是从同一 `Lowfreq.jsx` 混合 diff 中误捕获相邻壳层改造
- 第二风险是把格式整理误当成“顺手可带”的低成本改动
- 第三风险是当前工作区已有多主题 drift，导致提交目的描述失真

## 12. Conclusion

本计划不是 `Lowfreq` 整页收口计划，而是一条窄生产线，目标只有三件事：

- 只更新 `CandidatesPanel` 的状态文案来源
- 只用现有 focused carriers 做最小验证
- 只在 hunk 保持隔离与原子性时提交
