# OpsCenter 重拉测试实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-ops-center-reload-test-design.md`

## 1. 目标

本计划只覆盖 `OpsCenter` 的重拉行为测试落地，不扩展到 `/ops` 路由、页面 contract 收口、错误态样式统一或其他页面主题线。

本轮目标只有三个：

1. 为 `OpsCenter` 新增一个独立的重拉行为测试载体。
2. 验证点击刷新会重新请求当前日期。
3. 验证 `selectedDate` 变化会重新请求新日期。

本轮必须产出的核心结果：

- `OpsCenter` 的两个关键重拉入口有独立回归保护
- 断言聚焦在请求调用序列，而不是整页 UI 细节
- 提交中不包含无关页面、路由或样式主题线

## 2. 不在本轮完成

- `/ops` 路由命中验证
- `OpsCenter` 页尾 contract 收口
- `OpsCenter` 错误态样式统一
- `Overview` 或其他页面联动
- `OpsCenter.test.jsx` 的继续做胖
- 为了测试顺手重构 `DateSelector` 或 `useApp`

## 3. 当前实施起点

### 3.1 已有现实基础

- [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 已存在，并通过 `getOpsCenterSummary(selectedDate)` 拉取页面数据
- `OpsCenter` 已接入 `DateSelector`，并向其传入 `onRefresh={load}`
- [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx) 已覆盖正常渲染、异常摘要和失败态
- 当前缺口只在“刷新重拉”和“日期变化重拉”的独立行为回归

### 3.2 当前结构性风险

- `OpsCenter.test.jsx` 已承担现有页面展示验证，不适合继续混入新的触发链断言
- `OpsCenter.jsx` 若存在混杂依赖，测试很容易被真实上下文拖宽
- 若为测试便利直接改生产代码，容易把本刀从“补行为保护”扩大成“页面重构”

## 4. 实施原则

- 优先新增独立测试文件，不扩写 `OpsCenter.test.jsx`
- 优先通过 mock 隔离依赖，先尝试零生产代码改动
- 断言只围绕 `getOpsCenterSummary(selectedDate)` 的调用序列
- 若必须改 `OpsCenter.jsx`，只能做“仅为可测试性服务”的最小改动
- 如果最小改动边界无法成立，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/OpsCenter.reload.test.jsx`
- 如确有必要，`neotrade3-dashboard/src/pages/OpsCenter.jsx`

建议只包含以下逻辑：

- mock `getOpsCenterSummary`
- mock `DateSelector`，暴露刷新触发入口
- 用可控 provider 或 mock `useApp()` 驱动 `selectedDate` 变化
- 验证首次加载、刷新重拉、日期变化重拉的调用序列

明确不改：

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/pages/Overview.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.test.jsx`
- 共享 UI 组件样式与文案

## 6. 总体分段

本计划建议分为四段执行：

- `O3-R1`：冻结测试边界与依赖策略
- `O3-R2`：新增独立重拉测试载体
- `O3-R3`：如有必要，补最小可测试性改动
- `O3-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### O3-R1：冻结测试边界与依赖策略

目标：

- 在动手前确认 `OpsCenter` 的最小测试依赖，以及哪些主题线必须排除。

任务：

- 审计 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 的数据请求入口与 `DateSelector` 接线方式
- 审计 [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx) 已覆盖内容，避免重复覆盖
- 确认 `selectedDate` 的来源和最小替身方式
- 确认测试是否能通过 mock `DateSelector` + mock `useApp()` 完成

完成判定：

- 已形成明确的 include / exclude 清单
- 能判断是否可以做到零生产代码改动

### O3-R2：新增独立重拉测试载体

目标：

- 建立 `OpsCenter` 的独立重拉行为回归保护。

任务：

- 新增 `OpsCenter.reload.test.jsx`
- mock `getOpsCenterSummary`
- mock `DateSelector`，将 `onRefresh` 暴露为测试可点击入口
- 提供最小 `selectedDate` 驱动方式，支持测试内主动切换日期
- 编写两个聚焦用例：
  - 点击刷新后再次请求当前日期
  - 日期变化后再次请求新日期

关键约束：

- 不验证整页所有区块内容更新
- 不把测试写成页面全集成回归
- 不把刷新和日期切换与 `/ops` 路由或导航行为绑在一起

完成判定：

- 独立测试文件可以单独证明两个触发源都成立

### O3-R3：如有必要，补最小可测试性改动

目标：

- 只有在纯测试方案无法成立时，才为 `OpsCenter` 补最小可测试性支点。

任务：

- 判断失败原因是否确实来自不可测结构，而非 mock 方案不足
- 若必须修改 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx)，只允许处理：
  - 暴露稳定触发点
  - 稳定 `load` 绑定关系
  - 降低测试对复杂上下文的耦合

关键约束：

- 不借机调整页面布局、文案或 contract
- 不引入与本切片无关的新状态管理
- 改动必须能用一句话解释其“仅为可测试性服务”

完成判定：

- 生产改动被控制在最小范围
- 改动不改变用户可见行为

### O3-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `OpsCenter.reload.test.jsx`
- 若触及 `OpsCenter.jsx`，补跑 `OpsCenter.test.jsx`
- 检查暂存区 diff，只保留新测试文件与必要最小生产改动
- 提交前确认不带入其他页面、路由或样式漂移

完成判定：

- 测试通过
- 提交边界干净
- 本刀仍然是“行为回归保护”，不是“页面功能扩展”

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先审计 `OpsCenter.jsx` 与 `OpsCenter.test.jsx`
2. 再新增 `OpsCenter.reload.test.jsx`
3. 只有在纯测试方案失败时，才回补 `OpsCenter.jsx` 的最小可测试性改动
4. 最后做验证、精确暂存与提交

原因：

- 先定依赖策略，再写测试，能最大限度压住边界
- 先尝试零生产代码改动，能避免把测试补齐演变成页面重构
- 把生产改动放到最后决策，更容易及时止损

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit A：OpsCenter 重拉行为测试

范围：

- `OpsCenter.reload.test.jsx`
- 如确有必要，再加 `OpsCenter.jsx` 中仅为可测试性服务的最小 hunk

目标：

- 为 `OpsCenter` 的刷新重拉与日期变化重拉建立独立回归保护

如果 `OpsCenter.jsx` 的最小改动仍无法与其他主题线安全分离，则应停止实现并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 首次渲染会请求当前日期
2. 点击刷新会再次请求同一日期
3. `selectedDate` 变化会再次请求新日期
4. 使用独立测试载体，不扩写 `OpsCenter.test.jsx`
5. 提交中不包含 `/ops` 路由、页尾 contract 或其他页面主题线

## 11. 风险提示

- 当前最大风险不是测试代码本身，而是测试依赖注入方式可能把页面上下文拖宽
- 如果断言写成“所有区块都刷新成功”，会把本刀和页面展示细节绑定过深
- 如果为了测试方便重构 `OpsCenter.jsx`，会破坏这条线的原子性

## 12. 结论

本计划的核心不是“再补一个页面测试”，而是：

- 给 `OpsCenter` 的两个关键重拉入口建立最窄的一层行为保护
- 保持测试文件物理独立
- 优先零生产代码改动
- 如需触及生产文件，也只做最小可测试性收口

只有这样，后续 `OpsCenter` 的 contract 收口、错误态统一和更宽的页面治理，才能继续保持原子化推进。
