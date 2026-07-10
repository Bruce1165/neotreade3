# Lowfreq Test Market-Phase Carrier Cleanup 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-lowfreq-test-marketphase-carrier-cleanup-design.md`

## 1. 目标

本计划只覆盖当前工作区中 `Lowfreq.test.jsx` 的 market-phase 载体去肥，不扩展到任何生产代码或其他 focused carrier。

本轮目标只有三个：

1. 从 `Lowfreq.test.jsx` 删除与现存 3 条 market-phase 用例无关的 mock、fixture 和残余测试数据。
2. 让 `Lowfreq.test.jsx` 的职责重新收口到 market-phase / hot-sectors。
3. 先完成工作区去肥收口，再核对相对 `HEAD` 是否仍形成真实最小差异。

本轮必须产出的核心结果：

- `Lowfreq.test.jsx` 不再携带 `react-router-dom`、`localStorage` 和 `lowfreq-score/pool|events|summary` 这组无关依赖
- 3 条 market-phase 用例继续通过
- 若相对 `HEAD` 没有真实差异，则本轮结论明确为“只完成工作区收口，不产生 commit”

## 2. 不在本轮完成

- `Lowfreq.jsx` 任意生产代码改动
- `Lowfreq.scorePoolBaseline.test.jsx` 的改造
- `Lowfreq.manualActionsContract.test.jsx` 的改造
- `Lowfreq.candidatesWorkbenchSplit.test.jsx` 的改造
- `Lowfreq.test.jsx` 的 today-page 契约重构
- `buildTodayPayloads()` 的整体验证模型重写
- 页面壳层、路由或共享组件调整

## 3. 当前实施起点

### 3.1 已有现实基础

- [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 当前实际只剩 3 条 market-phase 用例：
  - `loads today snapshot and renders market + sector cards`
  - `shows fallback instead of NaN percent when market phase fields are missing`
  - `keeps hot sectors visible when market phase block fails`
- 同文件当前仍带有以下与这 3 条用例无关的主题依赖：
  - `react-router-dom` 的 `Link` mock
  - `localStorage` stub
  - `/api/lowfreq-score/pool?...`
  - `/api/lowfreq-score/events?...`
  - `/api/lowfreq-score/summary?...`
- 这些主题已有 focused carriers 承接：
  - [Lowfreq.scorePoolBaseline.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.scorePoolBaseline.test.jsx)
  - [Lowfreq.manualActionsContract.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx)
  - [Lowfreq.candidatesWorkbenchSplit.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx)

### 3.2 当前结构性风险

- `Lowfreq.test.jsx` 表面上已经是 market-phase carrier，但文件内部仍暗含多主题残余依赖
- 如果顺手改造 `buildTodayPayloads()` 或共享 mock 结构，很容易从“去肥”扩大成“测试重构”
- 若预设这轮一定产出 commit，容易忽略“相对 `HEAD` 可能只是工作区收口”的事实边界

## 4. 实施原则

- 先做工作区去肥收口
- 不预设一定产生 commit
- 不修改生产代码
- 不修改 focused carriers
- 只删除已被证据证明与 3 条 market-phase 用例无关的 mock / fixture
- 若删除某项依赖后发现用例仍真实使用它，必须以测试或代码路径证明，而不是凭感觉保留
- 若相对 `HEAD` 只形成工作区收口，则如实报告，不强行制造提交

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`

建议只包含以下逻辑：

- 删除 `react-router-dom` mock
- 删除 `localStorage` stub 及其清理
- 从 `buildTodayPayloads()` 中删除：
  - `/api/lowfreq-score/pool?...`
  - `/api/lowfreq-score/events?...`
  - `/api/lowfreq-score/summary?...`
- 保留 market-phase / hot-sectors 3 条用例所需的最小 payload

明确不改：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 其他任何 `Lowfreq*.test.jsx`
- `DateSelector` mock
- `fetchApi` mock 机制
- 3 条 market-phase 用例的断言主题

## 6. 总体分段

本计划建议分为四段执行：

- `LMP-R1`：冻结 market-phase carrier cleanup 切片边界
- `LMP-R2`：在 `Lowfreq.test.jsx` 删除无关 mock / fixture
- `LMP-R3`：验证 omnibus 文件仍通过
- `LMP-R4`：核对相对 `HEAD` 差异，并决定提交或仅收口

## 7. 分段实施计划

### LMP-R1：冻结 market-phase carrier cleanup 切片边界

目标：

- 在动手前确认哪些 `Lowfreq.test.jsx` 内容属于 market-phase 无关夹带，哪些必须保留。

任务：

- 审计 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 中现存 3 条用例
- 核对 `react-router-dom`、`localStorage`、`pool/events/summary` 是否未被这 3 条用例消费
- 确认本轮不处理 `scorePool`、`manual actions`、`candidates`
- 确认本轮不修改 `Lowfreq.jsx`

完成判定：

- 已形成明确 include / exclude 清单
- 可以把 market-phase 去肥作为最小测试切片独立完成

### LMP-R2：在 `Lowfreq.test.jsx` 删除无关 mock / fixture

目标：

- 让 `Lowfreq.test.jsx` 只保留 market-phase / hot-sectors 所需的最小依赖。

任务：

- 删除 `react-router-dom` mock
- 删除 `localStorage` stub 与对应清理
- 删除 `buildTodayPayloads()` 中 `pool/events/summary` 相关 payload
- 删除后检查是否存在：
  - 明显未使用的 import
  - 明显未使用的 helper 或变量
- 仅在能以最小 hunk 清理的情况下，附带最小整洁性修正

关键约束：

- 不顺手重写 `buildTodayPayloads()` 结构
- 不顺手删除其他主题测试
- 不顺手改 `fetchApi` mock 机制
- 不顺手扩大 market-phase 断言

完成判定：

- 目标无关 mock / fixture 已移除
- 其余 market-phase 断言保持原样

### LMP-R3：验证 omnibus 文件仍通过

目标：

- 确认 market-phase 去肥没有破坏 `Lowfreq.test.jsx` 的剩余职责。

任务：

- 运行 `npm test -- src/pages/Lowfreq.test.jsx`
- 如删除结果与 `scorePool` 边界判断出现不确定性，可补跑 `npm test -- src/pages/Lowfreq.scorePoolBaseline.test.jsx`
- 若最近编辑文件出现显式语法/结构问题，做最小修正

完成判定：

- `Lowfreq.test.jsx` 通过
- 如有补跑，相关 focused carrier 通过
- 最近编辑文件无新增语法/结构错误

### LMP-R4：核对相对 `HEAD` 差异，并决定提交或仅收口

目标：

- 根据真实差异判断本轮结果是“原子化提交”还是“工作区收口”。

任务：

- 核对 [Lowfreq.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.test.jsx) 相对 `HEAD` 的实际 hunk
- 判断删除无关 mock / fixture 后是否仍形成可安全隔离的最小差异
- 如果形成最小差异：
  - 精确暂存相关 hunk
  - 生成只代表 `market-phase carrier cleanup` 的提交
- 如果不形成最小差异：
  - 不提交
  - 明确记录为“已完成工作区去肥收口，不产生新 commit”

完成判定：

- 结论基于相对 `HEAD` 的真实差异，而不是预设
- 若提交，则提交中不包含生产代码和其他测试文件
- 若不提交，则明确说明原因和边界

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先定位 `Lowfreq.test.jsx` 中 3 条用例实际消费的数据
2. 再删除无关 mock / fixture
3. 然后运行 `Lowfreq.test.jsx`
4. 如有必要，补跑 `Lowfreq.scorePoolBaseline.test.jsx`
5. 最后核对相对 `HEAD` 是否仍有真实差异

原因：

- 先判断真实消费，再删依赖，可以避免误把历史残留当成当前必要输入
- 先验证 omnibus 文件，再决定是否补跑 focused carrier，能保持验证成本最小
- 先完成工作区收口，再决定是否提交，最符合当前事实边界

## 9. 建议提交切分

本轮默认不是“必有提交”，而是“先收口，再决定是否提交”。

### 若可提交：Commit LMP

范围：

- `Lowfreq.test.jsx` 中与 market-phase 无关的 mock / fixture 删除 hunk

可选附带：

- 该删除直接导致的最小未使用依赖清理 hunk

目标：

- 让 `Lowfreq.test.jsx` 的职责只保留在 market-phase / hot-sectors

### 若不可提交

结论应为：

- 工作区已完成去肥收口
- 相对 `HEAD` 不存在可安全隔离的最小差异
- 因而不产生新 commit

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `Lowfreq.test.jsx` 中不再包含 `react-router-dom` mock
2. `Lowfreq.test.jsx` 中不再包含 `localStorage` stub
3. `buildTodayPayloads()` 中不再包含 `pool/events/summary` 这组无关 payload
4. `Lowfreq.test.jsx` 继续通过
5. 不修改 `Lowfreq.jsx`
6. 最终对“是否提交”的结论基于相对 `HEAD` 的真实差异

## 11. 风险提示

- 当前最大风险不是删几个 mock，而是误把去肥扩大成 today-page 测试重构
- 如果 `buildTodayPayloads()` 某段数据被隐式复用，过度整理可能误伤 market-phase 用例
- 若因为“顺手清理”把其他主题 fixture 一并改掉，会再次模糊 omnibus 与 focused carrier 的边界

## 12. 结论

本计划的核心不是“删几段无关数据”，而是：

- 把 `Lowfreq.test.jsx` 的职责收回到 market-phase / hot-sectors
- 确保其他主题继续由 focused carriers 独占
- 先完成工作区去肥收口，再根据相对 `HEAD` 的事实决定是否形成提交

只有坚持这种“职责先收口、提交后判断”的推进方式，`Lowfreq.test.jsx` 才不会再次回流成多主题 omnibus 载体。
