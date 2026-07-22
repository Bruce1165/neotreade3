# Lowfreq Backtest Status-Copy Production Alignment Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `Lowfreq.jsx` 中 `BacktestPanel` 的回测状态文案契约对齐，不改回测布局、数据结构、轮询逻辑或详情链接逻辑。

目标是：

- 将 `BacktestPanel` 中已经被 focused carrier 明确依赖的回测状态文案收口到统一 `STATUS_COPY` 契约
- 让生产代码中的 `运行中...`、`报告编号`、`运行方式` 与现有 focused backtest carrier 的断言边界保持一致
- 在不卷入相邻 backtest UI 整理改动的前提下，完成一个最小生产切片

本切片不是：

- `BacktestPanel` 全量重构
- 回测卡片布局优化
- `PageHeader` / `ModeOverviewPanel` / 共享展示组件接入
- 回测详情链接、历史报告表格或日期逻辑改动
- `Lowfreq` 全页 copy 统一

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `BacktestPanel` 内与下列三处文案契约直接相关的最小 hunk
  - `STATUS_COPY.processing`
  - `STATUS_COPY.reportNumber`
  - `STATUS_COPY.runMode`
- 只针对回测状态文案契约收口

Excluded:

- `neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- `Lowfreq` 其他 focused carriers
- `BacktestPanel` 中 spacing / class 顺序 / 条件渲染风格重写
- `BacktestPanel` 中 next candidates 布局调整
- `PageHeader`、`ModeOverviewPanel`、`MetricCard`、`BlockMessage`
- `Lowfreq.jsx` 中 candidates / scorePool / shell 其他主题

## 3. Existing Context

当前 `Lowfreq.jsx` 的 `BacktestPanel` diff 是一个混合区块，其中同时存在：

1. 回测状态文案契约对齐
2. 条件渲染风格清理（`cond ? (...) : null` -> `cond && (...)`）
3. className 顺序与 spacing 调整
4. 下一交易日候选块的小布局变化

其中只有第一类已经有清晰、可核验的 focused carrier 契约支撑：

- `Lowfreq.backtestUxDetailLink.test.jsx`

该 focused carrier 已明确断言：

1. `运行方式：unbounded_opportunity`
2. `报告编号：report-done`
3. 当前报告详情页链接存在
4. 历史报告详情页链接存在且缺失时隐藏

这意味着生产代码中的以下文本属于真实契约面：

- 运行中按钮状态文案
- 报告编号展示前缀
- 运行方式展示前缀

而 `BacktestPanel` 同区块中的其他整理项：

- 不构成现有 focused carrier 的直接契约
- 一旦混入本轮提交，会把边界从“文案契约对齐”扩大成“回测 UI 收口”

现状风险：

- 若把 `BacktestPanel` 相邻 formatting / layout 变化一并纳入，容易制造一个语义不纯的大包 commit
- 若只改部分文案但同时带入条件渲染风格变化，后续很难解释提交真实目的
- 若跳过这三处文案契约，focused carrier 与生产 copy 会继续处于“语义已依赖、实现仍漂移”的状态

## 4. Approach Options

### Option A: 只对齐三处回测状态文案契约（推荐）

仅修改：

- `运行中...` -> `STATUS_COPY.processing`
- `报告编号：...` -> `STATUS_COPY.reportNumber`
- `运行方式：...` -> `STATUS_COPY.runMode`

Pros:

- 与 focused carrier 的真实断言直接对应
- 边界最窄
- 不卷入 backtest 区块其他整理项

Cons:

- 不会顺手改善相邻的视觉与结构漂移

### Option B: 顺手合并整个 `BacktestPanel` 相邻 diff

把条件渲染、spacing、next candidates 布局等一并收口。

Pros:

- 一次性减少更多 drift

Cons:

- 边界明显扩大
- 不再是清晰的“copy-contract alignment”
- 更难形成单主题原子提交

### Option C: 暂不处理，等待未来 `BacktestPanel` 大整理

保留当前 production drift。

Pros:

- 当前不需要动生产代码

Cons:

- focused carrier 已经依赖的 copy 契约继续漂移
- 后续会继续混淆“文案契约”与“布局整理”两类问题

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `Lowfreq.backtestUxDetailLink.test.jsx`
  - 继续作为 backtest UX/detail-link 权威 focused carrier
  - 继续断言 `运行方式`、`报告编号` 与详情页链接契约
- `Lowfreq.jsx` / `BacktestPanel`
  - 只在这三处 copy 接口上对齐到 `STATUS_COPY`
  - 不承担本轮布局或结构整理

### 5.2 Alignment Strategy

本切片只允许修改 `BacktestPanel` 中以下三类点位：

1. 运行按钮 loading 文案
   - `运行中...` -> `STATUS_COPY.processing`
2. 当前结果区中的报告编号前缀
   - `报告编号` -> `STATUS_COPY.reportNumber`
3. 当前结果区中的运行方式前缀
   - `运行方式` -> `STATUS_COPY.runMode`
4. 运行中空态中的报告编号前缀
   - `报告编号` -> `STATUS_COPY.reportNumber`

除了上述点位，本轮不允许顺手改动：

- JSX 结构
- 条件渲染写法
- className 顺序
- grid 顺序
- 候选卡片布局

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `Lowfreq.backtestUxDetailLink.test.jsx`
- 不修改 `BacktestPanel` 中详情链接路径逻辑
- 不修改 `BacktestPanel` 中 `summary` / `reports` / `next_session` 数据使用方式
- 不修改 `Lowfreq.jsx` 中 `scorePool` / `candidates` / `tabs` / `PageHeader`
- 若这三处文案位于更大 diff hunk 中，必须优先评估是否能安全隔离；不能隔离则暂停提交判断，而不是强行扩大范围

## 6. Testing Design

验证只需要覆盖：

1. `Lowfreq.backtestUxDetailLink.test.jsx` 继续通过
2. 如实现后有必要，可补跑最小相关 `Lowfreq.test.jsx` 回测契约用例载体，但不作为默认要求

默认不要求：

- 全量 `Lowfreq` 测试矩阵
- `App` 层回归
- 其他 focused carriers 回归

## 7. Validation

预期验证命令：

- `npm test -- src/pages/Lowfreq.backtestUxDetailLink.test.jsx`

若实现后判断相邻回测区域存在偶发依赖，可增加：

- `npm test -- src/pages/Lowfreq.test.jsx`

但这不是默认必跑项。

## 8. Commit Boundary

目标提交应限制为：

- `Lowfreq.jsx` 中 `BacktestPanel` 的三处状态文案契约对齐最小 hunk

允许的最小附带项：

- 若为了隔离三处 copy 需要包含同一逻辑块中的第四处 `STATUS_COPY.reportNumber` 对齐，可纳入

必须排除：

- `BacktestPanel` 中条件渲染风格重写
- `BacktestPanel` 中 spacing / class 顺序变化
- `next candidates` 布局变化
- `PageHeader` / `ModeOverviewPanel`
- `candidates` / `scorePool` / `manual actions` 任何主题
- 其他文件

若相对 `HEAD` 无法从邻近 drift 中安全隔离该 hunk，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
