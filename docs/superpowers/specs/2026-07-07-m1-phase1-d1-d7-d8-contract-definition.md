# M1 Phase 1 首批正式契约定义（D1 / D7 / D8）

日期：2026-07-07

## 1. 目的

本文只定义 `Phase 1` 需要落地的首批正式契约，不扩展到 `D2-D6`，也不提前实现 `M2/M3` 正式对象。

本文基于以下前提：

- `Phase 0` 仓库现实审计已经完成
- `D1` 已具备首批正式冻结条件
- `D7` 可进入首批正式契约，但必须显式保留其当前耦合边界
- `D8` 首批只允许 primitive derived facts

本文不做以下事情：

- 不把当前数据库表结构直接等同于正式对象
- 不把分析层输出并入 `M1`
- 不在本文件中直接声明代码已实现

关联文档：

- [`2026-07-06-m1-fact-layer-design.md`](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-06-m1-fact-layer-design.md)
- [`2026-07-07-m1-phase0-repo-audit.md`](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m1-phase0-repo-audit.md)
- [`2026-07-07-m1-m2-m3-phase0-1-task-list.md`](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m1-m2-m3-phase0-1-task-list.md)

## 2. 契约硬规则

首批正式契约必须遵守以下规则：

1. 正式对象字段名采用语义化命名；若当前仓库底层列名不同，必须显式写出来源映射。
2. 只有当前仓库已存在、已消费、可回链的字段才能进入首批正式契约。
3. 当前代码存在但语义未收口的字段，不得因为“以后可能有用”而提前纳入。
4. `D8` 只收口浅派生，不允许收口排序、分层、分类、评分、候选翻译。
5. 下游 `M2/M3` 在首期只能消费本文定义的正式对象，不能继续绕过 `M1` 直接抓取临时分析产物。

## 3. D1 最小正式事实对象

### 3.1 对象定义

首批正式对象名建议为：`d1_daily_price_fact`

对象粒度：

- 一条记录对应一只股票在一个交易日的日线行情事实

主键：

- `stock_code`
- `trade_date`

当前仓库来源：

- 主来源表：`daily_prices`
- 主来源列：`code`, `trade_date`, `open`, `high`, `low`, `close`, `volume`, `amount`, `turnover`, `preclose`, `pct_change`, `updated_at`

### 3.2 字段契约

| 正式字段 | 当前来源 | 必填性 | 说明 |
| --- | --- | --- | --- |
| `stock_code` | `daily_prices.code` | 必填 | 个股标识 |
| `trade_date` | `daily_prices.trade_date` | 必填 | 交易日 |
| `open_price` | `daily_prices.open` | 条件必填 | 日线开盘价 |
| `high_price` | `daily_prices.high` | 条件必填 | 日线最高价 |
| `low_price` | `daily_prices.low` | 条件必填 | 日线最低价 |
| `close_price` | `daily_prices.close` | 必填 | 日线收盘价 |
| `preclose_price` | `daily_prices.preclose` | 条件必填 | 前收盘价 |
| `pct_change` | `daily_prices.pct_change` | 条件必填 | 日涨跌幅 |
| `volume_shares` | `daily_prices.volume` | 条件必填 | 成交量，语义按股数口径 |
| `amount_cny` | `daily_prices.amount` | 条件必填 | 成交额 |
| `turnover_rate` | `daily_prices.turnover` | 可空 | 换手率，当前不作为首批发布硬门禁 |
| `updated_at` | `daily_prices.updated_at` | 必填 | 当前记录最近一次刷新时间 |

### 3.3 字段说明

- `close_price` 是首批 `D1` 的硬核心字段。
- `open_price`、`high_price`、`low_price`、`preclose_price`、`pct_change`、`volume_shares`、`amount_cny` 属于首批正式行情对象组成部分，但允许在极少数退化路径中按质量门禁单独判定。
- `turnover_rate` 当前代码路径中已存在列位和消费方，但主更新链并未把它作为硬覆盖门禁，因此首批应定义为“可空正式字段”，而不是“必有字段”。
- `volume_shares` 的正式语义必须固定为“股数口径”，不能保留“手/股不确定”状态。

### 3.4 刷新与发布责任

首批 `D1` 的刷新责任链为：

- 生产触发：`launchd`
- 运行入口：`update_daily_prices_authoritative`
- 编排入口：`daily_pipeline_run_view()`
- 权威更新：`update_daily_prices_authoritative_view()`
- 落库表：`daily_prices`

源级口径：

- `Tushare`：`S1`
- `Tencent safety-net`：`S3`

### 3.5 首批禁止事项

以下内容不属于首批 `D1` 契约：

- 任意技术指标扩展列
- 排序结果
- 复权解释层
- 市场阶段解释
- 主题/概念解释

## 4. D7 最小正式事实对象

`D7` 首批不定义成一个大而杂的“元数据桶”，而是拆成两个最小对象：

- `d7_security_master_minimal`
- `d7_trading_day_status`

### 4.1 对象一：d7_security_master_minimal

对象粒度：

- 一条记录对应一只股票的最小基础主数据

主键：

- `stock_code`

当前仓库来源：

- 主来源表：`stocks`

字段契约：

| 正式字段 | 当前来源 | 必填性 | 说明 |
| --- | --- | --- | --- |
| `stock_code` | `stocks.code` | 必填 | 个股标识 |
| `stock_name` | `stocks.name` | 条件必填 | 股票名称 |
| `asset_type` | `stocks.asset_type` | 必填 | 资产类型，首批只允许 `stock` 进入主消费面 |
| `is_delisted` | `stocks.is_delisted` | 必填 | 是否退市 |
| `sector_lv1` | `stocks.sector_lv1` | 可空 | 一级板块/行业映射 |
| `sector_lv2` | `stocks.sector_lv2` | 可空 | 二级板块/行业映射 |
| `last_trade_date` | `stocks.last_trade_date` | 可空 | 最近交易日期，仅作为辅助元数据 |

字段边界说明：

- `asset_type` 与 `is_delisted` 是首批可交易过滤的正式基础字段。
- `sector_lv1`、`sector_lv2` 当前可作为最小映射字段进入正式对象，但不能被夸大为“完整行业分类体系已冻结”。
- `last_trade_date` 可作为辅助状态字段，但首批不把它等同于停复牌正式真值。

明确不纳入首批正式契约的字段：

- `is_suspended`
- `resume_date`
- 任意未在当前主链稳定消费的扩展主数据字段

原因：

- 当前仓库对停牌的处理更多依赖运行时 `suspend_d` 辅助判断，而不是稳定持久的 `stocks` 正式字段。

### 4.2 对象二：d7_trading_day_status

对象粒度：

- 一条记录对应一个目标日期的交易日状态视图

主键：

- `target_date`

当前仓库来源：

- 主消费路径：`trading_day_view()`
- 底层依赖：`trading_calendar_cache` / `trading_calendar` / `trading_calendar_meta`
- 回退路径：`var/ledgers/trading_calendar/trading_calendar.json`

字段契约：

| 正式字段 | 当前来源 | 必填性 | 说明 |
| --- | --- | --- | --- |
| `target_date` | `trading_day_view().target_date` | 必填 | 被查询日期 |
| `is_trading_day` | `trading_day_view().is_trading_day` | 条件必填 | 是否交易日；覆盖不足时允许未知 |
| `nearest_trading_day` | `trading_day_view().nearest_trading_day` | 可空 | 最近不晚于目标日的交易日 |
| `min_trading_day` | `trading_day_view().min_trading_day` | 可空 | 当前缓存覆盖起点 |
| `max_trading_day` | `trading_day_view().max_trading_day` | 可空 | 当前缓存覆盖终点 |
| `calendar_covered_until` | `trading_day_view().calendar_covered_until` | 可空 | 当前日历覆盖上界 |
| `calendar_source` | `trading_day_view()._meta.calendar_source` | 必填 | 当前判定所依据的日历来源 |

字段边界说明：

- `d7_trading_day_status` 是正式视图对象，不等同于单一底层表。
- 首批必须承认它当前是“运行主消费面”，但不是“完全独立权威源”。
- 当覆盖不足时，`is_trading_day` 允许为未知；此时下游不能假装它等于 `False`。

### 4.3 D7 首批禁止事项

以下内容不应在首批文档中写成已冻结正式能力：

- 全量证券主数据体系
- 完整停复牌历史真值链
- 独立于 `D1` 的完全自治交易日历工程
- 任意未来可能有用但当前未稳定消费的映射字段

## 5. D8 最小正式派生对象

### 5.1 对象定义

首批正式对象名建议为：`pf1_trading_profile`

对象粒度：

- 一条记录对应一只股票在一个观察日期上的最小交易活跃度与近端强度派生画像

主键：

- `stock_code`
- `as_of_trade_date`

上游依赖：

- `d1_daily_price_fact`
- `d7_trading_day_status`

当前仓库来源：

- `apps/api/main.py` 中的 `signals["trading_profile"]`

### 5.2 正式字段契约

| 正式字段 | 当前来源 | 必填性 | 说明 |
| --- | --- | --- | --- |
| `stock_code` | 上下文股票代码 | 必填 | 个股标识 |
| `as_of_trade_date` | `trading_profile.latest_trade_date` 的正式化替代 | 必填 | 本次画像对应的观察交易日 |
| `latest_amount` | `trading_profile.latest_amount` | 可空 | 最近交易日成交额 |
| `avg_amount_5d` | `trading_profile.avg_amount_5d` | 可空 | 近 5 个交易日平均成交额 |
| `avg_amount_20d` | `trading_profile.avg_amount_20d` | 可空 | 近 20 个交易日平均成交额 |
| `latest_turnover` | `trading_profile.latest_turnover` | 可空 | 最近交易日换手率 |
| `avg_turnover_5d` | `trading_profile.avg_turnover_5d` | 可空 | 近 5 个交易日平均换手率 |
| `median_turnover_20d` | `trading_profile.median_turnover_20d` | 可空 | 近 20 个交易日换手率中位数 |
| `return_20d` | `trading_profile.return_20d` | 可空 | 近 20 个交易日收益率 |
| `avg_pct_change_5d` | `trading_profile.avg_pct_change_5d` | 可空 | 近 5 个交易日日涨跌幅均值 |
| `positive_days_5d` | `trading_profile.positive_days_5d` | 可空 | 近 5 个交易日上涨天数 |

### 5.3 派生规则收口

首批正式契约必须把窗口语义写清楚：

- `5d` 字段只在可确认拿到 5 个交易日样本时产生正式值，否则为 `null`
- `20d` 字段只在可确认拿到 20 个交易日样本时产生正式值，否则为 `null`
- `return_20d` 的正式语义是“观察日相对 20 交易日前基准收盘价的收益率”，而不是“任意可得窗口收益率”

说明：

- 当前运行代码已具备这些字段的原型计算路径
- 但正式契约必须收紧窗口充足性，防止 partial window 被误消费为正式 5 日/20 日语义

### 5.4 当前明确不纳入契约的支撑字段

以下字段当前不进入首批正式业务派生字段集合：

- `latest_trade_date`
- `rows_20d`

原因：

- 它们更适合作为调试/支撑元信息
- 不应与正式业务派生特征混写

### 5.5 D8 首批禁止事项

以下对象一律不进入首批 `D8`：

- `theme_momentum`
- `market_phase`
- `sector_rotation`
- `stock_tiering`
- `factor_matrix`
- `config_leader_candidate`
- `institutional_attention_candidate`
- `trading_leader_candidate`

统一原因：

- 它们已经包含排序、分类、分层、评分或候选判断语义
- 它们属于分析层、识别层或 proto-决策层，不属于 `M1` 事实层

## 6. 首批消费规则

`M2/M3` 首批消费 `M1` 时，必须遵守以下规则：

1. `D1` 缺少 `close_price` 或目标交易日数据不存在时，不得伪造行情对象继续消费。
2. `D7` 若 `is_trading_day` 为未知，不得静默按非交易日处理。
3. `D8` 若窗口不足导致字段为 `null`，下游只能识别为“证据不足”，不能拿分析层输出回填。
4. 首批 `M2/M3` 不得直接绕过本文对象去消费 `factor_matrix`、`market_phase` 或 candidate tags。

## 7. 当前已知实现缺口

本文定义的是首批正式契约，不等于代码已全部满足。

当前仍存在的实现缺口包括：

- 正式对象 schema 尚未独立落盘
- `D8` 当前原型路径对 partial window 的处理仍需按正式契约收紧
- `D7` 中“可交易/停牌”尚未形成完全稳定的持久化正式字段链
- `M2/M3` 仍未切换为只消费本文对象

## 8. 最终冻结结论

`Phase 1` 的首批正式契约冻结为：

- `D1`：`d1_daily_price_fact`
- `D7`：`d7_security_master_minimal` + `d7_trading_day_status`
- `D8`：`pf1_trading_profile`

冻结同时附带以下硬边界：

- `D1` 只承诺当前真实主链稳定供给到的日线事实
- `D7` 只承诺当前运行真正消费到的最小主数据与交易日状态
- `D8` 只承诺 primitive derived facts
- 所有高阶分析对象全部留在 `M1` 正式契约之外
