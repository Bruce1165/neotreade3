# Lowfreq Manual Actions Contract Design

Date: 2026-07-09

## 1. Goal

本切片只解决 `Lowfreq` 中人工动作提交链路的 contract 收口问题：

- `买进(T+1)` 提交必须走 `POST /api/lowfreq-score/manual/buy-intent`
- `放弃` 提交必须走 `POST /api/lowfreq-score/manual/abandon`
- 提交载荷中的 `sector` 必须统一使用展示层已经确认的板块名，而不是遗留编码或旧字段

目标：

- 把人工动作链路从当前混杂的工作台/布局/文案主题中单独剥离出来
- 为 buy / abandon 两条提交 contract 建立独立测试载体
- 避免继续把这类 contract 行为堆进 `Lowfreq.test.jsx`

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 一个新的聚焦测试载体
- `handleBuyIntent()` / `handleAbandon()` 的 contract 收口
- 对 `sector` 提交值的最小一致性收口

Excluded:

- `CandidatesPanel` 双栏布局与 `人工动作区 / 候选阅读区` 文案
- `PageHeader` / `ModeOverviewPanel` / `MetricCard` / `STATUS_COPY`
- `scorePool` baseline / request guard / drilldown
- `backtest` 状态轮询、详情链接、end date sync
- `App.jsx` / 路由 / 新页面
- 后端 API 或数据库变更

## 3. Existing Context

当前工作区里，`Lowfreq.jsx` 与 `Lowfreq.test.jsx` 混有多条主题，但人工动作 contract 具备独立成刀的条件：

1. 生产代码中动作入口已经集中到两个函数：
   - `handleBuyIntent()`
   - `handleAbandon()`
2. buy / abandon 的 contract 断言已出现在 `Lowfreq.test.jsx` 中，但目前与工作台布局、tab 文案、backtest 行为混在一起
3. 该主题的行为边界清晰，不依赖 `App`、route、shared foundation 或 scorePool 页面结构

现状风险：

- 如果继续把 buy / abandon 断言留在 `Lowfreq.test.jsx`，会进一步加重 omnibus test
- 当前工作区的候选区 UI 与 contract 行为缠在一起，提交时容易混入布局/文案漂移
- 若 `sector` 继续直接取旧字段，可能出现 UI 展示值与提交值不一致

## 4. Approach Options

### Option A: Contract Only（推荐）

只收口动作提交 endpoint 与 payload，不处理候选区布局和动作区呈现。

Pros:

- 边界最窄
- 与已有双栏布局主题解耦
- 最适合将 contract 测试从 `Lowfreq.test.jsx` 中剥离

Cons:

- UI 结构上的重复/文案问题留待后续单独处理

### Option B: Contract + Candidates UI

一并处理动作 endpoint 与候选区双栏布局。

Pros:

- 一次把“动作在哪里”和“动作怎么提交”都整理完

Cons:

- 会把 contract 收口和布局主题混为一刀
- 提交边界显著放大

### Option C: Contract + Shared Copy

在动作 contract 收口时顺带统一 `STATUS_COPY` 文案。

Pros:

- 表达一致性更强

Cons:

- 会跨入 shared foundation 主题
- 和当前“只收口动作链路”的目标不一致

Decision:

- choose Option A

## 5. Design

### 5.1 Production Boundary

本切片只允许修改 `Lowfreq.jsx` 中与人工动作直接相关的最小逻辑：

- `handleBuyIntent()`
- `handleAbandon()`
- 相关的最小 payload 构造

不允许顺手修改：

- `CandidatesPanel` 布局
- `scorePool` / `backtest` / `tools`
- shared 组件或文案体系

### 5.2 Buy Intent Contract

`handleBuyIntent(candidate)` 需要满足：

- endpoint: `POST /api/lowfreq-score/manual/buy-intent`
- payload fields:
  - `code`
  - `name`
  - `sector`
  - `role`
  - `buy_score`
  - `requested_date`
  - `requested_by`

其中：

- `requested_date` 必须等于当前 `selectedDate`
- `requested_by` 固定为 `dashboard.react`
- `sector` 必须使用 `displaySectorName(candidate)` 的结果，保证提交值与页面展示语义一致

### 5.3 Abandon Contract

`handleAbandon(candidate)` 需要满足：

- endpoint: `POST /api/lowfreq-score/manual/abandon`
- payload fields:
  - `code`
  - `requested_date`
  - `requested_by`

其中：

- `requested_date` 必须等于当前 `selectedDate`
- `requested_by` 固定为 `dashboard.react`

### 5.4 Error / Refresh Behavior

本切片保持当前最小行为，不新增交互：

- 成功后继续 `await fetchData()`
- 失败后继续写入 `setError(e.message || String(e))`
- 不新增 toast
- 不新增局部 loading UI
- 不调整 posting flag 机制

### 5.5 Boundary Guardrails

实现时必须遵守：

- 不新增新的动作类型
- 不改按钮禁用条件
- 不改 `CandidatesPanel` 呈现结构
- 不改回测、股票池、工具页签行为
- 不把已有独立测试主题再次并入新 carrier

## 6. Testing Design

新增一个 focused test 文件，建议命名：

- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`

最少覆盖：

1. 从候选 tab 触发 `买进(T+1)` 时：
   - 调用 `POST /api/lowfreq-score/manual/buy-intent`
   - payload 中 `requested_date === selectedDate`
   - payload 中 `requested_by === 'dashboard.react'`
   - payload 中 `sector` 为展示名，例如 `机器人`
   - 明确不再调用旧 endpoint `POST /api/lowfreq/manual/buy-intent`
2. 从候选 tab 触发 `放弃` 时：
   - 调用 `POST /api/lowfreq-score/manual/abandon`
   - payload 中 `requested_date === selectedDate`
   - payload 中 `requested_by === 'dashboard.react'`
   - 明确不再调用旧 endpoint `POST /api/lowfreq/manual/abandon`

测试策略：

- 只保留触发动作所需的最小页面上下文
- 不在本文件中复验 `候选阅读区 / 人工动作区` 布局
- 不在本文件中复验 `scorePool`、`backtest`、`tools`
- 将现有 `Lowfreq.test.jsx` 中对应 buy / abandon contract 断言迁出或去重，避免重复职责

## 7. Validation

预期校验：

- 跑新的 focused test（manual actions contract）
- 必要时补跑一次最小 `Lowfreq` 相关回归，仅限动作链路直接依赖

不要求：

- 全量 `Lowfreq.test.jsx`
- `App` 级测试
- 后端测试
- 其他 tab 的回归

## 8. Commit Boundary

目标提交只包含：

- `Lowfreq.jsx` 中 buy / abandon contract 的最小 hunk
- `Lowfreq.manualActionsContract.test.jsx`
- 如有必要，`Lowfreq.test.jsx` 中与 buy / abandon contract 直接重复的最小移除 hunk

必须排除：

- 候选区双栏布局
- `tools tab`
- `scorePool` baseline / request guard / drilldown
- `backtest` UX / detail link / end date sync
- `PageHeader` / `ModeOverviewPanel` / `MetricCard` / `STATUS_COPY` 的 shared 收口
