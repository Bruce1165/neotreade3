# NeoTrade3 V3 自动化与主题视角（方案 1）设计规格

日期：2026-06-02  
范围：NeoTrade3 V3（/Users/mac/NeoTrade3）  
目标：以量化选股为核心，实现从数据到筛选到交易到回测到优化的自动闭环，且具备可观测性与可追溯性。  

## 0. 已确认的硬约束（Decision Log）

1. 自动化链路：采用“方案 1”，以 Tencent 日更作为唯一触发器，串行跑完核心任务链。  
2. 每日回测：采用滚动窗口回测（A），窗口长度 N=60 个交易日。  
3. 自动优化目标函数：在 `max_drawdown_pct <= 10%` 约束下最大化收益。  
4. 热门板块默认展示：改为“团队主题”口径；行业热门只作为二级切换入口。  
5. 团队主题数据源：主源使用东方财富“概念板块”；允许使用最近成功快照，陈旧不超过 3 天。  
6. 若团队主题快照陈旧超过 3 天：默认页提示“主题数据不可用（超过 3 天）”，不自动回退行业热门。  
7. 低频模型：从今天开始按当前模型逻辑自动买入/卖出/调仓，起始资金 100 万元，交易记录必须在持仓监控中可见。  
8. 单股核验：未通过筛选器必须给到参数级别原因，需实时运行核验逻辑，不能只返回“当日筛选结果不包含”。  

## 1. 总体架构与数据流

### 1.1 核心流水线（由 Tencent 日更触发）

触发器：`update_daily_prices_tencent`（scheduler/launchd）  

串行步骤（同一次触发周期内）：
1) 每日行情更新（Tencent）  
2) 筛选器对当日数据批量运行（bulk-run）  
3) 低频模型每日运行（推进模拟状态：买/卖/调仓 + 交易记录落盘）  
4) 每日滚动回测（60 交易日窗口，异步生成报告，保留最近 10 份）  
5) 基于回测指标的自动优化（在回撤约束下做受控参数搜索，生成次日生效 overrides）  

输出与落盘：
- 数据：`var/db/stock_data.db`（daily_prices 等）  
- 筛选器运行：`var/ledgers/screener_runs/<date>/...` + `var/artifacts/screener_runs/<date>/...`  
- 低频模拟状态：`var/ledgers/lowfreq_sim/state.json`  
- 回测报告：`var/artifacts/lowfreq_backtest/<report_id>/{status.json,trades.pdf,trades.json}`  
- 自动化台账：新增 `var/ledgers/daily_runs/<date>.json`（详细见 §2）  
- 自动优化台账：新增 `var/ledgers/auto_optimization/<date>.json`（详细见 §6）  

### 1.2 可观测性（必须可排障）

所有自动任务必须提供：
- status：ok / running / failed / blocked  
- timing：每一步耗时（毫秒）  
- artifact refs：产物路径 / report_id / 下载 URL  
- failure reason：失败原因与可执行建议  

## 2. 自动化总台账（Daily Run Ledger）

### 2.1 目的

为“自动化运行”提供可追溯证据：当天是否已完成、卡在何处、产物在哪里、失败原因是什么。  

### 2.2 结构（建议）

`var/ledgers/daily_runs/YYYY-MM-DD.json`

字段建议：
- version, target_date, triggered_by, started_at, finished_at  
- steps：数组，每步包含
  - step_id（tencent_update / screeners_bulk_run / lowfreq_sim_daily / lowfreq_backtest_60d / auto_optimize）
  - status, started_at, finished_at, elapsed_ms
  - outputs（路径/URL）
  - error（若失败）  

## 3. 低频回测：异步可靠性与 UI 行为

### 3.1 问题定义

回测报告生成较慢。用户在回测未完成前切换板块时，必须保证：
- 后台回测任务仍能完成（不被 UI 切换影响）  
- UI 具备可判断任务状态的能力（running/done/failed）  

### 3.2 接口设计

新增状态查询接口：
- `GET /api/lowfreq/backtest/status?report_id=<id>`  
  - 读取 `status.json`，返回 status、pid、错误、以及 pdf_url（done 时）  

回测启动（已有）：
- `POST /api/lowfreq/backtest/run`  
  - 默认 async_run=true  
  - 返回 accepted + report_id + pdf_url + job 信息  

报告列表（已有）：
- `GET /api/lowfreq/backtest/reports?limit=10`  

### 3.3 前端行为

- 点击“运行回测”后：
  - 保存 report_id（localStorage）
  - Backtest Tab 开启轮询 status（间隔可配置），直到 done/failed
- 切换 Tab：
  - 轮询停止
  - 回到 Backtest Tab 时继续轮询同一个 report_id
- Backtest Tab 需展示：
  - 最近 10 次报告列表（含下载）
  - 当前任务状态（若存在 running 任务）
  - 失败原因（failed）  

## 4. 单股核验：筛选器参数级失败原因（实时核验）

### 4.1 目标

对任意股票 code，在指定日期 target_date 上：
- 判断它是否通过各筛选器  
- 若未通过：返回参数级 explain_cn（含阈值、实际值、失败点）  

### 4.2 约束

- 不允许只用“当日筛选结果不包含该股票”作为失败原因  
- 必须实时运行核验逻辑（单股粒度），确保解释可复现  

### 4.3 实现策略

为每个筛选器提供“单股核验函数”：
- 输入：code, target_date, effective_parameters  
- 输出：result(bool) + explain_cn + evidence（字段值摘要）  

并在 `/api/check-stock` 聚合：
- screeners.items：每个筛选器的结果与 explain_cn  

## 5. 团队主题热门：主源 + 降级 + 兜底

### 5.1 目标

默认展示“团队主题”热门（AiDC、新能源、国产替代、绿能、储能、芯片、算电结合）。  

### 5.2 数据源与缓存

主源：东方财富概念板块  

落盘快照：
- 主题→概念列表映射（可配置）  
- 概念→成分股列表（按日快照）  
- 快照有效性：优先当天；允许使用最近成功快照，陈旧不超过 3 天  

### 5.3 降级策略（硬约束）

- 若当天主源失败：
  - 若存在 ≤3 天陈旧快照：使用快照并在 UI 标注 stale_days  
  - 若快照 >3 天或不存在：默认页提示“主题数据不可用（超过 3 天）”，不回退行业热门  

### 5.4 备选数据源（必须有）

实现为可插拔 provider：
- Provider 1：Eastmoney concept（主）  
- Provider 2：备用（第二供应商或本地导入），接口与数据结构对齐 Provider 1  

切换策略：
- 主源失败时先尝试快照；若快照不可用则尝试备用 provider；若仍失败则提示不可用。  

## 6. 自动优化（可落地最小闭环）

### 6.1 目标函数（硬约束）

约束：`max_drawdown_pct <= 10%`  
目标：在满足约束的候选中最大化 `total_return_pct`（或等价收益指标）。  

### 6.2 最小可落地方案

每天滚动回测完成后：
1) 读取回测指标  
2) 在受控参数空间中生成若干候选 overrides（阈值/权重类，边界明确）  
3) 对每个候选运行同一窗口回测，筛掉 max_drawdown 超限者  
4) 选择收益最优者写入“次日生效 overrides”  
5) 记录优化台账（候选参数、指标、淘汰原因、最终选择）  

### 6.3 生效与回滚

- overrides 生效边界：仅影响低频模型与回测，不影响数据层  
- 回滚策略：保留最近 N 份 overrides，支持手动指定回滚到某一份  

## 7. 验收清单（必须提供可复现证据）

1) Tencent 触发后，daily-run ledger 记录 4+1 步骤均可追溯（状态/耗时/产物/失败原因）。  
2) 筛选器每日运行可自动完成，且有运行记录与下载 CSV。  
3) 低频模型每日自动推进，交易记录在持仓监控中可见（买/卖/价/量/收益/日期/名称/编码）。  
4) 回测异步：切换板块不影响后台生成；UI 可显示 running/done/failed，并可下载 PDF。  
5) 单股核验：未通过筛选器返回参数级 explain_cn（阈值+实际值+失败点）。  
6) 团队主题热门默认展示；主源失败时可用 ≤3 天快照；超过 3 天明确提示不可用且不回退行业热门。  
7) 自动优化：在回撤约束下每日生成次日生效 overrides，并写入可追溯台账。  

