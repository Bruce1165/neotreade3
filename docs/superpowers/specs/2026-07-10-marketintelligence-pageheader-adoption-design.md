# MarketIntelligence PageHeader Adoption Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `MarketIntelligence` 页顶部标题区的共享壳层收口：将原地标题文案与刷新按钮替换为共享 `PageHeader`，并完成随之产生的必要 import 收口，不扩展到 `BlockMessage` 提取、`SummaryCard -> MetricCard` 替换或其他页面主题。

目标是：

- 为 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx) 的顶部标题区建立统一的 `PageHeader` 承载
- 保留现有标题、subtitle、刷新触发与 loading 语义
- 将当前 `MarketIntelligence` 剩余 diff 中最窄的一条 shared-shell adoption 线独立出来

本切片不是：

- `BlockMessage` 共享组件提取
- `MetricCard` adoption
- 页面内容区块重排
- API、测试、网关或文档改动

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
- 顶部标题区与刷新按钮替换为 `PageHeader`
- 与该替换直接相关的 `RefreshCw` import 清理

Excluded:

- `neotrade3-dashboard/src/pages/MarketIntelligence.test.jsx`（若存在也不在本轮处理）
- `BlockMessage` import / helper 提取
- `MetricCard` import / 统计卡替换
- 其他页面与共享组件实现改动

## 3. Existing Context

当前代码已给出可核验证据：

- 当前 [MarketIntelligence.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/MarketIntelligence.jsx#L299-L305) 已存在 `PageHeader` 目标形态：
  - `title="主线审阅"`
  - `subtitle="先看赛道，再看候选，再核对主线与候选之间的联动关系"`
  - `onRefresh={fetchData}`
  - `loading={loading}`
- 该标题区的旧形态是页面内联 `div + button`，包含：
  - 标题
  - subtitle
  - 刷新按钮
  - `RefreshCw` 图标
- 当前 diff 中 `RefreshCw` 已从 `lucide-react` import 中移除，说明它是标题区替换的直接伴随变更
- `BlockMessage` 与 `MetricCard` 同时也在当前文件 diff 中出现，但它们各自有独立 import 与消费点，不属于本轮最窄边界

现状风险：

- 如果把 `PageHeader` 与 `BlockMessage`、`MetricCard` 一起处理，本轮会从“顶部壳层 adoption”扩大成多主题共享组件收口
- 如果把 `RefreshCw` import 清理拆出去，会人为制造比功能替换更碎的提交
- 如果顺手调整标题文案或刷新交互语义，本轮会从“壳层替换”扩大成 copy/behavior 主题

## 4. Approach Options

### Option A: 只做 `PageHeader` adoption，并把 `RefreshCw` 清理一并纳入（推荐）

仅处理：

- 顶部标题区从原地结构切到 `PageHeader`
- 删除已无消费点的 `RefreshCw`

Pros:

- 边界最窄，只落一个视觉壳层消费点
- 保持提交具备单一目的
- `RefreshCw` 清理有直接因果关系，不会变成独立整洁性主题

Cons:

- 其他共享组件 adoption 仍需后续单独处理

### Option B: `PageHeader + BlockMessage` 一起收口

Pros:

- 都属于共享壳层 adoption

Cons:

- 已经跨两个不同消费面
- 会降低提交解释纯度

### Option C: 直接处理 `MetricCard`

Pros:

- 视觉变化更明显

Cons:

- 涉及四张统计卡与 badge 结构，明显更宽

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `MarketIntelligence.jsx`
  - 顶部页面标题区由共享 `PageHeader` 承载
- `PageHeader`
  - 承载标题、subtitle、refresh 触发与 loading 反馈
- `RefreshCw`
  - 不再由页面局部消费，因此从本页 import 移除

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. 顶部标题区内联结构
2. `PageHeader` import
3. `RefreshCw` import 清理
4. `PageHeader` 所需的 `title` / `subtitle` / `onRefresh` / `loading` 传参

本轮不允许顺手改动：

- 标题文案
- subtitle 文案
- `fetchData` 行为
- `loading` 语义
- 统计卡结构
- 加载占位与错误面板

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `BlockMessage` 消费点
- 不修改 `MetricCard` / `SummaryCard` 主题
- 不新增测试载体，除非现有最小验证无法覆盖
- 若发现 `PageHeader` 现有 API 无法承载当前页面语义，应暂停并报告边界问题，不能静默扩大到共享组件实现改动

## 6. Testing Design

验证优先采用：

1. `MarketIntelligence.jsx` 最近改动后的最小语法/结构检查
2. 如存在低成本页面 focused test，可复用现有 carrier

默认不要求：

- 新增专用测试文件
- 为 `BlockMessage` 或 `MetricCard` 补断言
- 跨页面共享组件回归矩阵

原因：

- 本轮是顶部壳层 adoption，主要风险在边界纯度与基本结构安全

## 7. Validation

预期验证方式：

- 确认标题区由 `PageHeader` 承载
- 确认 `fetchData` 与 `loading` 仍被透传到标题区
- 确认 `RefreshCw` 已无本页消费点

## 8. Commit Boundary

目标提交应限制为：

- `MarketIntelligence.jsx` 中顶部标题区的 `PageHeader` adoption 最小 hunk

必须排除：

- `BlockMessage` 相关 hunk
- `MetricCard` 相关 hunk
- 其他页面、测试、后端与文档改动

若相对 `HEAD` 无法将 `PageHeader` adoption 与相邻共享组件改动安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
