# 低频交易前端（B：左侧导航多页）+ 回测执行约束（涨跌停顺延）设计

## 目标
- 在现有 dashboard（`apps/dashboard`）中，以“左侧导航 + 多页（锚点分区）”方式展示低频模型的核心可实操信息。
- 回测执行口径更贴近实盘：涨停买不进、跌停卖不出，按交易日顺延继续尝试（仅日线收盘价数据）。
- 不新增 JSON 下载入口；回测报告仅提供 PDF 下载。

## 约束与范围
- 不引入新的前端工程，复用 `apps/dashboard/main.py` + `apps/dashboard/static/dashboard.js`。
- 不改变 API 的认证/路由框架；尽量复用现有低频接口（`lowfreq_*`）。
- 仅在回测链路引入“涨跌停顺延成交”约束；首版不强制扩展到所有实时模拟（后续再评估）。

## 页面结构（B：左侧导航 + 多页）
### 左侧导航（首版）
- 今日总览（保留原有）
- 低频交易（新增分组）
  - 今日快照
  - 持仓监控
  - 候选池（下一交易日）
  - 回测报告（仅 PDF 下载 + summary + report_id）
  - 执行约束（固定说明）
- 筛选器（原有“筛选器运行与参数”改名）
- 单股核验（CHECK）（原有“单股解释”改名）
- 其他原有分组先不动（量化交易/策略池管理/对照与变化等）

### 低频交易：各页内容（首版）
#### 1) 今日快照
- 数据源：`GET /api/v1/sectors/hot?date=YYYY-MM-DD`（兼容 `/api/sectors/hot`；服务端 `lowfreq_hot_sectors_view`）
- 展示：
  - 热门板块 Top5（heat_score）
  - 每板块：龙头/中军/跟随各若干（展示 code/name/sector/role/buy_score/return_5d/reasons/cup_handle_ok/buy_signal/sell_signal/sell_reason）
- 交互：
  - 默认“仅看买入信号”（buy_signal=true）；可切换为“显示全部（含未达阈值）”

#### 2) 持仓监控
- 数据源：同“今日快照”返回中的 `portfolio`（含 open_positions）
- 展示：
  - 当前总资产/收益
  - open_positions 表格：浮盈亏、是否离场、离场原因（人气消散优先，其次止损）
- 交互：
  - 持仓页刷新按钮仅刷新 portfolio（前端仍可复用同一个快照接口，但只重绘本页面板，避免“刷新整页”带来不必要的 UI 抖动）

#### 3) 候选池（下一交易日）
- 数据源：
  - 优先：同“今日快照”板块候选汇总（leaders/middle/followers）
  - 补充：回测报告中的 `next_session.candidates`（仅展示，不提供 JSON 下载）
- 展示：
  - 视图 A（默认）：仅 buy_signal=true（当日可买）
  - 视图 B：TopN（含未达阈值，按 buy_score 排序；用于复核“为什么没买”）
  - 字段：code/name/sector/role/buy_score/return_5d/reasons/cup_handle_ok
  - 标记：`cup_handle_ok`（若有）、以及“周线老鸭头确认”是否在 reasons 中

#### 4) 回测报告
- 数据源：
  - 运行：`POST /api/v1/lowfreq/backtest/run`（兼容 `/api/lowfreq/backtest/run`）
  - 下载：`GET /api/lowfreq/backtest/reports/<report_id>.pdf`（兼容 `/api/v1/lowfreq/backtest/reports/<report_id>.pdf`）
- 展示：
  - 表单：start_date/end_date（留空=全区间）、运行按钮
  - 结果卡：summary 指标、report_id、PDF 下载按钮
- 明确不提供：JSON 下载按钮
- “最新报告”策略：前端 localStorage 缓存最近一次 report_id（首版不做服务端 report list）

#### 5) 执行约束（重要）
- 固定说明（展示即可）：
  - 仅收盘价数据：日频执行
  - no-lookahead 强校验开启
  - 回测可成交性口径：涨停买不进、跌停卖不出（顺延尝试）
  - 涨跌停判定阈值（见下一节）
- 文案格式：
  - 以结构化清单呈现，且与回测报告（PDF）中的“执行约束摘要”保持一致

## 回测执行约束：涨跌停顺延成交（核心）
### 涨跌停判定（用户选择 A）
- 目标：只依赖现有数据字段（daily_prices 的 `pct_change/open/high/low/close` + stocks 的 `code/name`）
- 阈值（采用保守边界，避免误判）：
  - `ST`：±4.8%（从 `stocks.name` 含 “ST” 判定）
  - `688*` 或 `300*`：±19.8%
  - 其他：±9.8%
- 判定规则：
  - 涨停：`pct_change >= limit_up_pct`
  - 跌停：`pct_change <= -limit_up_pct`
  - 首版先按 `pct_change`；后续可增强为 `close==high/low` 组合以降低误判。

### 顺延成交规则（用户选择 B）
- 买入：
  - 若当日出现买入信号但为涨停：不成交，进入“待买入队列”，下一交易日继续尝试。
  - 待买入队列的最大尝试天数：3 个交易日（超时作废），避免长期挂单扭曲回测。
- 卖出：
  - 若当日出现离场信号但为跌停：不成交，进入“待卖出状态”，后续每个交易日优先尝试卖出，直到成交或回测结束平仓。
  - 待卖出状态下：仍更新峰值/收益用于追踪止损统计，但不改变离场信号优先级（信号已出，优先执行）。
- 执行顺序（每日，已实现）：
  1) 先处理待卖出（若不跌停则卖出；否则继续等待）
  2) 再评估当日新离场信号（若跌停则进入待卖出；否则当日卖出）
  3) 再处理待买入（若涨停则继续等待；最多尝试 3 个交易日）
  4) 最后在调仓日生成当日新买入信号（若涨停则进入待买入；否则当日买入）

### 回测报告体现
- trades.pdf 的“回测假设/执行约束”段落增加一条说明：
  - “涨停买不进、跌停卖不出按交易日顺延尝试（待买最多 3 天）”

## 代码落点（首版）
### Dashboard（前端）
- `apps/dashboard/main.py`
  - 左侧导航文案调整：筛选器、单股核验（CHECK）
  - 新增低频交易分组与 5 个锚点 section
- `apps/dashboard/static/neotrade3_enhanced.js`
  - 低频 5 页的渲染与交互（今日快照/持仓监控/候选池/回测报告/执行约束）
  - 快照拉取：GET `/api/v1/sectors/hot`
  - 回测运行：POST `/api/v1/lowfreq/backtest/run`
  - 回测报告：仅展示 PDF 下载链接（不展示 JSON）

### API/回测执行约束
- `apps/api/main.py::_lowfreq_backtest_with_trades`
  - 增加“涨跌停顺延成交”的待买/待卖队列与执行顺序
  - 引入 `stocks` 查询以判定 ST 与代码前缀阈值
- `lowfreq_engine_v16_advanced.py`
  - 提供/复用涨跌停判定辅助函数（或由 api/main.py 封装）

## 验收标准
- Dashboard 左侧导航出现：低频交易（5 页）、筛选器、单股核验（CHECK）
- 低频 5 页能在指定日期下正确渲染（至少展示：板块/候选/持仓/离场原因/回测 summary）
- 回测运行后仅提供 PDF 下载入口，无 JSON 下载按钮
- 回测中涨停买入会被顺延（并有最大尝试天数），跌停卖出会被顺延
- 不引入未来数据（no-lookahead）不被破坏
