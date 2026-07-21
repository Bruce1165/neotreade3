# 混沌模型：全历史 no-look-ahead 回测里程碑设计
Date: 2026-07-21
Status: draft

## 1. 里程碑目标（用户验收口径）

本里程碑的“可验收一句话”：

- 在**全 A 股、全历史区间**内，使用严格 **no-look-ahead** 的混沌模型决策语义（M3 只读当日及历史）生成“入池/持有/离场”动作；回测产物可以：
  - 按“时间窗口”汇总展示不同操作窗口与统计指标；
  - 下钻到每一笔交易的全过程（入池→持有→离场）与盈亏；
  - 记录“最高可获得收益（基于 close）”与“回吐（giveback）”；
  - 额外输出“滤噪能力”评估：在全 A 股上用后验 120D 收益率分层，统计模型触发在强增长/平庸分层中的分布。

## 2. 边界与硬约束（必须）

### 2.1 No-look-ahead（强约束）

- 回测模拟的任何“信号/动作”在交易日 T 只能读取：
  - `trade_date <= T` 的混沌快照、因子、历史引用（regime reference）；
  - `trade_date <= T` 的价格与基础数据。
- 未来窗口（例如 120D 标签）只允许出现在“评估报表层”，不得回灌进“当日动作生成”。

### 2.2 成交口径（冻结）

- 仅使用日线 `close`。
- 成交假设：**T 日产生动作，T+1 日以 close 成交**（避免使用同日 close 形成隐性前视）。

### 2.3 Fail-closed（强约束）

- 当 `chaos_daily_snapshot` 缺失或 `chaos_status != ready` 时：
  - 该标的在当日不产生入池/入场/离场等硬动作；
  - 在报表中明确记录为 `skipped_missing_snapshot` 或 `skipped_pending_snapshot`。

## 3. 输出物（一次到位：并行产出两条）

### 3.1 输出 A：操作窗口（时间窗口）摘要 + 交易明细（下钻）

#### A1. 窗口切分（两层）

1) **时间窗口（主视角）**  
- 默认按周窗口（每周最后一个交易日作为 `window_end_date`），对窗口内发生的入池/入场/离场与盈亏做汇总。  
- 原因：更贴近“按时间段观察模型在不同市场环境下的行为”。

2) **regime 窗口（辅助视角）**  
- 使用混沌 `self_history_reference_json.regime_anchor_date` 对每个 code 做“驱动段”切分（以 anchor 变化为段边界）。  
- 原因：用于复盘“阳转阴后”的行为差异与回吐特征聚合。

#### A2. 每笔交易必须记录的字段（最小集合）

每笔交易是一个 `trade_window`：从入场成交到离场成交。

- 基本信息：`code`、`name`
- 入场：
  - `signal_date`（T）
  - `entry_date`（T+1）
  - `entry_price_close`（T+1 close）
  - `entry_reason`（入池/入场触发原因）
  - `entry_snapshot_ref`（用于审计：包含 registry/weights/thresholds/version 与 reference_mode）
- 持有：
  - `holding_days`（交易日计数）
  - `peak_close_price`（持有期内最高 close）
  - `peak_close_date`
- 离场：
  - `exit_signal_date`（T）
  - `exit_date`（T+1）
  - `exit_price_close`（T+1 close）
  - `exit_reason`（例如：signal_exit/time_exit/stop_loss/take_profit/end_of_test）
  - `exit_snapshot_ref`
- 盈亏与回吐（用户关注点，全部基于 close 可复算）：
  - `exit_return_pct = exit_price_close / entry_price_close - 1`
  - `max_runup_pct_during_hold = peak_close_price / entry_price_close - 1`
  - `giveback_pct = max_runup_pct_during_hold - exit_return_pct`
  - `max_drawdown_from_peak_pct`（可选，但建议保留）：持有期内相对 `peak_close_price` 的最大回撤

#### A3. 窗口级汇总指标（时间窗口与 regime 窗口都适用）

- 交易统计：`trade_count`, `win_rate`, `avg_return`, `median_return`
- 风险：`max_drawdown_of_trades`（基于交易级回撤统计）
- 回吐：`avg_giveback`, `p90_giveback`
- “阳转阴修正”相关：按 `exit_reason` 与“exit_signal 当日的混沌读出特征”做分桶统计（仅报表层）

### 3.2 输出 B：全 A 股滤噪能力评估（后验分层，仅用于评估）

#### B1. 后验分层标签（冻结）

- 使用后验 **120 交易日收益率**作为主标签：
  - `ret_120d = close(T+120) / close(T) - 1`
- 在全 A 股上按 `ret_120d` 做分位分桶（例如：top 10%、mid、bottom 50% 等，桶位数量在实现阶段冻结）。

#### B2. 需要输出的评估指标（最小集合）

- 触发分布：模型产生“入池/入场”动作的样本，在各分桶的占比
- 捕获能力（对照）：在“强增长桶”内，模型触发覆盖了多少只（按 code 去重）/多少次（按事件计数）
- Top200 捕获率：以全历史区间的某个 “Top200 强势股定义”做对照（需在实现阶段明确选择：按 max_runup 或按终局收益）

## 4. 数据依赖与 SSOT 入口

### 4.1 数据库

- 价格与基础数据：`var/db/stock_data.db`（`daily_prices` 为主）
- 混沌快照（SSOT）：`var/db/chaos_factor_matrix.db`（`chaos_daily_snapshot` 为主）

### 4.2 版本锁定（必须写入审计信息）

回测运行必须显式记录：

- `registry_version`（例如 `chaos_registry_v1`）
- `weights_version`（例如 `chaos_weights_v1_2`）
- `thresholds_version`（例如 `chaos_thresholds_v0`）
- `signal_mode`（例如 `regime_combo`，以及 λ/β）

## 5. 回测行为语义（M3 级动作，需在实现阶段冻结）

本里程碑要求“可列出不同操作窗口与过程细节”，因此必须将混沌读出映射到最小动作集合：

- `pool_in`：入池（进入观察/候选）
- `entry`：入场（产生持仓）
- `hold`：持有（保持持仓不变）
- `exit`：离场（清仓）

约束：

- 动作生成只依赖当日混沌读出与历史引用（no-look-ahead）。
- 交易执行使用 T+1 close，因此动作触发日与成交日分离。

实现阶段需要明确的最小策略参数（先不拍脑门，需可配置）：

- `max_positions`（最多同时持仓数量）
- `position_sizing`（等权/固定比例）
- `entry_gate`（例如：Gate(K=8) 可用性通过时才允许 entry）
- `exit_rule`（阳转阴、回吐容忍、时间退出等的最小集合）

## 6. 产物落盘与可审计性

### 6.1 建议落盘路径（SSOT）

- `var/ledgers/chaos_backtest/<end_date>/...json`
- `var/artifacts/chaos_backtest/<end_date>/...json`

每次 run 必须输出：

- `meta`：版本、生成时间、数据范围、no-look-ahead 标记、成交口径（T+1 close）
- `window_summaries`：时间窗口与 regime 窗口摘要
- `trades`：全量交易明细（不截断，必要时分文件）
- `filters_eval`：全 A 股分层评估统计（桶定义 + 分布 + 指标）

### 6.2 最小审计项

- 能从任意一笔交易反查：
  - 触发日 T 的混沌快照（code, T, versions）与关键读出字段；
  - 成交日 T+1 的 close；
  - 离场触发日与成交日同理。

## 7. 验收清单（里程碑通过条件）

1) no-look-ahead：任意交易/动作的证据链均可证明只使用了当日及历史数据  
2) 交易明细可复算：`exit_return_pct/max_runup_pct/giveback_pct` 与 close 序列一致  
3) 窗口汇总可下钻：时间窗口与 regime 窗口都能定位到组成它的交易明细  
4) 滤噪评估可复现：全 A 股 120D 分桶与“触发分布”指标可复算且版本锁定  
