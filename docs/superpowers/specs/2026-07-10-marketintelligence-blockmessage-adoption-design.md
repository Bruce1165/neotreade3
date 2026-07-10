# MarketIntelligence BlockMessage Adoption Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `MarketIntelligence` 页内加载占位块的共享壳层收口：将页面内联 `BlockMessage` helper 替换为共享 `BlockMessage` 组件，并完成随之产生的必要 import / helper 收口，不扩展到 `MetricCard` 统计卡替换、`ErrorPanel`、`PageHeader` 或其他页面主题。

目标是：

- 为 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 中两个加载态占位建立统一的 `BlockMessage` 承载
- 删除本页已可由共享组件替代的本地 `BlockMessage` helper
- 将当前 `MarketIntelligence` 剩余 diff 中最窄的一条 shared-shell adoption 线独立出来

本切片不是：

- `MetricCard` adoption
- `SummaryCard` 删除
- `ErrorPanel` 结构调整
- 页面内容区块重排
- API、测试、网关或文档改动

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- `BlockMessage` import
- 本地 `BlockMessage` helper 删除
- 两个加载态消费点继续使用相同 message 文案

Excluded:

- `neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx`
- `MetricCard` import / 统计卡替换
- `SummaryCard` 删除
- `ErrorPanel` 与错误态文案
- 其他页面与共享组件实现改动

## 3. Existing Context

当前代码已给出可核验证据：

- 当前 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 相对 `HEAD` 的剩余 diff 同时混有两组主题：
  - `BlockMessage` import + 本地 helper 删除
  - `SummaryCard -> MetricCard` 统计卡替换
- 共享 [BlockMessage.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/BlockMessage.jsx) 现有契约为：
  - `tone = 'gray'`
  - `message`
  - 可选 `onRetry`
  - 可选 `retryLabel`
- `MarketIntelligence.jsx` 当前两个消费点分别是：
  - `决策摘要加载中...`
  - `主线审阅加载中...`
- `HEAD` 中本地 `BlockMessage` helper 的默认视觉语义与共享组件当前 `gray` tone 一致，均为灰底边框的加载提示块
- [MarketIntelligence.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx) 当前只显式感知其中一个加载 message：
  - `主线审阅加载中...`
  - 并未对本地 helper 实现细节建断言

现状风险：

- 如果把 `BlockMessage` 与 `MetricCard` 一起处理，本轮会从“加载占位共享化”扩大成多主题共享组件收口
- 如果把本地 `BlockMessage` helper 删除拆成另一条线，会人为制造比消费点替换更碎的提交
- 如果顺手调整 `ErrorPanel` 或加载文案，本轮会从 shared-shell adoption 扩大成错误态 / copy 主题

## 4. Approach Options

### Option A: 只做 `BlockMessage` adoption，并把本地 helper 删除一并纳入（推荐）

仅处理：

- 从共享组件 import `BlockMessage`
- 删除本地 `BlockMessage` helper
- 保持两个加载占位仍使用原 message

Pros:

- 边界最窄，只覆盖同一类加载占位消费点
- 本地 helper 删除与共享组件接入有直接因果关系，不会变成独立整洁性主题
- 现有测试感知面低，最小验证成本较低

Cons:

- `MetricCard` 仍需后续单独处理

### Option B: `BlockMessage + MetricCard` 一起收口

Pros:

- 都属于共享组件 adoption

Cons:

- 已跨“加载占位”和“统计卡”两个不同消费面
- 会降低提交解释纯度

### Option C: 直接处理 `MetricCard`

Pros:

- 视觉变化更明显

Cons:

- 涉及四张统计卡与 badge/value 语义，明显更宽
- 测试感知面更多，验证成本更高

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `MarketIntelligence.jsx`
  - 只消费共享 `BlockMessage` 作为加载态占位
- `BlockMessage`
  - 承载默认灰色 tone 的 message 展示和可选 retry 交互
- 本地 `BlockMessage` helper
  - 不再由本页持有，直接删除

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `BlockMessage` import
2. 本地 `BlockMessage` helper 删除
3. 两个加载态消费点继续渲染 `BlockMessage`
4. 保持原有 `message` 字面量不变

本轮不允许顺手改动：

- `主线审阅加载中...` 文案
- `决策摘要加载中...` 文案
- `ErrorPanel`
- `MetricCard` / `SummaryCard`
- `fetchData`、`loading`、请求时序语义

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改四张统计卡消费点
- 不修改 `MetricCard` / `SummaryCard` 主题
- 不修改 `ErrorPanel`
- 不新增测试载体，除非现有最小验证无法覆盖
- 若发现共享 `BlockMessage` 现有 API 无法承载当前加载占位语义，应暂停并报告边界问题，不能静默扩大到共享组件实现改动

## 6. Testing Design

验证优先采用：

1. `MarketIntelligence.jsx` 最近改动后的最小语法/结构检查
2. 复用现有 [MarketIntelligence.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx) focused test

默认不要求：

- 新增专用测试文件
- 为 `MetricCard` 补断言
- 跨页面共享组件回归矩阵

原因：

- 本轮是加载占位 shared-shell adoption，主要风险在边界纯度与基本结构安全
- 现有测试已感知 `主线审阅加载中...`，足以作为最小 carrier

## 7. Validation

预期验证方式：

- 确认本页从共享组件 import `BlockMessage`
- 确认本地 `BlockMessage` helper 已删除
- 确认两个加载占位仍展示原 message
- 确认 `MarketIntelligence.test.jsx` 仍通过

## 8. Commit Boundary

目标提交应限制为：

- `MarketIntelligence.jsx` 中 `BlockMessage` adoption 的最小 hunk

必须排除：

- `MetricCard` 相关 hunk
- `SummaryCard` 删除
- 其他页面、测试、后端与文档改动

若相对 `HEAD` 无法将 `BlockMessage` adoption 与相邻 `MetricCard` 改动安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
