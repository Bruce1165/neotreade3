# OpsCenter 页面基线设计

日期：2026-07-09

## 1. 目标

本切片只解决一个问题：

把 `OpsCenter` 页面本体及其页面基线测试，作为独立页面层主题线正式纳入仓库基线。

本切片的目标不是扩展 `OpsCenter` 的功能，也不是继续收口页尾 contract，而是把页面主结构与基线测试从工作区漂移中独立收口。

## 2. 范围

包含：

- `neotrade3-dashboard/src/pages/OpsCenter.jsx`
- `neotrade3-dashboard/src/pages/OpsCenter.test.jsx`

不包含：

- `neotrade3-dashboard/src/pages/OpsCenter.footerContract.test.jsx`
- `OpsCenter.jsx` 中“运行证据”区块
- `/ops` 路由
- 刷新/日期切换行为扩展
- 共享组件改动
- 页面功能扩展

## 3. 现有证据

当前仓库中已有以下可验证证据：

- 共享展示骨架层已进入 `HEAD`：
  - `BlockMessage.jsx`
  - `MetricCard.jsx`
  - `PageHeader.jsx`
  - `StatusPill.jsx`
  - `statusCopy.js`
- 当前工作区中 `OpsCenter.jsx` 与 `OpsCenter.test.jsx` 已存在，但尚未进入基线
- 当前工作区中的 `OpsCenter.jsx` 已经混入“运行证据”区块
- 当前工作区中的 `OpsCenter.test.jsx` 只覆盖主区块渲染、异常摘要和失败态
- `OpsCenter.reload.test.jsx` 已经进入 `HEAD`，并且属于独立测试线，不应被重新并入页面基线切片

这说明 `B` 当前真正要解决的不是“做新页面”，而是“把页面本体与页尾 contract 线重新拆开，再收口页面基线”。

## 4. 职责归属

本切片职责属于 `OpsCenter` 页面层基线收口。

它只回答两个问题：

- `OpsCenter` 页面主结构是否正式进入仓库基线
- 页面基线测试是否能独立保护正常渲染、异常摘要和失败态

它不回答以下问题：

- 页尾“运行证据”区块是否存在
- 页尾字段 contract 是否完整
- `/ops` 路由是否命中
- 刷新和日期切换行为是否正确

因此本切片应保持为“页面基线收口”，而不是“页面功能升级”。

## 5. 页面设计

### 5.1 页面边界

本切片只收口 `OpsCenter` 的主页面结构，包括：

- 页面标题与副标题
- 主卡片区域
- 每日巡检区块
- 关键链路状态区块
- 异常处置摘要区块
- 页面失败态

### 5.2 必须排除的内容

本切片必须显式排除：

- 页尾“运行证据”区块
- 与页尾字段 contract 直接相关的 UI
- `OpsCenter.footerContract.test.jsx`

这意味着在实施 `B` 时，`OpsCenter.jsx` 必须回到“不含页尾区块”的状态。

### 5.3 展示要求

页面层要求保持收敛：

- 保持现有主区块标题与数据消费方式
- 保持失败态可见
- 不新增主区块
- 不新增操作入口
- 不借机统一页面样式主题

因此本切片只是“页面本体入基线”，不是“页面改版”。

## 6. 测试设计

### 6.1 测试载体

本切片测试只使用：

- `OpsCenter.test.jsx`

不包含：

- `OpsCenter.footerContract.test.jsx`
- `OpsCenter.reload.test.jsx` 的新增修改

### 6.2 最小断言集合

推荐最小断言集合：

- 正常渲染页面主结构
- 渲染后端返回的异常摘要
- 请求失败时展示页面失败态

断言重点应放在：

- 页面主区块是否存在
- 异常摘要是否可见
- 错误态是否可见

而不是扩展为：

- 页尾字段展示
- 刷新行为
- 路由命中

## 7. 非目标

本切片明确不处理：

- 页尾“运行证据”区块
- 页尾 contract 测试
- `/ops` 路由
- 刷新或日期切换行为
- 共享组件 API 调整
- 页面更宽的视觉重排

这些都属于其他已拆分或待拆分的主题线。

## 8. 提交边界

目标实现提交只允许包含：

- `OpsCenter.jsx`
- `OpsCenter.test.jsx`

必须排除：

- `OpsCenter.footerContract.test.jsx`
- `OpsCenter.reload.test.jsx` 的新增修改
- 共享组件文件
- `App.jsx`
- 其他页面文件

## 9. 验证要求

预期最小验证闭环：

- 运行 `OpsCenter.test.jsx`
- 如需验证页面回归稳定性，可补跑已存在的 `OpsCenter.reload.test.jsx`
- 确认提交中不带页尾 contract 线与其他页面主题线

## 10. 结论

本切片的本质不是继续推进 `O2`，而是把 `OpsCenter` 页面本体与其页面基线测试，先从混杂工作区中独立收口进仓库基线。

只有先把页面层和页尾 contract 线重新拆开，后续 `O2` 的页尾收口才有可能继续保持原子化推进。
