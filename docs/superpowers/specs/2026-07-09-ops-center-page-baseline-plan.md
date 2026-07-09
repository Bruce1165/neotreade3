# OpsCenter 页面基线实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-ops-center-page-baseline-design.md`

## 1. 目标

本计划只覆盖 `OpsCenter` 页面基线落地，不扩展到页尾 contract 收口、`/ops` 路由、刷新行为或其他页面主题线。

本轮目标只有三个：

1. 把 `OpsCenter.jsx` 页面本体正式纳入仓库基线。
2. 把 `OpsCenter.test.jsx` 页面基线测试正式纳入仓库基线。
3. 在提交边界中显式排除 `O2` 的页尾“运行证据”区块和 `OpsCenter.footerContract.test.jsx`。

本轮必须产出的核心结果：

- `OpsCenter` 页面主结构正式进入提交历史
- 页面基线测试能独立保护正常渲染、异常摘要和失败态
- 提交中不包含页尾 contract 线

## 2. 不在本轮完成

- `OpsCenter.jsx` 中“运行证据”区块
- `OpsCenter.footerContract.test.jsx`
- `/ops` 路由命中验证
- 刷新或日期切换行为扩展
- `OpsCenter.reload.test.jsx` 的新增修改
- 共享组件改动
- 页面功能扩展

## 3. 当前实施起点

### 3.1 已有现实基础

- 共享展示骨架层已进入 `HEAD`：
  - [BlockMessage.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/BlockMessage.jsx)
  - [MetricCard.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/MetricCard.jsx)
  - [PageHeader.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/PageHeader.jsx)
  - [StatusPill.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/StatusPill.jsx)
  - [statusCopy.js](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/components/statusCopy.js)
- 当前工作区中以下文件已存在但尚未进入基线：
  - [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx)
  - [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx)
- 当前工作区中的 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 已经混入页尾“运行证据”区块
- [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx) 当前只覆盖页面主结构、异常摘要和失败态
- [OpsCenter.reload.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.reload.test.jsx) 已在 `HEAD`，属于独立行为测试线

### 3.2 当前结构性风险

- 当前最大风险不是依赖闭包，而是 `OpsCenter.jsx` 同时承载页面基线与 `O2` 页尾线
- 若直接整文件提交 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx)，会把“运行证据”区块错误带入 `B`
- 若把页尾 contract 断言继续写进 [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx)，会破坏页面层与 contract 层的分离

## 4. 实施原则

- 只收口 `OpsCenter.jsx` 页面主结构与 `OpsCenter.test.jsx`
- `OpsCenter.jsx` 在本轮提交中必须排除页尾“运行证据”区块
- `OpsCenter.test.jsx` 只承担页面基线测试，不承担页尾 contract 测试
- 不修改共享组件
- 若页面基线无法与页尾线分离，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/OpsCenter.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.test.jsx`

建议只包含以下逻辑：

- 收口页面标题、副标题与主区块
- 保留失败态
- 保留异常摘要展示
- 从 `OpsCenter.jsx` 的本次提交内容中排除页尾“运行证据”区块

明确不改：

- `neotrade3-dashboard/src/pages/OpsCenter.footerContract.test.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.reload.test.jsx`
- `neotrade3-dashboard/src/App.jsx`
- 共享组件文件
- 其他页面文件

## 6. 总体分段

本计划建议分为四段执行：

- `B-R1`：冻结页面基线与页尾 contract 的切片边界
- `B-R2`：整理 `OpsCenter.jsx` 的页面基线版本
- `B-R3`：收口 `OpsCenter.test.jsx` 页面基线测试
- `B-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### B-R1：冻结页面基线与页尾 contract 的切片边界

目标：

- 在动手前确认 `OpsCenter` 页面层与 `O2` 页尾线的分界位置。

任务：

- 审计 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 当前结构
- 标出必须从 `B` 中排除的页尾“运行证据”区块
- 审计 [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx) 当前覆盖内容
- 确认 [OpsCenter.footerContract.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.footerContract.test.jsx) 不进入本刀

完成判定：

- 已形成明确的 include / exclude 清单
- 可以稳定区分页面层与页尾 contract 层

### B-R2：整理 `OpsCenter.jsx` 的页面基线版本

目标：

- 让 `OpsCenter.jsx` 的本次提交内容只代表页面主结构，不包含页尾 contract 线。

任务：

- 收口 [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 的页面主结构
- 保留主区块：
  - 页面标题与副标题
  - 每日巡检
  - 关键链路状态
  - 异常处置摘要
  - 页面失败态
- 从本次提交内容中排除页尾“运行证据”区块

关键约束：

- 不新增区块
- 不顺手扩展页面交互
- 不调整共享组件 API

完成判定：

- `OpsCenter.jsx` 可单独代表页面基线
- 页尾“运行证据”区块未被带入本次提交

### B-R3：收口 `OpsCenter.test.jsx` 页面基线测试

目标：

- 让 `OpsCenter.test.jsx` 只保护页面基线，而不侵入 `O2` 页尾 contract 线。

任务：

- 收口 [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx)
- 保持或确认以下覆盖：
  - 正常渲染页面主结构
  - 渲染异常摘要
  - 请求失败时展示失败态

关键约束：

- 不增加页尾字段断言
- 不加入刷新或路由行为断言
- 不把 `OpsCenter.reload.test.jsx` 合并进来

完成判定：

- 页面基线测试职责清晰
- 测试文件不承担 `O2` contract 回归

### B-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成页面基线收口。

任务：

- 运行 `OpsCenter.test.jsx`
- 如有必要，补跑已存在的 [OpsCenter.reload.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.reload.test.jsx) 做回归确认
- 检查暂存区 diff，只保留：
  - `OpsCenter.jsx`
  - `OpsCenter.test.jsx`
- 提交前确认不带入：
  - 页尾“运行证据”区块
  - `OpsCenter.footerContract.test.jsx`
  - 共享组件或其他页面文件

完成判定：

- 测试通过
- 提交边界干净
- 本刀仍然是“页面基线收口”，不是“页面功能扩展”

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先审计 `OpsCenter.jsx` 中页面层与页尾层的分界
2. 再整理 `OpsCenter.jsx` 的页面基线版本
3. 然后收口 `OpsCenter.test.jsx`
4. 最后做验证、精确暂存与提交

原因：

- 先拆页面层与页尾层，能避免整文件提交时混线
- 先稳定页面本体，再确认测试职责，断言对象更清晰
- 把提交边界检查放到最后，可最大限度保持原子化

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit B：OpsCenter 页面基线

范围：

- `OpsCenter.jsx`
- `OpsCenter.test.jsx`

目标：

- 为 `OpsCenter` 页面本体与页面基线测试建立正式基线

如果该提交无法与页尾 contract 线安全分离，则应停止实现并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `OpsCenter.jsx` 正式进入基线
2. `OpsCenter.test.jsx` 正式进入基线
3. 页面仍覆盖正常渲染、异常摘要和失败态
4. 提交中不包含页尾“运行证据”区块
5. 提交中不包含 `OpsCenter.footerContract.test.jsx`
6. 提交中不包含共享组件与其他页面主题线

## 11. 风险提示

- 当前最大风险是 `OpsCenter.jsx` 已在工作区中混入 `O2` 页尾区块，若直接整文件提交会导致切片失真
- 如果把页尾字段断言继续塞进 [OpsCenter.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.test.jsx)，会破坏页面层与 contract 层的物理边界
- 如果借这刀继续扩展刷新、路由或页面视觉调整，会破坏 `B` 的原子性

## 12. 结论

本计划的核心不是“顺手把 OpsCenter 全做完”，而是：

- 先把页面本体与页面基线测试正式纳入基线
- 显式排除 `O2` 页尾 contract 线
- 保持页面层、行为测试线和页尾 contract 线三者分离

只有这样，后续 `O2` 页尾收口才不会再次与页面基线缠在一起。
