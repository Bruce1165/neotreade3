# Lowfreq 人工动作 Contract 实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-lowfreq-manual-actions-contract-design.md`

## 1. 目标

本计划只覆盖 `Lowfreq` 中人工动作提交链路的 contract 收口，不扩展到候选区布局、工作台壳层、回测、股票池或其他页面主题。

本轮目标只有三个：

1. 收口 `handleBuyIntent()` 与 `handleAbandon()` 的 endpoint 和 payload contract。
2. 为 buy / abandon 行为建立独立 focused test 载体。
3. 从混杂的 `Lowfreq.test.jsx` 中剥离对应 contract 断言，避免继续扩大 omnibus 测试。

本轮必须产出的核心结果：

- `买进(T+1)` 明确调用 `POST /api/lowfreq-score/manual/buy-intent`
- `放弃` 明确调用 `POST /api/lowfreq-score/manual/abandon`
- `sector` 提交值与页面展示语义一致，统一使用展示名
- 提交中不包含候选布局、scorePool、backtest、tools 等其他 `Lowfreq` 主题

## 2. 不在本轮完成

- `CandidatesPanel` 双栏布局或文案重构
- `PageHeader` / `ModeOverviewPanel` / `MetricCard` / `STATUS_COPY` 的 shared 收口
- `scorePool` baseline、request guard、drilldown
- `backtest` 状态轮询、详情链接、结果展示、end date sync
- `App.jsx` / 路由 / 新页面接线
- 后端接口、存储或数据库调整

## 3. 当前实施起点

### 3.1 已有现实基础

- [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 已集中存在：
  - `handleBuyIntent()`
  - `handleAbandon()`
- 当前工作区中的 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 已包含 buy / abandon 的 contract 断言雏形
- 当前工作区也已出现 `displaySectorName(candidate)` 的使用方向，说明 `sector` 提交值已具备统一到展示名的现实基础

### 3.2 当前结构性风险

- `Lowfreq.jsx` 当前混有多条主题，若直接整文件提交，容易把候选布局、壳层 copy、backtest 等漂移带进本刀
- `Lowfreq.test.jsx` 已非常混杂，如果继续扩写会进一步模糊 contract 和 UI 主题边界
- 若 buy / abandon 断言不迁出，未来很难判断失败是 contract 回归还是页面布局漂移

## 4. 实施原则

- 只处理人工动作 endpoint 与 payload contract
- 不修改 buy / abandon 的按钮可用性规则
- 不修改 `CandidatesPanel` 结构、列表排序或卡片布局
- 优先新增独立测试文件，不继续把 contract 测试堆进 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)
- 如发现必须牵动候选布局或 shared 文案，停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx` 中与 buy / abandon contract 直接重复的最小移除 hunk

建议只包含以下逻辑：

- 收口 `handleBuyIntent()` 的 endpoint 与 payload
- 收口 `handleAbandon()` 的 endpoint 与 payload
- 用独立测试载体验证 buy / abandon contract

明确不改：

- `CandidatesPanel` 双栏结构
- `scorePool` / `backtest` / `tools`
- `App.jsx`
- 其他页面与后端文件

## 6. 总体分段

本计划建议分为四段执行：

- `MAC-R1`：冻结人工动作 contract 切片边界
- `MAC-R2`：在 `Lowfreq.jsx` 收口 buy / abandon contract
- `MAC-R3`：新增独立 focused test 载体并去重旧断言
- `MAC-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### MAC-R1：冻结人工动作 contract 切片边界

目标：

- 在动手前确认哪些 `Lowfreq` 改动属于人工动作 contract，哪些必须排除。

任务：

- 审计 [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 中 buy / abandon 相关函数
- 审计 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中 buy / abandon 相关断言
- 确认本轮不处理候选布局、scorePool、backtest、tools
- 确认测试采用独立文件，而非继续扩写 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)

完成判定：

- 已形成明确 include / exclude 清单
- buy / abandon contract 可在不触碰其他主题的前提下单独完成

### MAC-R2：在 `Lowfreq.jsx` 收口 buy / abandon contract

目标：

- 让人工动作链路与当前确认的 lowfreq-score contract 一致。

任务：

- 在 [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 中定位：
  - `handleBuyIntent()`
  - `handleAbandon()`
- 收口 buy intent endpoint：
  - `POST /api/lowfreq-score/manual/buy-intent`
- 收口 abandon endpoint：
  - `POST /api/lowfreq-score/manual/abandon`
- 收口 payload：
  - `requested_date` 固定为当前 `selectedDate`
  - `requested_by` 固定为 `dashboard.react`
  - buy intent 中 `sector` 统一使用 `displaySectorName(candidate)`

关键约束：

- 不改按钮禁用条件
- 不新增新的动作类型
- 不顺手改 `CandidatesPanel` 布局
- 不改 posting/error/fetchData 基本流程

完成判定：

- `Lowfreq.jsx` 中 buy / abandon 的 endpoint 与 payload 均符合 design
- 修改范围仍局限在两条动作链路

### MAC-R3：新增独立 focused test 载体并去重旧断言

目标：

- 为人工动作 contract 建立独立回归测试，并降低 `Lowfreq.test.jsx` 的混杂度。

任务：

- 新增 `Lowfreq.manualActionsContract.test.jsx`
- 最小 mock `useApp`、`fetchApi`、`DateSelector`、必要路由依赖
- 用独立用例覆盖：
  - `买进(T+1)` 调用 `POST /api/lowfreq-score/manual/buy-intent`
  - `放弃` 调用 `POST /api/lowfreq-score/manual/abandon`
  - `requested_date === selectedDate`
  - `requested_by === 'dashboard.react'`
  - buy intent 的 `sector` 为展示名
  - 旧 endpoint 不再被调用
- 在 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中移除与上述 contract 直接重复的最小断言，避免双重职责

关键约束：

- 不在新文件中复验候选布局
- 不在新文件中复验 `scorePool` / `backtest` / `tools`
- `Lowfreq.test.jsx` 只做最小去重，不顺手清理其他主题

完成判定：

- 新测试文件可独立证明人工动作 contract
- `Lowfreq.test.jsx` 不再承担重复的 buy / abandon contract 责任

### MAC-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `Lowfreq.manualActionsContract.test.jsx`
- 如触及 [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 且需要回归，可补跑一次与人工动作链路直接相关的最小测试
- 检查最近编辑文件的诊断错误
- 精确暂存，仅纳入：
  - `Lowfreq.jsx` 中 buy / abandon contract 的最小 hunk
  - `Lowfreq.manualActionsContract.test.jsx`
  - `Lowfreq.test.jsx` 的最小去重 hunk（如有）

完成判定：

- focused test 通过
- 最近编辑文件无新增语法/结构错误
- 提交中不包含候选布局、scorePool、backtest、tools 等其他漂移

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先复核 `Lowfreq.jsx` 中 buy / abandon 相关函数
2. 再最小修改 `Lowfreq.jsx`
3. 然后新增 `Lowfreq.manualActionsContract.test.jsx`
4. 最后最小去重 `Lowfreq.test.jsx` 并做验证、精确暂存

原因：

- 先稳住生产 contract，再写独立测试，断言边界更清晰
- 先有新 carrier，再从旧测试中去重，能避免出现 coverage 空窗
- 把 `Lowfreq.test.jsx` 的变动压到最后，有助于防止顺手整理成大规模 drift

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit MAC：Lowfreq 人工动作 contract 收口

范围：

- `Lowfreq.jsx` 中 buy / abandon contract 的最小 hunk
- `Lowfreq.manualActionsContract.test.jsx`
- `Lowfreq.test.jsx` 的最小去重 hunk（如有）

目标：

- 为 `Lowfreq` 人工动作链路建立独立、明确、可回归的 contract

如果该提交无法与候选布局、scorePool 或 backtest 漂移安全分离，则应停止提交并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `买进(T+1)` 调用 `POST /api/lowfreq-score/manual/buy-intent`
2. `放弃` 调用 `POST /api/lowfreq-score/manual/abandon`
3. buy intent payload 中 `sector` 为展示名，而非遗留编码
4. `requested_date === selectedDate`
5. `requested_by === 'dashboard.react'`
6. 使用独立测试载体，不继续把 contract 测试堆进 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx)
7. 提交中不包含候选布局、scorePool、backtest、tools 主题

## 11. 风险提示

- 当前最大风险不是实现难度，而是容易把 buy / abandon contract 顺手扩成候选工作台重构
- 若 `Lowfreq.test.jsx` 去重范围拿捏不住，容易把其他主题断言误删
- 若 `sector` 取值处理不一致，可能出现 UI 显示为名称而提交仍为编码的语义裂缝

## 12. 结论

本计划的核心不是“再补两条接口断言”，而是：

- 把 `Lowfreq` 人工动作链路从混杂工作区中单独收口
- 把 buy / abandon contract 明确化
- 用独立 focused test 载体承接这条 contract

只有把这条线物理独立出来，后续 `Lowfreq` 的候选布局、工作台 copy、scorePool、backtest 等主题才能继续按原子边界推进。
