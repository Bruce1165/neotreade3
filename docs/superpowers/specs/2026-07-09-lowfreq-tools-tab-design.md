# Lowfreq Tools Tab Design

Date: 2026-07-09

## 1. Goal

本切片只在 `Lowfreq` 页面内部增加一个 `辅助工具` 子页签，把已有的专业工具入口收纳进工作台内部。

目标是：

- 在不改全局导航结构的前提下，给 `Lowfreq` 提供工具入口收纳位
- 复用已经存在的 `/screeners` 与 `/stock-check` 页面能力
- 保持本次提交边界足够窄，避免混入工作台壳层、候选区重构、运维中心或全局路由改造

本切片不是信息架构重做，也不是全局导航迁移。

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 一个新的聚焦前端测试载体
- `Lowfreq` tabs 中新增 `辅助工具`
- `辅助工具` 子页签中的两个入口卡片：
  - `/screeners`
  - `/stock-check`

Excluded:

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/App.test.jsx`
- 全局侧边栏导航改造
- `OpsCenter` 页面与路由
- `LowfreqBacktestReport` 页面与路由
- `Lowfreq` 候选阅读区 / 人工动作区重构
- `PageHeader` / `MetricCard` / `statusCopy` 等 shared 组件抽取
- 后端 API 变更

## 3. Existing Context

当前 `Lowfreq` 相关剩余 drift 是混合状态，至少包含以下几条独立线：

1. 工作台壳层与共享组件抽取
2. 候选阅读区 / 人工动作区分栏
3. `辅助工具` 子页签
4. `App` 级侧边栏与路由调整

其中第 3 条最窄，因为：

- 只依赖 `Lowfreq.jsx`
- 跳转目标 `/screeners` 与 `/stock-check` 已存在
- 当前测试文件里已有对应行为证据
- 不要求引入新的后端契约

## 4. Approach Options

### Option A: Lowfreq 内部工具子页签 only

只在 `Lowfreq` 内新增 `辅助工具` 页签，并渲染工具入口卡片。

Pros:

- 边界最小
- 不依赖全局路由重构
- 与现有测试证据直接对应
- 最适合作为下一刀独立提交

Cons:

- 全局导航仍保留原有入口，不做 IA 收口

### Option B: Lowfreq + 全局侧边栏一起改

同时把工具从全局侧边栏迁入工作台。

Pros:

- 信息架构更完整

Cons:

- 会混入 `App.jsx` / `App.test.jsx`
- 会与运维中心、报告详情页等其他路线交叉
- 不适合当前最小提交目标

### Option C: 工具页签并入更大工作台重构

把候选区、壳层、工具入口一起做成完整工作台。

Pros:

- 一次形成更完整界面

Cons:

- 范围过大
- 无法保证当前工作树中的独立提交边界

Decision:

- choose Option A

## 5. Design

### 5.1 Functional Design

`Lowfreq` 的 tabs 新增一项：

- `id: 'tools'`
- `label: '辅助工具'`

当 `activeTab === 'tools'` 时，页面展示一个只读工具入口面板，包含：

- 筛选器入口卡片
- 单股核验入口卡片

每张卡片只负责：

- 展示工具名称
- 展示一句用途说明
- 提供跳转链接

本切片不在 `Lowfreq` 内嵌入筛选器或单股核验能力本身，只负责入口收纳。

### 5.2 UI Design

`辅助工具` 页签内容采用简单卡片式布局：

- 顶部一段说明文案，说明这些是“保留原有能力的专业工具入口”
- 下方两张入口卡片
- 卡片 CTA 分别跳转到：
  - `/screeners`
  - `/stock-check`

视觉上保持与当前 `Lowfreq` 页面的白底卡片风格一致即可，不引入新的页面壳层，不抽 shared 组件。

### 5.3 Boundary Rules

实现时必须遵守：

- 不改 `App.jsx` 侧边栏
- 不新增或修改全局路由
- 不把 `PageHeader`、`MetricCard`、`statusCopy` 抽进本次提交
- 不顺手带入候选区重构
- 不调整回测页、股票池页现有行为

### 5.4 File Strategy

生产文件预期只包含：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`

测试文件预期新增：

- 一个聚焦 `tools tab` 的新测试文件

不扩充当前已经混合较多的 `Lowfreq.test.jsx`，避免继续放大 monolithic test drift。

## 6. Testing Design

新增聚焦测试至少覆盖：

1. `Lowfreq` 渲染后存在 `辅助工具` 页签
2. 点击 `辅助工具` 后能看到工具说明区域
3. `进入筛选器` 链接指向 `/screeners`
4. `进入单股核验` 链接指向 `/stock-check`

本切片不要求新增 API mock 维度，只需要沿用最小页面渲染所需的已有 stub。

## 7. Validation

预期验证方式：

- 运行新的聚焦测试载体
- 如有必要，再运行一次与 `Lowfreq` tabs 基础切换相关的最小回归

不需要：

- 后端校验
- 路由级端到端校验
- 全局 `App` 页面回归

## 8. Commit Boundary

目标提交应限制为：

- `Lowfreq` 内部 `辅助工具` 子页签
- 一个聚焦测试载体

必须排除：

- 全局导航与路由调整
- 候选区重构
- 工作台壳层升级
- 运维中心
- 回测详情页
