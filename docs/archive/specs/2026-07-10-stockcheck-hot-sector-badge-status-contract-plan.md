# StockCheck Hot-Sector Badge Status Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-stockcheck-hot-sector-badge-status-contract-design.md`

## 1. 目标

本计划只覆盖 `StockCheck` 页面的热门板块命中区 badge status contract 收口，不扩展到 debug 标题、按钮文案、共享壳层或 API 行为。

本轮目标只有三个：

1. 将热门板块命中区 badge 的 `semanticKey` 统一到正确的状态语义 contract。
2. 将热门板块命中区 badge 的 `label` 统一到 `STATUS_COPY.actionable / observing / followerObserving`。
3. 将 `StockCheck.test.jsx` 中对应 badge 断言同步到同一 contract。

本轮必须得到的核心结果：

- `buy_signal === true` 使用 `entry_ready` + `STATUS_COPY.actionable`
- `leaders/leader` 观察态使用 `watch_general` + `STATUS_COPY.observing`
- 其他观察态使用 `watch_follower` + `STATUS_COPY.followerObserving`
- `StockCheck.test.jsx` 显式验证上述 badge contract
- 提交中不包含 `STATUS_COPY.debugData`、`PageHeader` subtitle 或其他结构性改动

## 2. 不在本轮完成

- `STATUS_COPY.debugData`
- debug 折叠标题
- `PageHeader` subtitle
- 搜索按钮文案
- `BlockMessage`
- `fetchApi` 调用
- `handleCheck` 逻辑
- 热门板块正文 message
- 结果区与输入区结构调整
- 其他页面测试或全量前端测试矩阵

## 3. 当前实施起点

### 3.1 已知事实

- [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前剩余 drift 同时包含三类主题：
  - 热门板块 badge status contract
  - debug 折叠标题
  - subtitle / import 相邻漂移
- [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 当前已承接 `可出手` badge 结果断言，但尚未承接 leader / follower 两类观察态 badge
- [statusCopy.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/statusCopy.js) 已具备 `actionable / observing / followerObserving` 文案常量，本轮不需要修改常量源
- `StockCheck` 的 shared-shell adoption 与 button copy contract 已分别独立提交，本轮不需要再触碰相邻主题

### 3.2 结构性风险

- 最大风险不是 badge 替换本身，而是从同一文件的混合 diff 中误带入 `STATUS_COPY.debugData`
- 如果只改 `label` 不改 `semanticKey`，展示文案与状态语义仍会失配
- 如果顺手修改 subtitle 或 import，本轮就会从“badge status contract”扩大成页面级整理

## 4. 实施原则

- 只改 `StockCheck.jsx` 与 `StockCheck.test.jsx`
- 只做热门板块 badge status contract 收口
- 不改 `statusCopy.js`
- 不改 debug 标题
- 不改共享壳层
- 不改 API 与交互逻辑
- 若验证暴露的是 debug 标题、subtitle 或其他页面 copy 问题，应暂停并报告边界问题，不能静默扩大范围
- 若相对 `HEAD` 无法安全隔离 badge 相关 hunk，本轮结论应是“不提交”，而不是扩大提交范围

## 5. 建议改动边界

允许改动文件：

- `neotrade3-dashboard/src/pages/StockCheck.jsx`
- `neotrade3-dashboard/src/pages/StockCheck.test.jsx`

允许改动逻辑：

- `buy_signal === true` -> `entry_ready` + `STATUS_COPY.actionable`
- `buy_signal !== true && role in ['leaders', 'leader']` -> `watch_general` + `STATUS_COPY.observing`
- 其他观察态 -> `watch_follower` + `STATUS_COPY.followerObserving`
- 对应测试断言同步覆盖三类 badge contract

明确不改：

- `STATUS_COPY.debugData`
- debug 折叠区 `<summary>`
- `PageHeader`
- 搜索按钮文案
- `fetchApi`
- 搜索逻辑和请求参数
- 热门板块 message 正文
- 结果区渲染结构
- `AlertCircle` import

## 6. 总体分段

本计划建议分为四段执行：

- `SCH-R1`：冻结 badge contract 的精确边界
- `SCH-R2`：只实施 badge 语义与文案 contract
- `SCH-R3`：跑最小验证并检查语法/结构安全
- `SCH-R4`：隔离 badge-contract hunk 并提交

## 7. 分段实施计划

### SCH-R1：冻结 badge contract 的精确边界

目标：

- 明确 `StockCheck.jsx` 和 `StockCheck.test.jsx` 中哪些点位属于本轮 badge contract，哪些相邻改动必须排除。

任务：

- 读取 [StockCheck.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.jsx) 当前热门板块 badge 区块
- 读取 [StockCheck.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/StockCheck.test.jsx) 当前 badge 相关断言
- 对照 `HEAD` 检查当前剩余 diff
- 只标记以下目标点位：
  - badge `semanticKey`
  - badge `label`
  - 对应 badge 断言
- 显式排除：
  - `STATUS_COPY.debugData`
  - debug 折叠标题
  - `PageHeader` subtitle
  - 搜索按钮 copy
  - `AlertCircle` import

完成判定：

- include / exclude 列表明确
- badge contract 与 debug / subtitle 相邻 drift 已清楚分开

### SCH-R2：只实施 badge 语义与文案 contract

目标：

- 在不改变业务逻辑和页面结构的前提下，完成热门板块 badge 的生产与测试同步。

任务：

- 将 `buy_signal === true` 对齐到 `entry_ready` + `STATUS_COPY.actionable`
- 将 `leaders/leader` 观察态对齐到 `watch_general` + `STATUS_COPY.observing`
- 将其他观察态对齐到 `watch_follower` + `STATUS_COPY.followerObserving`
- 在测试中补齐 leader / follower 观察态 badge 断言

关键约束：

- 不调整热门板块数据源逻辑
- 不调整结果区结构
- 不修改 debug 标题
- 不修改按钮 contract

完成判定：

- 生产 badge 的语义 key 与展示文案 contract 对齐
- 测试显式覆盖三类 badge contract

### SCH-R3：跑最小验证并检查语法/结构安全

目标：

- 证明本轮只影响热门板块 badge status contract，不影响 `StockCheck` 既有核验流程。

任务：

- 运行 `npm test -- src/pages/StockCheck.test.jsx`
- 检查最近编辑文件是否存在明显语法或结构问题
- 若失败原因来自 debug 标题、subtitle 或其他相邻 drift，则停止并报告边界问题

完成判定：

- `StockCheck.test.jsx` 通过
- 最近编辑文件无明显语法或结构错误

### SCH-R4：隔离 badge-contract hunk 并提交

目标：

- 生成一个单一目的的切片，只表达 `StockCheck` 的热门板块 badge status contract 收口。

任务：

- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.jsx`
- 检查 `git diff HEAD -- neotrade3-dashboard/src/pages/StockCheck.test.jsx`
- 只暂存 badge contract 与对应测试断言 hunk
- 排除 `STATUS_COPY.debugData`、subtitle 与其他相邻 drift
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含热门板块 badge status contract
- 提交中不包含 debug 标题
- 提交中不包含 shared-shell、按钮文案或结构性改动

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `StockCheck.jsx` badge 区块与 `StockCheck.test.jsx` 现有断言
2. 对照 `HEAD` 切分 badge contract 与 debug / subtitle 两类 drift
3. 只改 badge contract 点位
4. 跑 `StockCheck.test.jsx`
5. 再检查 `HEAD`-relative diff
6. 只暂存 badge-contract hunk

原因：

- 先切主题再改代码，可以避免把同文件中的 debug 标题与 subtitle 相邻改动一起带进提交
- 先验证 focused carrier，再决定是否提交，可以把边界失真风险控制在最小范围

## 9. 建议提交切分

建议单一提交：

### Commit SCH：StockCheck hot-sector badge status contract

范围：

- `StockCheck.jsx` 中热门板块 badge 的 `semanticKey` / `label` 最小 hunk
- `StockCheck.test.jsx` 中对应 badge 断言的最小 hunk

目的：

- 让 `StockCheck` 热门板块命中区的状态语义和可见文案使用同一 contract

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成 badge + debug 标题的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `buy_signal === true` 显示 `可出手` 且语义为 `entry_ready`
2. `leaders/leader` 观察态显示 `观察中` 且语义为 `watch_general`
3. 其他观察态显示 `跟随观察` 且语义为 `watch_follower`
4. `StockCheck.test.jsx` 对应 badge 断言通过
5. `StockCheck.test.jsx` 全部通过
6. 提交中不包含 `STATUS_COPY.debugData`、subtitle 或按钮文案变更

## 11. 风险提示

- 主要风险是 `StockCheck.jsx` 当前剩余 diff 混有 debug 标题、subtitle 与 import 相邻改动，隔离时必须逐 hunk 对照 `HEAD`
- 第二风险是测试若只覆盖 `可出手`，会导致 leader / follower 两类观察态 contract 继续无承接面
- 第三风险是若为了减少 diff 一次性带入 debug 标题，本轮提交目的会失真

## 12. 结论

本计划不是 `StockCheck` 整页 `STATUS_COPY` 清理计划，而是一条更窄的状态 contract 线，目标只有三件事：

- 只统一热门板块 badge 的 `semanticKey`
- 只统一热门板块 badge 的 `label`
- 只同步对应测试断言，并仅在相对 `HEAD` 可安全隔离时提交
