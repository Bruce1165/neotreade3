# Chaos Rulebook（混沌模型规则手册，SSOT）
Date: 2026-07-20

本文件定义 NeoTrade3 的混沌模型（Chaos Model）作为全链路的唯一判定标准（SSOT: Single Source of Truth）。M1–M6 的闭环结构不变，但每一层的“判断语义”必须收敛为对阴阳序列及其历史沿革的统一读出；其它形态/筛选器/评分只能作为证据输入（evidence / factor）进入因子矩阵，不得形成第二套动作语义。

本文件是 `docs/architecture/lowfreq_v16_model_rulebook.md` 的体系升级版；LowFreq V16 的旧口径（wave_phase / pattern / certainty_score 等）在后续将被标记为冻结并退出主链路。

---

## 1. 核心原则与硬约束

### 1.1 SSOT：混沌阴阳序列

混沌模型的每日核心输出：

- `yin_value`
- `yang_value`
- `net_energy = yang_value - yin_value`

所有可执行动作（入池、入场、持有、离场、降级观察）必须由对上述序列（以及其派生状态，如 regime_anchor/flip_rate/速度/加速度）的统一读出产生。

### 1.2 正向性（No-lookahead）

- M3 在线决策只允许使用 `target_date` 当日及历史数据（`trade_date <= target_date`）。
- 任何使用未来窗口真值的逻辑只能存在于 M4/M5 的评估与治理层，且不得回灌为在线输入。

### 1.3 Fail-closed

当关键数据不足以形成可复算的混沌输出时：

- `chaos_status` 必须为 `pending`
- `yin_value/yang_value/net_energy` 必须清零
- 不得产生任何入场/离场等硬动作

### 1.4 连续性（阴阳刻度统一）

- 阴阳的计算刻度在全阶段必须一致，不得按阶段切换权重/口径。
- 阈值、权重、分桶等调整只允许通过 M5 治理版本推进，不得在同一版本内“边跑边改”。

---

## 2. 关键对象与字段契约

### 2.1 日度快照（Daily Snapshot）

混沌模型对每个 `(code, trade_date)` 输出一条日度快照（落盘于 `chaos_daily_snapshot`，实现证据见 store 相关模块）：

- `chaos_status`：`ready|pending`
- `yin_value/yang_value/net_energy`
- `yin_yang_ratio`：可选派生（用于诊断与解释）
- `self_history_reference_json`：只依赖自身历史的引用摘要（用于“历史沿革”读出）
- `raw_factors_json`：当日原始因子（必须可对齐 EAV）
- `evidence_json`：可审计证据束（必须可追溯到事实层）

实现证据（已存在）：

- [store.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/store.py)
- [chaos_model_v0.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/chaos_model_v0.py)

### 2.2 Regime Anchor 与翻转率

本 rulebook 允许把形态语言（杯柄/老鸭头等）用于解释与复盘，但动作决策只承认以下“混沌序列语言”的对象：

- `regime_anchor`：趋势级“阴→阳”翻转确认的锚点（日期 + 证据）
- `flip_rate`：窗口内阴阳主导权翻转频率（用于识别“高频互换/噪声化”）
- `yang_speed` / `yin_speed`：阳/阴变化速度及其加速度（用于识别“消耗提速/加速度恶化”）

注：上述字段如何在 JSON 中承载、如何落盘、以及每个字段的 fail-closed 规则，必须通过契约条目注册（见第 5 节）。

### 2.3 阴阳值怎么算（v1 初始版，口径冻结）

这一步就是把“事实数据”翻译成“阴阳力量”。为了让人用日常语言也能读懂，这里用三个直觉解释：

- 阳：市场在“推你往上走”的力量
- 阴：市场在“把你往下拽”的力量
- 净能量：今天到底是“推的多”还是“拽的多”

v1 初始版不再把阴阳说成一个抽象黑箱，而是明确为“多个因子贡献的合力”。每个因子都会产生一个贡献值（可以是正也可以是负）：

- 贡献值 > 0：记到阳（yang_contrib）
- 贡献值 < 0：记到阴（yin_contrib，取绝对值）
- `yang_value = Σ(max(0, contrib_i))`
- `yin_value = Σ(max(0, -contrib_i))`
- `net_energy = yang_value - yin_value`

这套拆分规则的好处是：你不用强迫一个因子“永远是阳或永远是阴”；同一个东西在不同情境下可以“转性”（例如涨跌幅正负切换），但最终仍能被拆成阴阳两股力。

证据边界（现状）：

- 当前线上实现是把 `net_energy_adjusted` 直接做正负拆分（见 [chaos_model_v0.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/chaos_model_v0.py#L221-L226)），尚未升级到“按因子贡献逐项求和”的实现。
- 本节定义的是 v1 的冻结口径；代码侧切换必须通过 M5 治理版本推进并补齐测试。

### 2.4 v1 因子清单、阴阳属性与初始权重（口径冻结）

你要求“技术面、资金面、综合面只要能拿到的信息就尽量用上”，这里把 v1 的因子清单按三大层面冻结下来，并明确每个因子的阴阳属性与初始权重。写法尽量用日常语言：每个因子都回答三个问题——它在说什么、它算出来是什么数、它算阳还是算阴。

分类规则（冻结）：

- 技术面 / 资金人气 / 综合面 = 3 : 4 : 3（分类倍率，来自设计稿 [chaos-model-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-20-chaos-model-design.md#L115-L134)）
- 每个因子还会有自己的 `factor_weight`（初始值见 v1 registry）

阴阳属性（冻结）：

- `yang`：数越大越“推你向上”，直接加到阳
- `yin`：数越大越“把你往下拽”，直接加到阴
- `signed`：它自己带方向（正是阳、负是阴），按正负拆分
- `neutral`：它不直接记阴阳（通常是放大器/诊断项），先落盘等治理决定如何消费

v1 registry（配置文件）：

- [chaos_factor_registry_v1.json](file:///Users/mac/NeoTrade3/config/chaos/chaos_factor_registry_v1.json)

#### 2.4.1 技术面（3）

1) `pct_change`（当日涨跌幅，带方向，signed）

- 人话：涨了就是加阳，跌了就是加阴
- 数据：`daily_prices.pct_change`

2) `resonance_score`（共振评分，yang）

- 人话：技术形态是不是“顺”，越顺越加阳
- 数据：`resonance_scorer.calculate_technical_score()`（见 [factor_contract.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_contract.py#L152-L160)）

3) `sector_rps_120`（板块相对强度，yang）

- 人话：你所在板块是不是在“持续更强”，越强越加阳
- 数据：`sector_rotation.analyze() → rps_120`（见 [factor_contract.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_contract.py#L179-L187) 与 [factor_matrix.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_matrix.py#L985-L992)）

#### 2.4.2 资金人气面（4）

1) `amount`（成交额，yang）

- 人话：今天资金关注度，越大越“有钱/有人气”
- 数据：`daily_prices.amount`（见 [factor_contract.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_contract.py#L60-L67)）

2) `amount_rank`（成交额排名，yin）

- 人话：排名越靠后，说明今天资金关注度越弱，按“阴”处理
- 数据：`daily_prices.amount` 排序得到（见 [factor_contract.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_contract.py#L69-L76)）

3) `volume_ratio_20d`（量比 20 日，neutral）

- 人话：这是“力度放大器”，不决定涨跌方向，但能说明涨跌的真假
- 数据：`volume / avg_volume_20d`（当前 v0 已计算并写入 raw_factors，见 [chaos_model_v0.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/chaos_model_v0.py#L179-L183)）

4) 板块资金与板块涨跌（按你要求纳入）

- `sector_total_amount_today`（板块今日成交额，yang）
- `sector_amount_ratio_today_over_avg20`（板块今日成交额 / 20 日均值，yang）
- `sector_avg_pct_today`（板块今日平均涨跌，signed）
- `sector_avg_pct_20d`（板块近 20 日平均涨跌，signed）
- 数据证据：来自板块繁荣度产物的 `evidence.capital_proxy` 与 `evidence.market_proxy`（见 [sector_prosperity.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/sector_prosperity.py#L185-L241)）

#### 2.4.3 综合面（3）

这里的“综合”不是指“把所有东西都再算一遍”，而是指：估值/机构配置/研究关注这类更慢、更像“底层条件”的东西。

1) 估值三件套（已在系统其它模块出现，纳入混沌）

- `pe_ratio`（yin）：越贵越阴
- `pb_ratio`（yin）：越贵越阴
- `roe`（yang）：越能赚钱越阳
- 数据证据：见 [factor_matrix.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_matrix.py#L739-L760) 与 [factor_contract.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_contract.py#L96-L122)

2) ETF / 指数 / 基金配置证据（按你要求纳入 ETF 相关数据）

这部分不是“ETF 自己的价格涨跌”，而是“这只股票有没有被 ETF/指数/机构配置”，属于资金/结构性证据。

- `holder_etf_count`（yang）：有多少只 ETF 持有这只股票
- `holder_fund_count`（yang）：有多少只基金持有这只股票
- `index_count`（yang）：进入了多少个指数成分
- `config_score`（yang）：综合打分（0–5）
- 数据证据：都来自 [market_focus_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/market_focus_snapshot.py#L260-L420)

3) 事实事件（消息类：你选择“只做事实事件”）

v1 不做“利好/利空情绪打分”，只做能落成数字、可复算的事实代理：

- `attention_score`（yang，0–4）：研究关注综合分
- `research_inst`（yang）：近 90 天出研报的机构数
- `consensus_orgs`（yang）：一致预期/盈利预测参与机构数
- `survey_orgs`（yang）：近 180 天调研机构数
- `survey_count`（yang）：近 180 天调研次数
- 数据证据：同样来自 [market_focus_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/market_focus_snapshot.py#L325-L420)，其底层表是 `research_reports / report_consensus / institutional_surveys`

#### 2.4.4 风向与逆风（阴因子，来自 v0 扣分常量）

这类因子人话就是一句：外部环境在“顶着你”。只要发生，就给阴加分。

权重来源是 v0 里对 `net_adj` 的扣分常量，但在 v1 registry 里把“方向”改成阴因子（权重取绝对值）。为保证可复算与可治理，v1 对其中一部分采用“纯日线事实代理口径”（不依赖外部接口、不依赖持仓上下文）。

市场逆风（market_*，代理口径）：

- `market_breadth_weak`：全市场下跌家数占比 `market_down_ratio > 0.6` 记 1，否则 0
- `market_price_trend_weak`：全市场 20 日均值为负且当日为负：`market_avg_pct_20d < 0 and market_avg_pct_today < 0` 记 1，否则 0
- `market_drawdown_weak`：全市场大幅走弱日：`market_down_ratio > 0.75 and market_avg_pct_today < -1.0` 记 1，否则 0

板块逆风（sector_*，代理口径）：

- `sector_cooldown_detected`：板块成交额降温且当日走弱：`sector_amount_ratio_today_over_avg20 < 0.8 and sector_avg_pct_today < 0` 记 1，否则 0
- `sector_trend_deteriorating`：板块近 20 日平均涨跌为负：`sector_avg_pct_20d < 0` 记 1，否则 0
- `sector_leader_rollover`：板块相对强度偏弱且当日走弱：`sector_rps_120 < 40 and sector_avg_pct_today < 0` 记 1，否则 0

见顶风险（hazard_*，结构化事实）：

- `hazard_score_5d_high`：当 hazard 模块输出 ready 且 `stock_top_risk_5d >= 70` 时记 1，否则 0

趋势衰竭（trend_exhaustion_*）：

- 这两项需要持仓上下文（买入价/峰值/持有天数），不适合作为“纯日度快照因子”。v1 中默认权重为 0，后续作为 M3 持有期因子启用（见 RB.M3.CHAOS.HOLD_FACTORS_V1.001）。

#### 2.4.5 v1 的 net_energy（如何把三层面合成）

日常理解：

- 技术面给你“形态顺不顺”
- 资金人气给你“有没有人推”
- 综合面给你“底层条件稳不稳”
- 逆风给你“外部在不在顶着你”

投影规则（冻结，来自设计稿）：

- `yang_value = Σ (category_multiplier(category) * factor_weight(factor) * norm(factor_value))` 对所有阳因子求和
- `yin_value = Σ (category_multiplier(category) * factor_weight(factor) * norm(factor_value))` 对所有阴因子求和
- `net_energy = yang_value - yin_value`

设计证据：[chaos-model-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-20-chaos-model-design.md#L115-L134)

边界说明（现状）：

- v1 的投影求和已实现并接入日度落盘：当 `registry-id=v1` 时，`yin_value/yang_value/net_energy` 由 v1 registry + 3:4:3 倍率投影生成（见 [projection_v1.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/projection_v1.py) 与 [build_chaos_daily_snapshot.py](file:///Users/mac/NeoTrade3/scripts/build_chaos_daily_snapshot.py)）。

#### 2.4.6 registry / matrix（EAV）应该如何体现 v1

v1 的硬要求是：上面列出的因子必须都能：

- 出现在 `raw_factors_json`
- 被拆解写入 EAV：`chaos_factor_values(code, trade_date, factor_id, factor_value, registry_version)`

落盘结构证据：

- registry 结构与 loader：[registry.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/registry.py)
- EAV + snapshot schema：[store.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/store.py#L21-L75)

边界说明（现状）：

- 当前 registry 文件 [chaos_factor_registry_v0.json](file:///Users/mac/NeoTrade3/config/chaos/chaos_factor_registry_v0.json) 的 `yin_or_yang` 仍是 `unassigned`，且 B 类逆风项还没有进入 registry/raw_factors/EAV；因此这部分属于 v1 的“口径冻结 + 待实现切换”。

---

## 3. M1–M6 分层语义（闭环不变，逻辑收敛为阴阳）

### 3.1 M1：事实层（Fact Layer）

职责：

- 事实接入、派生事实与质量证明（供阴阳计算消费）
- 形成可复算的事实输入：价格、成交量/额、人气/资金、ETF 份额等（以实际接入为准）

输出要求：

- 必须能支持“按日复算”与“可审计证据束”落盘
- 必须提供数据质量状态以驱动 fail-closed

### 3.2 M2：周期识别与确定性（用阴阳实现）

职责（目标态）：

- 使用混沌序列（及其派生）进行周期识别与确定性判断
- 输出 M3 可直接消费的“状态更新依据”（不再输出旧口径 wave_phase / pattern / certainty_score）

输出（建议命名，后续可在治理中冻结）：

- `chaos_m2_status`：`ready|pending`
- `chaos_cycle_state`：周期阶段（必须由阴阳关系读出，不得由形态枚举）
- `chaos_certainty`：确定性读出（可为 0–100 或分桶等级，但必须可解释、可复算）
- `m2_evidence_bundle`：证据束（必须能落入 EAV / evidence_json）

当前实现边界（可核验）：

- M2 全面以阴阳替换旧口径：尚未在代码中宣告为 implemented（需要在契约注册表中新增条目并补齐证据）。

### 3.3 M3：决策引擎（只消费阴阳）

职责（目标态）：

- 跟踪池状态机的更新依据只允许来自混沌序列读出与 M2 的阴阳结论
- 入场/持有/离场动作只允许由混沌通用读出产生

输出要求：

- `chaos_snapshot`：必须进入决策审计链路（已存在实现证据，见第 5 节）

### 3.4 M4：评估监测（只做评估，不回灌）

职责：

- 对混沌序列输出的可解释性与有效性进行后验评估（例如 5D/10D 方向命中率、平均收益）
- 评估产物只进入治理链路，不得作为在线输入

实现证据（已存在）：

- [m4_eval_monitor.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/m4_eval_monitor.py)
- [run_chaos_m4_eval_monitor.py](file:///Users/mac/NeoTrade3/scripts/run_chaos_m4_eval_monitor.py)

#### 3.4.1 M4 验收门槛（Gate-v1，科学口径）

目标：让 M4 不再只回答“单点方向猜对了吗”，而是回答“按阴阳平衡关系读出的方向，是否在收益上有区分度”，且对中期稳健性不产生退化。

评估对象：

- `accuracy_direction`：方向命中率（仍保留，但不再是唯一指标）
- `avg_return_pred_up / avg_return_pred_down`：按预测方向分组的平均收益
- `return_spread = avg_return_pred_up - avg_return_pred_down`：方向分组收益差（可理解为“信号是否真的把未来收益分开了”）

Gate-v1 的默认验收方式（冻结）：

- **约束（10D）**：候选信号的
  - `accuracy_direction_10d >= accuracy_direction_10d(point_baseline)`
  - `return_spread_10d >= return_spread_10d(point_baseline)`（仅当 10D 的 spread 在 baseline 与 candidate 两侧都“有效”时）
- **主目标（5D）**：在满足 10D 约束前提下，优先最大化
  - `accuracy_direction_5d`
  - 若 5D 命中率相近，则再最大化 `return_spread_5d`

边界与注意事项（冻结）：

- `return_spread` 是否“有效”必须满足**比例阀值**：设 `r` 为最小组占比阀值（默认 `r=0.1`），对某个 horizon：
  - `min_group_count = ceil(evaluable * r)`
  - 当且仅当 `pred_up_count >= min_group_count 且 pred_down_count >= min_group_count` 时，才认为该 horizon 的 spread 可作为强约束/强目标使用；否则该 horizon 的 spread 只能记录，不得作为硬约束。
- rolling 稳健性必须作为 Gate-v1 的配套复核：对 20 个窗口（20D，步长 1D）输出 per-window 指标与总体均值，不允许只看单一时间段。
- rolling 复核必须输出**窗口级 gate 统计**（默认对 10D 做约束统计）：
  - `10d_accuracy_not_decrease_vs_point`：该窗口内 10D 命中率是否不低于 point baseline
  - `10d_spread_not_decrease_vs_point`：当且仅当 baseline 与 candidate 两侧的 10D spread 都“有效”时，才计算并作为约束；否则该窗口该约束视为不适用（仅记录）
  - `10d_gate_pass`：10D 命中率约束通过且（若适用）10D spread 约束通过

### 3.5 M5：治理（版本化阈值/权重/门禁）

职责：

- 将 M4 评估证据转化为版本化的阈值、权重与门禁参数（不得“边跑边改”）
- 输出治理记录并绑定 evidence

设计证据（已存在）：

- [2026-07-20-chaos-model-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-20-chaos-model-design.md)
- [2026-07-20-chaos-model-implementation-plan.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-20-chaos-model-implementation-plan.md)

### 3.6 M6：交付与解释

职责：

- 报告与可视化必须只消费已注册字段，不得发明语义
- 形态叙事只作为解释模板，不得成为动作规则

---

## 4. 数据落盘与可复算性（EAV 对齐）

约束：

- 每一条 `ready` 的日度快照必须能在 EAV 因子表中找到对齐行（同 code/date/registry_version）
- 快照中的 `raw_factors_json` 必须可被拆解为 EAV（registry + factor_id 对齐）

实现证据（已存在）：

- [registry.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/registry.py)
- [store.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/store.py)
- [operational_gates.py](file:///Users/mac/NeoTrade3/neotrade3/chaos/operational_gates.py)

---

## 5. 契约注册（可机器验收）

本节用于声明哪些条目已实现、哪些是计划中的目标态。状态含义与 `lowfreq_v16_model_rulebook.md` 的注册表规则一致。

- `RB.M3.CHAOS.SNAPSHOT.001` status=implemented evidence=neotrade3/decision_engine/chaos_model_v0.py,tests/unit/test_chaos_model_v0.py,tests/unit/test_position_contract_snapshot_chaos_field.py
- `RB.M3.CHAOS.PROJECTION_V1.001` status=implemented evidence=neotrade3/chaos/projection_v1.py,tests/unit/test_chaos_projection_v1.py,scripts/build_chaos_daily_snapshot.py
- `RB.M4.CHAOS.EVAL_MONITOR.001` status=implemented evidence=neotrade3/chaos/m4_eval_monitor.py,scripts/run_chaos_m4_eval_monitor.py,tests/unit/test_chaos_m4_eval_monitor.py
- `RB.M4.CHAOS.EVAL_GATE_V1.001` status=implemented evidence=docs/architecture/chaos_rulebook.md,neotrade3/chaos/m4_eval_monitor.py,scripts/run_chaos_m4_gate_v1_sweep.py
- `RB.M4.CHAOS.EVAL_ROLLING.001` status=implemented evidence=scripts/run_chaos_m4_eval_monitor_rolling.py
- `RB.M5.CHAOS.GOVERNANCE.001` status=planned evidence=docs/superpowers/specs/2026-07-20-chaos-model-design.md

待补齐（本次升级后需要新增/重写并绑定证据）：

- `RB.M2.CHAOS.CYCLE.001` status=planned evidence=docs/architecture/chaos_rulebook.md
- `RB.M2.CHAOS.CERTAINTY.001` status=planned evidence=docs/architecture/chaos_rulebook.md
- `RB.M3.CHAOS.FACTOR_REGISTRY_V1.001` status=planned evidence=docs/architecture/chaos_rulebook.md
- `RB.M3.CHAOS.HOLD_FACTORS_V1.001` status=planned evidence=docs/architecture/chaos_rulebook.md
