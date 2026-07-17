Status: Approved
Owner: market_intelligence
Scope: market_intelligence recent-N-day windows use DB as-of date
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-17-market-intelligence-window-asof-date-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-17

# Market Intelligence Recent-Window As-Of Date

## 背景

`_load_market_intelligence_for_stocks` 在生成 signals 的统计项时，使用 SQLite 的 `DATE('now', '-N day')` 作为“最近 N 天”窗口的基准日。

在 DB 数据不是实时更新、或单测使用历史固定日期数据时，这会导致窗口统计不稳定（例如 announcements 的 `recent_30d_count` 可能因为当前系统日期变化而变成 0）。

## 目标

- “最近 N 天”窗口以 DB 的最新可用日线日期作为基准，从而让离线 DB / 单测语义稳定。
- 仅当 DB 缺少 `daily_prices`（或无有效 `trade_date`）时，才回退到 SQLite `DATE('now')`。

## 非目标

- 不改变 `latest` 列表项的排序/选取逻辑。
- 不改变 signals 的字段结构。

## 设计

### asof_date

- `asof_date = MAX(daily_prices.trade_date)`（限定在请求的 `stock_codes` 范围内）
- 若 `asof_date` 不存在：
  - `asof_date = DATE('now')`

### recent windows

将以下统计从 `DATE('now', '-N day')` 改为基于 `asof_date`：

- announcements：`recent_30d_count`
- research_reports：`recent_90d_count` 与 `distinct_institutions_90d`
- institutional_surveys：`recent_180d_count` 与 `distinct_orgs_180d`

SQL 形态示例：

- `DATE(publish_date) >= DATE(?, '-30 day')`
- `DATE(trade_date) >= DATE(?, '-90 day')`
- `DATE(surv_date) >= DATE(?, '-180 day')`

参数 `?` 传入 `asof_date`。

## 测试

目标用例：`test_load_market_intelligence_for_stock_summarizes_new_tables`

- DB 内日线最新日期为 `2026-06-13`
- announcements publish_date 为 `2026-06-13`
- 期望 `recent_30d_count == 1`
