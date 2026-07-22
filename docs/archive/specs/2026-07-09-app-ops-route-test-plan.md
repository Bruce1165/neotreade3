# App `/ops` 路由独立测试实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-app-ops-route-test-design.md`

## 1. 目标

本计划只覆盖 `App` 层的 `/ops` 路由独立测试落地，不扩展到 `OpsCenter` 页面功能、首页跳转、导航 IA 或其他 `App` 路由主题线。

本轮目标只有三个：

1. 为 `/ops` 增加一个独立的 App 级路由测试载体。
2. 确认 `App` 直接访问 `/ops` 时能够命中 `OpsCenter`。
3. 用最小验证与最小提交边界收口，不带入其他 `App` 漂移。

本轮必须产出的核心结果：

- 直接访问 `/ops` 时可以命中 `OpsCenter`
- 测试断言聚焦在“路由命中”而不是“页面功能”
- 提交中不包含 `OpsCenter` 页面实现或其他 `App` 主题线

## 2. 不在本轮完成

- `OpsCenter.jsx` 页面 contract 调整
- `OpsCenter` 刷新或日期切换测试
- 首页风险卡片到 `/ops` 的点击验证
- 侧边栏 IA 调整
- Header 文案修改
- `App.test.jsx` 收口

## 3. 当前实施起点

### 3.1 已有现实基础

- [OpsCenter.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/OpsCenter.jsx) 已存在
- 当前工作树中 [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 已具备 `/ops` 路由接线
- 回测详情页已采用独立路由测试模式，见 [App.lowfreqBacktestReportRoute.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.lowfreqBacktestReportRoute.test.jsx)

### 3.2 当前结构性风险

- `App.jsx` 当前仍是混杂区，包含导航 IA、Header copy、`OpsCenter` 接线等多条未收口主题线
- [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 已混入多条其他主题断言，不适合继续扩写
- 若直接整文件提交，容易把 `/ops` 路由测试线与其他 `App` 改动混并

## 4. 实施原则

- 优先新增独立测试文件，不扩写 `App.test.jsx`
- 测试只证明 `/ops` 路由命中，不顺手验证页面内部行为
- 若需要触及 `App.jsx`，只能通过索引快照或精确暂存提取 `/ops` route 最小 hunk
- 保持和低频详情页路由测试相同的窄边界风格

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/App.opsCenterRoute.test.jsx`
- 如确有必要，`neotrade3-dashboard/src/App.jsx`

建议只包含以下逻辑：

- 设置地址到 `/ops`
- 渲染 `App`
- 验证 `OpsCenter` 页面桩命中

明确不改：

- `neotrade3-dashboard/src/pages/OpsCenter.jsx`
- `neotrade3-dashboard/src/pages/Overview.jsx`
- `neotrade3-dashboard/src/App.test.jsx`
- Header 与侧边栏 IA

## 6. 总体分段

本计划建议分为四段执行：

- `R1`：冻结 `/ops` 路由测试切片边界
- `R2`：新增独立路由测试文件
- `R3`：如有必要，最小提取 `/ops` route hunk
- `R4`：验证、精确暂存并提交

## 7. 分段实施计划

### R1：冻结 `/ops` 路由测试切片边界

目标：

- 在真正动手前，确认 `/ops` 路由测试需要哪些最小依赖，哪些改动必须排除。

任务：

- 审计 `App.jsx` 中 `/ops` 路由是否已经存在
- 审计 [App.lowfreqBacktestReportRoute.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.lowfreqBacktestReportRoute.test.jsx) 作为测试模板
- 记录 `App` 其余未收口主题线，防止混入

完成判定：

- 已有明确 include/exclude 清单
- 可以判断本刀是否只新增测试文件即可

### R2：新增独立路由测试文件

目标：

- 建立 `/ops` 路由的独立 App 级回归保护。

任务：

- 新增 `App.opsCenterRoute.test.jsx`
- 设置浏览器地址到 `/ops`
- mock `OpsCenter` 与其他页面占位组件
- mock `getDataStatus()` 稳定返回
- 断言 `OpsCenter` 页面桩被命中
- 断言 `App` 壳层基础结构仍存在

关键约束：

- 不验证 `OpsCenter` 内部接口行为
- 不验证首页点击跳转
- 不把测试写成 `App` 集成大全

完成判定：

- 测试能单独证明 `/ops` 路由命中

### R3：如有必要，最小提取 `/ops` route hunk

目标：

- 如果当前工作树中的 `/ops` route 尚未进入基线，则只提取这一个最小 hunk。

任务：

- 审计 `HEAD` 与工作树差异
- 若 `/ops` 已存在于当前基线，则跳过
- 若 `/ops` 仅存在于工作树，则使用索引快照只提取：
  - `OpsCenter` import
  - `/ops` route

关键约束：

- 不同时带入导航标签变化
- 不带入 Header copy
- 不带入其他 `App` 路由

完成判定：

- `/ops` route 在提交边界内可独立存在

### R4：验证、精确暂存并提交

目标：

- 用最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `App.opsCenterRoute.test.jsx`
- 若触及 `App.jsx`，补跑同一测试即可
- 检查暂存区 diff，只保留测试文件与必要 route hunk
- 提交时不带其他 `App` 漂移

完成判定：

- 路由测试通过
- 暂存区边界干净
- 提交中不包含 `OpsCenter` 页面实现和其他 `App` 主题线

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先审计 `App.jsx` 的 `/ops` route 现状
2. 再新增 `App.opsCenterRoute.test.jsx`
3. 最后视需要提取 `/ops` route hunk
4. 收尾验证并提交

原因：

- 很可能只需新增测试文件即可完成本刀
- 先有测试，再决定是否必须触及 `App.jsx`，边界更稳
- 把 `App.jsx` 的最小提取留到最后，可最大限度避免误带其他 drift

## 9. 建议提交切分

建议优先尝试一个窄提交：

### Commit A：App `/ops` 路由独立测试

范围：

- `App.opsCenterRoute.test.jsx`
- 如确有必要，再加 `App.jsx` 中 `/ops` route 的最小相关 hunk

目标：

- 为 `/ops` 路由建立独立回归保护

如果 `/ops` route 无法与其他 `App` 漂移安全分离，则应停止实现并回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 直接访问 `/ops` 时可命中 `OpsCenter`
2. 断言保持在路由层，不扩展为页面功能测试
3. 使用独立测试载体，不扩写 `App.test.jsx`
4. 提交中不包含 `OpsCenter.jsx` 或其他 `App` 漂移

## 11. 风险提示

- 当前最大风险不在测试实现，而在于 `App.jsx` 属于混杂区
- 若误把 `/ops` route 与导航 IA 一起提交，会破坏这条线的独立性
- 若测试断言写得过宽，容易把后续 `App` copy 变化都耦合进这条回归用例

## 12. 结论

本计划的核心不是“补一个更多的 App 测试”，而是：

- 给 `/ops` 路由加上最窄的一层 App 级保护
- 保持测试文件物理独立
- 如需改 `App.jsx`，也只提取最小 route hunk

只有这样，后续 `OpsCenter` 页面 contract、刷新行为、以及更大的 `App` 导航主题线，才能继续保持原子化推进。
