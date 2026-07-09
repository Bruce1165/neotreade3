# Lowfreq Backtest UX Duplicate Cleanup 实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-lowfreq-backtest-ux-duplicate-cleanup-design.md`

## 1. 目标

本计划只覆盖当前工作区中 `Lowfreq.test.jsx` 里 `backtest UX/detail link` 重复断言的最小去肥，不扩展到 `Lowfreq` 其他重复主题或任何生产代码。

本轮目标只有三个：

1. 从 `Lowfreq.test.jsx` 删除与 `Lowfreq.backtestUxDetailLink.test.jsx` 重叠的 3 条 `backtest UX/detail link` 用例。
2. 保持 `Lowfreq.backtestUxDetailLink.test.jsx` 作为该主题唯一权威测试载体。
3. 先完成工作区去肥收口，再核对相对 `HEAD` 是否仍形成真实最小差异。

本轮必须产出的核心结果：

- `Lowfreq.test.jsx` 不再承担 `backtest UX/detail link` 主题验证
- `Lowfreq.backtestUxDetailLink.test.jsx` 继续独立覆盖该主题
- 若相对 `HEAD` 没有真实差异，则本轮结论明确为“只完成工作区收口，不产生 commit”

## 2. 不在本轮完成

- `Lowfreq.jsx` 任意生产代码改动
- `Lowfreq.backtestUxDetailLink.test.jsx` 的功能扩展
- `manual actions` 重复用例删除
- `tools tab` 重复用例删除
- `scorePool baseline` 重复用例删除
- `Lowfreq.test.jsx` 全量清理或 mock 体系重写

## 3. 当前实施起点

### 3.1 已有现实基础

- [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 当前工作区包含 3 条 `backtest UX/detail link` 重复用例：
  - `treats unknown backtest status as an error state instead of endless running`
  - `shows execution mode when backtest status resolves to done`
  - `uses detail page links for history reports and hides missing detail links`
- [Lowfreq.backtestUxDetailLink.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx) 已存在并独立覆盖同一主题
- 当前审计已确认：这 3 条更像工作区回流漂移，而不是已明确存在于 `HEAD` 中的旧职责残留

### 3.2 当前结构性风险

- `Lowfreq.test.jsx` 当前是脏文件，混有多条主题，若整文件收口，容易误删其他断言
- 若误把工作区回流当成 `HEAD` 已存在职责，容易错误承诺原子化提交
- `backtest` 主题涉及 `localStorage`、状态轮询、历史报告和当前报告，验证面大于 `tools tab` / `manual actions`

## 4. 实施原则

- 先做工作区去肥收口
- 不预设一定产生 commit
- 不修改生产代码
- 不修改 `Lowfreq.backtestUxDetailLink.test.jsx` 的断言语义
- 除非删除该用例后出现显式未使用依赖且能以最小 hunk 清理，否则不动共享 mock
- 若发现 `Lowfreq.test.jsx` 中这 3 条用例与其他主题存在意外耦合，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`

建议只包含以下逻辑：

- 删除 `unknown status` 重复用例
- 删除 `execution mode + current detail link` 重复用例
- 删除 `history detail link` 重复用例
- 如有必要，删除这 3 条用例专属且已显式未使用的最小依赖

明确不改：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx`
- 其他任何 `Lowfreq*.test.jsx`

## 6. 总体分段

本计划建议分为四段执行：

- `LBT-R1`：冻结 `backtest UX/detail link` duplicate cleanup 切片边界
- `LBT-R2`：在 `Lowfreq.test.jsx` 删除 3 条重复用例
- `LBT-R3`：验证独立 carrier 与 omnibus 文件
- `LBT-R4`：核对相对 `HEAD` 差异，并决定提交或仅收口

## 7. 分段实施计划

### LBT-R1：冻结 `backtest UX/detail link` duplicate cleanup 切片边界

目标：

- 在动手前确认哪些 `Lowfreq.test.jsx` 改动属于 `backtest UX/detail link` 重复职责，哪些必须排除。

任务：

- 审计 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中 `backtest` 相关用例
- 审计 [Lowfreq.backtestUxDetailLink.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx) 的现有覆盖
- 确认本轮不处理 `manual actions`、`tools tab`、`scorePool`、`candidates`
- 确认本轮不修改 `Lowfreq.jsx`

完成判定：

- 已形成明确 include / exclude 清单
- 能把 `backtest UX/detail link` 主题作为最小测试去肥切片独立完成

### LBT-R2：在 `Lowfreq.test.jsx` 删除 3 条重复用例

目标：

- 让 `Lowfreq.test.jsx` 不再承担 `backtest UX/detail link` 主题验证。

任务：

- 在 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中定位：
  - `treats unknown backtest status as an error state instead of endless running`
  - `shows execution mode when backtest status resolves to done`
  - `uses detail page links for history reports and hides missing detail links`
- 仅删除这 3 条用例
- 删除后检查是否存在：
  - 明显未使用的 helper
  - 明显未使用的 import
- 只有在能以最小 hunk 清理的情况下，才附带最小整洁性修正

关键约束：

- 不顺手删除 `manual actions` 用例
- 不顺手删除 `tools tab` 用例
- 不顺手调整 backtest 共享 payload 结构
- 不顺手改 mock 结构

完成判定：

- `Lowfreq.test.jsx` 中这 3 条重复用例已被移除
- 其余主题断言保持原样

### LBT-R3：验证独立 carrier 与 omnibus 文件

目标：

- 确认 `backtest UX/detail link` 主题已经完全由独立 carrier 承接，且 omnibus 删除后未产生隐式断裂。

任务：

- 运行 `Lowfreq.backtestUxDetailLink.test.jsx`
- 运行 `Lowfreq.test.jsx`
- 如删除用例后触发最近编辑文件的诊断问题，做最小修正

完成判定：

- `Lowfreq.backtestUxDetailLink.test.jsx` 通过
- `Lowfreq.test.jsx` 通过
- 最近编辑文件无新增语法/结构错误

### LBT-R4：核对相对 `HEAD` 差异，并决定提交或仅收口

目标：

- 根据真实差异判断本轮结果是“原子化提交”还是“工作区收口”。

任务：

- 核对 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 相对 `HEAD` 的实际 hunk
- 判断这 3 条删除是否仍形成可安全隔离的最小差异
- 如果形成最小差异：
  - 精确暂存相关 hunk
  - 生成只代表 `backtest UX duplicate cleanup` 的提交
- 如果不形成最小差异：
  - 不提交
  - 明确记录为“已完成工作区去肥收口，不产生新 commit”

完成判定：

- 结论基于相对 `HEAD` 的真实差异，而不是预设
- 若提交，则提交中不包含 `Lowfreq.jsx`
- 若不提交，则明确说明原因和边界

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先定位 `Lowfreq.test.jsx` 中 3 条重复用例
2. 再删除这 3 条用例
3. 然后运行 `Lowfreq.backtestUxDetailLink.test.jsx`
4. 最后运行 `Lowfreq.test.jsx`
5. 再核对相对 `HEAD` 是否仍有真实差异

原因：

- 先删最小 hunk，可避免过早卷入共享 mock 整理
- 先验证独立 carrier，能快速证明职责迁移已成立
- 先完成工作区收口，再决定是否提交，最符合当前事实边界

## 9. 建议提交切分

本轮默认不是“必有提交”，而是“先收口，再决定是否提交”。

### 若可提交：Commit LBT

范围：

- `Lowfreq.test.jsx` 中 3 条 `backtest UX/detail link` 重复用例删除 hunk

可选附带：

- 该删除直接导致的最小未使用依赖清理 hunk

目标：

- 让 `backtest UX/detail link` 测试职责只保留在独立 carrier 中

### 若不可提交

结论应为：

- 工作区已完成去肥收口
- 相对 `HEAD` 不存在可安全隔离的最小差异
- 因而不产生新 commit

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `Lowfreq.test.jsx` 中不再包含 3 条 `backtest UX/detail link` 重复用例
2. `Lowfreq.backtestUxDetailLink.test.jsx` 继续通过
3. `Lowfreq.test.jsx` 继续通过
4. 不修改 `Lowfreq.jsx`
5. 最终对“是否提交”的结论基于相对 `HEAD` 的真实差异

## 11. 风险提示

- 当前最大风险不是删除 3 个测试，而是误把工作区回流说成 `HEAD` 里的旧职责
- 若共享 mock 恰好被多个主题复用，过度清理未使用项可能误伤其他用例
- `backtest` 主题验证面较大，若顺手整理 payload 或轮询 mock，容易把切片扩大成测试重构

## 12. 结论

本计划的核心不是“删 3 条测试”，而是：

- 把 `backtest UX/detail link` 的测试职责从 omnibus 文件中拿掉
- 确认独立 carrier 已足够承担该主题
- 先完成工作区去肥收口，再根据相对 `HEAD` 的事实决定是否形成提交

只有坚持这种“事实先于提交假设”的推进方式，`Lowfreq.test.jsx` 的后续去肥才不会再次漂移失控。
