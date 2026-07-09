# Lowfreq Tools Tab Duplicate Cleanup 实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-lowfreq-tools-tab-duplicate-cleanup-design.md`

## 1. 目标

本计划只覆盖 `Lowfreq.test.jsx` 中 `tools tab` 重复断言的最小去重，不扩展到 `Lowfreq` 其他重复主题或任何生产代码。

本轮目标只有三个：

1. 删除 `Lowfreq.test.jsx` 中与 `Lowfreq.toolsTab.test.jsx` 完全重叠的单个 `tools tab` 用例。
2. 保持 `Lowfreq.toolsTab.test.jsx` 作为该主题唯一权威测试载体。
3. 在不扩大边界的前提下，为后续 `Lowfreq.test.jsx` 持续去肥建立一个干净起点。

本轮必须产出的核心结果：

- `Lowfreq.test.jsx` 不再承担 `tools tab` 行为验证
- `Lowfreq.toolsTab.test.jsx` 继续独立覆盖该主题
- 提交中不包含 `manual actions`、`scorePool`、`backtest`、`candidates` 等其他主题

## 2. 不在本轮完成

- `Lowfreq.jsx` 任意生产代码改动
- `Lowfreq.toolsTab.test.jsx` 的功能扩展
- `manual actions` 重复用例删除
- `backtest UX` 重复用例删除
- `scorePool baseline` 重复用例删除
- `Lowfreq.test.jsx` 全量清理或 mock 体系重写

## 3. 当前实施起点

### 3.1 已有现实基础

- [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 当前包含一个 `tools tab` 重复用例：
  - `keeps screener and stock check tools under workbench tools tab`
- [Lowfreq.toolsTab.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.toolsTab.test.jsx) 已存在并独立覆盖同一主题
- `Lowfreq.toolsTab.test.jsx` 已被历史提交承接，具备作为唯一权威载体的现实基础

### 3.2 当前结构性风险

- `Lowfreq.test.jsx` 当前是脏文件，混有多条主题，若整文件收口，容易误删其他断言
- 如果把本刀扩大成多主题去肥，提交边界会立刻失控
- 若删掉重复用例后出现共享 mock 未使用，容易诱发“顺手清理”冲动，从而把最小切片扩大

## 4. 实施原则

- 只删一个重复用例
- 不修改生产代码
- 不修改 `Lowfreq.toolsTab.test.jsx` 的断言语义
- 除非删除该用例后出现显式未使用依赖且能以最小 hunk 清理，否则不动共享 mock
- 若发现 `Lowfreq.test.jsx` 中该用例与其他主题存在意外耦合，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`

建议只包含以下逻辑：

- 删除 `keeps screener and stock check tools under workbench tools tab` 单个用例
- 如有必要，删除该用例专属且已显式未使用的最小依赖

明确不改：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.toolsTab.test.jsx`
- 其他任何 `Lowfreq*.test.jsx`

## 6. 总体分段

本计划建议分为四段执行：

- `LTT-R1`：冻结 `tools tab` duplicate cleanup 切片边界
- `LTT-R2`：在 `Lowfreq.test.jsx` 删除单个重复用例
- `LTT-R3`：验证独立 carrier 与 omnibus 文件
- `LTT-R4`：精确暂存并提交

## 7. 分段实施计划

### LTT-R1：冻结 `tools tab` duplicate cleanup 切片边界

目标：

- 在动手前确认哪些 `Lowfreq.test.jsx` 改动属于 `tools tab` 重复职责，哪些必须排除。

任务：

- 审计 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中 `tools tab` 相关用例
- 审计 [Lowfreq.toolsTab.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.toolsTab.test.jsx) 的现有覆盖
- 确认本轮不处理 `manual actions`、`backtest`、`scorePool`、`candidates`
- 确认本轮不修改 `Lowfreq.jsx`

完成判定：

- 已形成明确 include / exclude 清单
- 能把 `tools tab` 主题作为单个最小测试去肥切片独立完成

### LTT-R2：在 `Lowfreq.test.jsx` 删除单个重复用例

目标：

- 让 `Lowfreq.test.jsx` 不再承担 `tools tab` 行为验证。

任务：

- 在 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中定位：
  - `keeps screener and stock check tools under workbench tools tab`
- 仅删除该单个用例
- 删除后检查是否存在：
  - 明显未使用的 helper
  - 明显未使用的 import
- 只有在能以最小 hunk 清理的情况下，才附带最小整洁性修正

关键约束：

- 不顺手删除 `manual actions` 用例
- 不顺手删除 `backtest` 用例
- 不顺手调整 `buildTodayPayloads()`
- 不顺手改 mock 结构

完成判定：

- `Lowfreq.test.jsx` 中该重复用例已被移除
- 其余主题断言保持原样

### LTT-R3：验证独立 carrier 与 omnibus 文件

目标：

- 确认 `tools tab` 主题已经完全由独立 carrier 承接，且 omnibus 删除后未产生隐式断裂。

任务：

- 运行 `Lowfreq.toolsTab.test.jsx`
- 运行 `Lowfreq.test.jsx`
- 如删除用例后触发最近编辑文件的诊断问题，做最小修正

完成判定：

- `Lowfreq.toolsTab.test.jsx` 通过
- `Lowfreq.test.jsx` 通过
- 最近编辑文件无新增语法/结构错误

### LTT-R4：精确暂存并提交

目标：

- 用最小提交边界完成这条测试去肥切片。

任务：

- 精确暂存 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中与该用例删除直接相关的最小 hunk
- 如有最小未使用依赖清理，也仅暂存对应最小 hunk
- 生成一个只代表 `tools tab duplicate cleanup` 的提交

完成判定：

- 提交中不包含 `Lowfreq.jsx`
- 提交中不包含 `manual actions`、`scorePool`、`backtest`、`candidates` 的测试改动
- 提交 message 能准确表达这是测试去肥切片

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先定位 `Lowfreq.test.jsx` 中单个重复用例
2. 再删除该用例
3. 然后运行 `Lowfreq.toolsTab.test.jsx`
4. 最后运行 `Lowfreq.test.jsx`，确认 omnibus 未断

原因：

- 先删最小 hunk，可避免过早卷入共享 mock 整理
- 先验证独立 carrier，能快速证明职责迁移已成立
- 最后再跑 omnibus，更容易判断问题是否由去重本身引起

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit LTT：Lowfreq tools tab duplicate cleanup

范围：

- `Lowfreq.test.jsx` 中单个 `tools tab` 重复用例删除 hunk

可选附带：

- 该删除直接导致的最小未使用依赖清理 hunk

目标：

- 让 `tools tab` 行为测试职责只保留在独立 carrier 中

如果该提交无法与其他 `Lowfreq.test.jsx` 漂移安全分离，则应停止提交并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `Lowfreq.test.jsx` 中不再包含 `tools tab` 重复用例
2. `Lowfreq.toolsTab.test.jsx` 继续通过
3. `Lowfreq.test.jsx` 继续通过
4. 不修改 `Lowfreq.jsx`
5. 提交中不包含其他重复主题的去肥

## 11. 风险提示

- 当前最大风险不是删除一个测试，而是误把去肥扩大成 `Lowfreq.test.jsx` 的整文件整理
- 若共享 mock 恰好被多个主题复用，过度清理未使用项可能误伤其他用例
- 若暂存边界控制不严，容易把同文件中其他正在漂移的主题一起带进提交

## 12. 结论

本计划的核心不是“删一条测试”，而是：

- 把 `tools tab` 的测试职责从 omnibus 文件中拿掉
- 确认独立 carrier 已足够承担该主题
- 用最小可验证的方式建立 `Lowfreq.test.jsx` 去肥的第一条原子化路径

只有先完成这种单主题、单用例级别的去肥切片，后续 `manual actions`、`backtest`、`scorePool` 等重复职责收口才不会再次混刀。
