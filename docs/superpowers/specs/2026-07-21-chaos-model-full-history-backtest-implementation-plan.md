# 混沌模型：全历史 no-look-ahead 回测实现计划
Date: 2026-07-21
Status: draft
Depends_on:
- docs/superpowers/specs/2026-07-21-chaos-model-full-history-backtest-design.md

## 0. 目标与验收（摘要）

目标：实现“混沌模型全历史 no-look-ahead 回测”，并一次性产出两条可验收产物：

1) 操作窗口摘要 + 交易明细（入池/持有/离场全过程 + 盈亏 + giveback，全部基于 close）
2) 全 A 股 120D 收益率分层滤噪评估（仅评估，不回灌在线）

硬约束：

- 动作生成只读取 `trade_date <= T` 的数据（no-look-ahead）
- 成交口径：T+1 close
- fail-closed：缺快照/非 ready -> 不产生硬动作
- 所有“持有天数/周期长度/窗口计数”均以交易日计数

## 1. 总体方案（路线 A：基于 chaos_daily_snapshot 驱动）

### 1.1 入口与数据源

- 价格/交易日历：`var/db/stock_data.db`（`daily_prices`）
- 混沌 SSOT：`var/db/chaos_factor_matrix.db`（`chaos_daily_snapshot`）
- 版本锁定：在 CLI 参数中显式传入 `registry_version/weights_version/thresholds_version/signal_mode`

### 1.2 关键输出（落盘）

建议落盘路径（与现有 ledgers/artifacts 结构一致）：

- `var/ledgers/chaos_backtest/<end_date>/...json`
- `var/artifacts/chaos_backtest/<end_date>/...json`

输出文件（建议）：

- `chaos_backtest_meta.json`
- `chaos_backtest_trades.json`（全量交易明细）
- `chaos_backtest_window_summary_weekly.json`
- `chaos_backtest_window_summary_regime.json`
- `chaos_backtest_filters_eval_120d.json`

## 2. Phase 1：定义契约对象与最小状态机

### 2.1 新增模块（建议路径）

- `neotrade3/chaos/backtest/contracts.py`
  - `BacktestConfig`
  - `TradeRecord`（包含 giveback 相关字段）
  - `WindowSummary`（weekly/regime 两类通用结构）
  - `FiltersEval120D`（分桶定义 + 分布统计结构）

- `neotrade3/chaos/backtest/engine.py`
  - `ChaosBacktestEngine.run(...) -> BacktestRunResult`

### 2.2 最小动作语义（可配置，先不拍脑门）

先实现一个“可回放、可审计”的最小版本：

- `pool_in`：当日满足 entry 条件但尚未入场（或作为入场候选）
- `entry`：入场（T+1 close）
- `hold`：持有
- `exit`：离场（T+1 close）

需要配置的最小参数（先做最小默认值 + 可传参覆盖）：

- `max_positions`
- `position_sizing`（等权）
- `entry_gate`（默认：使用 Gate(K=8) 可用性为 True 才允许 entry；否则只 pool_in）
- `exit_rule`（默认：只做 `signal_exit` + `end_of_test`；其余止盈止损后续再加）

## 3. Phase 2：实现 no-look-ahead 与成交执行（T+1 close）

### 3.1 no-look-ahead 审计点（必须）

在回测引擎中对每个交易日 T：

- 只加载 `trade_date == T` 的混沌快照（以及内部引用字段），不允许查询未来日期快照
- 生成动作后，若需要成交，则成交日固定为 T+1，并且成交价格读取 `daily_prices.close`（T+1）

### 3.2 fail-closed 行为（必须）

- 当 code 在 T 日缺少 `chaos_daily_snapshot` 或 `chaos_status != ready`：
  - `entry/exit` 不得产生
  - 报表中记录 skip 计数，并在窗口摘要中暴露

## 4. Phase 3：产出交易明细 + 窗口汇总（weekly + regime）

### 4.1 交易明细（TradeRecord）

对每笔交易计算并落盘：

- `entry_date/entry_price_close`
- `exit_date/exit_price_close`
- `exit_return_pct`
- `peak_close_price/peak_close_date`
- `max_runup_pct_during_hold`
- `giveback_pct`

峰值与回吐计算只使用 close：

- `peak_close_price = max(close[entry_date..exit_date])`
- `giveback_pct = (peak/entry - 1) - (exit/entry - 1)`

### 4.2 weekly 窗口汇总

按周末交易日聚合：

- 交易数、胜率、平均收益、中位数收益
- 平均 giveback、p90 giveback
- skip 计数（missing/pending）

### 4.3 regime 窗口汇总

对每个 code 按 `self_history_reference_json.regime_anchor_date` 切段：

- 每段内交易汇总与 giveback 汇总
- 用于复盘“阳转阴后”的行为差异

## 5. Phase 4：全 A 股 120D 分层滤噪评估（仅评估）

### 5.1 后验标签计算

对任意日期 T：

- `ret_120d = close(T+120) / close(T) - 1`
- 若未来 close 缺失：标记为 `label_missing`，不参与分桶统计

### 5.2 分桶与统计

实现最小版本：

- 桶定义：先用固定分位（例如 10/20/30/40/50/60/70/80/90），实现阶段再与用户确认是否需要调整桶数
- 输出：
  - `trigger_event_count_by_bucket`（入池/入场分别统计）
  - `trigger_code_count_by_bucket`（按 code 去重）

## 6. CLI 与运行形态

新增脚本（建议）：

- `scripts/run_chaos_full_history_backtest.py`

参数（最小集合）：

- `--start-date/--end-date`（默认从 daily_prices 的 min/max 推导）
- `--registry-version/--weights-version/--thresholds-version`
- `--signal-mode/--combo-lambda/--combo-beta`
- `--max-positions/--position-size-pct`
- `--report-suffix`

## 7. 最小测试与校验

### 7.1 单测（最小集合）

- `test_no_lookahead_guard`：确保动作生成阶段不查询未来 trade_date
- `test_fill_closed_missing_snapshot`：缺快照不产生硬动作
- `test_t_plus_1_close_execution`：成交日/价严格按 T+1 close
- `test_giveback_computation_close_only`：giveback 与 close 序列可复算

### 7.2 最小运行校验

- `python -m compileall` 通过
- 在一个短区间（例如 60 个交易日）内跑通：
  - 产出 trades/window_summaries/filters_eval 三类文件
  - 产物 schema 自洽且可复算抽查

## 8. 风险与缓解

- 全 A 股全历史计算量：先确保引擎可分段运行（start/end 可切片），并落盘可增量合并
- 数据缺口导致标签缺失：在 filters_eval 中显式记录 `label_missing` 比例，避免“静默偏差”
