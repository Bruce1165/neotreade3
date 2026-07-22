# M6（LowFreq V16）全量 no-look-ahead 回测 + Top200 BullStocks 捕获率 + 净值峰顶守住能力（PDF 报告）设计

## 目标

- 在 NeoTrade3 现有低频回测引擎（`LowFreqTradingEngineV16`）基础上，执行一次“全量 no-look-ahead 回测”。
- 目标 1：评估模型对“Top200 BullStocks”的捕获能力（捕获率）。
- 目标 2：评估模型是否能持有这些股票直到“策略净值的真实峰顶”（并允许峰顶后有限回撤容差）。
- 产出一份可落盘、可复核的 PDF 报告，包含净收益（net gain）与关键分解指标。

## 前提与边界（已对齐）

- 模型链路：以 NeoTrade3 现有的 `LowFreqTradingEngineV16` 回测链路为准（API/脚本均可调用）。
- no-look-ahead：启用引擎内置 guard（未来数据引用直接 fail-closed 抛错终止）。
- 全量回测时间窗：使用 DB 全覆盖区间
  - `start_date = MIN(daily_prices.trade_date)`
  - `end_date = MAX(daily_prices.trade_date)`
- “Top200 BullStocks”口径：全样本期 Top200（不按单一年份）。
- 数据补齐：在回测前使用 Tushare 对“DB 覆盖区间内的缺口”做回补，写入 NeoTrade3 主行情库（`var/db/stock_data.db`）。
  - 不扩容到更早起点：不将 `start_date` 前推到 2010/2005，只补齐现有区间缺口。
- 净收益口径：使用引擎内置成本模型/净值输出（策略参数来自 `config/strategies/lowfreq_v16.json`）。
- 峰顶守住判定：以“策略净值峰顶”为峰顶，允许峰顶后回撤不超过 `X%` 退出也算守住；默认 `X=5%`。
- 输出：PDF 默认保存到 `var/reports/`（文件名含日期范围与生成时间戳）。

## 关键输入

- 行情库：`var/db/stock_data.db`（可通过 `NEOTRADE3_STOCK_DB_PATH` 覆盖）
- 策略配置：`config/strategies/lowfreq_v16.json`
- 数据源策略：`config/data_control/source_registry.json`（确认 `daily_prices` primary_provider 为 `tushare`）

## 关键输出

### 1) 报告文件（PDF）

- 路径：`var/reports/m6_full_backtest_<start>_<end>_<ts>.pdf`

### 2) 可复核中间产物（JSON/CSV）

- 建议同目录落盘：
  - `m6_full_backtest_payload_<start>_<end>_<ts>.json`
  - `top200_bullstocks_<start>_<end>_<ts>.csv`
  - `top200_capture_eval_<start>_<end>_<ts>.json`

## 执行流程（推荐：方案 A，脚本一键跑）

### Step 0. 运行环境校验

- Python 版本与依赖可用（遵循仓库 `.venv` 约束）。
- DB 文件存在且可写。

### Step 1. 数据补齐（Tushare 回补，主库写入）

目的：避免回测出现 “no data support”。

- 读取 DB 覆盖区间 `[start_date, end_date]`。
- 调用范围回补（复用现有能力）：
  - `backfill_daily_prices_tushare_range_view(start_date, end_date, requested_by, min_close_coverage, min_amount_coverage, dry_run=False)`
- 质量闸：
  - `min_close_coverage=0.99`
  - `min_amount_coverage=0.99`
- fail-closed：
  - token 缺失 / provider 失败 / coverage 未通过 / 写库异常 → 终止并输出错误。

### Step 2. 全量 no-look-ahead 回测（LowFreq V16）

- 调用引擎入口：
  - `LowFreqTradingEngineV16.run_backtest(start_date, end_date, include_trades=True, include_daily_values=True)`
- no-look-ahead：
  - 引擎内部 `_ensure_no_lookahead_trade_dates` 对未来日期直接抛错，整体终止。
- 产物：
  - 回测 payload（含交易明细、每日净值序列）落盘，供后续评估与审计复核。

### Step 3. Top200 BullStocks（全样本期）计算

目标：从 `daily_prices` 推导“全样本期 bullness”，并取 Top200。

#### 3.1 bullness 指标（可复现 SQL）

定义：每只股票在覆盖期内的“最大回撤前涨幅”（最大 run-up）。

- 对每只股票按交易日排序：
  - `min_close_so_far(t) = MIN(close[<=t])`
  - `runup(t) = close(t) / min_close_so_far(t) - 1`
  - `max_runup = MAX(runup(t))`
- Top200：按 `max_runup` 倒序取前 200。

备注：该口径关注“历史最大主升段幅度”，不依赖年度归因字段，可在 DB 内完全重算。

### Step 4. 目标 1：Top200 捕获率计算

“捕获”定义（可证伪）：Top200 股票中，至少发生过一次买入成交（buy trade）。

输出指标：

- `captured_count`
- `capture_rate = captured_count / 200`
- `captured_codes[]`（含：首次买入日期、买入次数、平均持有天数、该股票贡献净收益等摘要）
- `missed_codes[]`

### Step 5. 目标 2：净值峰顶守住能力计算（Top200 子集）

#### 5.1 峰顶定义

- 从回测输出的每日净值序列计算：
  - `peak_value = MAX(equity)`
  - `peak_date = argmax_date(equity)`

#### 5.2 守住判定

对 Top200 中被捕获的股票，按“退出时刻”评估：

- 找出该股票最后一次卖出（或平仓）日期 `sell_date` 对应的权益 `equity_at_sell`。
- 计算峰顶回撤：
  - `drawdown_at_sell = (peak_value - equity_at_sell) / peak_value`
- 判定：`drawdown_at_sell <= X` 视为守住（默认 `X=0.05`）。

输出指标：

- `held_to_peak_rate`（守住率）
- `drawdown_at_sell_distribution`（P50/P80/P95，及分桶统计）
- Top200 子集的个股明细（code → drawdown_at_sell, sell_date, 持仓天数等）

## 报告结构（PDF）

### 1) 摘要（One-page）
- 回测区间、策略配置摘要（含配置文件 hash 或关键参数摘要）
- no-look-ahead 状态（开启/关闭）
- net gain（净收益额、净收益率、期末权益、起始权益）
- 目标 1：Top200 捕获率（captured_count/200）
- 目标 2：峰顶守住率（在回撤阈值 X 下）

### 2) 数据补齐摘要
- 回补范围、回补天数、upsert 行数
- 质量闸结果（coverage 与 gate_reasons）
- 若失败：fail-closed 原因与错误码

### 3) Top200 定义与样本概览
- bullness 指标定义（max_runup）与 SQL 口径说明
- Top10 样本表格（code、max_runup、对应区间等）

### 4) 目标 1：捕获率与分解
- 捕获率总览
- 被捕获样本的买入分布（首次买入日期分布、次数分布）
- 未捕获样本列表（可只输出 TopN）

### 5) 目标 2：峰顶守住能力
- 净值峰顶日期、峰顶值、阈值 X
- `drawdown_at_sell` 分布与守住率
- Top200 子集的个股明细（可只输出 TopN 极端值：最好/最差）

### 6) 附录（审计信息）
- DB 路径（safe ref）
- 生成时间
- 关键中间产物文件路径（payload/top200/capture_eval）

## 失败策略（Fail-closed）

- 数据补齐阶段：
  - token 缺失、回补失败、质量闸不通过、写库异常 → 直接终止，不继续回测。
- 回测阶段：
  - no-look-ahead 触发 → 直接终止并报错。
  - 回测输出缺失关键字段（trades/daily_values） → 直接终止并报错。
- 评估阶段：
  - Top200 SQL 计算失败或结果不足 200（在 universe 过滤后）→ 终止并报错（报告不生成）。

## 实施落点（代码位置建议）

- 新增脚本（推荐）：
  - `scripts/run_m6_full_backtest_top200_report.py`
- 新增分析模块（若需要复用/测试）：
  - `neotrade3/analysis/top200_bullstocks.py`（Top200 计算与口径封装）
  - `neotrade3/analysis/m6_backtest_eval.py`（捕获率、峰顶守住能力评估）
- PDF 输出：复用仓库现有 reportlab 方式（参照 lowfreq backtest PDF 生成逻辑）。

## 验收标准

- 产出 PDF 文件，且包含：
  - net gain（含成本模型）
  - Top200 捕获率
  - 峰顶守住率（含阈值 X）
- 中间产物可复核（payload/top200/eval 落盘）。
