# App Tushare 黄旗详情折叠实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-app-tushare-banner-details-design.md`

## 1. 目标

本计划只覆盖 `App` 壳层中 `Tushare 黄旗` 的详情折叠落地，不扩展到 Header、导航 IA、全局 API 错误横幅或其他 `App` 主题线。

本轮目标只有四个：

1. 将 `GlobalBanner` 的默认展示收敛为主文案。
2. 将辅助诊断细节收进折叠区。
3. 为黄旗展示行为补齐聚焦测试载体。
4. 用精确暂存或索引快照方式提交，不带入其他 `App` 漂移。

本轮必须产出的核心结果：

- `credit_insufficient=false` 时不显示黄旗
- `credit_insufficient=true` 时显示稳定主文案
- 细节字段不再平铺在主行
- 折叠入口 `查看详细信息` 稳定存在

## 2. 不在本轮完成

- `GlobalBanner` 触发条件变化
- Header 环境文案改写
- 全局 API 错误横幅
- 侧边栏导航或 `OpsCenter`
- 黄旗关闭按钮
- 自定义展开动画、展开持久化

## 3. 当前实施起点

### 3.1 已有现实基础

- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 当前工作树里，`GlobalBanner` 已存在把细节收进 `details` 的展示雏形
- 当前基线则是把 `last_insufficient / api / last_ok / last_ok_api` 平铺在主行
- `getDataStatus()` 与 `tushare.credit_insufficient` 判定链已经存在，不需要改动

### 3.2 当前结构性风险

- `App.jsx` 里 `A3` 与导航、Header、`OpsCenter`、全局 API 错误横幅等其他主题线混在同一文件
- 若继续在 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 上扩写，容易把测试边界拉宽
- 若直接整文件提交，极易把 `A2/A4/A1` 误带进去

## 4. 实施原则

- 只动 `GlobalBanner` 的展示层，不动触发逻辑。
- 主文案保持不变，只收口细节呈现方式。
- 优先新增聚焦测试载体，不扩写混杂测试文件。
- 若 `App.jsx` 仍有其他未提交改动，必须使用索引快照或精确暂存提取最小 hunk。
- 本轮不强测浏览器原生 `details` 的完整交互，只验证展示边界收口。

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/App.tushareBanner.test.jsx` 或 `App.test.jsx` 的最小相关 hunk

建议只包含以下逻辑：

- `GlobalBanner` 中主文案保留
- `查看详细信息` 入口
- 细节字段进入折叠区

明确不改：

- `isEnvironmentUnavailable()`
- `GlobalApiErrorBanner()`
- Header
- navItems
- `OpsCenter`

## 6. 总体分段

本计划建议分为四段执行：

- `T1`：冻结 A3 切片边界
- `T2`：收口 `GlobalBanner` 展示层
- `T3`：补聚焦测试
- `T4`：验证、索引快照暂存与提交

## 7. 分段实施计划

### T1：冻结 A3 切片边界

目标：

- 在真正动手前，确认 `App.jsx` 中哪些 hunk 属于黄旗详情折叠，哪些必须排除。

任务：

- 审计 `GlobalBanner` 当前工作树改动
- 审计 `App.test.jsx` 是否已有可复用的黄旗断言
- 记录必须排除的 `A1/A2/A4` 改动

完成判定：

- 已有明确的 include/exclude 清单
- 可以不改 Header、导航、API 错误横幅而单独完成本刀

### T2：收口 `GlobalBanner` 展示层

目标：

- 让 `GlobalBanner` 成为“主文案简洁、细节按需展开”的壳层提醒。

任务：

- 保留主文案：
  - `Tushare 黄旗：`
  - `检测到 Tushare 积分不足，日线主源可能受影响。`
- 将以下字段移入折叠区：
  - 最近一次受影响时间
  - 受影响接口
  - 最近一次恢复时间
  - 最近一次恢复接口
- 为折叠入口固定文案：
  - `查看详细信息`
- 对缺失恢复字段执行隐藏，而非空占位

关键约束：

- 不新增按钮或自定义交互
- 不改触发逻辑
- 不改主文案语义

完成判定：

- 主行默认不再平铺细节字段
- 折叠入口存在
- 黄旗未触发时仍不显示整个横幅

### T3：补聚焦测试

目标：

- 用独立测试文件证明黄旗展示边界已经正确收口。

任务：

- 优先新增 `App.tushareBanner.test.jsx`
- 覆盖 `credit_insufficient=false` 不显示黄旗
- 覆盖 `credit_insufficient=true` 显示主文案与折叠入口
- 避免继续使用旧平铺结构作为断言目标

建议实现策略：

- 使用最小页面 mock
- 不顺手验证 Header、导航或其他共享 copy
- 不强测 `details` 原生展开动作

完成判定：

- 黄旗展示行为可由独立测试文件单独证明

### T4：验证、索引快照暂存与提交

目标：

- 在保留工作树其他漂移的前提下，安全提交 A3 单一主题线。

任务：

- 运行黄旗聚焦测试
- 如触及 `App.test.jsx`，仅补跑最小相关 `App` 测试
- 使用索引快照或精确暂存只纳入 `GlobalBanner` 最小 hunk
- 再次检查暂存区 diff，确认不含 `A1/A2/A4`

完成判定：

- 聚焦测试通过
- 暂存区只剩 `A3` 相关文件与 hunk
- 提交中不包含 Header、导航、API 错误横幅、`OpsCenter`

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先审计 `GlobalBanner` 相关 hunk
2. 再收口 `GlobalBanner` 展示层
3. 再新增 `App.tushareBanner.test.jsx`
4. 最后用索引快照提取 `App.jsx` 最小改动并提交

原因：

- `App.jsx` 当前是混杂区，越早冻结边界越安全
- 先有聚焦测试，再做暂存提取，更容易判断切片是否跑偏
- 把索引快照留到最后，能最大限度避免误带其他未提交改动

## 9. 建议提交切分

建议拆成一个窄提交即可：

### Commit A：App Tushare 黄旗详情折叠

范围：

- `App.jsx` 中 `GlobalBanner` 相关最小 hunk
- `App.tushareBanner.test.jsx` 或 `App.test.jsx` 的最小相关 hunk

目标：

- 让黄旗默认展示更简洁，同时保留按需查看细节的能力

如果 `GlobalBanner` 的 hunk 无法与其他漂移安全分离，则本轮应停止实现，先回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `credit_insufficient=false` 时不显示黄旗
2. `credit_insufficient=true` 时显示黄旗主文案
3. `查看详细信息` 入口存在
4. 细节字段不再作为主行平铺结构呈现
5. 提交中不包含 Header、导航、API 错误横幅、`OpsCenter`

## 11. 风险提示

- 当前 `App.jsx` 的主要风险不在功能复杂度，而在于与其他主题线共享同一文件
- 如果继续依赖 [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 扩写，容易重新放大测试边界
- 若不使用索引快照，极易把 `A2/A4/A1` 一并误提交

## 12. 结论

本计划的核心不是“给黄旗加新能力”，而是：

- 保留稳定主提醒
- 把细节移入折叠区
- 用聚焦测试证明展示边界已收口
- 最后用索引快照保证提交边界干净

只有这样，`App` 中剩余的 Header、导航 IA 等其他主题线，才能继续保持原子化推进。
