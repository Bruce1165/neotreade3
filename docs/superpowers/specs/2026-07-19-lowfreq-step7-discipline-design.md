# LowFreq v16 Step7（低频纪律）设计说明
Date: 2026-07-19

## 1. 背景与问题

LowFreq v16 的目标不是高频刷单式交易，而是以“有确定机会才操作”为纪律约束，避免在候选与持仓链路里产生过量的交易冲动与噪音波动。

Step7 用于把“低频纪律”从口头原则固化为可审计、可复算的输出对象，并在进入执行前提供 fail-closed 的 guard verdict。

## 2. 目标与非目标

### 2.1 目标

- 定义 Step7 的三类输出契约（RB ids）：
  - `trade_discipline_metrics`（指标）
  - `discipline_guard_verdict`（守门判定）
  - `discipline_audit_event`（审计事件）
- 明确 fail-closed：
  - 当必要输入缺失导致指标不可计算时，guard 必须返回 block
  - block 必须给出可复核的 reason 与 evidence_key

### 2.2 非目标

- Step7 不定义具体交易规则（选股、入场、出场），仅约束“交易频率/节奏/冲动控制”维度
- Step7 不直接修改 Step1–Step6 的业务语义，仅对“是否允许触发新增交易动作”给出守门 verdict

## 3. 输入（约束性描述）

Step7 的实现需要读取“当日决策链路已经生成”的最小审计信息。该输入来源在实现落地前不做强绑定，只约束为以下类别信息可被提取：

- 当日 asof_date
- 当日计划交易动作（例如 buy/sell/hold 的候选动作集合或摘要）
- 当前持仓数量与当日新增/减少数量（或同等可复核口径）
- 近期窗口内的交易次数统计所需的历史审计数据（或同等数据源）

## 4. 输出契约（RB.*）

### 4.1 `trade_discipline_metrics`（RB.M3.STEP7.TRADE_DISCIPLINE_METRICS.001）

建议输出对象：

- `asof_date`: `YYYY-MM-DD`
- `window_days`: `int`
- `open_positions`: `int`
- `planned_entries_today`: `int`
- `planned_exits_today`: `int`
- `executed_trades_window`: `int`
- `entry_churn_ratio_window`: `float | null`
- `metrics_status`: `"ready" | "pending"`
- `pending_reason`: `str | null`

约束：

- `metrics_status="pending"` 表示输入不足或统计口径缺失；此时不得基于猜测生成指标数值
- `entry_churn_ratio_window` 仅在分母可复核时才允许输出；否则必须为 null 且 `metrics_status="pending"`

### 4.2 `discipline_guard_verdict`（RB.M3.STEP7.DISCIPLINE_GUARD.001）

建议输出对象：

- `status`: `"pass" | "block"`
- `policy_id`: `str`
- `block_reason_code`: `str | null`
- `block_reason`: `str | null`
- `evidence_keys`: `list[str]`
- `asof_date`: `YYYY-MM-DD`

fail-closed 规则：

- 若 `trade_discipline_metrics.metrics_status="pending"`，则 `status` 必须为 `"block"`
- 若 `status="block"`：
  - `block_reason_code` 与 `block_reason` 必须非空
  - `evidence_keys` 必须包含可复核的关键字段名（例如 `metrics_status`、`executed_trades_window`）

### 4.3 `discipline_audit_event`（RB.M3.STEP7.DISCIPLINE_AUDIT.001）

建议输出对象：

- `event_type`: `"trade_discipline_guard"`
- `asof_date`: `YYYY-MM-DD`
- `policy_id`: `str`
- `guard_verdict`: `discipline_guard_verdict`
- `metrics`: `trade_discipline_metrics`

约束：

- 该事件用于“解释为什么当天没有/减少交易”，必须可落盘并支持离线归因复算
- 该事件不得引入未来信息

## 5. 与主链的关系（定位）

- Step7 位于 Step6（risk_action/stop_loss）之后、执行前
- Step7 的输出属于 M3 守门与审计范畴：
  - 不改写已有选股/风险语义
  - 只对“当日是否允许触发新增交易动作”给出 block/pass

## 6. 校验与测试（后续实现要求）

实现落地时至少需要：

- 单测锁定 fail-closed：
  - 当输入不足导致 metrics pending 时必须 block
- 单测锁定审计对象可序列化：
  - `discipline_audit_event` 结构稳定，字段齐全
