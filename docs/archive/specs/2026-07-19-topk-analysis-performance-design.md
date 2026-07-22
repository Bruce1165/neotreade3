# 2026-07-19 TopK 分析阶段性能优化（不改变逐日口径）

## 1. 背景与问题证据

在 TopK（Top3/Top200）归因报告脚本中，分析阶段的逐日审计 `_audit_daily_reason(...)` 会先尝试从 `ctx.entry_signals(...) / ctx.candidate_signals(...)` 判断“当日是否进入 entry/candidate”，而这两者依赖 `AuditContext.signal_snapshot()` 内部调用 `engine.generate_buy_signals(target_date)`。

- `AuditContext.signal_snapshot` 调用 `engine.generate_buy_signals`：[generate_lowfreq_top200_attribution_report.py:L288-L312](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L288-L312)
- `_audit_daily_reason` 每个交易日都会触发 `ctx.entry_signals / ctx.candidate_signals`：[generate_lowfreq_top200_attribution_report.py:L428-L454](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L428-L454)

在 `limit` 很小（例如 Top3）但 segment 覆盖全年时，这等价于“按交易日复算全市场信号”，导致分析阶段耗时不可控，并阻塞 `status.stage` 从 `backtest_ready` 推进到 `analysis_ready/done`。

## 2. 目标（验收标准）

1. 保持 daily_audits 逐交易日全量覆盖（不降口径、不改对外字段结构）。
2. 分析阶段不再调用 `engine.generate_buy_signals(...)`。
3. “当日已进入候选/建仓池”的判定以回测产物 `summary.buy_signal_audit` 为真值来源（反映回测当日真实执行链审计）。
4. 对未出现在 `buy_signal_audit` 的日期，仍输出与当前脚本一致的解释路径（market filter → hot sector → seed → candidates → reason）。
5. 性能目标（操作性）：Top3 smoke 在可控时间内推进到 `done`，并产出 ranking/segments/report 等文件。

## 3. 与 Rulebook 的一致性检查（边界）

- 本优化属于报告/解释层（M6），不改变 M3 决策引擎逻辑，不引入 Top200 反向框定候选宇宙。
- 仅消费回测输出的正式审计字段 `buy_signal_audit`（M3 输出的一部分），符合“只消费模型正式字段，不发明语义”的边界。
- 不引入离线标签表、不引入未来信息，不触碰 no-lookahead 约束。

## 4. 方案 A（已确认实施）

### 4.1 核心思路

在逐日审计中引入“回测审计真值快路径”：

- 先查 `summary.buy_signal_audit` 是否存在对应 `(code, date)` 的事件记录：
  - 若存在：
    - 直接输出 `entry_signal_selected` 或 `candidate_signal_selected` 的审计条目（使用 `buy_signal_audit` 自带的 buy_score/role/wave_phase/evidence_bundle 等字段适配 daily audit 的 signal 结构）。
    - 不再需要 `generate_buy_signals` 的复算。
  - 若不存在：
    - 走现有解释路径（market filter / hot sector / seed / candidates），但移除对 `ctx.entry_signals / ctx.candidate_signals` 的依赖。

### 4.2 信号适配规则（从 buy_signal_audit → daily audit signal）

输出保持 `build_entry_signal_selected_audit` / `build_candidate_signal_selected_audit` 所需字段：

- `buy_score`：来自 `buy_signal_audit.buy_score`
- `role`：来自 `buy_signal_audit.role`
- `wave_phase`：来自 `buy_signal_audit.wave_phase`
- `reasons`：优先使用 `tracking_evidence_bundle`，否则回退 `evidence_bundle`，否则空列表
- `candidate_tier`：若 `buy_signal_audit` 无该字段则置空字符串
- `entry_ready`：优先使用 `tracking_ready`，否则根据 `funnel_stage/execution_status` 推断（仅作为展示字段）

### 4.3 连接复用优化（等价改写）

`AuditContext.sector_candidates(...)` 当前每次都会 `engine._conn()` 新建 sqlite 连接并关闭。

改为复用 `AuditContext.conn`：

- 使用 `ctx.conn.cursor()` 作为 `engine.get_sector_candidates(..., cursor=...)` 的 cursor 参数。
- 行为等价：同一 db 文件读取，不改变 SQL 语义，仅减少连接开销。

### 4.4 hot_sectors 批量预计算（等价加速）

逐日调用 `engine.get_hot_sectors` 的主要成本来自“每个交易日一次全市场 sector 聚合 SQL（JOIN + GROUP BY）”。

优化策略：

- 在 `_analyze_topk` 开始阶段，基于全局分析日期区间（min_start..max_top）用 1 次 SQL 批量拉取 `trade_date×sector_lv1` 的日聚合（`stock_count/avg_change`）。
- 在内存中按日期取 `avg_change` 排序的前 `top_n*2` 个 sector 作为候选，再对候选 sector 调用 `detect_sector_cooldown` 过滤“人气消散”的扇区，最终得到当日 hot_sectors。
- 对外语义保持一致：仍然以同样的过滤规则判定“是否属于 hot sector 分支”，只是把 N 次大查询降为 1 次。

## 5. 风险与防护

- 风险：`buy_signal_audit` 的字段与 daily audit 的 signal 结构并非完全同构。
  - 防护：明确适配规则；缺失字段回退为空值，不影响主字段稳定性。
- 风险：未出现在 `buy_signal_audit` 的日期，其“为什么没入候选/建仓”仍需依赖 seed/candidate 逻辑，可能仍有一定成本。
  - 防护：该路径已按 code/sector 做种子与候选的轻量计算，不再复算全市场信号。

### 4.5 seed_only 模式（可跑完且不伪装）

当候选阶段复算仍不可控时，支持在逐日审计中启用 `analysis_mode=seed_only`：

- 逐交易日仍输出 daily_audits（不做稀疏化）。
- 若命中当日种子（sector/global），直接产出 `*_seed_hit` 审计并停止在该日继续复算候选阶段。
- 对外显式标注：
  - daily_audits 的 `*_seed_hit` 记录包含 `analysis_mode="seed_only"`。
  - attribution.json 的 `_meta` 包含 `analysis_mode`；status.json 在 `analysis_ready/done` 阶段也包含 `analysis_mode`。

## 6. 测试与验证

1. 单测：构造一个 `buy_signal_audit` 事件，断言 `_audit_daily_reason` 在该日期直接返回 `entry_signal_selected/candidate_signal_selected` 且不会触发 `generate_buy_signals`（可用 stub engine 的 generate_buy_signals=raise 作为护栏）。
2. 烟雾跑：`--limit 3` 执行一次 TopK 脚本，验证：
   - `status.stage` 能推进到 `done`
   - `status.json` 仍包含 Step8 与 backtest 证据字段（不回退）
   - 产物 ranking/segments/report 等落盘存在
