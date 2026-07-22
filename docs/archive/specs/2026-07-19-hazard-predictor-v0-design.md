# Hazard Predictor v0（T2）设计说明
Date: 2026-07-19

## 1. 背景与问题

当前我们已完成 `stock_top_hazard_labels_t2` 全历史回填。该表的 `hit` 是监督标签（以 obs_date 之后的未来窗口判定），用于校准与评估，不能直接用于严格 no-lookahead 的日常决策与回测主链。

为了让 hazard 真正服务于每日交易，必须落地一个只使用 target_date 当日及历史信息即可计算的在线 hazard 预测器（v0），并将其接入 M3 的持有期滤噪与审计链路。

## 2. 目标与非目标

### 2.1 目标

- 提供一个 **在线 hazard predictor v0（T2）**：
  - 输入：`(code, target_date)` 与历史日线序列
  - 输出：`stock_top_risk_5d/20d`（0–100 分制）与 `risk_status`（ready/pending），并携带 evidence
  - 约束：严格 no-lookahead（不得读取 target_date 之后任何数据）
- 将 v0 接入 M3：
  - 仅影响 `hold_noise_filter_state` 的 stage/level/reasons/evidence/warning_flags
  - v0 默认不直接触发 `risk_action=exit`，不注入 sell_payload
- 输出可审计：
  - 在 position contract snapshot / audit payload 中落下 hazard 对象，支持离线归因与复算

### 2.2 非目标（v0 不做）

- 不使用 `stock_top_hazard_labels_t2.hit` 直接触发退出
- 不引入 ML/监督学习模型
- 不定义 risk-off（系统性砸盘）机制

## 3. 定义与语义

### 3.1 risk_status

- `pending`：历史不足导致无法计算（例如不足 K=15，无法判定加速段）。必须 fail-closed：
  - 不允许把 pending 当作高风险
  - 不允许触发退出
- `ready`：历史充足，可以计算 risk_score（仅用历史）。

### 3.2 hazard_score（0–100）与 hazard_state（状态机）

v0 拆分为两类输出，避免“事后状态”污染“事前预测”：

- hazard_score：规则预测分（0–100），用于提前预警（对齐未来 N 日 hit 的可预测部分），不是概率。
- hazard_state：在线状态机，用于表达截至 target_date 的已发生状态（break_armed/stale/recovering 等），用于当下处置与审计，不要求对齐未来 hit。

两个 horizon 分别输出：

- `stock_top_risk_5d`：hazard_score_5d（短紧迫度，提前预警分）
- `stock_top_risk_20d`：hazard_score_20d（中紧迫度，提前预警分）

## 4. v0 规则预测器（T2-online）设计

### 4.1 设计原则

- 分解监督定义与在线可观测状态：监督标签用“未来确认窗口”定义事件，在线预测器用“截至今日的状态机”逼近紧迫度。
- 明确阶段：加速（accel）→ 破坏（break）→ 修复进展（recovery progress）→ 长时间未修复（stale）。

### 4.2 状态机（只看历史）

参数与 rulebook T2 保持一致：

- K=15（加速窗口）、阈值=30%
- 破坏信号：当日跌幅 <= -7%
- 修复参考线：破坏日前 5 日最高价
- 观测窗：10 个交易日（在线不做“失败确认”的未来判定，只做“已过去多少天仍未修复”的状态更新）

在线状态（hazard_state，示意）：

- `not_ready`：历史不足
- `neutral`：无加速、无破坏
- `accel_only`：满足加速但未破坏
- `break_armed`：满足加速且出现破坏（触发日作为 first_event_date）
- `recovering`：破坏后已发生修复（高点突破参考线）
- `stale_break`：破坏后已过去多日仍未修复（紧迫度提高）

### 4.3 分数映射（hazard_score，0–100，v0）

v0 采用简单、可解释的映射（可在 M5 通过评估再调整）：

- `not_ready`：pending
- `neutral`：0–10
- `accel_only`：20–40（可按 accel_return 的强弱线性拉伸）
- `break_armed/stale_break/recovering`：hazard_state 负责表达当下处置状态；hazard_score 不抬高（避免把“已发生”当作“未来将发生”）

两个 horizon 的差异：

- 5d 更敏感（break_armed / stale_break 权重更高）
- 20d 更平滑（accel_only 权重更高，stale_break 上升更慢）

## 5. M3 集成设计（v0）

### 5.1 集成点

- 在 lowfreq engine 的持仓日更链路中，对每个持仓标的计算 hazard v0，并输出到 position contract snapshot。
- 不改动 `check_sell_signal_v2` 的硬退出链（v0 不注入 sell_payload）。

### 5.2 输出字段形态（建议）

在 position contract snapshot 增加字段：

- `hazard_snapshot`（object 或 null）：
  - `risk_status`：ready/pending
  - `hazard_state`：not_ready/neutral/accel_only/break_armed/stale_break/recovering
  - `stock_top_risk_5d`：0–100（int）
  - `stock_top_risk_20d`：0–100（int）
  - `first_event_date`：首次进入 break_armed 的日期（如有）
  - `evidence`：简短证据列表（如 “accel_15d>=30%”, “break_day<=-7%”, “recovered_by_prebreak_5d_high”）

### 5.3 对持有期滤噪的影响

若 `risk_status=ready` 且 risk_score 达到门槛（门槛在 rulebook 中定义）：

- 上调 `hold_noise_filter_state.stage` 与 `level`
- 将 hazard evidence 合并进 `hold_noise_filter_state.evidence/warning_flags`

## 6. 校验与测试

- 单测覆盖三类：
  - pending（历史不足）
  - ready + neutral/accel_only
  - ready + break_armed + stale_break + recovering
- 最小一致性验证：
  - risk_status 不得因未来数据而变化（同一 target_date 重跑必须一致）
  - v0 不得修改退出主链输出（不影响 sell_payload 触发）

## 7. 后续演进（非 v0）

- 使用 `stock_top_hazard_labels_t2` 作为监督真值，对 v0 的 risk_score 做校准（分桶/等频或简单回归）。
- 在“误杀率可控 + 可解释性完整”的前提下，再把 hazard 提升为可触发 exit_signal 的退出链之一（需要显式规则与审计字段）。
