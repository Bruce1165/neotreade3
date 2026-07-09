# App Header 环境文案与测试归位设计

日期：2026-07-09

## 1. 目标

本切片只解决一个问题：

把 `App` 壳层中 Header 环境文案与其相关测试责任收口为一个独立、可验证的 copy contract，并清理当前重复的环境横幅测试覆盖。

本切片的目标不是调整导航 IA、全局错误横幅实现或路由行为，而是只处理：

- `Header()` 中环境文案的最终表达
- `App.test.jsx` 与 `App.apiErrorBanner.test.jsx` 之间的测试职责归位
- Header copy 的独立、聚焦验证

## 2. 范围

包含：

- `neotrade3-dashboard/src/App.jsx` 中 `Header()` 的环境文案
- `neotrade3-dashboard/src/App.test.jsx` 中与环境横幅重复覆盖相关的断言清理
- 一个独立的 Header copy 测试载体，例如 `neotrade3-dashboard/src/App.headerCopy.test.jsx`

不包含：

- `Sidebar()` 导航 IA
- `GlobalBanner()` 的 Tushare 黄旗逻辑
- `GlobalApiErrorBanner()` 的展示与关闭逻辑
- `neotrade3-dashboard/src/App.navigationIa.test.jsx`
- 路由表与页面内容

## 3. 现有证据

当前仓库中已有以下可验证证据：

- `App.jsx` 当前 drift 将 Header 环境文案从：
  - `API: 本地模式`
  改成：
  - `当前环境：本地工作区`
- 同一时期，`GlobalApiErrorBanner()` 已经有独立测试文件：
  - `App.apiErrorBanner.test.jsx`
- 但 `App.test.jsx` 中又新增了一条 `shows environment banner when local api is unreachable` 断言，与 `App.apiErrorBanner.test.jsx` 形成重复覆盖
- `App.test.jsx` 同时还承担共享 copy 断言，继续把横幅测试塞进去会让文件承担过多主题

因此，当前问题不是“App 壳层都需要重新设计”，而是：

- Header 环境 copy 已形成一条可独立收口的主题线
- 环境横幅测试职责需要回到独立测试载体，不应继续在 `App.test.jsx` 中重复

## 4. 职责归属

本切片职责属于 `App` 壳层 copy contract 与测试责任归位。

它只回答两个问题：

- Header 中环境文案最终如何表达
- 环境横幅测试应由哪个测试载体负责

它不回答以下问题：

- 环境不可达判定逻辑是否需要变化
- 横幅内容是否需要视觉升级
- 导航 IA 是否还要调整
- `App.test.jsx` 是否整体拆分

因此，这一刀应被定义为“Header 环境文案与测试归位”，而不是“App shell 总整理”。

## 5. 方案比较

### 5.1 方案 A：只改 Header 文案

做法：

- 只保留 `App.jsx` 中 `当前环境：本地工作区`
- 不碰测试责任

优点：

- 最小生产改动

缺点：

- `App.test.jsx` 中环境横幅重复覆盖仍然存在
- copy contract 与测试职责没有一起收口

### 5.2 方案 B：Header 文案 + 独立 copy 测试

做法：

- 收口 Header 文案
- 新增独立 Header copy 测试

优点：

- Header 文案有独立验证

缺点：

- `App.test.jsx` 的重复横幅断言仍未清掉

### 5.3 方案 C：Header 文案 + 重复测试清理 + copy 测试归位

做法：

- 收口 Header 文案
- 新增独立 Header copy 测试
- 从 `App.test.jsx` 移除环境横幅重复断言
- 保留 `App.apiErrorBanner.test.jsx` 作为环境横幅的唯一权威测试载体

优点：

- 生产 copy 与测试职责一起收口
- 边界仍然单一，没有扩到导航或横幅实现
- 能减少 `App.test.jsx` 的主题混杂

缺点：

- 范围略宽于单纯 copy 修改

### 5.4 选择

本切片建议采用方案 C。

## 6. 设计要求

### 6.1 Header 文案语义

Header 环境文案应统一表达为：

- `当前环境：本地工作区`

该表达比 `API: 本地模式` 更贴近当前 App 壳层面对人的工作台语义，而不是底层连接状态语义。

本切片不要求引入更复杂的环境枚举，也不要求把文案扩成多状态切换。

### 6.2 不改变横幅实现

虽然本切片会清理横幅测试重复覆盖，但必须明确：

- 不修改 `GlobalApiErrorBanner()` 的生产逻辑
- 不修改 `isEnvironmentUnavailable()` 的判断方式
- 不修改横幅的 copy、关闭行为或 details 展开行为

这样可以保证这一刀仍然是 copy contract 收口，而不是横幅行为改造。

### 6.3 测试职责归位

测试职责应按如下方式重新归位：

- `App.apiErrorBanner.test.jsx`
  - 继续作为环境不可达横幅与关闭行为的唯一权威测试载体
- `App.test.jsx`
  - 只保留共享 copy 级断言
  - 不再重复测试环境横幅显示
- `App.headerCopy.test.jsx`
  - 作为 Header copy 的独立测试载体

### 6.4 不扩写 omnibus 测试

本切片不应继续把新的断言堆入 `App.test.jsx`。

原因：

- 该文件已经承载共享 copy 主题
- 如果继续塞进 Header 与横幅双重责任，后续更难收口

因此，本切片应新增独立测试文件，而不是继续在旧文件上叠加职责。

## 7. 测试设计

### 7.1 测试载体

建议新增：

- `App.headerCopy.test.jsx`

并保留：

- `App.apiErrorBanner.test.jsx`

### 7.2 最小断言集合

Header copy 载体的最小断言建议为：

- `团队控制台：审阅 / 监控 / 复盘` 仍存在
- `当前环境：` 存在
- `本地工作区` 存在
- 不再依赖 `API:` 与 `本地模式`

`App.apiErrorBanner.test.jsx` 继续负责：

- 默认不显示 API 错误横幅
- 本地 API 不可达时显示环境横幅
- 横幅可关闭

### 7.3 不扩展的测试范围

本切片测试不应扩展为：

- 导航入口测试
- 路由保护测试
- Tushare 黄旗测试
- 页面内容测试

## 8. 非目标

本切片明确不处理：

- 导航 IA 调整
- 环境状态来源重构
- 全局横幅 copy 优化
- `App.test.jsx` 全面拆分
- 其他页面壳层 copy

这些都属于后续独立主题线。

## 9. 提交边界

目标实现提交只允许包含：

- `App.jsx` 中 Header 环境文案最小改动
- `App.test.jsx` 中重复环境横幅断言的最小移除
- `App.headerCopy.test.jsx`

必须排除：

- `App.apiErrorBanner.test.jsx` 的行为性改造
- `GlobalApiErrorBanner()` 逻辑变更
- 导航 IA
- 其他页面文件

## 10. 验证要求

预期最小验证闭环：

- 运行 `App.headerCopy.test.jsx`
- 运行 `App.apiErrorBanner.test.jsx`
- 如有必要，补跑 `App.routeGuard.test.jsx`
- 确认 Header 文案与测试职责符合设计
- 确认提交中不带入导航或横幅实现主题

## 11. 结论

本切片的本质不是“改一行 Header 文案”，而是：

- 把 Header 环境 copy 收口成明确 contract
- 把环境横幅测试职责归回独立载体
- 降低 `App.test.jsx` 的主题混杂

只有这样，后续如果继续处理壳层 copy 或横幅行为，才能保持边界清晰。
