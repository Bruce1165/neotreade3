# LowFreq V16 低频量化模型工作原理（规则手册）
Date: 2026-07-19

本文件描述 NeoTrade3 LowFreq V16 低频量化模型的工作原理与运行机制，包括：

- 顶层逻辑与筛选流程（模型如何筛选/甄别股票）
- 每一部分的职能、输入输出与实现方式（按 M1–M6 分层归属）
- 模型运行机制（跟踪池、入场、持有、离场、风控）
- 修正/更新机制（以 M4 评估 → M5 提案与治理 → 回到 M2/M3 调整 为主线）

如需审计具体实现，可在对应章节按需补充代码位置（文件/行号）。本文件以“工作原理与规则”作为长期参照标准。

重要说明（体系升级）：

- 本文件仍保留 M1–M6 与 Step1–8 的闭环结构描述，但“最终判定标准（SSOT）”已升级为混沌模型（阴阳序列）。
- 混沌模型的 SSOT 定义、硬约束与契约条目见 [chaos_rulebook.md](file:///Users/mac/NeoTrade3/docs/architecture/chaos_rulebook.md)。
- 本文件中旧口径（wave_phase / pattern / certainty_score 等）后续将被标记为冻结并退出主链路；在完成代码侧切换前，它们可作为历史遗留字段存在，但不得被视为最终动作语义。

---

## 1. 核心目标与边界

### 1.1 评估标尺与当前工作顺序

- 跟踪池质量：反映模型“筛选/甄别逻辑”的水平高低，是评估标尺之一。
- 入场/离场择时：反映模型“执行/择时能力”的水平高低，是评估标尺之一。
- 两条标尺不存在绝对意义上的第一/第二重要。
- 当前工作顺序：先把未来可能大涨的牛股识别并选入跟踪池，再在此基础上优化入场/离场择时。

### 1.2 关键口径（默认值，可调整）

- 确定性（certainty）长周期目标窗口：未来 100 个交易日以内
- 确定性（certainty）长周期目标涨幅：区间最大涨幅不少于 50%
- 确定性（certainty）短周期目标（待补齐，RB.M2.CERTAINTY_SHORT.001）：未来 10–20 个交易日内上涨 30% 以上
- 高确定性门槛：certainty_score >= 80（百分制 0–100）
- 风控止损线：跌破买入价 5% 触发硬风控（默认值；例外见第 4 章）

### 1.3 关键定义：见顶风险强度（hazard）

本项目语境中的 hazard 不是“系统性砸盘/市场整体异常”，也不是“必然大跌”的预测器。hazard 的职责是度量“见顶窗口紧迫程度”。

- hazard 定义：从当前时点继续持有，未来 N 天内进入“离场窗口/见顶窗口”的紧迫程度
- hazard 输出：两层输出（每日更新）
  - stock_top_risk_5d：未来 5 个交易日内进入离场窗口的紧迫程度
  - stock_top_risk_20d：未来 20 个交易日内进入离场窗口的紧迫程度
- hazard 主口径（当前阶段 SSOT）：个股层（E2），即以“个股自身进入离场/见顶窗口”为目标事件定义与校准对象
- 目标事件定义与阈值：必须可回溯、可复算、可回测；阈值为“暂定默认值”，允许后续通过全历史回填与校准调整
- 目标事件（当前阶段 SSOT，T2：加速段结束 + 结构破坏 + 失败确认）：
  - 加速段（K=15）：过去 15 个交易日累计涨幅 >= 30%
  - 破坏信号：当日跌幅 <= -7%
  - 修复结构（暂定默认值，C）：破坏信号出现后，未来 10 个交易日内重新突破“破坏日前 5 日最高价”
  - 失败确认（M=10）：破坏信号出现后，未来 10 个交易日内未能修复结构
- hazard 与系统性风险（risk-off）的优先级：
  1) 系统性 risk-off（市场整体异常/砸盘，RB.M3.RISKOFF.001）为独立机制，一旦触发对所有标的一票否决（全清仓 + 观察锁）
  2) hazard 仅在未触发 risk-off 时生效，用于驱动持有期滤噪与离场动作
  3) entry_window 仅在未触发 risk-off 且 hazard 不处于高风险区时才允许产生可执行入场

hazard 的实现分为两条线（必须拆分语义，避免“事后状态”污染“事前预测”）：

- 在线预测器（Prediction，M3）：只允许使用 target_date 当日及历史数据，输出 `hazard_score`（0–100）与 `hazard_state`（状态机），可用于日常持有期滤噪与离场链路的演进。
  - `hazard_score`：必须对齐“未来 N 日内进入目标事件窗口”的可预测部分（用于提前预警），不能用任何未来数据。
  - `hazard_state`：表达“截至 target_date 的已发生状态”（例如 break_armed/stale/recovering），用于当下处置与审计；不要求对齐未来 hit。
- 离线标签（Label，M4/M5）：允许使用未来窗口，用于全历史校准与评估，不能直接用于严格 no-lookahead 的日常决策。

当前阶段落地策略（v0，先有用再收敛）：

- v0 在线预测器只影响持有期滤噪，不直接触发退出：
  - `risk_status=pending`：表示历史不足导致无法计算（例如不足 K=15 无法判定加速段），必须 fail-closed，不得升级为退出信号。
  - `risk_status=ready`：表示可以计算 `hazard_score` 与 `hazard_state`（只用历史），但 v0 仍然默认不把 hazard_score 直接映射成 `risk_action=exit`。
  - `hazard_state`：用于当下处置与审计，优先驱动持有期观测等级（hold_noise_filter_state）。
  - `hazard_score`（0–100）：用于提前预警（对齐未来 N 日 hit 的可预测部分）；分数越高代表提前预警更强，但仍需通过评估与校准治理后再决定如何驱动执行链。
- v0 的可见效果：
  - 上调 `hold_noise_filter_state` 的 stage/level，并提供可审计 reasons/evidence/warning_flags
  - 不注入 `sell_payload`，不改变 `risk_action` 的主链（硬证伪/趋势衰竭/系统退出）语义
- v0 的输出契约（供审计/归因复算）：
  - `hazard_snapshot`（object 或 null）
    - `risk_status`：ready/pending
    - `hazard_state`：not_ready/neutral/accel_only/break_armed/stale_break/recovering
    - `stock_top_risk_5d`：0–100（hazard_score_5d，提前预警分）
    - `stock_top_risk_20d`：0–100（hazard_score_20d，提前预警分）
    - `first_event_date`：首次进入高风险 armed 状态的日期（如有）
    - `evidence`：证据列表（只允许使用 target_date 当日及历史信息）

hazard 的评估与演进原则（硬约束）：

- Label/Prediction 严格分离：离线标签表 `stock_top_hazard_labels_t2` 及其 `hit/label_status` 只能用于评估/校准（M4/M5），不得作为在线预测器输入，不得作为 M3 日常决策的直接依据。
- No-lookahead：在线 hazard predictor 只能读取 target_date 当日及历史数据（如 `daily_prices.trade_date <= target_date`）；任何依赖未来窗口的逻辑只能存在于离线评估层。
- 评估闭环优先：若预测质量不足，允许按如下顺序改进，并必须先更新 rulebook 再改代码：
  1) 分桶/校准（把 0–100 分映射为稳定等级/概率区间）
  2) 在线可观测信号增强（仍只用历史数据）
  3) 目标事件（label）定义修订（高风险变更）
- 校准产物（用于治理，不得反向污染预测器）：
  - 评估脚本生成的 `bins_5d.csv / bins_20d.csv`（每个 score bin 的样本量与 hit_rate）属于“校准证据”，用于 M5 决策阈值与门槛治理。
  - 校准产物的输入只能是离线标签（真值）与在线预测输出（prediction）；在线预测器不得读取离线标签表，也不得依赖评估脚本运行时产物作为输入。

离线标签表的语义边界（用于校准/评估，不得直接驱动日常决策）：

- 表：`stock_top_hazard_labels_t2`
- `hit`：监督标签，语义为“从 obs_date 往后 N 天内是否发生目标事件”（包含未来信息）
- `label_status=ready`：表示该监督标签在离线评估中可判定（需要未来窗口存在）
- `label_status=pending`：表示该监督标签在离线评估中不可判定（未来窗口不足）
- 该表只能用于评估/校验在线预测器（Prediction）的预测质量，不得作为预测器输入或 M3 日常决策的直接依据

### 1.4 回测验证口径（Top200 只作为外部对照基准）

- 回测验收必须采用“模型推演结果 vs 历史最强 Top200 牛股”的对照逻辑。
- Top200 是外部对照基准（oracle），用于评估模型是否圈定了大多数牛股，以及持仓是否接近真正见顶。
- Top200 不得作为模型运行的反向框定工具（不得用于限定候选宇宙/入口或引导运行路径）。

---

## 2. M1–M6 分层归属（避免混层）

本节用于把“谁拥有哪类语义”固定下来，后续任何修改都应以此为边界。

### 2.1 M1：事实层（Fact Layer）

职责：

- 事实接入、标准化、派生事实、质量证明、任务契约

输出（供 M2/M3 消费）：

- 日线量价与衍生序列（K 线、涨跌幅、成交量/成交额等）
- 可见日口径的财报/估值（防前视）
- 数据质量状态（完整性、新鲜度、时点一致性）

### 2.2 M2：周期识别与确定性层（Cycle & Certainty Layer）

职责：

- 使用混沌序列（阴阳关系及其历史沿革）完成周期识别与确定性判断，并输出可直接驱动 M3 状态机更新的依据
- 形态（杯柄/老鸭头等）只允许作为证据输入（evidence/factor），不得形成独立动作语义
- 旧口径（wave_phase / pattern / certainty_score）被冻结/移除为主链路输出，后续仅作为历史遗留字段存在（直至代码侧切换完成）

输出（供 M3 消费）：

- 候选跟踪池（以龙头/中军为主）
- 每只候选的：
  - chaos_m2_status（ready/pending）
  - chaos_cycle_state（周期阶段：由阴阳关系读出）
  - chaos_certainty（确定性读出：可为分数或分桶，但必须可解释/可复算）
  - role（龙头/中军/跟随）
  - evidence_bundle（可审计证据束）

### 2.3 M3：决策引擎层（Decision Layer）

职责：

- 跟踪池状态机：跟踪→成熟→入场候选
- 入场窗口识别：以 1/3/5/B 浪“初涨阶段”为最佳入场时间
- 持有期滤噪：识别震仓/回调，观察人气状态
- 离场：识别见顶并离场（比“空仓”更准确）
- 见顶风险强度（hazard）：在未触发系统性 risk-off 时，计算并更新 stock_top_risk_5d/20d，用于驱动 hold_noise_filter_state/exit_signal/risk_action
- 风控：跌破买入价 5% 启动硬风控；以及“负面消息/板块人气/财报”例外触发（需明确证据）
- 市场整体异动：命中系统性异动信号后立刻全清仓，并进入观察阶段；在观察锁解除前禁止新增开仓

输出（供 M4/M6 消费）：

- 交易与持仓生命周期（trades / positions）
- 决策审计（buy/sell audit）
- 风控与离场原因（可解释）

### 2.4 M4：评估层（Benchmark / Evaluation Layer）

职责：

- 对模型表现做独立评估与对比
- 以“跟踪池质量”与“入场/离场择时”作为两条主评估标尺（当前迭代顺序先聚焦跟踪池质量）
- 提供可复核证据束（支撑 M5 提案）

输出：

- 评估报告（结构化指标 + 证据引用）

### 2.5 M5：治理与更新层（Governance Layer）

职责：

- 将 M4 的评估结论转化为可执行提案与治理记录
- 输出“调整建议 → 风险评估 → 变更范围 → 验证方案”

输出：

- 提案与决策记录（版本化、可回溯）

### 2.6 M6：交付与解释层（Delivery & Observability Layer）

职责：

- 报告、接口、可视化与“说人话”的解释
- 只消费模型正式字段，不发明语义

输出：

- PDF/JSON 报告、API view、前端展示

---

## 3. 顶层筛选/甄别流程与运行机制（不等同于“模型每天按什么顺序做事”）

本章描述模型的“筛选/甄别 → 跟踪 → 入场 → 持有 → 离场 → 风控”主流程。
这里的“顺序”仅指筛选流程的逻辑依赖与输入输出关系，不等同于每天调度/执行任务的编排顺序；具体实现可并行、可增量，但必须满足同一条逻辑链路的因果约束。

### Step 1：全市场小周期定位（画第一个圈）

目标：

- 对每只股票进行周期阶段定位（以阴阳关系读出为准；不再依赖旧口径 1/3/5/B 浪枚举）

输出：

- chaos_cycle_state（planned：以混沌 SSOT 口径替换旧 wave_phase）

归属：

- M2

### Step 2：形态甄别 + 确定性评分（画第二个圈）

目标：

- 对 Step 1 入围股票做证据增强：形态/筛选器只作为 evidence/factor 输入混沌因子矩阵
- 输出混沌口径的确定性读出（chaos_certainty），不再输出旧 certainty_score

输出：

- chaos_certainty（planned：混沌 SSOT 口径）
- evidence_bundle（形态证据作为输入，不作为动作语义）

归属：

- M2

### Step 3：身份确认与聚焦（画第三个圈）

目标：

- 对 certainty_score>=80 的股票进一步确认身份：龙头/中军/跟随
- 聚焦龙头/中军，将其作为跟踪池核心对象

输出：

- role（龙头/中军/跟随，RB.M2.STEP3.ROLE.001）
- tracking_pool_candidates（RB.M2.STEP3.TRACKING_POOL_CANDIDATES.001）

归属：

- M2

### Step 4：识别入场窗口（最佳入场时间）

目标：

- 在跟踪过程中识别入场窗口（以混沌通用读出为准）

输出：

- entry_window（可执行/不可执行 + 原因，RB.M3.STEP4.ENTRY_WINDOW.001）

归属：

- M3

### Step 5：持有期滤噪与离场

目标：

- 持有期滤噪：识别震仓/回调；观察人气状态
- 识别真实见顶并离场（比“空仓”更准确）

输出：

- hold_noise_filter_state（RB.M3.STEP5.HOLD_NOISE_FILTER_STATE.001）
- exit_signal（离场信号 + 原因 + 证据，RB.M3.STEP5.EXIT_SIGNAL.001）
- - chaos_snapshot（混沌模型 SSOT：yin/yang/net_energy + 历史沿革引用；用于决策与复盘，RB.M3.CHAOS.SNAPSHOT.001；详细契约见 chaos_rulebook.md）
- hazard_score_5d/20d（字段名：stock_top_risk_5d/stock_top_risk_20d，RB.M3.HAZARD.SCORE_FIELDS.001）
- hazard_state（RB.M3.HAZARD.STATE_FIELD.001）

归属：

- M3

### Step 6：风控机制（硬阈值 + 例外条件）

目标：

- 硬风控：股价低于买入价 5% 触发平仓并等待下一机会
- 默认不启动风控：未跌破买入价时不触发硬风控
- 例外：若明确判断板块人气/财报/行业新闻释放大量负面消息，可触发风控/离场（需证据）
- 系统性风险：若命中“市场整体异动”，立刻触发系统性退出（全清仓）并进入观察阶段，直到市场稳定、人气回归后再恢复开仓

输出：

- risk_action（hold/exit）+ reasons + evidence（RB.M3.STEP6.RISK_ACTION.001）
- entry_stop_loss（默认 -5%，RB.M3.STEP6.STOP_LOSS.001）
- 系统性 risk-off 的观察锁状态与审计（见第 1.3 节优先级）

归属：

- M3（前提：负面消息证据需要 M1 提供事实输入）

### Step 7：低频纪律（只在确定机会时操作）

目标：

- 时候没到不操作，只跟踪与更新判断
- 交易次数是低频纪律的硬约束：出现大量高频式交易属于异常信号，应触发评估与治理

输出：

- trade_discipline_metrics（含 total_trades 等，RB.M3.STEP7.TRADE_DISCIPLINE_METRICS.001）
- discipline_guard_verdict（是否触发异常/是否阻断后续动作，RB.M3.STEP7.DISCIPLINE_GUARD.001）
- discipline_audit_event（审计事件与证据，RB.M3.STEP7.DISCIPLINE_AUDIT.001）

归属：

- M3

### Step 8：跟踪池质量评估与迭代入口

目标：

- 对跟踪池质量与确定性兑现情况做评估
- 为调整提供证据与方向

输出：

- tracking_pool_quality_report（RB.M4.STEP8.QUALITY_REPORT.001）
- adjustment_proposal（RB.M5.STEP8.ADJUSTMENT_PROPOSAL.001）
- governance_decision_log（RB.M5.STEP8.GOVERNANCE_DECISION_LOG.001）

归属：

- M4（评估）→ M5（提案/治理）→ 回到 M2/M3（调整）

---

## 4. 修正/更新机制（M4 → M5 → M2/M3）

### 4.1 评估触发（M4）

- 对以下问题给出结构化评估：
  - 跟踪池是否包含足够多高确定性（>=80）的票
  - 高确定性票的留存是否合理（是否“隔天掉队”）
  - 入场/离场是否在合理窗口
  - 风控是否过早/过晚
  - 交易次数是否违背低频纪律（出现大量交易属于异常信号）

契约：

- evaluation_trigger_inputs（RB.M4.CH4.EVAL_TRIGGER_INPUTS.001）
- evaluation_outputs（RB.M4.CH4.EVAL_OUTPUTS.001）

### 4.2 提案与治理（M5）

- 将评估结论转化为提案：
  - 调整目标：提升跟踪池质量 / 改善留存 / 降低噪音
  - 调整范围：M2（识别/确定性/身份）或 M3（跟踪/入场/离场/风控）
  - 风险与验证：如何证明改动有效且不引入回归

契约：

- proposal_contract（RB.M5.CH4.PROPOSAL_CONTRACT.001）
- governance_verdict（RB.M5.CH4.GOVERNANCE_VERDICT.001）

### 4.3 执行调整（回到 M2/M3）

- M2 调整示例：
  - wave_phase 判定
  - pattern 识别
  - certainty_score 的构成与阈值
  - role 识别与聚焦策略
- M3 调整示例：
  - tracking 池的留存与晋级规则
  - entry window 与执行节奏
  - 持有期滤噪
  - exit 与风控触发条件

契约：

- adjustment_application_record（RB.M5.CH4.ADJUSTMENT_APPLICATION_RECORD.001）

---

## 5. 附录（按需补充）

### 5.1 Contract Registry（契约注册表）

本节用于把 rulebook 中“会影响行为/输出契约/边界”的条目注册为可机器验收的清单。

规则：

- 每条契约必须包含：`id`、`status`、`evidence`
- `status` ∈ implemented / planned / deferred
- implemented：必须存在可核验 evidence（至少包含一个测试文件或校验脚本文件路径）
- planned/deferred：必须存在可核验 evidence（至少一个设计文档或说明文档路径），且不得被线上链路消费

条目：

- RB.M3.HAZARD.PREDICTOR_V0.001 status=implemented evidence=neotrade3/decision_engine/hazard_predictor_v0.py,tests/unit/test_hazard_predictor_v0_t2.py
- RB.M3.HAZARD.SNAPSHOT.001 status=implemented evidence=neotrade3/decision_engine/position_contract_snapshot.py,tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py
- RB.M4.HAZARD.EVAL_RECENT2Y.001 status=implemented evidence=scripts/eval_hazard_v0_t2_recent2y.py,docs/superpowers/specs/2026-07-19-hazard-v0-eval-design.md
- RB.M3.RISKOFF.001 status=deferred evidence=docs/superpowers/specs/2026-07-19-market-anomaly-riskoff-design.md
- RB.M2.CERTAINTY_SHORT.001 status=planned evidence=docs/architecture/lowfreq_v16_model_rulebook.md
- RB.M2.STEP1.WAVE_PHASE.001 status=implemented evidence=neotrade3/cycle_intelligence/global_entry_selector.py,neotrade3/cycle_intelligence/sector_entry_selector.py,neotrade3/decision_engine/signal_seed.py,neotrade3/decision_engine/signal_payload.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP1.WAVE_CONFIDENCE.001 status=implemented evidence=neotrade3/cycle_intelligence/global_entry_selector.py,neotrade3/cycle_intelligence/sector_entry_selector.py,neotrade3/decision_engine/signal_seed.py,neotrade3/decision_engine/signal_payload.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP1.EVIDENCE_BUNDLE.001 status=implemented evidence=neotrade3/cycle_intelligence/global_entry_selector.py,neotrade3/cycle_intelligence/sector_entry_selector.py,neotrade3/decision_engine/signal_seed.py,neotrade3/decision_engine/signal_payload.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP2.CERTAINTY_SCORE.001 status=implemented evidence=lowfreq_engine_v16_advanced.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP2.CERTAINTY_HORIZON.001 status=implemented evidence=lowfreq_engine_v16_advanced.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP2.CERTAINTY_TARGET_RETURN.001 status=implemented evidence=lowfreq_engine_v16_advanced.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP2.PATTERN_EVIDENCE.001 status=implemented evidence=neotrade3/cycle_intelligence/global_entry_selector.py,neotrade3/cycle_intelligence/sector_entry_selector.py,neotrade3/decision_engine/signal_seed.py,neotrade3/decision_engine/signal_payload.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP2.EVIDENCE_BUNDLE.001 status=implemented evidence=neotrade3/cycle_intelligence/global_entry_selector.py,neotrade3/cycle_intelligence/sector_entry_selector.py,neotrade3/decision_engine/signal_seed.py,neotrade3/decision_engine/signal_payload.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP3.ROLE.001 status=implemented evidence=neotrade3/cycle_intelligence/global_entry_selector.py,neotrade3/cycle_intelligence/sector_entry_selector.py,neotrade3/decision_engine/signal_seed.py,tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- RB.M2.STEP3.TRACKING_POOL_CANDIDATES.001 status=implemented evidence=neotrade3/decision_engine/signal_payload.py,tests/unit/test_lowfreq_engine_v16_signal_convergence.py
- RB.M3.STEP4.ENTRY_WINDOW.001 status=implemented evidence=neotrade3/decision_engine/formal_front.py,tests/unit/test_lowfreq_formal_front_projection.py
- RB.M3.HAZARD.SCORE_FIELDS.001 status=implemented evidence=neotrade3/decision_engine/hazard_predictor_v0.py,tests/unit/test_hazard_predictor_v0_t2.py
- RB.M3.HAZARD.STATE_FIELD.001 status=implemented evidence=neotrade3/decision_engine/hazard_predictor_v0.py,tests/unit/test_hazard_predictor_v0_t2.py
- RB.M3.STEP5.HOLD_NOISE_FILTER_STATE.001 status=implemented evidence=neotrade3/decision_engine/position_contract_snapshot.py,tests/unit/test_lowfreq_engine_v16_sell_logic.py,tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py
- RB.M3.STEP5.EXIT_SIGNAL.001 status=implemented evidence=neotrade3/decision_engine/position_contract_snapshot.py,tests/unit/test_lowfreq_engine_v16_sell_logic.py,tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py
- RB.M3.STEP6.RISK_ACTION.001 status=implemented evidence=neotrade3/decision_engine/position_contract_snapshot.py,tests/unit/test_lowfreq_engine_v16_sell_logic.py,tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py
- RB.M3.STEP6.STOP_LOSS.001 status=implemented evidence=lowfreq_engine_v16_advanced.py,tests/unit/test_lowfreq_engine_v16_sell_logic.py
- RB.M3.STEP7.TRADE_DISCIPLINE_METRICS.001 status=implemented evidence=neotrade3/decision_engine/trade_discipline.py,lowfreq_engine_v16_advanced.py,tests/unit/test_lowfreq_engine_v16_trade_discipline.py
- RB.M3.STEP7.DISCIPLINE_GUARD.001 status=implemented evidence=neotrade3/decision_engine/trade_discipline.py,lowfreq_engine_v16_advanced.py,tests/unit/test_lowfreq_engine_v16_trade_discipline.py
- RB.M3.STEP7.DISCIPLINE_AUDIT.001 status=implemented evidence=neotrade3/decision_engine/trade_discipline.py,lowfreq_engine_v16_advanced.py,tests/unit/test_lowfreq_engine_v16_trade_discipline.py
- RB.M4.STEP8.QUALITY_REPORT.001 status=implemented evidence=neotrade3/analysis/step8_quality_report.py,neotrade3/analysis/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M5.STEP8.ADJUSTMENT_PROPOSAL.001 status=implemented evidence=neotrade3/governance/step8_governance.py,neotrade3/governance/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M5.STEP8.GOVERNANCE_DECISION_LOG.001 status=implemented evidence=neotrade3/governance/step8_governance.py,neotrade3/governance/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M4.CH4.EVAL_TRIGGER_INPUTS.001 status=implemented evidence=neotrade3/analysis/step8_quality_report.py,neotrade3/analysis/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M4.CH4.EVAL_OUTPUTS.001 status=implemented evidence=neotrade3/analysis/step8_quality_report.py,neotrade3/analysis/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M5.CH4.PROPOSAL_CONTRACT.001 status=implemented evidence=neotrade3/governance/step8_governance.py,neotrade3/governance/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M5.CH4.GOVERNANCE_VERDICT.001 status=implemented evidence=neotrade3/governance/step8_governance.py,neotrade3/governance/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M5.CH4.ADJUSTMENT_APPLICATION_RECORD.001 status=implemented evidence=neotrade3/governance/step8_governance.py,neotrade3/governance/step8_artifact_writer.py,tests/unit/test_step8_eval_governance_v0.py
- RB.M3.CHAOS.SNAPSHOT.001 status=implemented evidence=neotrade3/decision_engine/chaos_model_v0.py,tests/unit/test_chaos_model_v0.py,tests/unit/test_position_contract_snapshot_chaos_field.py
- RB.M4.CHAOS.EVAL_MONITOR.001 status=implemented evidence=neotrade3/chaos/m4_eval_monitor.py,scripts/run_chaos_m4_eval_monitor.py,tests/unit/test_chaos_m4_eval_monitor.py
- RB.M5.CHAOS.GOVERNANCE.001 status=planned evidence=docs/superpowers/specs/2026-07-20-chaos-model-design.md

- A. 关键字段字典（certainty_score 等）
- B. 关键阈值与默认值列表
- C. 版本与变更记录（何时改了什么、为什么）

### 5.2 混沌序列的通用读出（动作规则）
本节已迁移为混沌 SSOT 的主规则手册，参见 [chaos_rulebook.md](file:///Users/mac/NeoTrade3/docs/architecture/chaos_rulebook.md)。

### 5.3 示例：杯柄的阴阳转换叙事（混沌模型）
本节作为解释模板已迁移至 [chaos_rulebook.md](file:///Users/mac/NeoTrade3/docs/architecture/chaos_rulebook.md)（形态叙事只用于复盘/沟通，不构成动作规则）。
