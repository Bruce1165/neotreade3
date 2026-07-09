# Lowfreq 回测详情页实施计划

日期：2026-07-09  
对应设计：`docs/superpowers/specs/2026-07-09-lowfreq-backtest-report-page-design.md`

## 1. 目标

本计划只覆盖 `Lowfreq` 回测详情页的独立落地，不扩展到其他前端漂移治理，也不扩展到后端回测链路调整。

本轮目标只有四个：

1. 将回测详情页路由正式接入前端。
2. 将 `LowfreqBacktestReport` 收口为只读详情页。
3. 为详情页补齐独立聚焦测试载体。
4. 以窄提交方式收口，不混入其他 `App / Lowfreq` 漂移。

本轮必须产出的核心结果：

- `App` 能命中 `/lowfreq/backtest-reports/:reportId`
- `LowfreqBacktestReport` 能稳定加载已有详情接口
- 详情页成功、失败、缺字段场景有明确 UI 行为
- 页面测试不再依赖扩写 `Lowfreq.test.jsx`

## 2. 不在本轮完成

- `Lowfreq.jsx` 其他残余 drift 清理
- 左侧导航新增“回测详情页”入口
- 回测状态轮询、重试按钮、筛选/折叠等新交互
- 后端接口或报告生成逻辑调整
- 全局 `App` 文案或导航顺手整理
- 回测详情页的视觉重设计

## 3. 当前实施起点

### 3.1 已有现实基础

- [LowfreqBacktestReport.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx) 已存在页面雏形
- [App.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/App.jsx) 当前工作树已包含详情页路由接线
- 后端已存在 `GET /api/lowfreq/backtest/report-detail?report_id=<id>` 入口
- `Lowfreq` 摘要页已在之前切片中产出详情链接契约

### 3.2 当前结构性风险

- `App.jsx` 当前还有其他无关 drift，若直接整文件提交容易混线
- `App.test.jsx` 已混入其他共享文案变更，需精确提取与详情页路由相关的最小覆盖
- 若继续复用 `Lowfreq.test.jsx`，容易把详情页与摘要页责任混在一起

## 4. 实施原则

- 先收口详情页本身，再补路由测试，不反向扩大 `Lowfreq` 页责任。
- 详情页只消费已有接口，不新增前端业务推导。
- 使用独立测试载体，不扩写混杂测试文件。
- 所有变更必须能被精确暂存和单独验证。
- 若 `App` 现有 drift 无法安全剥离，则优先缩小实现边界，而不是强行并线。

## 5. 建议改动边界

建议改动仅限：

- `neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx`
- `neotrade3-dashboard/src/pages/LowfreqBacktestReport.test.jsx`
- `neotrade3-dashboard/src/App.jsx` 中与详情页路由直接相关的最小变更
- `neotrade3-dashboard/src/App.test.jsx` 中与详情页路由直接相关的最小变更

明确不改：

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx`
- 其他页面与服务端文件

## 6. 总体分段

本计划建议分为五段执行：

- `R1`：冻结详情页切片边界
- `R2`：收口详情页页面实现
- `R3`：补独立详情页测试
- `R4`：最小接入 `App` 路由与路由测试
- `R5`：验证、精确暂存与提交

## 7. 分段实施计划

### R1：冻结详情页切片边界

目标：

- 在实施前明确哪些改动属于本刀，哪些一律排除。

任务：

- 审计 `LowfreqBacktestReport.jsx` 当前字段与区块
- 审计 `App.jsx` 当前路由相关 drift
- 审计 `App.test.jsx` 是否已有可复用 mock 与路由断言
- 记录必须排除的无关改动清单

完成判定：

- 已有一份明确的 include/exclude 清单
- 可以在不改 `Lowfreq.jsx` 的前提下完成本刀

### R2：收口详情页页面实现

目标：

- 让详情页成为稳定的只读详情页，而不是半成品页面。

任务：

- 统一页面加载态、错误态、空值回退策略
- 固定首批展示区块：
  - `summary`
  - `execution_action_summary`
  - `exit_quality`
  - `next_session`
  - `recent_trades`
- 保留返回 `Lowfreq` 的导航
- 保留 `PDF / JSON` 下载链接
- 清理任何超出本轮范围的新交互苗头

关键约束：

- 不新增轮询
- 不新增重试
- 不新增前端二次业务计算
- 不新增新的页面交互流

完成判定：

- 详情页成功载入时能稳定展示核心区块
- 接口失败或字段缺失时不白屏

### R3：补独立详情页测试

目标：

- 把详情页行为验证从混杂测试中物理分离出来。

任务：

- 新增 `LowfreqBacktestReport.test.jsx`
- 覆盖成功态渲染
- 覆盖失败态渲染
- 覆盖缺字段或缺 `reportId` 的保守降级
- 验证下载链接展示规则

建议实现策略：

- 使用聚焦 mock，而不是复用 `Lowfreq.test.jsx` 的大体量上下文
- 每个测试只证明一个行为组，不把路由大壳和页面细节混在一起

完成判定：

- 详情页主要行为可由独立测试文件单独证明

### R4：最小接入 `App` 路由与路由测试

目标：

- 让详情页可以通过正式路由进入，但不扩大 `App` 其他改动。

任务：

- 在 `App.jsx` 中保留或补上：
  - `import LowfreqBacktestReport`
  - `/lowfreq/backtest-reports/:reportId` 路由
- 在 `App.test.jsx` 中补最小路由命中覆盖
- 如 `App.test.jsx` 当前 drift 过宽，则只提取与详情页路由直接相关的最小 hunk

关键约束：

- 不新增侧边栏入口
- 不顺手整理 `Header`、共享 copy 或其他导航项
- 不扩大到其他页面路由修正

完成判定：

- 通过正式路由访问时，详情页组件可命中渲染

### R5：验证、精确暂存与提交

目标：

- 以最小验证闭环和最小提交边界完成收口。

任务：

- 运行 `LowfreqBacktestReport.test.jsx`
- 如触及 `App.test.jsx`，补跑最小 `App` 测试
- 检查最近修改文件的诊断错误
- 使用精确暂存，仅纳入本刀文件和本刀 hunk

完成判定：

- 详情页聚焦测试通过
- `App` 相关最小测试通过
- 最近编辑文件无新增语法/结构错误
- 提交中不包含无关 drift

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先收口 `LowfreqBacktestReport.jsx`
2. 再新增 `LowfreqBacktestReport.test.jsx`
3. 再最小处理 `App.jsx`
4. 最后最小处理 `App.test.jsx`
5. 收尾做验证和精确暂存

原因：

- 先稳住页面本体，最容易判断范围是否漂移
- 先有页面测试，再接 `App` 路由，回归成本更低
- `App` 是当前工作树的混杂区，越晚接入越容易保持边界

## 9. 建议提交切分

建议至少拆成两个窄提交：

### Commit A：详情页页面与独立测试

范围：

- `LowfreqBacktestReport.jsx`
- `LowfreqBacktestReport.test.jsx`

目标：

- 先冻结详情页自身行为，不依赖 `App` 路由收口

### Commit B：`App` 路由接线与最小回归

范围：

- `App.jsx`
- `App.test.jsx`

目标：

- 让详情页通过正式路由可达

如果 `App` 当前 drift 审计后无法安全拆出 `Commit B`，则需要先回到设计层重新收缩边界，不允许把其他 `App` 变更顺手并入。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `Lowfreq` 继续是摘要层，不承担详情页职责
2. 详情页只消费既有详情接口
3. 详情页成功、失败、缺字段场景都不白屏
4. 页面测试由独立载体覆盖
5. 正式提交不包含无关 `Lowfreq/App` drift

## 11. 风险提示

- 当前 `App.jsx` 与 `App.test.jsx` 已存在混杂漂移，真正的难点不是写路由，而是保证暂存边界干净
- 若详情页现有实现里混入未审计区块，可能需要回退到更窄的“只保留必需区块”策略
- 若测试上下文搭得过大，容易再次把详情页测试做成 `App` 集成测试，失去聚焦性

## 12. 结论

本计划的核心不是“把现有工作树一口气提交掉”，而是：

- 先把回测详情页本体收口
- 再用独立测试把行为钉住
- 再最小接入 `App` 路由
- 最后用精确暂存和最小验证完成提交

只有按这个顺序推进，才能继续保持本轮 `Lowfreq` 前端治理的一贯方法：窄边界、可验证、可单独提交。
