# Lowfreq Candidates Workbench Split Design

Date: 2026-07-09

## 1. Goal

本切片只处理 `Lowfreq` 页内候选区域的职责拆分：把“阅读信息”和“执行动作”分开，降低操作噪音。

目标：

- 在 `CandidatesPanel` 内形成 `候选阅读区` 与 `人工动作区` 两栏
- 保持现有买进/放弃能力可用，但把动作入口集中到动作区
- 严格限制提交边界，不混入路由、页面壳层、shared 组件抽取、运维中心等其他线路

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- 一个新的聚焦测试载体
- `CandidatesPanel` 的阅读区/动作区结构改造

Excluded:

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/App.test.jsx`
- `OpsCenter` 页面与路由
- `LowfreqBacktestReport` 页面与路由
- `PageHeader` / `MetricCard` / `statusCopy` shared 组件抽取
- `scorePoolRequestIdRef` / `previousSelectedDateRef` 这类状态修正小线
- 后端 API 变更

## 3. Existing Context

当前剩余前端 drift 至少包含三条独立线：

1. `App` 级导航与新页面引入（运维中心、报告详情页）
2. `Lowfreq` 工作台壳层与 shared 组件抽取
3. `CandidatesPanel` 阅读区 / 动作区分离

其中第 3 条可独立成立，且证据链最直接：

- 现有测试断言已出现 `候选阅读区`、`人工动作区`
- 改动主要落在 `Lowfreq.jsx` 的 `CandidatesPanel`
- 无需额外后端契约

## 4. Approach Options

### Option A: CandidatesPanel only（推荐）

只做候选区分栏重排，不做 shared 组件抽取，不动全局壳层。

Pros:

- 边界最窄
- 可与现有 drift 解耦
- 最适合继续原子化提交

Cons:

- 文案与卡片复用暂不统一

### Option B: CandidatesPanel + shared copy

分栏同时接入 `statusCopy`、`MetricCard` 等共享抽象。

Pros:

- 一次统一文案与呈现复用

Cons:

- 会跨越单页改造边界
- 牵扯未提交 shared 资产

### Option C: CandidatesPanel + 工作台壳层

分栏与标题壳层、模式概览一起推进。

Pros:

- 视觉一致性更完整

Cons:

- 规模显著扩大
- 失去“下一个最小切片”属性

Decision:

- choose Option A

## 5. Design

### 5.1 Panel Responsibility

`CandidatesPanel` 改为双栏：

- 左栏 `候选阅读区`：
  - 只承担读取候选信息
  - 不提供买进/放弃按钮
- 右栏 `人工动作区`：
  - 汇总当前待处理候选
  - 集中放置买进/放弃入口

### 5.2 Read Zone

阅读区表格字段：

- 代码
- 名称
- 板块
- 角色
- 状态
- 买入分
- 5日涨幅

状态仅用于识别，不触发动作。

### 5.3 Action Zone

动作区包含两层内容：

1. 简要状态汇总（可出手/观察/已排队/已放弃）
2. 待处理列表（只列出未放弃且未排队的候选）

动作按钮规则：

- `买进(T+1)`：沿用原有禁用条件（非 buy_signal 或 role 为 跟随 时不可用）
- `放弃`：沿用现有提交行为

### 5.4 Boundary Guardrails

实现时必须遵守：

- 不改 `App` 导航
- 不改路由结构
- 不引入新页面
- 不抽 shared 组件
- 不顺带修改 backtest / scorePool / today tab 行为

## 6. Testing Design

新增聚焦测试文件，至少覆盖：

1. 渲染后可见 `候选阅读区` 与 `人工动作区`
2. 待处理候选在动作区出现且可触发买进/放弃
3. 已放弃或已排队候选不进入动作区待处理列表
4. 阅读区仍保留候选核心字段展示

不扩充当前混合较多的 `Lowfreq.test.jsx`，避免继续扩大 monolithic drift。

## 7. Validation

预期验证：

- 运行新的聚焦测试载体
- 必要时补跑一次与候选 tab 切换直接相关的最小回归

不需要：

- 后端测试扩展
- 全量前端回归
- `App` 级回归

## 8. Commit Boundary

目标提交应限制为：

- `Lowfreq.jsx` 中 `CandidatesPanel` 分栏改造
- 一个候选分栏聚焦测试文件

必须排除：

- `App.jsx` / `App.test.jsx`
- `OpsCenter` / `LowfreqBacktestReport`
- shared 组件抽取
- 其他 tab 的行为修正
