# Lowfreq Engine Six-Layer Accounting Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-engine-six-layer-accounting-design.md`

## 1. Goal

本计划不是立即重写 `lowfreq_engine_v16_advanced.py`，而是定义如何基于已批准的六层账本，安全推进后续第一阶段重组准备与分段实施。

本计划有四个目标：

1. 把“认账结果”转成可执行的重组顺序。
2. 先保护 `M3 nucleus`，避免重组时拆散运行时状态机。
3. 明确邻层责任的推荐剥离顺序与每阶段边界。
4. 为后续每一刀 implementation 建立统一的验证标准，避免“拆完才发现语义漂移”。

本计划不在本轮直接完成：

- `lowfreq_engine_v16_advanced.py` 代码迁移
- 新文件树一次性落地
- `M2/M3` 行为重写
- `M4/M5` benchmark / governance 正式实现
- API、scripts、frontend 的同步改造

## 2. Current Starting Point

根据已批准设计，当前低频 engine 的账本已经明确：

- `M1`
  - 正式 owner 已在 `neotrade3/data_control`
  - engine 内主要表现为 formal 输入消费适配
- `M2`
  - 正式 owner 已有 `neotrade3/cycle_intelligence`
  - engine 内仍保留大量 legacy recognition logic
- `M3`
  - 是当前文件的主体 owner
  - `TradeRecord / SellSignal / LayerContract / tracking / execution / exit / run_backtest` 构成 `M3 nucleus`
- `M4/M5`
  - 当前主要以 evidence feed 形式存在
- `M6`
  - 已明确混入 CLI / JSON 落盘 / 结果交付职责

关键前提：

- 认账优先级不等于执行顺序
- 语义上最需要先认清的是 `M2 / M1 / formal front` 邻层区
- 实施上最适合先动手的，不一定是语义上最“错层”的区域

## 3. Execution Principles

- 先保护 `M3 nucleus`，再剥离邻层责任。
- 一次只处理一个层边界，不在同一轮同时迁移多个 ownership。
- 先做低风险、边界清晰的剥离，再做高风险识别逻辑迁移。
- 所有迁移都必须遵循：
  - 不新增消费者层语义 owner
  - 不把 formal 承载包重新堆回 engine
  - 不让 API / frontend / scripts 反向定义模型语义
- 所有阶段都必须保留可比对输出，至少能比较：
  - `all_trades`
  - `daily_values_net`
  - `daily_values_gross`
  - `buy_signal_audit`
  - `sell_signal_audit`
  - `config_snapshot`

## 4. Accounting Priority vs Execution Order

### 4.1 Accounting Priority

按语义扭曲程度，最需要优先认账的是：

1. `M2 legacy recognition zone`
2. `M1 formal input adapters`
3. `formal front` 装配接线区
4. `M6 delivery mixin`

原因：

- 前三者最容易让后续重组错误地把 engine 继续当作“全层 owner”
- `M6` 越层虽然明确，但不会像 `M1/M2` 那样持续污染模型 ownership 判断

### 4.2 Recommended Execution Order

按实际改造风险，建议顺序是：

1. `E0`：冻结 `M3 nucleus` 边界
2. `E1`：先拆 `M6 delivery mixin`
3. `E2`：再拆 `M1 formal input adapters`
4. `E3`：再拆 `formal front` 装配接线区
5. `E4`：最后处理 `M2 legacy recognition zone`

原因：

- `M6` 的 ownership 最清晰、风险最低，适合作为第一刀建立重组节奏
- `M1 adapter` 比 `M2 recognition` 风险低，因为它更多是接线与事实消费，而不是识别语义本体
- `formal front` 接线区需要在 `M1 adapter` 澄清后再处理，避免两层适配叠在一起
- `M2 recognition` 风险最高，应放在最后，且只能在 `M3 nucleus` 已被保护之后推进

## 5. Recommended Phases

### E0：冻结 `M3 nucleus`

目标：

- 在任何代码迁移前，先把绝对不能被误拆的 `M3` 主核明确成正式保护名单。

任务：

- 冻结 `M3 nucleus` 名单：
  - `TradeRecord`
  - `SellSignal`
  - `LayerContract`
  - `_tracking_snapshot_from_signal()`
  - `_decorate_signal_with_phase1_contracts()`
  - `_record_tracking_candidate_events()`
  - `_execution_signal_gate_snapshot()`
  - `_elite_execution_candidate_snapshot()`
  - `check_sell_signal_v2()`
  - `run_backtest()` 中 runtime decision / execution 推进段
- 为每个 `M3 nucleus` 对象补一行说明：
  - 当前 owner
  - 上游依赖
  - 下游消费者
  - 本阶段不允许迁移理由
- 明确禁止事项：
  - 不能在第一刀把 `run_backtest()` 整体拆散
  - 不能先移动 `TradeRecord`
  - 不能同时改 `tracking / execution / exit`

完成判定：

- 后续任何实现计划都能引用同一份 `M3 nucleus` 保护名单
- 不会在第一刀 implementation 中误伤决策状态机中心

### E1：剥离 `M6 delivery mixin`

目标：

- 先把 CLI / JSON 落盘 / 纯交付组织从 engine 主体语义中分离出来，建立低风险分层拆分范式。

建议边界：

- `_calc_metrics()` 中偏交付/展示的组织段
- `main()`
- JSON 输出与文件落盘
- 只服务于 CLI/结果展示的 summary 组织逻辑

边界约束：

- 不改 `M3` 决策逻辑
- 不改 `M4/M5` 证据字段语义
- 不改变 backtest 返回结构中的正式字段名

完成判定：

- engine 主体不再直接拥有 CLI 交付职责
- 外部消费者仍能得到等价结果对象
- `all_trades / daily_values / audits / config_snapshot` 对比不漂移

### E2：剥离 `M1 formal input adapters`

目标：

- 把 engine 内“消费事实并组装 formal 输入底座”的职责认账到专门 adapter/gateway，而不继续混在策略决策主核中。

建议边界：

- `_get_formal_d1_facts_batch()`
- `_get_formal_security_master_batch()`
- `_build_formal_trading_day_status()`
- 与 recent price / fundamentals / security master 相关的 formal 输入 adapter

边界约束：

- 不能修改 `data_control` 的正式 owner 语义
- 不能在 adapter 层新增 `M3` 决策判断
- 不能顺带迁移 `M2` 识别逻辑

完成判定：

- facts / formal input 的消费入口被物理分离
- engine 内对应调用点只保留“读取 adapter 输出”的责任
- formal 输入与 `M3` 决策核的边界更清晰

### E3：剥离 `formal front` 装配接线区

目标：

- 把 engine 中“消费正式承载包并附着 payload”的接线职责单独认账，避免 formal owner 与 engine consumer 混淆。

建议边界：

- `_build_formal_front_chain_payload()`
- `_attach_formal_front_payloads()`

边界约束：

- 不能在此阶段重定义 `small_cycle / identify_state / tracking_state / entry_state`
- 不能让 engine 再次成为 formal object owner
- 不能顺带重写候选发现与 entry 规则

完成判定：

- engine 仍可消费 formal payload
- 但“formal owner 在哪里”和“engine 如何接线”被清晰分开

### E4：处理 `M2 legacy recognition zone`

目标：

- 最后再处理 engine 内最重的识别遗留逻辑，把它从 `M3` 主核中单独认账。

建议边界：

- `detect_wave_phase()`
- `_detect_wave_phase_from_series()`
- `check_weekly_duck_head()`
- `_structure_confirm()`
- `get_hot_sectors()`
- `detect_sector_cooldown()`
- 其他板块热度/结构识别 helper

边界约束：

- 不与 `tracking / execution / exit` 同轮混改
- 不在同一轮重写 scoring 哲学
- 不允许为了迁移 `M2` 而修改 `M3 nucleus` 的正式 owner

完成判定：

- engine 不再继续直接拥有高密度周期/结构识别语义
- `M2` 识别逻辑与 `M3` 决策推进分界清楚

## 6. Validation Strategy

### 6.1 Phase-Level Validation

每一阶段完成后，都至少检查三类结果：

1. 结构校验
   - 目标职责是否从 engine 主核中被单独认账
   - 是否有新的越层反弹
2. 行为校验
   - 对同一固定回测输入，核心输出对象是否保持语义稳定
3. 边界校验
   - 本阶段是否只改了计划内 ownership，不带入其他主题

### 6.2 Output Parity Baseline

每次 implementation 最少对比：

- `all_trades`
- `daily_values_net`
- `daily_values_gross`
- `buy_signal_audit`
- `sell_signal_audit`
- `config_snapshot`
- 如该阶段触及结果交付，再对比最终 JSON 结构

### 6.3 Testing Guidance

- 若阶段只涉及交付/接线层，优先用 focused regression 校验，不扩大为策略行为重写测试。
- 若阶段涉及 `M1 adapter / formal front / M2 recognition`，必须增加最小 contract regression，确保 owner 变了但语义没偷偷变。
- 在处理 `M2` 阶段前，必须确认前几轮已建立稳定的回归比较基线。

## 7. Commit Strategy

后续实现必须采用窄切片提交，每刀只处理一个 ownership 主题。

推荐提交顺序：

1. `M6 delivery extraction`
2. `M1 formal adapter extraction`
3. `formal front attachment isolation`
4. `M2 recognition extraction`

每刀提交必须满足：

- 只改一个层边界
- 不混入格式化噪音
- 不混入无关 contract 清理
- 先验证，再提交

## 8. First-Slice Recommendation

如果后续进入真正 implementation，第一刀推荐：

- `M6 delivery mixin`

推荐原因：

- ownership 最清晰
- 对 `M3 nucleus` 风险最低
- 能先建立“如何从 giant engine 中安全剥离邻层责任”的最小工作样板

明确不推荐作为第一刀：

- `M2 legacy recognition zone`

原因：

- 语义最复杂
- 与候选发现、评分、entry 推进耦合最深
- 在没有前几轮边界清理的情况下极易把识别变更和决策变更混在一起

## 9. Commit Boundary

本轮计划提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-engine-six-layer-accounting-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/*`
- `neotrade3/cycle_intelligence/*`
- `neotrade3/decision_engine/*`
- `apps/api/main.py`
- `scripts/*`
- `neotrade3-dashboard/*`
- 其他任何工作区改动
