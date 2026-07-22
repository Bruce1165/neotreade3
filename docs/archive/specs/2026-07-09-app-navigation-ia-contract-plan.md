# App 导航 IA 收口实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-app-navigation-ia-contract-design.md`

## 1. 目标

本计划只覆盖 `App` 壳层中侧边栏导航 IA 的收口，不扩展到 Header 环境文案、全局错误横幅或其他页面主题线。

本轮目标只有三个：

1. 收口 `App.jsx` 侧边栏的一级入口集合。
2. 收口导航 active 命中规则，使子路径页面得到一致高亮。
3. 用独立测试载体为导航 IA 建立回归验证。

本轮必须产出的核心结果：

- 侧边栏只暴露当前确认的 4 个一级入口
- `/lowfreq/*` 与 `/ops/*` 这类子路径能命中对应导航入口
- 提交中不包含 Header 文案与全局横幅主题线

## 2. 不在本轮完成

- `Header()` 环境文案收口
- `GlobalBanner()` 的 Tushare 黄旗逻辑
- `GlobalApiErrorBanner()` 的环境不可达横幅逻辑
- `App.test.jsx` 的全面拆分
- 路由表增删或页面内容改动
- 其他页面文件变更

## 3. 当前实施起点

### 3.1 已有现实基础

- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 已具备完整的 App 壳层结构
- 当前 drift 中，侧边栏导航已经出现新的 IA 方向：
  - `今日总览`
  - `主线审阅`
  - `选股工作台`
  - `运维中心`
- 同一批 drift 中，导航 active 规则也已从“精确匹配”向“前缀命中”演进
- [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 当前已混入导航文案与环境告警主题，不适合作为这条线的唯一测试载体

### 3.2 当前结构性风险

- 当前最大风险不是导航功能无法实现，而是容易把这刀从“导航 IA”扩大成“App shell 总整理”
- 如果顺手一起改 Header 文案，会把 copy contract 混入导航主题
- 如果继续扩写 `App.test.jsx`，会继续增加 omnibus 测试负担

## 4. 实施原则

- 只处理 `Sidebar()` 导航入口集合与 active 规则
- 不修改 `Header()` 文案
- 不修改全局横幅逻辑
- 优先新增独立测试文件，不继续扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)
- 若实现需要扩大到 Header 或全局横幅，应停止实现并回到边界审计

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/App.navigationIa.test.jsx`

建议只包含以下逻辑：

- 收口侧边栏一级入口集合
- 收口 active 命中规则
- 新增独立导航 IA 测试

明确不改：

- `neotrade3-dashboard/src/App.test.jsx`
- `Header()` 中环境文案
- `GlobalBanner()` / `GlobalApiErrorBanner()`
- 其他页面文件

## 6. 总体分段

本计划建议分为四段执行：

- `AIA-R1`：冻结导航 IA 切片边界
- `AIA-R2`：在 `App.jsx` 收口入口集合与 active 规则
- `AIA-R3`：新增独立导航测试载体
- `AIA-R4`：验证、精确暂存并提交

## 7. 分段实施计划

### AIA-R1：冻结导航 IA 切片边界

目标：

- 在动手前确认哪些壳层 drift 属于导航 IA，哪些必须排除。

任务：

- 审计 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 当前 `Sidebar()` 漂移
- 确认一级入口集合固定为：
  - `今日总览`
  - `主线审阅`
  - `选股工作台`
  - `运维中心`
- 确认 Header 文案与全局横幅属于排除主题
- 确认测试采用独立载体而非继续扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)

完成判定：

- 已形成明确 include / exclude 清单
- 导航 IA 语义已经固定

### AIA-R2：在 `App.jsx` 收口入口集合与 active 规则

目标：

- 让侧边栏导航与当前 3.0 工作台入口集合一致，并让子路径拥有一致高亮。

任务：

- 在 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 中收口 `navItems`
- 一级入口只保留：
  - `今日总览`
  - `主线审阅`
  - `选股工作台`
  - `运维中心`
- 收口 active 判断：
  - `/` 命中 `今日总览`
  - `/market-intelligence` 命中 `主线审阅`
  - `/lowfreq` 与 `/lowfreq/...` 命中 `选股工作台`
  - `/ops` 与 `/ops/...` 命中 `运维中心`

关键约束：

- 不调整 `Header()`
- 不触碰全局横幅
- 不引入通用路由匹配框架

完成判定：

- 侧边栏入口集合与 active 规则符合 design

### AIA-R3：新增独立导航测试载体

目标：

- 为导航 IA 补上一层独立、可回归的 contract 验证。

任务：

- 新增 `App.navigationIa.test.jsx`
- mock 最小页面依赖
- 用独立用例覆盖：
  - 侧边栏只显示 4 个目标入口
  - 不再显示 `筛选器`
  - 不再显示 `单股核验`
  - `/lowfreq` 命中 `选股工作台`
  - `/lowfreq/backtest-reports/:id` 仍命中 `选股工作台`
  - `/ops` 命中 `运维中心`

关键约束：

- 不在本文件复验 Header 文案
- 不在本文件复验全局错误横幅
- 不扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)

完成判定：

- 新测试文件可独立保护导航 IA

### AIA-R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `App.navigationIa.test.jsx`
- 如触及 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx)，补跑 `App.routeGuard.test.jsx`
- 检查暂存区 diff，只保留：
  - `App.jsx` 中与导航 IA 直接相关的最小 hunk
  - `App.navigationIa.test.jsx`
- 提交前确认不带入 Header 或全局横幅主题线

完成判定：

- 测试通过
- 提交边界干净
- 本刀仍然是“导航 IA 收口”，不是“App 壳层总整理”

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先确认导航 IA include / exclude 清单
2. 再在 `App.jsx` 中收口入口集合与 active 规则
3. 然后新增 `App.navigationIa.test.jsx`
4. 最后做验证、精确暂存与提交

原因：

- 先定导航 contract，再写实现，能避免把 Header 或横幅主题误带入
- 先稳定生产路径，再写测试，断言对象更清晰
- 把边界检查放到最后，可最大限度避免将壳层其他 drift 带入

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit AIA：App 导航 IA 收口

范围：

- `App.jsx` 中导航入口集合与 active 规则的最小 hunk
- `App.navigationIa.test.jsx`

目标：

- 为 App 壳层建立独立、明确的导航 IA contract

如果该提交无法与 Header 或全局横幅 drift 安全分离，则应停止提交并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 侧边栏只显示 `今日总览 / 主线审阅 / 选股工作台 / 运维中心`
2. 不再显示 `筛选器`
3. 不再显示 `单股核验`
4. `/lowfreq` 与 `/lowfreq/backtest-reports/:id` 命中 `选股工作台`
5. `/ops` 命中 `运维中心`
6. 使用独立测试载体，不扩写 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)
7. 提交中不包含 Header 文案或全局横幅主题线

## 11. 风险提示

- 当前最大风险不是实现难度，而是容易把导航 IA 顺手扩成 Header copy 收口
- 若继续把导航断言堆进 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx)，会削弱主题边界
- 若对子路径 active 规则做成过宽的通用匹配，可能误伤未来其他页面路径

## 12. 结论

本计划的核心不是“改几个侧边栏文案”，而是：

- 把当前已经成形的工作台入口集合收口成稳定的导航 IA
- 把 active 命中规则明确化
- 为这条 IA contract 建立独立测试载体

只有这样，后续如果要继续处理 Header 文案或全局横幅，才不会与导航主题互相污染。
