# Lowfreq Test Market-Phase Carrier Cleanup Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `Lowfreq.test.jsx` 当前工作区中的 market-phase 载体去肥，不改任何生产代码。

目标是：

- 将 `Lowfreq.test.jsx` 收口回只承接 market-phase / hot-sectors 主题
- 删除该文件中与现有 3 条 market-phase 用例无关的 mock、fixture 和残余测试数据
- 保持 `scorePool`、`manual actions`、`candidates` 等主题继续由各自 focused carriers 承接

本切片不是：

- `Lowfreq.jsx` 功能变更
- `Lowfreq.test.jsx` 全量重写
- `scorePool` / `manual actions` / `candidates` focused carrier 改造
- 页面壳层或路由逻辑调整

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- 只针对 market-phase 无关 mock / fixture / 残余测试数据的最小去肥

Excluded:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.scorePoolBaseline.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.manualActionsContract.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.candidatesWorkbenchSplit.test.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx`
- 任意生产代码、共享组件或路由改动

## 3. Existing Context

当前 `Lowfreq.test.jsx` 实际只剩 3 条 market-phase 主题用例：

1. `loads today snapshot and renders market + sector cards`
2. `shows fallback instead of NaN percent when market phase fields are missing`
3. `keeps hot sectors visible when market phase block fails`

但当前工作区中的同一文件仍夹带明显不属于这 3 条用例的内容：

- `react-router-dom` 的 `Link` mock
- `localStorage` stub
- `lowfreq-score/pool` payload
- `lowfreq-score/events` payload
- `lowfreq-score/summary` payload

这些内容的主题归属已经被 focused carriers 承接：

- `Lowfreq.scorePoolBaseline.test.jsx`
- `Lowfreq.manualActionsContract.test.jsx`
- `Lowfreq.candidatesWorkbenchSplit.test.jsx`

因此当前真实问题不是“测试失败”，而是 `Lowfreq.test.jsx` 作为 omnibus carrier 仍保留历史回流的多主题夹带依赖。

现状风险：

- `Lowfreq.test.jsx` 看上去像 market-phase carrier，但 fixture 和 mock 已经暗含 scorePool / candidates / router / localStorage 主题
- 后续继续修改 focused carriers 时，容易被这个 omnibus 载体里的残余数据干扰
- 若这轮顺手重写整份 `buildTodayPayloads()`，边界很容易从“去肥”扩大成“测试重构”

## 4. Approach Options

### Option A: 只去掉与 market-phase 无关的 mock / fixture（推荐）

只保留 market-phase 和 hot-sectors 这 3 条用例所需的最小依赖。

Pros:

- 边界最窄
- 与当前 `Lowfreq.test.jsx` 的剩余职责一致
- 不触碰 focused carriers

Cons:

- 不会顺手改善其他测试文件中的历史问题

### Option B: 直接把 `Lowfreq.test.jsx` 改造成更完整的 today-page contract carrier

把与首页展示相关的其他数据契约一并保留并重命名职责。

Pros:

- 可能减少后续再次清理次数

Cons:

- 边界明显扩大
- 与当前“只剩 3 条 market-phase 用例”的事实不匹配
- 会重新引入 omnibus 职责解释成本

### Option C: 暂不处理，保持现状

保留这些夹带 mock / fixture。

Pros:

- 当前无需改动测试文件

Cons:

- `Lowfreq.test.jsx` 职责继续失焦
- focused carrier 与 omnibus carrier 的边界继续模糊

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `Lowfreq.test.jsx`
  - 只负责 market-phase / hot-sectors 的基础 today-page 展示
  - 不再携带 scorePool / candidates / router / localStorage 主题依赖
- focused carriers
  - 继续独占各自主题的 contract 与交互断言

### 5.2 Cleanup Strategy

本切片只允许对 `Lowfreq.test.jsx` 做以下去肥：

1. 删除 `react-router-dom` mock
2. 删除 `localStorage` stub 及其 `unstub` 清理
3. 从 `buildTodayPayloads()` 中删除以下无关 payload：
   - `/api/lowfreq-score/pool?...`
   - `/api/lowfreq-score/events?...`
   - `/api/lowfreq-score/summary?...`
4. 保留 market-phase 和 hot-sectors 3 条用例的最小数据结构

本轮不允许顺手改动：

- 3 条 market-phase 用例的断言主题
- focused carriers 的 fixture
- `Lowfreq.jsx`
- `DateSelector` mock
- `fetchApi` mock 结构

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不把这轮去肥扩大成 today-page 契约重构
- 不回流任何 `scorePool`、`manual actions`、`candidates` 断言到 `Lowfreq.test.jsx`
- 若删除某项 mock / fixture 后发现 3 条 market-phase 用例仍隐式依赖它，必须先证明依赖真实存在；不能凭感觉保留
- 若相对 `HEAD` 只形成工作区收口而没有新的真实差异，要如实报告，不强行制造提交

## 6. Testing Design

验证只需要覆盖：

1. `Lowfreq.test.jsx` 继续通过
2. 如有必要，可补跑最接近的 focused carrier 以确认去掉的 fixture 没有被错误回流

默认不要求：

- 全量 `Lowfreq` 测试矩阵
- `App` 层回归
- 生产代码验证

## 7. Validation

预期验证命令：

- `npm test -- src/pages/Lowfreq.test.jsx`

若去肥过程中发现与 focused carrier 的边界判断存在不确定性，可补跑：

- `npm test -- src/pages/Lowfreq.scorePoolBaseline.test.jsx`

但这不是默认必跑项。

## 8. Commit Boundary

默认目标是：

- `Lowfreq.test.jsx` 的 market-phase 去肥收口

若相对 `HEAD` 存在真实最小差异，提交应限制为：

- 删除 `react-router-dom` mock
- 删除 `localStorage` stub
- 删除无关 `lowfreq-score/*` fixture

必须排除：

- `Lowfreq.jsx`
- 其他测试文件
- market-phase 断言主题扩大
- focused carrier 行为调整

若相对 `HEAD` 不存在真实最小差异，本轮结论应明确为：

- “已完成工作区去肥收口，不产生新 commit”
