# Lowfreq Manual Actions Duplicate Cleanup Design

Date: 2026-07-09

## 1. Goal

本切片只处理 `Lowfreq.test.jsx` 中 `manual actions` 重复断言的去肥，不改任何生产代码。

目标是：

- 删除 `Lowfreq.test.jsx` 中与独立测试载体重复的 `manual actions` 用例
- 保持 `Lowfreq.manualActionsContract.test.jsx` 作为该主题的唯一权威测试载体
- 继续收窄 `Lowfreq.test.jsx` 的职责，降低后续 drift 审计成本

本切片不是：

- `Lowfreq` 功能变更
- `manual actions` 交互重做
- `Lowfreq` 全量测试重构

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`
- 只针对 `manual actions` 重复断言的最小去重

Excluded:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `Lowfreq.toolsTab.test.jsx`
- `Lowfreq.backtestUxDetailLink.test.jsx`
- `Lowfreq.scorePoolBaseline.test.jsx`
- `Lowfreq.candidatesWorkbenchSplit.test.jsx`
- `Lowfreq` 其他重复主题的去肥
- 任意生产代码或路由改动

## 3. Existing Context

当前 `Lowfreq.test.jsx` 是一个混合型 omnibus test 载体，已经同时承接多条主题。

其中 `manual actions` 主题已经有独立载体：

- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`

该独立载体已经完整覆盖：

1. `买进(T+1)` 调用 `POST /api/lowfreq-score/manual/buy-intent`
2. buy intent payload 中：
   - `sector === '机器人'`
   - `requested_date === '2026-06-09'`
   - `requested_by === 'dashboard.react'`
3. `放弃` 调用 `POST /api/lowfreq-score/manual/abandon`
4. abandon payload 中：
   - `requested_date === '2026-06-09'`
   - `requested_by === 'dashboard.react'`
5. 旧 endpoint 不再被调用

但同样的主题仍保留在 `Lowfreq.test.jsx` 中，形成重复职责。

现状风险：

- 当 `manual actions` contract 变化时，可能出现两个测试文件同时失败，增加定位噪音
- 后续继续审计 `Lowfreq.test.jsx` 时，很难快速区分“仍应保留的真实职责”和“已经迁出的旧主题”
- 若继续保留重复断言，会阻碍后续更系统的 omnibus 去肥

## 4. Approach Options

### Option A: 只删除 `manual actions` 重复用例（推荐）

只从 `Lowfreq.test.jsx` 中删掉与独立 carrier 完全重叠的两条 `manual actions` 用例。

Pros:

- 边界仍然很窄
- 不触碰生产代码
- 不影响其他测试主题
- 适合作为 `tools tab` 之后的下一条去肥线

Cons:

- `Lowfreq.test.jsx` 仍然保留其他重复主题，不能一次性变干净

### Option B: 一次删掉所有已有独立 carrier 的重复用例

同时删除 `manual actions`、`backtest UX`、`scorePool baseline` 等重复断言。

Pros:

- 去肥效果更明显

Cons:

- 风险显著放大
- 边界不再是最小 hunk
- 一旦失败，难判断是哪条主题断裂

### Option C: 保留 `Lowfreq.test.jsx` 中的重复断言，仅依赖独立 carrier 继续演进

不删除任何旧断言。

Pros:

- 不改旧文件

Cons:

- 重复职责继续累积
- 与阶段性审计和原子化测试收口原则冲突

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后测试职责应明确为：

- `Lowfreq.manualActionsContract.test.jsx`：
  - 作为 `manual actions` 唯一权威测试载体
- `Lowfreq.test.jsx`：
  - 不再承担 `manual actions` contract 验证
  - 只保留当前尚未迁出的其他主题

### 5.2 Removal Strategy

本切片只删除 `Lowfreq.test.jsx` 中这两个重复用例：

- `creates a buy intent from candidates tab`
- `records abandon action from candidates tab via lowfreq-score endpoint`

不允许顺手删除：

- `tools tab` 相关用例
- `backtest` 相关用例
- `scorePool` 相关用例
- `sector_name` 展示相关用例

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `Lowfreq.manualActionsContract.test.jsx` 的行为断言范围
- 不修改 `Lowfreq.jsx`
- 不修改共享 mock 结构，除非删除这两条用例后出现显式未使用依赖且能最小清理
- 不把这次去肥扩大成“Lowfreq.test.jsx 大扫除”

## 6. Testing Design

验证只需要覆盖两件事：

1. `Lowfreq.manualActionsContract.test.jsx` 继续通过，证明独立 carrier 足以承担该主题
2. `Lowfreq.test.jsx` 在删除重复用例后仍通过，证明没有留下隐式依赖裂缝

不要求：

- 全量 `Lowfreq` 测试矩阵
- `App` 层回归
- 生产代码验证

## 7. Validation

预期验证命令：

- `npm test -- src/pages/Lowfreq.manualActionsContract.test.jsx`
- `npm test -- src/pages/Lowfreq.test.jsx`

## 8. Commit Boundary

目标提交应限制为：

- `Lowfreq.test.jsx` 中两条 `manual actions` 重复用例的最小删除 hunk

可选最小附带项：

- 若删除该用例后出现明显未使用 import / helper，并且能以最小 hunk 一并清理，可纳入提交

必须排除：

- `Lowfreq.jsx`
- 其他测试文件
- `tools tab` / `scorePool` / `backtest` / `candidates` 主题
