# App Header 环境文案与测试归位实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-app-header-environment-copy-contract-design.md`

## 1. 目标

本计划只覆盖 `App` 壳层中 Header 环境文案与测试职责归位，不扩展到导航 IA、全局错误横幅实现或其他页面主题线。

本轮目标只有三个：

1. 收口 `App.jsx` 的 Header 环境文案。
2. 把环境横幅测试职责归回独立测试载体。
3. 为 Header copy 建立独立、聚焦的回归验证。

本轮必须产出的核心结果：

- Header 环境文案统一为 `当前环境：本地工作区`
- `App.test.jsx` 不再重复覆盖环境不可达横幅
- `App.apiErrorBanner.test.jsx` 继续作为环境横幅唯一权威测试
- 提交中不包含导航 IA 或全局横幅实现逻辑

## 2. 不在本轮完成

- `Sidebar()` 导航 IA 调整
- `GlobalApiErrorBanner()` 的展示与关闭逻辑变更
- `GlobalBanner()` 的 Tushare 黄旗逻辑
- `App.test.jsx` 全面拆分
- 其他页面壳层 copy 调整
- 路由表与页面内容改动

## 3. 当前实施起点

### 3.1 已有现实基础

- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 中 `Header()` 当前 drift 已将环境文案从：
  - `API: 本地模式`
  改为：
  - `当前环境：本地工作区`
- [App.apiErrorBanner.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.apiErrorBanner.test.jsx) 已独立覆盖：
  - 默认不显示 API 错误横幅
  - 本地 API 不可达时显示环境横幅
  - 横幅可关闭
- [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 当前仍额外包含环境横幅显示断言，形成重复覆盖

### 3.2 当前结构性风险

- 当前最大风险不是 Header 文案无法修改，而是容易把这刀从“copy contract 收口”扩大成“壳层总清理”
- 如果顺手改动 `GlobalApiErrorBanner()` 行为，会把测试归位主题扩大成横幅实现主题
- 如果继续把 Header copy 验证留在 `App.test.jsx`，会继续累积 omnibus 测试职责

## 4. 实施原则

- 只处理 `Header()` 中环境文案
- 不修改 `GlobalApiErrorBanner()` 实现逻辑
- 保留 `App.apiErrorBanner.test.jsx` 作为横幅行为唯一权威测试
- 优先新增独立 Header copy 测试，不继续扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)
- 若实现需要扩大到横幅逻辑，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/App.test.jsx`
- `neotrade3-dashboard/src/App.headerCopy.test.jsx`

建议只包含以下逻辑：

- 收口 `Header()` 环境文案
- 从 `App.test.jsx` 移除重复环境横幅断言
- 新增独立 Header copy 测试

明确不改：

- `neotrade3-dashboard/src/App.apiErrorBanner.test.jsx`
- `GlobalApiErrorBanner()` 实现
- `Sidebar()` 导航 IA
- 其他页面文件

## 6. 总体分段

本计划建议分为四段执行：

- `AHC-R1`：冻结 Header copy 切片边界
- `AHC-R2`：在 `App.jsx` 收口环境文案
- `AHC-R3`：归位测试职责并新增独立 copy 测试
- `AHC-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### AHC-R1：冻结 Header copy 切片边界

目标：

- 在动手前确认哪些 drift 属于 Header copy，哪些必须排除。

任务：

- 审计 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 中 `Header()` 文案漂移
- 审计 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 与 [App.apiErrorBanner.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.apiErrorBanner.test.jsx) 的重复覆盖
- 固定 include / exclude 清单

完成判定：

- 已确认本刀只处理 Header 文案与重复测试归位
- 已确认不改横幅实现

### AHC-R2：在 `App.jsx` 收口环境文案

目标：

- 把 Header 环境文案收口成稳定 copy contract。

任务：

- 在 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 中保留并收口：
  - `当前环境：本地工作区`
- 确认 Header 其他 copy 不被扩大改动

关键约束：

- 不改 `GlobalApiErrorBanner()`
- 不改导航 IA
- 不引入额外环境状态来源逻辑

完成判定：

- Header 文案符合 design

### AHC-R3：归位测试职责并新增独立 copy 测试

目标：

- 让 Header copy 与环境横幅行为分别由正确的测试载体负责。

任务：

- 在 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 中移除重复的环境横幅断言
- 新增 `App.headerCopy.test.jsx`
- 用独立用例覆盖：
  - `团队控制台：审阅 / 监控 / 复盘`
  - `当前环境：`
  - `本地工作区`
  - 不再依赖 `API:` 与 `本地模式`

关键约束：

- 不改 [App.apiErrorBanner.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.apiErrorBanner.test.jsx) 的行为断言
- 不把 Header copy 与横幅行为再次混回同一测试文件

完成判定：

- Header copy 有独立测试
- 环境横幅只由独立横幅测试文件负责

### AHC-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `App.headerCopy.test.jsx`
- 运行 `App.apiErrorBanner.test.jsx`
- 如有必要，补跑 `App.routeGuard.test.jsx`
- 检查暂存区 diff，只保留：
  - `App.jsx` 中 Header 文案最小 hunk
  - `App.test.jsx` 中重复断言最小移除
  - `App.headerCopy.test.jsx`
- 提交前确认不带入导航或横幅实现主题

完成判定：

- 测试通过
- 提交边界干净
- 本刀仍然是“Header 环境文案与测试归位”，不是“App shell 总整理”

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先确认 Header copy 与横幅测试的边界
2. 再在 `App.jsx` 中收口环境文案
3. 然后新增 `App.headerCopy.test.jsx` 并移除 `App.test.jsx` 重复断言
4. 最后做验证、精确暂存与提交

原因：

- 先定责任边界，再改测试，能避免顺手误改横幅实现
- 先稳定生产 copy，再写独立断言，断言对象更清晰
- 把边界检查放到最后，可最大限度避免将导航或横幅主题带入

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit AHC：App Header 环境文案与测试归位

范围：

- `App.jsx` 中 Header 文案最小改动
- `App.test.jsx` 中重复环境横幅断言最小移除
- `App.headerCopy.test.jsx`

目标：

- 为 App 壳层建立独立的 Header 环境 copy contract，并把横幅测试职责归回独立载体

如果该提交无法与导航或横幅实现 drift 安全分离，则应停止提交并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. Header 显示 `当前环境：本地工作区`
2. `App.test.jsx` 不再重复测试环境横幅显示
3. `App.apiErrorBanner.test.jsx` 仍是环境横幅的唯一行为测试载体
4. Header copy 有独立测试载体
5. 提交中不包含导航 IA 或 `GlobalApiErrorBanner()` 实现逻辑

## 11. 风险提示

- 当前最大风险不是改文案本身，而是容易顺手把横幅实现也一起改掉
- 如果只改文案、不清测试职责，主题线就不完整
- 如果继续把 Header copy 断言塞进 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)，仍会积累 omnibus 测试债务

## 12. 结论

本计划的核心不是“改一个 label”，而是：

- 把 Header 环境 copy 收口成明确 contract
- 把环境横幅测试职责归回独立载体
- 降低 `App.test.jsx` 的主题混杂

只有这样，后续如果继续处理壳层 copy 或横幅行为，边界才不会重新混乱。
