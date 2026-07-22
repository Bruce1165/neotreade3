# App 全局 API 错误横幅实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-app-api-error-banner-design.md`

## 1. 目标

本计划只覆盖 `App` 壳层中的全局 API 错误横幅落地，不扩展到导航 IA、环境文案或 `Tushare 黄旗` 展示优化。

本轮目标只有四个：

1. 将环境异常判定逻辑从混杂漂移中单独收口。
2. 将全局 API 错误横幅以 `App` 壳层组件形式接入。
3. 为横幅行为补齐聚焦测试载体。
4. 用精确暂存或索引快照方式提交，不带入其他 `App` 漂移。

本轮必须产出的核心结果：

- `App` 默认不显示 API 错误横幅
- 当收到环境异常类 `neotrade3:api-error` 事件时，横幅稳定显示
- 横幅可关闭，且不依赖本地持久化
- 测试能够单独证明“全局事件 -> 横幅渲染”链路

## 2. 不在本轮完成

- 侧边栏从“低频交易”改成“选股工作台”
- `OpsCenter` 导航与路由接入
- Header 从 `API: 本地模式` 改成 `当前环境：本地工作区`
- `GlobalBanner` 从平铺元信息改成 `details` 展开
- 页面内部局部错误态统一
- 错误队列、自动消失、重试、持久化

## 3. 当前实施起点

### 3.1 已有现实基础

- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 当前工作树里已存在：
  - `isEnvironmentUnavailable()` 雏形
  - `GlobalApiErrorBanner()` 雏形
  - 横幅挂载点
- [App.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.test.jsx) 当前工作树里已存在通过派发 `neotrade3:api-error` 验证环境异常横幅的测试雏形

### 3.2 当前结构性风险

- `App.jsx` 中 `A4` 与导航 IA、环境文案、`OpsCenter`、`Tushare 黄旗` 优化混在同一批 drift 中
- `App.test.jsx` 也混入了与 `A4` 无关的共享 copy 与页面 mock 调整
- 若直接整文件提交，极易把多条主题线合并成一刀

## 4. 实施原则

- 先抽出全局 API 错误横幅最小逻辑，再补聚焦测试，不反向扩大 `App` 壳层的其他改动。
- 事件判定必须收敛在单一函数中，避免分散判断。
- 优先新增聚焦测试载体，不扩写已混杂的 `App.test.jsx`。
- 若 `App.jsx` 工作树存在其他未提交改动，则必须使用索引快照或精确暂存方式提取最小 hunk。
- 本轮只交付“统一提示”，不交付“统一修复”。

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/App.jsx`
- `neotrade3-dashboard/src/App.apiErrorBanner.test.jsx` 或 `App.test.jsx` 的最小相关 hunk

建议只包含以下逻辑：

- `isEnvironmentUnavailable(apiError)`
- `GlobalApiErrorBanner()`
- `App` 中横幅挂载点

明确不改：

- `OpsCenter` import / route
- 侧边栏 navItems
- Header 环境文案
- `GlobalBanner`
- 其他页面文件

## 6. 总体分段

本计划建议分为四段执行：

- `B1`：冻结 A4 切片边界
- `B2`：收口横幅逻辑与挂载点
- `B3`：补聚焦测试
- `B4`：验证、索引快照暂存与提交

## 7. 分段实施计划

### B1：冻结 A4 切片边界

目标：

- 在真正动手前，确认 `App.jsx` 里哪些 hunk 属于 API 错误横幅，哪些必须排除。

任务：

- 审计 `App.jsx` 中 `A4` 相关代码块
- 审计 `App.test.jsx` 中与横幅相关的断言与 mock
- 记录必须排除的 `A1/A2/A3` 主题改动

完成判定：

- 已有一份明确的 include/exclude 清单
- 可以只通过 `App` 壳层完成本刀，而不动其他页面

### B2：收口横幅逻辑与挂载点

目标：

- 让全局 API 错误横幅成为一个边界清晰、只负责提示的壳层组件。

任务：

- 固定环境异常判定条件：
  - `api_unreachable`
  - `api_timeout`
  - `后端不可达`
  - `请求超时`
- 固定环境异常主文案：
  - `开发环境未连接：`
  - `本地 API 服务暂未连接，页面会先展示占位信息。`
- 保留辅助诊断信息折叠区：
  - `endpoint`
  - `status`
  - `code`
  - `happenedAt`
- 保留手动关闭能力
- 将横幅挂在 `App` 壳层稳定位置

关键约束：

- 不新增本地持久化
- 不新增自动消失
- 不新增错误队列
- 不把导航或 Header 改动带进本刀

完成判定：

- 收到环境异常事件时横幅能稳定显示
- 关闭后横幅隐藏
- 非环境异常逻辑不要求在本轮扩展验证

### B3：补聚焦测试

目标：

- 用独立测试文件证明“事件 -> 横幅”链路，不依赖重测整个 `App`。

任务：

- 优先新增 `App.apiErrorBanner.test.jsx`
- 覆盖默认不显示横幅
- 覆盖派发环境异常事件后显示横幅
- 覆盖辅助诊断信息入口存在
- 如有必要，覆盖关闭行为

建议实现策略：

- 使用最小页面 mock
- 测试只断言与横幅直接相关的文案和行为
- 不顺手验证导航、Header 或其他页面 copy

完成判定：

- 横幅行为可以由独立测试文件单独证明

### B4：验证、索引快照暂存与提交

目标：

- 在保留工作树其他 drift 的前提下，安全提交 A4 单一主题线。

任务：

- 运行 API 错误横幅聚焦测试
- 如触及 `App.test.jsx`，补跑最小相关 `App` 测试
- 使用索引快照或精确暂存只纳入 A4 hunk
- 再次检查暂存区 diff，确认不含 `A1/A2/A3`

完成判定：

- 聚焦测试通过
- 暂存区只剩 `A4` 相关文件与 hunk
- 提交中不包含导航、Header、黄旗或 `OpsCenter` 改动

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先审计 `App.jsx` 中 A4 相关 hunk
2. 再收口 `GlobalApiErrorBanner()` 与判定函数
3. 再新增 `App.apiErrorBanner.test.jsx`
4. 最后用索引快照提取 `App.jsx` 最小改动并提交

原因：

- `App.jsx` 当前是混杂区，越早冻结边界越安全
- 先有聚焦测试，再做暂存提取，更容易判断切片是否跑偏
- 把索引快照留到最后，能最大限度避免误带其他未提交改动

## 9. 建议提交切分

建议拆成一个窄提交即可：

### Commit A：App 全局 API 错误横幅

范围：

- `App.jsx` 中 A4 相关最小 hunk
- `App.apiErrorBanner.test.jsx` 或 `App.test.jsx` 的最小相关 hunk

目标：

- 让 `App` 壳层具备稳定的环境异常横幅提示能力

如果 `App.jsx` 的 A4 hunk 无法与其他漂移安全分离，则本轮应停止实现，先回到边界审计，而不是扩大提交范围。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. 默认不显示全局 API 错误横幅
2. 环境异常事件能触发横幅显示
3. 横幅显示统一主文案
4. 辅助诊断信息入口存在
5. 提交中不包含 `OpsCenter`、导航 IA、Header、`GlobalBanner` 改动

## 11. 风险提示

- 当前 `App.jsx` 的主要风险不在功能实现，而在于与其他主题线共享同一文件
- 如果继续依赖 `App.test.jsx` 扩写，容易把测试边界重新拉宽
- 若不使用索引快照，极易把 `A1/A2/A3` 一并误提交

## 12. 结论

本计划的核心不是“顺手清一批 App 漂移”，而是：

- 先把全局 API 错误横幅这条线单独抽出来
- 再用聚焦测试把行为钉住
- 最后用索引快照确保提交边界干净

只有这样，后续 `App` 里的导航 IA、环境文案、黄旗展示等其他主题线，才可以继续保持原子化推进。
