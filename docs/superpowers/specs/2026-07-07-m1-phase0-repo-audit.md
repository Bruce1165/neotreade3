# M1 Phase 0 仓库现实审计

日期：2026-07-07

## 1. 目的

本审计只回答 `Phase 0` 需要冻结的现实问题：

- 当前仓库中，`D1` 的真实生产主链是什么。
- 当前仓库中，`D7` 的真实供给边界是什么。
- 当前仓库中，`D8` 首批哪些派生字段可以诚实地冻结进 `M1`。
- 当前仓库里，哪些现有资产只应视作 `M2/M3` 的迁移素材，而不能宣称为正式对象。

本审计不做以下事情：

- 不把设计图纸直接表述成“已实现”。
- 不把分析层输出提前抬升为 `M1` 正式事实。
- 不在本文件中直接定义最终 schema 或代码实现。

## 2. 审计范围与证据基线

本次结论只基于当前仓库可核查代码与配置文本，不基于历史对话口径，不基于设计意图推断。

核心证据文件：

- `docs/operations/production_task_registry.md`
- `neotrade3/scheduler/task_scheduler.py`
- `apps/api/main.py`
- `neotrade3/data_control/pipeline.py`
- `neotrade3/analysis/factor_matrix.py`
- `neotrade3/analysis/market_phase.py`
- `neotrade3/analysis/stock_tiering.py`
- `config/data_control/source_registry.json`

## 3. D1 现实供给链审计

### 3.1 结论

`D1` 当前已经具备首批正式冻结条件，真实主链清晰，且具备生产触发、权威更新、质量门禁与入库落点。

### 3.2 当前真实主链

当前 `D1` 的现实主链可收敛为：

`launchd` -> `update_daily_prices_authoritative` -> `daily_pipeline_run_view()` -> `update_daily_prices_authoritative_view()` -> `daily_prices`

### 3.3 代码证据

1. 生产任务登记明确指出，当前生产实际启用的自动任务之一是 `update_daily_prices_authoritative`，触发源是 `launchd`，而不是 APScheduler。
2. `task_scheduler.py` 顶部注释明确说明：当前生产启用口径由 `config/launchd/` 与已安装 LaunchAgents 定义，APScheduler 注册只用于本地开发和调试。
3. `_run_update_daily_prices_authoritative()` 的实际执行逻辑会调用 `daily_pipeline_run_view()`。
4. `daily_pipeline_run_view()` 内部会执行交易日检查，并调用 `update_daily_prices_authoritative_view()` 完成权威更新。
5. `update_daily_prices_authoritative_view()` 明确以 `daily_prices` 为资源，采用 `Tushare` 主源、`Tencent` safety-net 的权威更新策略。

### 3.4 对首批 M1 的意义

对 `Phase 0/1` 而言，`D1` 可以按“当前运行真相源已经存在”处理，而不是按“仍是占位能力”处理。

因此，首批 `M1 D1` 可以围绕 `daily_prices` 建立最小正式事实契约，并把以下内容视作已存在的现实基础：

- 生产触发入口
- 权威更新逻辑
- 交易日检查
- 主源 / 兜底源策略
- 数据落库事实

## 4. D7 现实供给链审计

### 4.1 结论

`D7` 当前可进入首批正式契约，但必须明确写出边界：

- 它“可用”
- 但“尚非完全独立权威源”

### 4.2 当前真实结构

当前 `D7` 的现实结构不是单一真相源，而是分层回退结构：

1. 运行时优先读 `trading_calendar_cache`
2. 若覆盖不足，则尝试通过 `tushare.trade_cal` 扩展覆盖
3. 若缓存路径不可用，则回退到 `var/ledgers/trading_calendar/trading_calendar.json`
4. 而该 ledger 在 `capture` 阶段又可能从 `daily_prices.trade_date` 重建

因此，当前 `D7` 不是完全独立于 `D1` 的稳定一等真相源。

### 4.3 代码证据

1. `trading_day_view()` 优先调用 `_trading_day_from_calendar_cache()`。
2. `_trading_day_from_calendar_cache()` 直接读取 `trading_calendar_cache`，并在覆盖不足时调用 `_ensure_trading_calendar_coverage()`。
3. `_ensure_trading_calendar_coverage()` 使用 `TushareConceptAdapter.fetch_trade_calendar()` 拉取 `trade_cal`，再回写 `trading_calendar_cache`、`trading_calendar` 与 `trading_calendar_meta`。
4. 若缓存路径不可用，`trading_day_view()` 会回退到 `_load_trading_calendar_days()`，即读取 `var/ledgers/trading_calendar/trading_calendar.json`。
5. `DataControlPipeline._maybe_rebuild_trading_calendar()` 会从 `daily_prices` 提取 `trade_date`，重建该 ledger。

### 4.4 对首批 M1 的意义

`D7` 首批可以正式化的，不是“一个绝对纯净的独立日历域”，而是当前仓库已经存在且被运行逻辑消费的最小对象：

- 交易日判定
- 最近交易日回退
- 覆盖区间
- 日历来源元信息

但首批文档和契约必须同时注明：

- 当前 `D7` 与 `D1` 仍存在较强耦合
- `trading_calendar_cache` 是当前运行主消费面
- ledger 重建路径不能被误表述为独立权威日历工程已经完成

## 5. D8 首批派生事实边界审计

### 5.1 结论

`D8` 首批只应冻结“直接从 `D1/D7` 做浅层窗口聚合、计数或简单比对得到的 primitive derived facts”。

不能进入首批 `D8` 的内容包括：

- 排序后的赛道主线判断
- 分类后的市场阶段判断
- 分层后的个股 tier 判断
- 综合打分矩阵
- 候选股打标与启发式决策翻译

### 5.2 可进入首批 D8 的对象

当前仓库中，最适合作为首批 `D8/PF1` 的对象，是 `apps/api/main.py` 中基于 `daily_prices` 直接构造的 `signals["trading_profile"]`。

其核心字段包括：

- `latest_amount`
- `avg_amount_5d`
- `avg_amount_20d`
- `latest_turnover`
- `avg_turnover_5d`
- `median_turnover_20d`
- `return_20d`
- `avg_pct_change_5d`
- `positive_days_5d`

这些字段符合首批 `D8` 的理由：

- 上游来源清晰，直接来自 `daily_prices`
- 派生方式浅，只是窗口聚合、简单统计或简单比值
- 不包含排序、分类、标签解释、候选翻译等高阶语义
- 当前代码已经在真实运行路径中消费

### 5.3 不建议作为核心 D8 本体的支撑字段

以下字段可保留为派生视图支撑元信息，但不建议作为首批核心业务派生事实本体：

- `latest_trade_date`
- `rows_20d`

原因是这两个字段更偏“数据可用性/窗口状态说明”，而不是业务意义上的核心派生特征。

### 5.4 明确排除项：theme_momentum

`theme_momentum` 不应进入首批 `D8`。

原因：

- 它依赖 `mainline_rank`
- 依赖 `heat_rank`
- 依赖 `mainline_score`
- 依赖 `trend_state`
- 依赖 `risk_level`
- 还包含对 leading concepts 的筛选与排序

这已经不是浅派生，而是赛道层解释与排序语义。

### 5.5 明确排除项：market_phase / sector_rotation / stock_tiering / factor_matrix

以下对象均不应进入首批 `D8`：

- `market_phase`
- `sector_rotation`
- `stock_tiering`
- `factor_matrix`

原因：

- `market_phase` 已经是分类结果，输出 `phase` 与 `confidence`
- `sector_rotation` 已经是板块排序、轮动判断与上下文解释
- `stock_tiering` 已经引入 `leadership_score`、`rs_vs_sector_20d`、`volatility_20d` 等分析层语义
- `factor_matrix` 进一步整合 `market_phase`、`sector_rotation`、`stock_tiering`、筛选器命中、实验室命中与 certainty 分层，属于更高阶综合分析产物

这些对象应被视为未来 `M2/M3/M4` 的输入素材或迁移参考，而不是首批 `M1 D8`。

### 5.6 明确排除项：market intelligence tags

`_derive_market_intelligence_tags()` 及其输出不应进入首批 `D8`。

包括：

- `config_leader_candidate`
- `institutional_attention_candidate`
- `trading_leader_candidate`

原因：

- 这里已经发生规则判断
- 已经把底层 signals 翻译成候选语义
- 已经带有“是否候选、候选强弱、候选原因”的启发式决策色彩

这类对象更接近 proto-`M3`，而不是 `M1` 事实层。

### 5.7 当前不进入首批 D8 的另一类原因

`announcements`、`research_reports`、`report_consensus`、`institutional_surveys`、`fund_portfolios`、`index_weights` 虽然部分聚合较浅，但当前不建议进入首批 `D8`，原因不是“它们一定高阶”，而是：

- 它们当前并不都位于首批生产主链上
- `source_registry.json` 仍明确是 bootstrap placeholder
- 若在此时冻结进 `M1`，容易把“已有接入能力”误写成“首批正式供给责任”

## 6. M2 / M3 现实资产映射

### 6.1 M2 现状

当前仓库中尚不存在新设计意义上的正式 `M2 small_cycle` 对象主链。

也就是说，当前不能宣称以下对象已实现：

- `small_cycle`
- `cycle_state`
- `evidence_bundle`
- `confidence`
- `invalidation`

当前仓库里与未来 `M2` 最接近的资产，是以下分析模块：

- `market_phase`
- `sector_rotation`
- `stock_tiering`

但这些对象只是研究/分析实现或迁移素材，不等于正式 `M2`。

### 6.2 M3 现状

当前仓库中也尚不存在新设计意义上的正式 `M3` 行为状态机对象。

不能宣称已实现的对象包括：

- `identify_state`
- `tracking_state`
- `entry_state`
- `hold_state`
- `exit_state`
- `decision_lifecycle_log`

当前更接近历史/原型状态的资产包括：

- 旧低频链路中的 `hold_state`
- `market_exit_state`
- `sector_exit_state`
- `market intelligence` 的 candidate tags

这些对象可作为未来迁移参考，但不能直接等同于正式 `M3`。

## 7. 首批冻结建议

### 7.1 可以冻结

本轮 `Phase 0` 之后，可以冻结的最小集合是：

- `D1`：以 `daily_prices` 为核心的个股行情事实主链
- `D7`：以 `trading_calendar_cache` 为运行消费面、并明确其当前耦合边界的元数据/交易日历事实
- `D8`：仅限 `trading_profile` 这一类 primitive per-stock 派生指标

### 7.2 不可以冻结

本轮 `Phase 0` 之后，以下对象不应被冻结进首批正式 `M1`：

- `theme_momentum`
- `market_phase`
- `sector_rotation`
- `stock_tiering`
- `factor_matrix`
- `market intelligence candidate tags`
- 其他带排序、分层、分类、评分、候选翻译、主线判断语义的对象

## 8. 对 Phase 1 的直接约束

`Phase 1` 在进入 `M1` 契约定义时，应遵守以下硬边界：

1. `D1` 只按当前真实生产链写契约，不重新发明来源。
2. `D7` 要写清楚“当前运行可用，但并非完全独立权威源”。
3. `D8` 只允许浅派生 primitive metrics 进入首批。
4. 任何带分析结论、排序、评分、候选判断的对象，一律不提前放入 `M1`。
5. `M2/M3` 在本阶段只能做现实资产盘点与迁移映射，不能口径漂移成“已落地正式对象”。

## 9. 最终结论

本次仓库现实审计后的正式结论是：

- `D1` 已具备首批正式冻结条件。
- `D7` 可进入首批正式契约，但必须显式记录其当前仍与 `D1` 存在较强耦合。
- `D8` 首批边界应严格收敛为 `trading_profile` 这一类 primitive derived facts。
- 当前仓库中的 `market_phase`、`sector_rotation`、`stock_tiering`、`factor_matrix` 与 candidate tags，只能视作未来 `M2/M3/M4` 的迁移素材，不能宣称为首批正式 `M1` 产物。
