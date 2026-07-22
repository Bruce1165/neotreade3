# Lowfreq Candidates Carrier Realignment 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-lowfreq-candidates-carrier-realignment-design.md`

## 1. 目标

本计划只覆盖 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 的职责重新对齐，不扩展到 `Lowfreq` 其他测试主题或任何生产代码。

本轮目标只有三个：

1. 将 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 从旧 tab 文案与旧 endpoint contract 断言中收口到当前布局主题。
2. 保持 `Lowfreq.manualActionsContract.test.jsx` 继续作为人工动作 endpoint contract 的唯一权威测试载体。
3. 用最小测试改动完成 focused carrier 职责边界修正，并形成单主题原子化提交。

本轮必须产出的核心结果：

- `Lowfreq.candidatesWorkbenchSplit.test.jsx` 只承接 `阅读区 / 动作区分离` 主题
- `Lowfreq.manualActionsContract.test.jsx` 继续独立承接 `/api/lowfreq-score/manual/*` contract
- 提交中不包含 `Lowfreq.jsx`、`Lowfreq.test.jsx` 或其他 focused carrier 改动

## 2. 不在本轮完成

- `Lowfreq.jsx` 任意生产代码改动
- `Lowfreq.manualActionsContract.test.jsx` 的功能扩展
- `Lowfreq.test.jsx` 的 omnibus 去肥
- `Lowfreq.scorePoolBaseline.test.jsx` / `Lowfreq.scorePoolRequestGuard.test.jsx` 改动
- `Lowfreq.backtestUxDetailLink.test.jsx` / `Lowfreq.toolsTab.test.jsx` 改动
- `Lowfreq` 全量测试重构或 mock 体系重写

## 3. 当前实施起点

### 3.1 已有现实基础

- [Lowfreq.candidatesWorkbenchSplit.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx) 当前包含两条 focused tests：
  - 一条验证 `候选阅读区 / 人工动作区 / 待处理列表`
  - 一条同时验证动作按钮与旧 endpoint `/api/lowfreq/manual/*`
- [Lowfreq.manualActionsContract.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx) 已独立覆盖：
  - `POST /api/lowfreq-score/manual/buy-intent`
  - `POST /api/lowfreq-score/manual/abandon`
  - payload 关键字段
  - 旧 endpoint 不再被调用
- 当前生产语义已经切到：
  - tab 文案 `候选与人工`
  - 人工动作 endpoint `lowfreq-score/manual/*`

### 3.2 当前结构性风险

- `Lowfreq.candidatesWorkbenchSplit.test.jsx` 当前同时包含布局职责与接口契约职责，focused carrier 边界已经混刀
- 第二条用例仍依赖旧 endpoint，若直接修成新 endpoint，会与 `Lowfreq.manualActionsContract.test.jsx` 形成新的职责重叠
- 如果顺手扩展到 `Lowfreq.jsx` 或其他测试文件，本轮最小边界会立即失控

## 4. 实施原则

- 只改 `Lowfreq.candidatesWorkbenchSplit.test.jsx`
- 不修改生产代码
- 不修改 `Lowfreq.manualActionsContract.test.jsx` 的断言语义
- 优先保留“布局分离”主题，移除“人工动作 contract”主题
- 若第二条用例在移除 contract 后不再具备独立价值，应直接删除，而不是强行保留弱价值断言
- 除非收口后出现显式未使用 helper / import 且能以最小 hunk 清理，否则不动文件其余结构

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx`

建议只包含以下逻辑：

- 将 tab 入口从 `候选池` 更新为 `候选与人工`
- 保留并校准 `候选阅读区`、`人工动作区`、`待处理列表` 相关断言
- 保留已排队 / 已放弃项不进入待处理列表的断言
- 删除或收缩关于 `/api/lowfreq/manual/*` 的旧 contract 断言
- 如有必要，清理对应最小未使用依赖

明确不改：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- 其他任何 `Lowfreq*.test.jsx`

## 6. 总体分段

本计划建议分为四段执行：

- `LCC-R1`：冻结 candidates carrier realignment 切片边界
- `LCC-R2`：重写或删除 stale second carrier test，并校准 tab 文案
- `LCC-R3`：验证 split carrier 与 manual-actions carrier
- `LCC-R4`：精确暂存并提交

## 7. 分段实施计划

### LCC-R1：冻结 candidates carrier realignment 切片边界

目标：

- 在动手前确认哪些 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 断言属于“布局分离”，哪些已经越界到“人工动作 contract”。

任务：

- 审计 [Lowfreq.candidatesWorkbenchSplit.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx) 两条现有用例
- 审计 [Lowfreq.manualActionsContract.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx) 的既有覆盖
- 确认本轮不处理 `Lowfreq.jsx`、`Lowfreq.test.jsx` 与其他 focused carriers
- 确认第二条用例若失去独立价值，可直接删除

完成判定：

- 已形成明确 include / exclude 清单
- 能将“布局分离”与“manual actions contract” 两类职责清晰拆开

### LCC-R2：重写或删除 stale second carrier test，并校准 tab 文案

目标：

- 让 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 回到“只验证候选工作台布局分离”的 focused boundary。

任务：

- 将文件中所有 tab 入口断言从 `候选池` 更新为 `候选与人工`
- 保留第一条用例作为：
  - `候选阅读区`
  - `人工动作区`
  - `待处理列表`
  - 已排队 / 已放弃对象不进入待处理列表
  的核心权威断言
- 处理第二条用例，二选一：
  - 若仍能形成独立的“动作区交互存在性”价值，则去掉 endpoint contract 断言后最小保留
  - 若只剩 contract 内容而无独立布局价值，则直接删除
- 删除收口后显式未使用的最小 helper / import（如存在）

关键约束：

- 不把旧 endpoint `/api/lowfreq/manual/*` 替换成新 endpoint 继续断言
- 不把 second test 扩写成 `manualActionsContract` 的替代品
- 不顺手修改 payload、mock 结构或生产语义

完成判定：

- 文件中不再出现 `候选池`
- 文件中不再承担 `/api/lowfreq/manual/*` 或 `/api/lowfreq-score/manual/*` contract 验证
- 文件保留清晰的候选工作台布局主题

### LCC-R3：验证 split carrier 与 manual-actions carrier

目标：

- 确认布局 carrier 和 contract carrier 在收口后都仍然成立，且职责不互相覆盖。

任务：

- 运行 `Lowfreq.candidatesWorkbenchSplit.test.jsx`
- 运行 `Lowfreq.manualActionsContract.test.jsx`
- 如最近编辑文件出现显式语法 / 结构问题，做最小修正

完成判定：

- `Lowfreq.candidatesWorkbenchSplit.test.jsx` 通过
- `Lowfreq.manualActionsContract.test.jsx` 通过
- 最近编辑文件无新增语法/结构错误

### LCC-R4：精确暂存并提交

目标：

- 用最小提交边界完成这条 focused carrier realignment 切片。

任务：

- 精确暂存 [Lowfreq.candidatesWorkbenchSplit.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx) 中与本轮职责对齐直接相关的最小 hunk
- 如有最小未使用依赖清理，也仅暂存对应最小 hunk
- 生成一个只代表 `candidates carrier realignment` 的提交

完成判定：

- 提交中不包含 `Lowfreq.jsx`
- 提交中不包含 `Lowfreq.manualActionsContract.test.jsx`
- 提交 message 能准确表达这是 focused carrier 职责对齐切片

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先重新标记 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 中布局职责与 contract 职责
2. 再更新 tab 文案并处理第二条 stale 用例
3. 然后运行 `Lowfreq.candidatesWorkbenchSplit.test.jsx`
4. 最后运行 `Lowfreq.manualActionsContract.test.jsx`

原因：

- 先锁定职责边界，可避免把第二条用例误改成新的 contract carrier
- 先验证 split carrier，可快速确认本轮布局主题仍成立
- 再验证 manual-actions carrier，可确认 contract 主题没有被误伤

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit LCC：Lowfreq candidates carrier realignment

范围：

- `Lowfreq.candidatesWorkbenchSplit.test.jsx` 中 tab 文案校准与 stale carrier 断言收口 hunk

可选附带：

- 该收口直接导致的最小未使用依赖清理 hunk

目标：

- 让 `candidatesWorkbenchSplit` 只保留布局分离职责
- 让 `manualActionsContract` 继续独占人工动作 contract

如果该提交无法与其他文件安全隔离，则应停止提交并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `Lowfreq.candidatesWorkbenchSplit.test.jsx` 中不再出现旧 tab 文案 `候选池`
2. 该文件不再承担 manual endpoint contract 验证
3. `Lowfreq.candidatesWorkbenchSplit.test.jsx` 继续通过
4. `Lowfreq.manualActionsContract.test.jsx` 继续通过
5. 不修改 `Lowfreq.jsx`
6. 提交中不包含其他测试主题或生产改动

## 11. 风险提示

- 当前最大风险不是改一个测试文件，而是把“职责重新对齐”误做成“合同测试扩写”
- 如果为了保留第二条用例而强行补新 endpoint 断言，会重新制造 focused carrier 重叠
- 若顺手清理过多 helper / mock，容易把一个小切片扩大成测试文件重构

## 12. 结论

本计划的核心不是“修旧断言”，而是：

- 把 `Lowfreq.candidatesWorkbenchSplit.test.jsx` 拉回到正确的 focused boundary
- 保持 `Lowfreq.manualActionsContract.test.jsx` 继续独占人工动作 contract
- 用最小、可验证、可提交的方式完成一次测试职责重新对齐

只有先把 focused carrier 边界重新拉直，后续 `Lowfreq.jsx` 剩余生产 drift 的审计与切片推进才不会继续被旧测试噪音干扰。
