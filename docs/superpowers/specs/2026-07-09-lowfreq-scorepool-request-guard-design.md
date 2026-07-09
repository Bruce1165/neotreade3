# Lowfreq ScorePool Request Guard Design

Date: 2026-07-09

## 1. Goal

本切片只解决 `Lowfreq` 中 `scorePool` 的请求竞态问题：当用户快速切换日期时，旧请求晚到不能覆盖新请求数据。

目标：

- 只接受最后一次 `scorePool` 请求的响应
- 避免旧日期 summary/pool 回写到当前页面
- 保持提交边界最小，不混入其他 UI 或路由改造

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 一个新的聚焦测试载体
- `loadScorePoolBlock()` 内的 request guard 逻辑

Excluded:

- `previousSelectedDateRef` / `backtestEndDate` 跟随逻辑
- `App.jsx` / `App.test.jsx`
- `OpsCenter` / `LowfreqBacktestReport`
- shared 组件抽取（`PageHeader` / `MetricCard` / `statusCopy`）
- `candidates` / `today` / `backtest` 其他 tab 行为

## 3. Existing Behavior and Risk

`HEAD` 中的 `loadScorePoolBlock()` 行为：

1. 请求 summary
2. 回写 summary
3. 请求 pool
4. 回写 summary+pool

风险：

- 日期 A 请求先发，日期 B 请求后发
- 若 A 的响应更晚返回，可能覆盖 B 的结果
- 用户在 `股票池与台账` 中看到“当前选中日期与内容不一致”的旧数据

## 4. Approaches

### Option A: request id guard（推荐）

为每轮 `loadScorePoolBlock()` 分配递增 `requestId`，每次响应前检查是否仍是最新请求，不是则丢弃。

Pros:

- 侵入最小
- 不改 API 契约
- 行为可预测，易测试

Cons:

- 需要在 summary 成功、pool 成功、error 三个分支都做一致校验

### Option B: AbortController

新请求触发时中断旧请求。

Pros:

- 理论上更省资源

Cons:

- 需要 `fetchApi` 层支持取消信号，当前切片边界会扩大

### Option C: 回写时按日期比较

响应携带日期，回写前比较当前 `selectedDate` 是否一致。

Pros:

- 思路直观

Cons:

- 依赖 payload/date 传递一致性，且比 request id 容易遗漏

Decision:

- choose Option A

## 5. Design

### 5.1 State Additions

在 `Lowfreq` 组件中新增：

- `scorePoolRequestIdRef = useRef(0)`

### 5.2 Flow

每次进入 `loadScorePoolBlock()`：

1. `requestId = scorePoolRequestIdRef.current + 1`
2. `scorePoolRequestIdRef.current = requestId`
3. 启动 block loading

随后在以下分支回写前都做校验：

- summary 成功后（partial payload）
- pool 成功后（final payload）
- catch 分支

校验规则：

- 若 `scorePoolRequestIdRef.current !== requestId`，直接 `return`
- 仅最新请求可更新 `data.scorePool` 和 `blocks.scorePool`

### 5.3 Guardrails

本切片禁止：

- 顺手引入 `previousSelectedDateRef`
- 修改 tabs 结构
- 修改 `ScorePoolPanel` 展示字段
- 修改其他 block 的加载策略

## 6. Testing Design

新增一个 focused test 文件，最少覆盖：

1. 日期 A 与日期 B 连续触发 `scorePool` 加载
2. 人工控制响应顺序为 B 先回、A 后回（制造竞态）
3. 最终界面保持 B 的数据，不被 A 覆盖

验证点建议：

- 表格或 summary 中只出现 B 日期对应数据
- 不出现 A 的覆盖痕迹

## 7. Validation

预期校验：

- 跑 focused test（request guard）
- 必要时补跑一次 scorePool baseline 的最小回归

不要求：

- 全量 `Lowfreq.test.jsx`
- 路由级回归
- 后端测试

## 8. Commit Boundary

目标提交只包含：

- `Lowfreq.jsx` 中 `scorePool` request guard
- 新增 focused test 载体

必须排除：

- `previousSelectedDateRef`
- `App` / 路由 / 新页面
- shared 组件与文案收敛
