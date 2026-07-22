# NeoTrade3：低频交易“把握度(概率)”闭环与前端直观流程（A1 口径）

## 0. 目标与非目标

### 目标
- 用“把握度(%)”取代零散的技术指标展示：把“未来 60 个交易日内出现 ≥50% 区间最大涨幅”的概率，作为可校准、可核验的核心指标。
- 前端以“发现 → 跟踪 → 决策 → 执行 → 复盘”的业务流程组织信息，用户只在“动作”（买入/卖出/调仓/放弃）上介入或启用 autopilot，其它过程直观呈现。
- 成交口径与标签口径一致：信号日 d 触发动作，next trading day open 成交（A1）。

### 非目标
- 不承诺达到“概率≥85%”的业务结果；系统提供可核验的训练/校准闭环与展示，模型迭代目标由后续持续验证驱动。
- 第一版不引入复杂机器学习训练框架；以可解释、可上线的分桶经验概率为主（后续可替换/增强校准器）。

## 1. 核心口径（已确认）

### 1.1 标签定义（A1）
对样本 `(code, obs_date=d)`：
- `entry_date = next_trading_day(d)`
- `entry_price = open(code, entry_date)`
- `max_high_60d = max(high(code, t))`，`t ∈ [entry_date, entry_date + 60 个交易日窗口]`
- `max_return_60d = (max_high_60d - entry_price) / entry_price`
- `hit_50pct = (max_return_60d >= 0.50)`

约束：
- 标签回填必须满足 `latest_trade_date >= entry_date + 60 交易日`，避免任何 lookahead。

### 1.2 交易成交价口径（与 A1 对齐）
- 买入：动作在信号日生成，`entry_date=open` 成交。
- 卖出：动作在触发日生成，下一交易日 `open` 成交（保持“动作→次日成交”的一致性）。
- 调仓：拆为两条动作（卖出多少 + 买入多少），也以次日 open 成交。

## 2. 数据范围与每日闭环

### 2.1 每日观测样本集合（范围可控）
每日生成观测样本集（并集）：
- 人气概念 TopN 的成分股（按龙头/中军/跟随分层后取 TopK）
- 热门板块候选（现有 `sectors/hot` 输出的 leaders/middle/followers）
- 当前持仓 + 执行队列涉及股票

目的：
- 覆盖“概念→分层→持续跟踪→触发动作→持仓监控”的主要路径，而不是全市场枚举。

### 2.2 三张核心表（闭环最小集）

1) `stock_daily_observations`
- 主键：`(obs_date, code)`
- 字段：
  - `obs_date`, `code`, `name`
  - 归因：`concept_code/concept_name`（可空），`sector`（团队主题/行业），`role`（龙头/中军/跟随）
  - 模型原始输出（内部）：`raw_score`（不面向用户解释）
  - 风险：`risk_level(ok/warn/exit)`, `risk_reason`
  - 动作建议（面向前端）：`state_label`（观察/接近买点/待执行/持仓/离场预警），`why`（一句话）
  - 当日价格快照：`close`（可选），用于展示趋势与回溯

2) `stock_forward_labels_60d`
- 主键：`(obs_date, code)`
- 字段：
  - `entry_date`, `entry_price`
  - `max_high_60d`, `max_return_60d`
  - `hit_50pct`（0/1）
  - `label_ready_at`, `label_status`（pending/ready）

3) `confidence_calibration_buckets`
- 主键：`(bucket_key, as_of_date)`
- 字段：
  - `bucket_key`：由若干维度拼装（建议：raw_score 分位桶 × role × market_regime × risk_level）
  - `n`, `hits`
  - `confidence_prob`：带平滑的经验概率
  - `updated_at`

说明：
- 第一版 bucket_key 维度保持少而稳定，优先确保样本量充足；维度增多会导致稀疏与不稳定。

### 2.3 每日任务分解
每日运行：
1) 写入 `stock_daily_observations`（当日样本）
2) 对已满足窗口的数据回填 `stock_forward_labels_60d`
3) 依据 `stock_forward_labels_60d` 刷新 `confidence_calibration_buckets`

## 3. API 设计（面向“直观展示”，避免术语）

### 3.1 统一“标的卡片”结构
所有页面复用同一结构（概念详情/行动中心/持仓跟踪）：
- `code`, `name`
- `concept/sector`, `role`
- `confidence_prob`（0~1），`confidence_samples`（样本量）
- `state_label`（观察/接近买点/待执行/持仓/离场预警）
- `why`（一句话原因）
- `risk_level`（ok/warn/exit），`risk_reason`
- `actions`：
  - `can_buy/can_sell/can_rebalance`（布尔）
  - `blocked_reason`（未到执行日/无价格/资金不足/无仓位等）

### 3.2 概念 → 分层接口
- 返回人气概念列表（含概念风险灯、热度、可跟踪数量）
- 返回概念详情：三列（龙头/中军/跟随），每只股票附带“标的卡片”字段与最近 N 天把握度趋势点（用于简单折线或↑↓）。

### 3.3 行动中心接口
- 执行队列：按“动作”展示（买/卖/调仓/放弃），并标注：
  - 执行日（next trading day）
  - 是否可执行（未到执行日则禁用）
  - 执行后状态（已处理/已放弃/已取消+原因）

### 3.4 兑现度（校准）概览接口
- 返回把握度分段（例如 0.5~0.6、0.6~0.7…）：
  - 历史命中率（hit_50pct）
  - 样本量 n
- 前端用业务语言展示：“把握度 70% 的历史兑现度约 X%，样本 n=Y”。

## 4. 前端信息架构（3 块固定区）

### 4.1 观察池（按概念）
- 列表：人气概念 TopN
- 每项：热度、风险灯、趋势（近 7 日）、可跟踪标的数量、把握度上升数量
- 点击进入概念详情

### 4.2 概念详情（分层锁定）
- 三列：龙头/中军/跟随
- 每只股票：把握度(%)、风险灯、状态（观察/接近买点/待执行/持仓/离场预警）、一句话原因、建议动作按钮（若可执行）

### 4.3 行动中心（执行队列）
- 只保留动作：买入/卖出/调仓（拆为卖多少+买多少）/放弃
- autopilot 只影响“动作是否自动提交”，展示结构不变

## 5. 验收标准（第一版）
- 任意股票在概念详情中可看到连续的“把握度(%)”与状态变化（至少近 7 日）。
- 执行队列动作与成交口径一致：信号日生成、次交易日 open 执行；未到执行日不可执行。
- 兑现度概览可查询并展示：每个把握度段有命中率与样本量。
- 全流程不要求用户理解 raw_score/阈值/窗口等术语。

