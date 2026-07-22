# Lowfreq Backtest UX Duplicate Cleanup Design

Date: 2026-07-09

## 1. Goal

本切片只处理当前工作区中 `Lowfreq.test.jsx` 与独立 `backtest UX/detail link` 测试载体之间的重复职责收口，不改任何生产代码。

目标是：

- 删除 `Lowfreq.test.jsx` 中与独立测试载体重复的 `backtest UX/detail link` 用例
- 保持 `Lowfreq.backtestUxDetailLink.test.jsx` 作为该主题的唯一权威测试载体
- 用“工作区去肥收口”的方式继续收窄 `Lowfreq.test.jsx` 的职责

本切片不是：

- `Lowfreq` 功能变更
- `backtest` 交互或轮询逻辑重做
- `Lowfreq` 全量测试重构

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx`
- 只针对 `backtest UX/detail link` 重复断言的最小去重

Excluded:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `Lowfreq.manualActionsContract.test.jsx`
- `Lowfreq.toolsTab.test.jsx`
- `Lowfreq.scorePoolBaseline.test.jsx`
- `Lowfreq.candidatesWorkbenchSplit.test.jsx`
- `Lowfreq` 其他重复主题的去肥
- 任意生产代码或路由改动

## 3. Existing Context

当前 `Lowfreq.test.jsx` 是一个混合型 omnibus test 载体，已经同时承接多条主题。

其中 `backtest UX/detail link` 主题已经有独立载体：

- `neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx`

该独立载体已经完整覆盖：

1. `unknown` 状态进入 `回测状态异常`，不再无限显示 `报告生成中`
2. `done` 状态显示 `execution_mode`
3. 当前报告显示 `查看明细` 跳转
4. 历史报告使用详情页链接，并在缺失明细时隐藏链接

当前工作区中的 `Lowfreq.test.jsx` 仍包含 3 条相同主题的用例：

- `treats unknown backtest status as an error state instead of endless running`
- `shows execution mode when backtest status resolves to done`
- `uses detail page links for history reports and hides missing detail links`

但和前面的 `tools tab`、`manual actions` 不同，这 3 条更像当前工作区的回流漂移，而不是已确定存在于 `HEAD` 中的旧职责残留。

这意味着：

- 本轮目标首先是工作区去肥收口
- 只有在相对 `HEAD` 仍形成真实最小差异时，才进入提交

现状风险：

- 若误把当前工作区回流当作已存在于 `HEAD` 的旧职责，容易提前承诺一个并不存在的提交切片
- 若一次性删除 3 条 backtest 用例并顺手整理共享 mock，边界很容易从“去肥”扩张成“回测测试重构”
- `backtest` 主题依赖 `localStorage`、状态轮询、历史报告与当前报告，验证面比 `tools tab` / `manual actions` 更大

## 4. Approach Options

### Option A: 只做工作区去肥收口（推荐）

先从 `Lowfreq.test.jsx` 删除这 3 条重复用例，再核对相对 `HEAD` 是否仍存在可提交的最小差异。

Pros:

- 结论与当前证据一致
- 不预设一定有 commit
- 最符合当前工作区真实状态

Cons:

- 可能最后只完成工作区收口而不产生新提交

### Option B: 预设为原子化提交切片

直接把这 3 条去重视为一条必然可提交的测试去肥切片。

Pros:

- 节奏看起来更线性

Cons:

- 与当前证据不足的现实冲突
- 容易把“工作区回流”误说成“HEAD 已有旧职责”

### Option C: 暂不处理，先转去 `scorePool baseline`

跳过 `backtest`，先处理别的重复主题。

Pros:

- 避开 `backtest` 较大的验证面

Cons:

- 当前已识别出的重复职责继续堆在 `Lowfreq.test.jsx`
- 不利于持续推进工作区去肥

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后测试职责应明确为：

- `Lowfreq.backtestUxDetailLink.test.jsx`：
  - 作为 `backtest UX/detail link` 唯一权威测试载体
- `Lowfreq.test.jsx`：
  - 不再承担该主题验证
  - 只保留当前尚未迁出的其他主题

### 5.2 Removal Strategy

本切片只删除 `Lowfreq.test.jsx` 中这 3 条重复用例：

- `treats unknown backtest status as an error state instead of endless running`
- `shows execution mode when backtest status resolves to done`
- `uses detail page links for history reports and hides missing detail links`

不允许顺手删除：

- `manual actions` 相关用例
- `tools tab` 相关用例
- `scorePool` 相关用例
- `sector_name` 展示相关用例

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `Lowfreq.backtestUxDetailLink.test.jsx` 的行为断言范围
- 不修改 `Lowfreq.jsx`
- 不修改共享 mock 结构，除非删除这 3 条用例后出现显式未使用依赖且能最小清理
- 不把这次去肥扩大成“Lowfreq.test.jsx 大扫除”
- 在提交前必须再次核对相对 `HEAD` 是否仍形成真实差异

## 6. Testing Design

验证只需要覆盖两件事：

1. `Lowfreq.backtestUxDetailLink.test.jsx` 继续通过，证明独立 carrier 足以承担该主题
2. `Lowfreq.test.jsx` 在删除重复用例后仍通过，证明没有留下隐式依赖裂缝

不要求：

- 全量 `Lowfreq` 测试矩阵
- `App` 层回归
- 生产代码验证

## 7. Validation

预期验证命令：

- `npm test -- src/pages/Lowfreq.backtestUxDetailLink.test.jsx`
- `npm test -- src/pages/Lowfreq.test.jsx`

## 8. Commit Boundary

默认目标是“工作区收口”，不是预设“必有提交”。

若相对 `HEAD` 仍存在真实最小差异，提交应限制为：

- `Lowfreq.test.jsx` 中这 3 条 `backtest UX/detail link` 重复用例的最小删除 hunk

可选最小附带项：

- 若删除该用例后出现明显未使用 import / helper，并且能以最小 hunk 一并清理，可纳入提交

必须排除：

- `Lowfreq.jsx`
- 其他测试文件
- `manual actions` / `tools tab` / `scorePool` / `candidates` 主题

若相对 `HEAD` 不存在真实最小差异，则本轮结论应明确为：

- “已完成工作区去肥收口，不产生新 commit”
