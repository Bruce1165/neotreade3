# Lowfreq Backtest End Date Sync Design

Date: 2026-07-09

## 1. Goal

本切片只解决 `Lowfreq` 中 `backtestEndDate` 的同步规则问题：

- 初始状态自动带入 `selectedDate`
- 用户未手改时，继续跟随新的 `selectedDate`
- 用户手改后，后续切换全局日期时保留手改值

目标是把“自动同步”和“用户显式输入”区分开，避免回测表单被无意覆盖。

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 一个新的聚焦测试载体
- `backtestEndDate` 的同步 effect 调整

Excluded:

- `scorePoolRequestIdRef`
- `App.jsx` / `App.test.jsx`
- `OpsCenter` / `LowfreqBacktestReport`
- shared 组件抽取
- 其他 tab 行为

## 3. Existing Behavior and Risk

`HEAD` 中当前逻辑：

- 只有当 `backtestEndDate` 为空时，才把它设置为 `selectedDate`

风险：

- 当用户未手改、但全局 `selectedDate` 已变化时，结束日期不会继续跟随
- 表单显示的结束日期可能落后于全局日期

目标规则：

- 如果结束日期仍然是“系统上一次自动带入的值”，允许继续同步
- 如果用户手动输入了别的值，则停止自动覆盖

## 4. Approaches

### Option A: previousSelectedDateRef（推荐）

记录上一次自动同步参考值。同步时比较当前 `backtestEndDate` 是否仍等于上一次参考值。

Pros:

- 不引入额外布尔状态
- 语义与本切片边界匹配
- 易于局部落地

Cons:

- 需要正确维护“前一次自动值”的更新时机

### Option B: dirty flag

增加 `isBacktestEndDateDirty`。

Pros:

- 语义直观

Cons:

- 状态面扩大
- 对这条窄切片来说稍重

### Option C: current value direct compare

只比较 `backtestEndDate === selectedDate`。

Pros:

- 实现最短

Cons:

- 不能区分“用户手动输入刚好等于当前日期”与“系统自动同步”的情况

Decision:

- choose Option A

## 5. Design

### 5.1 State Additions

在 `Lowfreq` 中新增：

- `previousSelectedDateRef = useRef(selectedDate)`

### 5.2 Sync Rule

在 `selectedDate` 变化时执行：

1. 调用 `setBacktestEndDate((prev) => ...)`
2. 若 `prev` 为空，则返回新的 `selectedDate`
3. 若 `prev === previousSelectedDateRef.current`，说明该值仍是上一次自动同步值，则返回新的 `selectedDate`
4. 否则保留 `prev`
5. 最后把 `previousSelectedDateRef.current = selectedDate`

### 5.3 Guardrails

本切片禁止：

- 顺手修改 `scorePool` request guard
- 修改回测运行逻辑
- 修改开始日期行为
- 修改回测结果展示

## 6. Testing Design

新增一个 focused test 文件，至少覆盖：

1. 初始渲染时，`回测结束日期` 自动带入当前 `selectedDate`
2. 未手改时，`selectedDate` 变化后，结束日期自动更新
3. 手动输入后，`selectedDate` 再变化时，结束日期保持用户值

## 7. Validation

预期校验：

- 跑 focused test（end date sync）
- 必要时补跑一次 backtest UX 最小回归

不要求：

- 全量 `Lowfreq.test.jsx`
- `App` 级回归
- 后端测试

## 8. Commit Boundary

目标提交只包含：

- `Lowfreq.jsx` 中 `backtestEndDate` 同步规则修正
- 新增 focused test 载体

必须排除：

- `scorePoolRequestIdRef`
- `App` / 路由 / 新页面
- shared 组件与文案收敛
