# MarketIntelligence MetricCard Adoption Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `MarketIntelligence` 页内四张统计卡的共享壳层收口：将页面本地 `SummaryCard` 替换为共享 `MetricCard`，并完成随之产生的必要 import / helper 收口，不扩展到 `BlockMessage`、`ErrorPanel`、`PageHeader` 或其他页面主题。

目标是：

- 为 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 的四张统计卡建立统一的 `MetricCard` 承载
- 删除本页已可由共享组件替代的本地 `SummaryCard`
- 在保持四张卡片标题和 subtitle 语义不变的前提下，让 value / badge 展示契约与共享 `MetricCard` 形态对齐

本切片不是：

- `BlockMessage` adoption
- `ErrorPanel` 结构调整
- `PageHeader` 调整
- 页面内容区块重排
- API、测试、网关或文档改动

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- `MetricCard` import
- 本地 `SummaryCard` 删除
- 四张统计卡从 `SummaryCard` 切换到 `MetricCard`
- 与 `MetricCard` 形态直接相关的 `value` / `badge` 适配

Excluded:

- `neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx`
- `BlockMessage`
- `ErrorPanel`
- 其他页面与共享组件实现改动

## 3. Existing Context

当前代码已给出可核验证据：

- 当前 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 相对 `HEAD` 的剩余 diff 已只剩一组主题：
  - `MetricCard` import
  - 本地 `SummaryCard` 删除
  - 四张统计卡消费点替换
- 本地 `SummaryCard` 的现有契约是：
  - `title`
  - `value`
  - `subtitle`
  - `kind`
  - 组件内部基于 `summaryStateText()` / `summaryStateClass()` 生成状态胶囊
- 共享 [MetricCard.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/MetricCard.jsx) 的现有契约是：
  - `title`
  - `value`
  - `subtitle`
  - 可选 `badge`
  - 可选 `emphasis`
- 这意味着切到 `MetricCard` 后，`MarketIntelligence.jsx` 需要显式承担两类最小适配：
  - `value` 改为传入展示后的中文文案
  - `badge` 改为显式传入状态胶囊
- [MarketIntelligence.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx) 当前显式感知的是卡片标题：
  - `主线集中度`
  - `AI 聚焦`
  - 在加载过渡场景中再次断言 `主线集中度`
  - 但尚未对 value / badge 细节建断言

现状风险：

- 如果把 `MetricCard` 适配误扩大到 `summaryStateText()` / `summaryStateClass()` helper 重构，本轮会从消费点收口扩大成逻辑整理
- 如果顺手调整四张卡片的 copy，本轮会从 shared-shell adoption 扩大成文案主题
- 如果为 `MetricCard` 去修改共享组件实现，本轮会越过当前批准边界

## 4. Approach Options

### Option A: 只做 `MetricCard` adoption，并把 `SummaryCard` 删除一并纳入（推荐）

仅处理：

- 从共享组件 import `MetricCard`
- 删除本地 `SummaryCard`
- 让四张卡片显式传入 `value` / `badge`

Pros:

- 边界已经收敛为单一主题
- `SummaryCard` 删除与 `MetricCard` 接入有直接因果关系，不会变成独立整洁性主题
- 与现有 shared-shell 体系对齐后，页面内统计卡职责更清晰

Cons:

- 四张卡片都需要做最小展示适配，单刀宽度高于 `PageHeader` / `BlockMessage`

### Option B: 只删除 `SummaryCard`，继续保留现有卡片 DOM 结构

Pros:

- 视觉上可能更接近现状

Cons:

- 无法真正接入共享组件
- 会制造过渡态，后续仍需再切一次 `MetricCard`

### Option C: 同时改 `MetricCard` 共享组件实现

Pros:

- 可以把页面适配逻辑推回共享组件

Cons:

- 会越过当前批准边界
- 风险明显放大到跨页面共享组件主题

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `MarketIntelligence.jsx`
  - 只消费共享 `MetricCard` 作为四张统计卡壳层
  - 显式传入 `value`、`subtitle` 和 `badge`
- `MetricCard`
  - 负责统一的统计卡骨架与布局
- 本地 `SummaryCard`
  - 不再由本页持有，直接删除

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `MetricCard` import
2. 本地 `SummaryCard` 删除
3. 四张统计卡消费点从 `SummaryCard` 切换到 `MetricCard`
4. `value` 从原始状态值切到 `summaryStateText(...)`
5. `badge` 显式承载状态胶囊，并继续复用 `summaryStateClass(...)`

本轮不允许顺手改动：

- 四张卡片标题
- 四张卡片 subtitle 文案
- `summaryStateText()` / `summaryStateClass()` 的内部逻辑
- `MetricCard.jsx` 共享组件实现
- `BlockMessage`
- `ErrorPanel`

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改页面其他区块
- 不修改 `MetricCard.jsx`
- 不修改测试文件，除非现有最小验证无法覆盖
- 若发现现有 `MetricCard` API 无法承载当前四张卡片语义，应暂停并报告边界问题，不能静默扩大到共享组件实现改动

## 6. Testing Design

验证优先采用：

1. `MarketIntelligence.jsx` 最近改动后的最小语法/结构检查
2. 复用现有 [MarketIntelligence.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx) focused test

默认不要求：

- 新增专用测试文件
- 为共享 `MetricCard` 建跨页面回归矩阵
- 扩大到 helper 单测

原因：

- 本轮是统计卡 shared-shell adoption，主要风险在边界纯度与页面结构安全
- 现有测试已感知关键卡片标题，可作为最低成本的回归 carrier

## 7. Validation

预期验证方式：

- 确认本页从共享组件 import `MetricCard`
- 确认本地 `SummaryCard` 已删除
- 确认四张统计卡仍展示原有 title / subtitle 语义
- 确认 `MarketIntelligence.test.jsx` 仍通过

## 8. Commit Boundary

目标提交应限制为：

- `MarketIntelligence.jsx` 中 `MetricCard` adoption 的最小 hunk

必须排除：

- `BlockMessage`
- `ErrorPanel`
- 其他页面、测试、后端与文档改动

若相对 `HEAD` 无法将 `MetricCard` adoption 安全限制在本页消费点，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
