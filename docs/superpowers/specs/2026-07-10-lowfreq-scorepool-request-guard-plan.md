# Lowfreq ScorePool Request Guard 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-09-lowfreq-scorepool-request-guard-design.md`

## 1. 目标

本计划只覆盖 `Lowfreq.jsx` 中 `scorePool` 请求防串写（request guard）这一个生产切片，不扩展到 `Lowfreq` 其他 UI、文案或测试主题。

本轮目标只有三个：

1. 将 `loadScorePoolBlock()` 中的异步返回与当前请求身份绑定，避免旧日期返回覆盖新日期的股票池数据。
2. 保持修复边界只落在 `scorePool` 请求链，不波及 `manual actions`、`backtest`、`tools tab`、`shell/header` 等其他漂移主题。
3. 用现有 focused carrier `Lowfreq.scorePoolRequestGuard.test.jsx` 验证修复，并在相对 `HEAD` 能形成独立 hunk 时提交原子化切片。

本轮必须产出的核心结果：

- `Lowfreq.jsx` 中存在明确的 `scorePool` 请求身份保护
- 旧日期 summary 迟到返回时，不会再触发旧日期 pool 请求，也不会覆盖新日期已显示结果
- 提交中不包含其他 `Lowfreq.jsx` 混合 drift

## 2. 不在本轮完成

- `Lowfreq` 页头 / `PageHeader` / tab IA 调整
- `CandidatesPanel` 文案或布局调整
- `manual actions` endpoint 逻辑改动
- `backtest` UI、文案、详情链接或日期逻辑改动
- `Lowfreq.test.jsx` omnibus 去肥
- `Lowfreq.scorePoolBaseline.test.jsx` / `Lowfreq.toolsTab.test.jsx` / `Lowfreq.backtestUxDetailLink.test.jsx` 改动
- `Lowfreq` 任何全量重构

## 3. 当前实施起点

### 3.1 已有现实基础

- [Lowfreq.scorePoolRequestGuard.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.scorePoolRequestGuard.test.jsx) 已存在 focused carrier，直接验证：
  - 初始日期 `2026-06-09` 发出 summary 请求
  - 切换到新日期 `2026-06-10` 后发出新的 summary 与 pool 请求
  - 旧日期 summary 迟到返回时，不再触发旧日期 pool 请求
  - 页面最终只保留新日期数据
- [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 当前剩余 diff 里，`loadScorePoolBlock()` 是最窄且已有独立测试载体的生产主题。
- 这一主题与近期已完成切片不重叠：
  - `manual actions contract`
  - `backtest UX duplicate cleanup`
  - `candidates carrier realignment`

### 3.2 当前结构性风险

- `summary` 与 `pool` 是串行异步链路；当 `selectedDate` 变化后，旧请求若迟到返回，可能仍继续触发旧 pool 请求或写入旧结果。
- `Lowfreq.jsx` 还带有其他混合 drift；如果不先冻结 request-guard 边界，容易把本轮切片混成大包。
- 若修复方式依赖分散条件判断而不是统一请求身份令牌，后续维护与验证都会变得脆弱。

## 4. 实施原则

- 只改 `Lowfreq.jsx` 中与 `scorePool` 请求身份保护直接相关的最小 hunk
- 优先在 `loadScorePoolBlock()` 内完成 guard，而不是把状态管理扩散到无关区域
- 不改现有 contract、tab、文案、shell/header 结构
- 不修改 `Lowfreq.scorePoolRequestGuard.test.jsx`，除非现实执行证明测试本身有语法/结构问题
- 若修复后需要极小附带整洁性调整，必须与 request guard 有直接因果关系

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`

建议只包含以下逻辑：

- 在 `loadScorePoolBlock()` 请求链中为当前请求生成唯一身份
- 在 summary 返回后、pool 请求前确认该身份仍是当前有效请求
- 在 pool 返回前再次确认身份仍有效，只有当前请求才允许写入状态
- 对旧请求直接静默丢弃，不污染错误态与数据显示

明确不改：

- `neotrade3-dashboard/src/pages/Lowfreq.scorePoolRequestGuard.test.jsx`
- 任何其他 `Lowfreq*.test.jsx`
- `Lowfreq` 页面的 tab、header、copy、layout
- 任何后端接口 contract

## 6. 总体分段

本计划建议分为四段执行：

- `LSP-R1`：冻结 request guard 切片边界
- `LSP-R2`：在 `loadScorePoolBlock()` 内实现请求身份保护
- `LSP-R3`：运行 focused 验证并检查最近编辑文件
- `LSP-R4`：精确暂存并提交

## 7. 分段实施计划

### LSP-R1：冻结 request guard 切片边界

目标：

- 在动手前确认 `Lowfreq.jsx` 哪一段逻辑真正属于 scorePool stale-response 防护，哪些变更必须排除。

任务：

- 审计 [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) 中 `loadScorePoolBlock()` 的当前实现
- 对照 [Lowfreq.scorePoolRequestGuard.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.scorePoolRequestGuard.test.jsx) 的断言边界
- 明确排除 `PageHeader`、tabs、`CandidatesPanel`、`BacktestPanel`、manual endpoints 等其他主题

完成判定：

- 已形成明确 include / exclude 清单
- 能将 `scorePool request guard` 与其余 `Lowfreq.jsx` 混合 drift 清晰拆开

### LSP-R2：在 `loadScorePoolBlock()` 内实现请求身份保护

目标：

- 让 `scorePool` 的 summary -> pool 异步链只允许最新请求写入结果。

任务：

- 为当前 `scorePool` 请求生成 request id / token / epoch
- 在 summary 返回后检查请求是否已过期；若过期则停止后续 pool 请求
- 在 pool 返回后再次检查请求是否仍有效；仅当前请求允许写入 `scorePoolSummary` / `scorePoolItems` / `scorePoolMeta`
- 确保旧请求被丢弃时，不误清空已展示的新日期结果

关键约束：

- 不新增无关状态
- 不顺手重写整个 `loadScorePoolBlock()` 结构
- 不把 fix 扩大成别的异步防抖、缓存或 UI 优化主题
- 不因为 guard 而改动 endpoint、参数或 timeout

完成判定：

- 旧 summary 迟到返回时，不会再触发旧 pool 请求
- 旧 pool/summary 迟到结果不会覆盖新日期数据
- 新请求的正常成功路径保持不变

### LSP-R3：运行 focused 验证并检查最近编辑文件

目标：

- 证明 request guard 修复成立，且没有引入新的语法/结构问题。

任务：

- 运行 `Lowfreq.scorePoolRequestGuard.test.jsx`
- 如有必要，运行 `Lowfreq.scorePoolBaseline.test.jsx` 作为最小邻近回归
- 检查最近编辑文件是否出现新增语法/结构问题

完成判定：

- `Lowfreq.scorePoolRequestGuard.test.jsx` 通过
- 如运行 baseline，则 baseline 通过
- `Lowfreq.jsx` 无新增显式语法/结构错误

### LSP-R4：精确暂存并提交

目标：

- 只提交 `scorePool request guard` 这一条生产修复切片。

任务：

- 精确查看 `git diff HEAD -- neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 只暂存与 request identity guard 直接相关的最小 hunk
- 如果 `Lowfreq.jsx` 中其他 drift 无法与该 hunk 安全隔离，则停止提交并先回到边界审计

完成判定：

- 提交中不包含 shell/header/tab/candidates/backtest 等其他主题
- commit message 能准确表达 `scorePool request guard`

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先锁定 `loadScorePoolBlock()` 当前异步链边界
2. 再加 request identity guard
3. 先跑 `Lowfreq.scorePoolRequestGuard.test.jsx`
4. 视情况补跑 `Lowfreq.scorePoolBaseline.test.jsx`
5. 最后检查 `HEAD` 相对 diff 并决定是否提交

原因：

- 先界定异步链边界，能避免误把其他 `Lowfreq.jsx` 改动一起卷入
- focused carrier 先跑，能最快证明本轮修复是否命中核心问题
- `HEAD` diff 放在最后看，能避免在实现前被工作区混合噪音干扰判断

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit LSP：Lowfreq scorePool request guard

范围：

- `Lowfreq.jsx` 中 `loadScorePoolBlock()` 的 request identity guard 最小 hunk

目标：

- 防止旧日期返回覆盖当前 scorePool 结果
- 保持本次提交只代表一个异步竞态修复主题

如果该提交无法从 `Lowfreq.jsx` 其他 drift 中安全切开，则应停止提交并说明这是工作区收口，不强行制造大包 commit。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 旧 summary 迟到返回时，不再触发旧 pool 请求
2. 页面最终只显示新日期 scorePool 数据
3. `Lowfreq.scorePoolRequestGuard.test.jsx` 通过
4. 不修改无关 `Lowfreq*.test.jsx`
5. 不把其他 `Lowfreq.jsx` 漂移带入提交

## 11. 风险提示

- 当前最大风险不是 guard 写错，而是把 `Lowfreq.jsx` 里其他混合 diff 一起卷入提交
- 若 guard 分散在多个无关 effect / callback 中，后续可读性会下降，也更难证明边界
- 若为了保险而顺手补更多请求控制逻辑，容易把本轮从竞态修复扩大成架构改造

## 12. 结论

本计划的核心不是“重构 scorePool 模块”，而是：

- 在现有 `loadScorePoolBlock()` 上加一层最小请求身份保护
- 用已有 focused carrier 证明旧响应不会再覆盖新结果
- 在可隔离时形成一次真正原子化的生产修复提交
