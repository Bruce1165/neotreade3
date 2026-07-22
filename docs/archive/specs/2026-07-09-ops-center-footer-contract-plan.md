# OpsCenter 页尾 Contract 收口实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-ops-center-footer-contract-design.md`

## 1. 目标

本计划只覆盖 `OpsCenter` 页尾 contract 收口落地，不扩展到 `/ops` 路由、刷新行为、错误态样式统一或其他页面主题线。

本轮目标只有三个：

1. 把 `OpsCenter` 页尾当前平铺的 `meta + evidence` 字段整理成独立只读“运行证据”区块。
2. 为该区块新增一个独立聚焦测试载体。
3. 用最小验证与最小提交边界收口，不带入其他页面漂移。

本轮必须产出的核心结果：

- 页面底部存在稳定的“运行证据”区块
- 当前已有 6 个字段全部保留并按既有 contract 展示
- 提交中不包含路由、刷新或错误态等其他主题线

## 2. 不在本轮完成

- `/ops` 路由命中验证
- `OpsCenter` 刷新或日期切换行为
- `OpsCenter` 主卡片或表格区块重排
- `OpsCenter` 错误态样式统一
- `OpsCenter.test.jsx` 的继续做胖
- 后端字段增删或接口 contract 调整

## 3. 当前实施起点

### 3.1 已有现实基础

- [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 已存在，并在页面底部直接消费：
  - `meta.snapshot_generated_at`
  - `evidence.latest_run_date`
  - `evidence.expected_trade_date`
  - `evidence.overdue_shifted_count`
  - `evidence.inconsistency_count`
  - `evidence.pending_intents_after`
- 当前这组字段以一段平铺 `span` 方式展示在页尾
- [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx) 已覆盖主区块渲染、异常摘要和失败态
- 当前缺口只在页尾证据字段缺少独立区块边界与独立 contract 回归保护

### 3.2 当前结构性风险

- 页尾信息当前直接内嵌在 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 末尾，缺少单独命名区块，后续容易被其他页面改动顺手带走
- 若继续把断言写进 [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx)，会进一步放大混杂测试文件
- 若借机调整主区块或错误态，会把这刀从“页尾 contract 收口”扩大成“页面治理”

## 4. 实施原则

- 优先新增独立测试文件，不扩写 `OpsCenter.test.jsx`
- 生产改动只围绕页尾“运行证据”区块本身
- 继续沿用 `displayText()` 作为缺失值回退
- 断言聚焦字段集合、标签映射与缺失值回退
- 如果边界无法保持在页尾区块内，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/OpsCenter.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.footerContract.test.jsx`

建议只包含以下逻辑：

- 将页尾 6 个字段整理为独立只读“运行证据”区块
- 保持字段语义与取值来源不变
- 新增独立测试，验证标签、字段值与缺失值回退

明确不改：

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/pages/Overview.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.test.jsx`
- `DateSelector`、`PageHeader` 等共享组件
- 后端接口和 contract

## 6. 总体分段

本计划建议分为四段执行：

- `O2-R1`：冻结页尾 contract 切片边界
- `O2-R2`：整理“运行证据”区块
- `O2-R3`：新增独立 contract 测试载体
- `O2-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### O2-R1：冻结页尾 contract 切片边界

目标：

- 在动手前确认页尾区块的字段集合、展示边界，以及哪些主题线必须排除。

任务：

- 审计 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 页尾字段现状
- 审计 [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx) 已覆盖内容，避免重复覆盖
- 确认本刀只保留 6 个既有字段
- 记录必须排除的路由、刷新、错误态和主区块主题线

完成判定：

- 已形成明确的 include / exclude 清单
- 能保证本刀只围绕页尾区块推进

### O2-R2：整理“运行证据”区块

目标：

- 让页尾事实字段从平铺片段变为稳定、可识别的独立只读区块。

任务：

- 在 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 中把当前页尾字段整理为“运行证据”区块
- 保留现有 6 个标签与字段来源
- 继续使用 `displayText()` 处理空值
- 不引入任何交互动作、折叠、筛选或跳转

关键约束：

- 不新增字段
- 不改字段语义
- 不顺手调整主区块布局或样式主题

完成判定：

- 页面底部有明确的“运行证据”区块
- 6 个字段仍全部可见

### O2-R3：新增独立 contract 测试载体

目标：

- 为页尾“运行证据”区块建立独立回归保护。

任务：

- 新增 `OpsCenter.footerContract.test.jsx`
- mock `getOpsCenterSummary`
- mock `useApp()`
- 复用最小 `DateSelector` 替身或等价最小 mock
- 编写聚焦用例，验证：
  - 区块标题存在
  - 6 个标签存在
  - 6 个字段值按 contract 渲染
  - 缺失值回退到 `--`

关键约束：

- 不复验主区块卡片、表格或异常摘要
- 不把测试与刷新、路由行为绑在一起
- 不把该测试写成整页快照回归

完成判定：

- 独立测试文件可以单独保护页尾字段 contract

### O2-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `OpsCenter.footerContract.test.jsx`
- 如触及 `OpsCenter.jsx`，补跑 `OpsCenter.test.jsx`
- 检查暂存区 diff，只保留页尾区块相关改动与新测试文件
- 提交前确认不带入其他页面、路由或共享组件漂移

完成判定：

- 测试通过
- 提交边界干净
- 本刀仍然是“页尾 contract 收口”，不是“页面扩展重构”

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先审计 `OpsCenter.jsx` 页尾现状与 `OpsCenter.test.jsx` 现有覆盖
2. 再整理 `OpsCenter.jsx` 中的“运行证据”区块
3. 然后新增 `OpsCenter.footerContract.test.jsx`
4. 最后做验证、精确暂存与提交

原因：

- 先定字段边界，再写 UI 收口，能避免后续测试固化错误范围
- 先收口生产区块，再写聚焦测试，断言对象更稳定
- 把提交边界检查放到最后，可最大限度避免混入其他 `OpsCenter` 主题线

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit A：OpsCenter 页尾 contract 收口

范围：

- `OpsCenter.jsx` 中与“运行证据”区块直接相关的最小 hunk
- `OpsCenter.footerContract.test.jsx`

目标：

- 为 `OpsCenter` 页尾已有事实字段建立稳定展示区块与独立回归保护

如果页尾相关改动无法与主区块或其他主题线安全分离，则应停止实现并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 页面底部存在“运行证据”区块
2. `快照生成 / 最近任务 / 目标交易日 / 顺延待处理 / 收口异常 / 日后待执行` 六个标签全部存在
3. 六个字段值按既有 contract 正常渲染
4. 缺失值仍回退到 `--`
5. 使用独立测试载体，不扩写 `OpsCenter.test.jsx`
6. 提交中不包含 `/ops` 路由、刷新行为、错误态或其他页面主题线

## 11. 风险提示

- 当前最大风险不是实现难度，而是页尾区块与其他 `OpsCenter` 展示代码贴得很近，容易顺手带入额外改动
- 如果断言写成整页展示回归，会把本刀和主区块细节绑定过深
- 如果借这刀统一错误态或主区块布局，会破坏这条线的原子性

## 12. 结论

本计划的核心不是“补一个更大的 OpsCenter 页面测试”，而是：

- 给页尾已有 6 个事实字段建立稳定的独立展示区块
- 保持测试文件物理独立
- 继续沿用现有字段语义与缺失值回退
- 把生产改动控制在页尾区块之内

只有这样，后续 `OpsCenter` 的更宽展示治理、错误态统一或其他页面优化，才能继续保持原子化推进。
