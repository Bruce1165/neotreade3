# Hazard Predictor v0（T2-online）预测质量评估设计（近 2 年）
Date: 2026-07-19

## 1. 背景

我们已经落地 `hazard_predictor_v0`（T2-online），其输出为 0–100 的 `stock_top_risk_5d/20d`，并严格 no-lookahead（只允许使用 target_date 当日及历史数据）。

同时，我们已完成离线监督标签表 `stock_top_hazard_labels_t2` 的全历史回填。该表包含未来窗口信息，属于“真值/监督标签”，只能用于评估与校准，不得作为在线预测输入或 M3 日常决策依据。

本设计用于定义一个“可复算、可审计、可回滚”的评估闭环，用离线标签验证在线预测器的预测质量。

## 2. 目标与非目标

### 2.1 目标

- 基于离线标签对在线预测器做预测质量评估（近 2 年范围）
- 以分桶命中率为主，回答：
  - 分数是否有区分度（高分桶命中率是否显著更高）
  - 5d 与 20d 两条 horizon 的行为差异
- 输出结构化产物（JSON/CSV），支持后续校准/阈值调整

### 2.2 非目标

- 不把离线标签用于在线预测输入
- 不在本阶段引入 ML 模型
- 不把 hazard v0 升级为退出链（exit_signal/risk_action=exit）

## 3. 硬约束（必须满足）

- Label/Prediction 严格分离：
  - 评估层可以读取 `stock_top_hazard_labels_t2`
  - 在线预测器不得读取 `stock_top_hazard_labels_t2`
  - 评估脚本不得被在线预测器或 M3 运行链路调用（防止反向依赖）
- No-lookahead：
  - 在线预测计算只允许使用 `daily_prices.trade_date <= obs_date`
- 口径可复算：
  - 所有评估输出必须附带 config_snapshot / run_meta（参数、范围、SQL 版本等）

## 4. 评估范围（近 2 年）

### 4.1 日期范围定义（可核验）

- 以 `daily_prices` 的最大交易日 `max_trade_date` 为基准
- 令 `start_date = max_trade_date - 730 days`（自然日），评估区间为：
  - `start_date <= obs_date <= max_trade_date`
- 说明：该定义简单明确，可复算；实际交易日数量由市场休市决定。

### 4.2 样本选择

对每个 `(code, obs_date, horizon_days)`：

- 真值：来自 `stock_top_hazard_labels_t2`
- 过滤：
  - `label_status = 'ready'`（只评估可判定样本）
  - `obs_date` 落在近 2 年范围内
- horizon：
  - `horizon_days in (5, 20)` 分别评估

## 5. 评估输入（在线预测器输出）

对每个 `(code, obs_date)` 计算在线 hazard snapshot（T2-online）：

- 输出字段（最小集合）：
  - `risk_status`（ready/pending）
  - `hazard_state`（not_ready/neutral/accel_only/break_armed/stale_break/recovering）
  - `stock_top_risk_5d`（0–100）
  - `stock_top_risk_20d`（0–100）
- 评估约束：
  - 若 `risk_status != 'ready'`，该样本不进入分桶质量统计（但需要在 run summary 中单独统计占比）
  - 分桶质量评估只统计 `hazard_state in (neutral, accel_only)` 的样本，避免“事后状态”污染“事前预测”评估口径；其余状态单独输出分布与 hit_rate（作为状态的行为画像，不作为 score 质量指标）

## 6. 核心指标与输出

### 6.1 分桶命中率（主指标）

- 分桶：按 risk_score 10 分桶
  - [0–9], [10–19], …, [90–100]
- 对每个 horizon（5/20）分别输出：
  - `bin_low/bin_high`
  - `n`（样本数）
  - `hit_n`
  - `hit_rate = hit_n / n`
  - 可选：`cum_n/cum_hit_rate`（从高分到低分的累计覆盖）

### 6.2 Lift / 单调性（辅助指标）

- Lift（建议至少输出一个可解释指标）：
  - `top_bin_hit_rate / overall_hit_rate`
  - 或 `top_2_bins_hit_rate / bottom_2_bins_hit_rate`
- 单调性检查（不作为硬失败，但要输出异常计数）：
  - 统计 “高分桶 hit_rate < 低分桶 hit_rate” 的次数

### 6.3 近 2 年整体概览（summary.json）

- 每个 horizon：
  - `n_ready`（参与评估样本数）
  - `n_pending_or_not_ready`（被剔除样本数与比例）
  - `n_excluded_by_state`（因 hazard_state 不在 neutral/accel_only 而从 score 评估剔除的样本数）
  - `overall_hit_rate`
  - `lift_top_bin`
  - `monotonicity_violations`

## 7. 性能与实现策略（必须可执行）

直接对每条标签记录调用 `build_hazard_snapshot_v0_t2(cursor, code, obs_date)` 会产生大量 SQL 调用，不可接受。

因此评估实现必须采用“按 code 批处理”的方式：

- 对每个 code，一次性加载近 2 年所需的历史价格序列（必要时加载更长以满足 K=15 的前置窗口）
- 在内存中对该 code 的每个 obs_date 计算 hazard v0 分数

为避免评估逻辑与在线预测器逻辑分叉，建议对 `hazard_predictor_v0` 做一个小幅重构（仍保持对外 API 不变）：

- 将核心计算抽成纯函数：
  - 输入：`dates/closes/highs/pct_changes/target_idx/cfg`
  - 输出：hazard snapshot（dict）
- 在线预测器与评估脚本共用该纯函数

## 8. 产物与落盘

执行策略：

- 默认先以“终端打印摘要”的方式跑通评估口径，人工确认无误后再落盘生成文件产物（summary/bin/config）。

落盘目录（按 run_id 时间戳隔离）：

- `var/artifacts/evals/hazard_v0_t2/<run_id>/`

文件：

- `summary.json`
- `bins_5d.csv`
- `bins_20d.csv`
- `config_snapshot.json`（参数、日期范围、bin 规则、label 过滤条件、代码版本标识等）

## 9. 测试与护栏

- 单测：
  - 评估逻辑对分桶/命中率计算的正确性（用小样本 sqlite :memory:）
- 护栏：
  - 在线预测器不得读取离线标签表（已有护栏测试）
  - 评估脚本不得被线上链路 import（通过模块分层与目录约束保证，必要时加 `import` 路径检查测试）
