# Lowfreq 回测结束日期同步实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-lowfreq-backtest-end-date-sync-design.md`

## 1. 目标

本计划只覆盖 `Lowfreq` 中 `backtestEndDate` 的同步规则修正，不扩展到 `Lowfreq` 其他 UI、contract 或路由漂移。

本轮目标只有三个：

1. 修正 `selectedDate` 变化时 `backtestEndDate` 的跟随逻辑。
2. 保证用户手动输入的结束日期不会被后续全局日期切换误覆盖。
3. 用独立聚焦测试载体把该行为固定下来。

本轮必须产出的核心结果：

- 初始进入回测页时，结束日期自动带入当前 `selectedDate`
- 当结束日期仍是系统自动值时，后续 `selectedDate` 变化会继续同步
- 当用户手改结束日期后，后续 `selectedDate` 变化不再覆盖用户输入
- 提交中不包含 `Lowfreq` 其他主题线

## 2. 不在本轮完成

- `Lowfreq.jsx` 其他残余 drift 清理
- `PageHeader` / `ModeOverviewPanel` / tab copy 收口
- `lowfreq-score` endpoint 迁移
- `scorePoolRequestIdRef` 请求竞态保护
- 回测状态轮询、详情入口或结果展示改造
- `App.jsx` / 路由 / 新页面接线
- 后端逻辑调整

## 3. 当前实施起点

### 3.1 已有现实基础

- [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 已有 `backtestStartDate` / `backtestEndDate` 状态
- [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx#L1513-L1521) 已存在用于同步 `backtestEndDate` 的 `useEffect`
- 当前 design 已确定采用 `previousSelectedDateRef` 方案
- 用户已确认测试载体采用独立 focused file，而不是并回 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)

### 3.2 当前结构性风险

- `Lowfreq.jsx` 当前工作区同时混有多个主题，若直接整文件提交，容易把其他漂移带进来
- 若继续扩写 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)，会把日期同步契约重新混入 omnibus 测试
- 若实现时顺手修改回测面板其他行为，会破坏本刀的原子边界

## 4. 实施原则

- 只处理 `backtestEndDate` 的同步 effect
- 不改 `backtestStartDate` 规则
- 不改 `runBacktest()`、轮询、报告展示、tab 结构
- 使用独立测试载体，不扩写 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)
- 如发现实现需要牵动其他主题，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.backtestEndDate.test.jsx`

建议只包含以下逻辑：

- `backtestEndDate` 同步 effect 的最小修正
- 聚焦验证“跟随更新 / 用户手改保留”的独立测试

明确不改：

- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx`
- shared 组件、copy、route、API helper

## 6. 总体分段

本计划建议分为四段执行：

- `BED-R1`：冻结 `backtestEndDate` 切片边界
- `BED-R2`：在 `Lowfreq.jsx` 收口同步规则
- `BED-R3`：新增独立 focused test 载体
- `BED-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### BED-R1：冻结 `backtestEndDate` 切片边界

目标：

- 在动手前确认哪些 `Lowfreq` 改动属于日期同步，哪些必须排除。

任务：

- 审计 [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 中 `backtestEndDate` 相关状态和 effect
- 确认设计方案固定为 `previousSelectedDateRef`
- 确认测试使用独立文件，不扩写 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)
- 记录必须排除的其他 `Lowfreq` 主题

完成判定：

- 已形成明确 include / exclude 清单
- 本刀能在不触碰其他回测 UI 的前提下单独完成

### BED-R2：在 `Lowfreq.jsx` 收口同步规则

目标：

- 让 `backtestEndDate` 同时满足“系统自动跟随”和“用户手改保留”两个契约。

任务：

- 在 [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 中定位当前同步 effect
- 使用 `previousSelectedDateRef.current` 作为“上一轮自动值”参考
- 将同步规则收口为：
  - 若当前值为空，返回新的 `selectedDate`
  - 若当前值仍等于 `previousSelectedDateRef.current`，返回新的 `selectedDate`
  - 否则保留当前值
- 在 effect 末尾更新 `previousSelectedDateRef.current = selectedDate`

关键约束：

- 不引入新的 dirty flag
- 不修改开始日期逻辑
- 不调整回测结果展示
- 不顺手改动其他 effect

完成判定：

- `Lowfreq.jsx` 中的同步规则与 design 一致
- 修改范围仍局限在该 effect 及其直接依赖

### BED-R3：新增独立 focused test 载体

目标：

- 为结束日期同步规则建立物理独立的 contract 测试。

任务：

- 新增 `Lowfreq.backtestEndDate.test.jsx`
- 最小 mock `useApp`、`fetchApi`、`DateSelector`、路由依赖
- 覆盖以下场景：
  - 初始渲染时，`回测结束日期` 自动带入当前 `selectedDate`
  - 未手改时，`selectedDate` 变化后，结束日期自动更新
  - 用户手动修改结束日期后，`selectedDate` 再变化时，结束日期保持用户值

建议实现策略：

- 只驱动 `回测报告` tab 与两个日期输入框
- 只断言日期字段值，不混入回测结果、下载链接或轮询断言
- 如需重渲染，使用最小方式更新 `useApp` 返回值

完成判定：

- 新测试文件能独立证明日期同步契约
- 无需依赖 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)

### BED-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `Lowfreq.backtestEndDate.test.jsx`
- 如实现触及 [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 且需要回归，可补跑最小相关测试
- 检查最近修改文件的诊断错误
- 精确暂存，仅纳入：
  - `Lowfreq.jsx` 中 `backtestEndDate` effect 的最小 hunk
  - `Lowfreq.backtestEndDate.test.jsx`

完成判定：

- focused test 通过
- 最近编辑文件无新增语法/结构错误
- 提交中不包含其他 `Lowfreq` drift

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先复核 `Lowfreq.jsx` 中现有同步 effect
2. 再最小修改 `Lowfreq.jsx`
3. 然后新增 `Lowfreq.backtestEndDate.test.jsx`
4. 最后做验证、诊断检查与精确暂存

原因：

- 先稳住生产逻辑，测试目标更明确
- 先有清晰的同步 contract，再写独立测试，更容易避免混入其他行为断言
- 把边界检查放在最后，可最大限度防止把其他 `Lowfreq` 主题误带入提交

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit BED：Lowfreq 回测结束日期同步收口

范围：

- `Lowfreq.jsx` 中 `backtestEndDate` effect 的最小 hunk
- `Lowfreq.backtestEndDate.test.jsx`

目标：

- 为回测表单建立明确且可回归的结束日期同步契约

如果该提交无法与其他 `Lowfreq` drift 安全分离，则应停止提交并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 初始渲染时，结束日期自动等于当前 `selectedDate`
2. 当结束日期仍为系统自动值时，切换全局日期后会继续同步
3. 用户手改结束日期后，切换全局日期不会覆盖用户输入
4. 使用独立测试载体，不扩写 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)
5. 提交中不包含其他 `Lowfreq` 主题线

## 11. 风险提示

- 当前最大风险不是实现复杂度，而是把 `Lowfreq` 其他工作区漂移顺手并入本刀
- 若测试上下文搭建过大，容易把简单字段同步测试做成回测集成测试
- 若同步逻辑写得过度通用，可能把“用户手改保留”重新覆盖掉

## 12. 结论

本计划的核心不是“修一个日期默认值”，而是：

- 把 `backtestEndDate` 的自动跟随语义明确化
- 把“系统自动值”和“用户显式输入”稳定区分开
- 用独立 focused test 载体把这条 contract 钉住

只有按这个边界推进，后续 `Lowfreq` 其他主题线才能继续保持原子化收口，而不会再次混刀。
