# App Unused Import Cleanup Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `App.jsx` 中未使用的 icon import 清理，不改路由结构、不改页面跳转、不改导航信息架构、不改样式和交互。

目标是：

- 清除 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx#L1-L8) 中未被消费的 `Filter` 与 `Search` import
- 将 `App.jsx` 当前相对 `HEAD` 的功能性漂移收口为单点整洁性主题
- 明确把通配符路由行的缩进变化视为格式噪音，排除在本轮提交之外

本切片不是：

- 路由兜底 contract 变更
- 导航 IA 调整
- 新页面接线
- `MarketIntelligence` / `Overview` / `vite.config.js` 的漂移处理
- 样式、布局或交互行为调整

## 2. Scope

Included:

- `neotrade3-dashboard/src/App.jsx`
- 只针对未使用的 `Filter` 与 `Search` import 清理

Excluded:

- `neotrade3-dashboard/src/pages/*`
- `neotrade3-dashboard/vite.config.js`
- 路由通配符行的缩进变化
- 路由表与导航项
- 其他 import 整理

## 3. Existing Context

当前代码与 diff 已给出可核验证据：

- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx#L1-L8) 当前 `lucide-react` import 只包含 `AlertTriangle / LayoutDashboard / TrendingUp / Target`
- `git diff HEAD -- neotrade3-dashboard/src/App.jsx` 显示当前剩余漂移有两类：
  1. 未使用 import 删除：`Filter`、`Search`
  2. `Route path="*"` 行的缩进变化
- 通过代码检索，`App.jsx` 中不存在 `Filter` 或 `Search` 的实际消费点
- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx#L263-L271) 当前通配符路由仍与既有结构一致，缩进差异不构成独立行为变化

现状风险：

- 如果把未使用 import 清理与缩进噪音一起提交，本轮会从“整洁性清理”扩大成“cleanup + formatting”
- 如果顺手改动路由顺序、导航项或组件 wiring，本轮会失去单一目的
- 如果为了这条 import cleanup 补充无关测试，本轮会扩大成测试主题

## 4. Approach Options

### Option A: 只处理未使用 import，并排除缩进噪音（推荐）

仅处理：

- `Filter` import 删除
- `Search` import 删除

Pros:

- 边界最窄，和当前可解释的功能性漂移一致
- 不引入行为变化
- 提交目的单一，容易与 `HEAD` 对照说明

Cons:

- 缩进噪音仍需留待后续独立处理或回归基线时自然消失

### Option B: import cleanup + 缩进一起做

Pros:

- 一次减少更多 diff

Cons:

- 将整洁性清理扩大成格式整理
- 缩进变化没有独立业务价值
- 违背窄切片原则

### Option C: 暂不处理 App，直接转向更大页面主题

Pros:

- 优先解决更显眼页面漂移

Cons:

- 放弃当前最窄入口
- `App.jsx` 漂移继续滞留

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `App.jsx`
  - 只保留实际被导航壳层消费的 icon import
- `Filter` / `Search`
  - 不再作为 `App` 壳层依赖出现
- 通配符路由缩进
  - 继续视作独立格式噪音，不在本轮处理

### 5.2 Cleanup Strategy

本切片只允许对以下点位做改动：

1. `App.jsx` 的 `lucide-react` import 行
   - 删除 `Filter`
   - 删除 `Search`

本轮不允许顺手改动：

- `Route path="*"` 行缩进
- 路由定义顺序
- `navItems`
- 页面 import
- 壳层结构和样式

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改任何页面组件
- 不新增测试文件
- 不调整 `App.jsx` 中 JSX 结构
- 若验证暴露的是路由、页面或配置主题问题，应暂停并报告边界问题，不能静默扩大范围

## 6. Testing Design

验证优先采用：

1. 最小语法/结构检查
2. 如有必要，再使用现有前端 focused test 做回归验证

默认不要求：

- 新增独立测试文件
- 为未使用 import 清理新增断言
- 全量前端测试矩阵

原因：

- 本轮是单点 import cleanup，不涉及用户可见 contract
- 该类变更首先要求的是语法与结构安全，而不是新增测试职责

## 7. Validation

预期验证方式：

- 检查 `App.jsx` 最近编辑后无语法/结构错误
- 仅在需要时运行最小前端验证

如编辑过程中出现最近文件的明显语法/结构错误，再做最小修正。

## 8. Commit Boundary

目标提交应限制为：

- `App.jsx` 中 `Filter` / `Search` import 删除的最小 hunk

必须排除：

- `Route path="*"` 行缩进变化
- 路由定义
- 页面 wiring
- 其他文件改动

若相对 `HEAD` 无法将 import cleanup 与缩进噪音安全隔离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
