Status: active
Owner: lowfreq / chaos-model
Scope: 混沌模型 v0 实施计划（M3 计算与审计输出 + 全市场日度因子矩阵落盘 + M4/M5 治理闭环）
Canonical: docs/architecture/lowfreq_v16_model_rulebook.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-20

# 混沌模型 v0 实施计划

日期：2026-07-20  
对应设计：`docs/superpowers/specs/2026-07-20-chaos-model-design.md`

## 1. 目标

本计划落地的核心结果：

- M3 每日输出 `chaos_snapshot`（yin/yang/net_energy + 驱动段历史对照），并可被持有/离场链路与复盘消费。
- 形成全市场日度资产：
  - 因子注册表（Factor Registry，版本化）
  - 因子矩阵（EAV 长表，版本化）
  - 日度混沌快照（yin/yang/net_energy + 关键派生指标）
- 建立 M4 评估监测与 M5 治理回灌的闭环接口与版本边界（不引入未来窗口到日常运行）。
- 满足 fail-closed 与合规闸门：M3 不得读取 M4 标签或未来窗口产物；M3 只可读取 M5 批准版本。

## 2. 非目标（v0 不做）

- 不在 v0 将混沌模型替换现有 buy_score / 执行信号闸门；先以并行证据字段接入。
- 不在 v0 承诺公告/财报的深度 NLP 抽取；只冻结结构化事实入口的契约与版本边界。
- 不在 v0 一次性覆盖“全量因子”，先以可回测闭环驱动的最小因子集起步，并提供扩展机制。

## 3. 前置条件

- rulebook 中已存在 planned 契约条目：
  - RB.M3.CHAOS.SNAPSHOT.001
  - RB.M4.CHAOS.EVAL_MONITOR.001
  - RB.M5.CHAOS.GOVERNANCE.001
- 设计文档已冻结统一刻度与驱动段参照（regime_anchor）口径：
  - `docs/superpowers/specs/2026-07-20-chaos-model-design.md`
- 任务注册表需同步记录实施进度：
  - `docs/superpowers/specs/lowfreq_v16_task_registry.md`

## 4. 分阶段实施

### Phase 0：契约冻结与落点确认（文档与接口先行）

交付物：

- 冻结 `chaos_snapshot` 的字段契约与 fail-closed 语义（以 rulebook + design 为准）。
- 冻结 Factor Registry 的字段集合与分类权重调节器（综合:资金人气:技术 = 3:4:3）。
- 冻结“驱动段历史参照”的锚点逻辑：`regime_anchor`（与回调 2/4/A 浪区分）。

完成判定：

- rulebook 与 design 文档一致，且闸门测试通过。

### Phase 1：M3 混沌快照输出（先跟踪池重点，再扩展）

范围：

- 先对“跟踪池/持仓/观察列表”产出 `chaos_snapshot` 并纳入持有/离场审计输出，确保可回放与可归因。

建议接入点（以现有实现为准）：

- `neotrade3/decision_engine/position_contract_snapshot.py`：新增 `chaos_snapshot` 字段，并保证与现有 `hazard_snapshot` 并行，不相互污染。
- `lowfreq_engine_v16_advanced.py`：在构造 position contract snapshot 时传入 `chaos_snapshot`。

完成判定：

- `chaos_snapshot` 在 M3 输出对象中稳定出现，并在回测产物与报告链路中可被消费。
- 合规闸门测试通过：混沌计算不得读取任何离线标签或未来窗口真值表。

### Phase 2：全市场日度因子矩阵与日度快照落盘（离线批处理）

范围：

- 每日对全 A 股计算并落盘：
  - `chaos_factor_registry`（版本化）
  - `chaos_factor_values`（EAV）
  - `chaos_daily_snapshot`（yin/yang/net_energy + 对照指标）

落盘位置建议：

- `var/db/chaos_factor_matrix.db`

性能与容量约束：

- 必须先做小样本基准（例如：100 codes × 30 days × N_factors_initial），测耗时与 DB 增长，再外推全量规模后由 M5 决策是否扩容或拆分。

完成判定：

- DB 表结构落地且可复算；
- 基准结果可复现并形成固定报告（作为后续治理证据）。

### Phase 3：M4 偏差监测（只做评估，不进入线上输入）

范围：

- 产出“混沌判断 vs 后验走势”的监测报告与偏差归因（允许未来窗口，但只用于评估）。
- 输出调整建议（权重/阈值/因子定义），提交 M5。

完成判定：

- 监测入口可复现（脚本/任务），产物落盘可定位；
- 监测不向 M3 提供任何直接输入（仅治理建议）。

### Phase 4：M5 治理回灌（版本化、可机器验收）

范围：

- M5 批准并落盘：
  - `factor_registry_version`
  - `weights_version`
  - `thresholds_version`
- M3 只读取已批准版本；版本回滚可复现。

完成判定：

- 版本边界明确，且存在 fail-closed 行为：无批准版本则不允许进入强动作（只观察）。

## 5. 验收与门禁

门禁测试（必须）：

- rulebook 契约注册表闸门：`tests/unit/test_rulebook_contract_registry_gate.py`
- task registry 闸门：`tests/unit/test_task_registry_gate.py`
- 合规闸门（待新增）：禁止 M3 混沌计算读取离线标签/未来窗口真值表

运行验收（建议）：

- 选择固定样本集（Top/Mid/Bottom + 异常行情样本）做混沌序列回放与读出质量评估。

