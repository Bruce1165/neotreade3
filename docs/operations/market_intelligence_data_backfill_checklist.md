# Market Intelligence 缺失数据源补齐清单

日期：2026-06-15

## 1. 目的

- 本清单只解决一个问题：
  - 把当前 `market_intelligence` 所依赖、但尚未进入真实生产库的 4 类数据源补齐。
- 本清单不讨论：
  - 新的数据模型设计
  - 新的推荐规则设计
  - 建议层到执行层的桥接条件

## 2. 当前结论

- 当前仓库已经具备这 4 类资源的：
  - Tushare 适配器抓取能力
  - API 同步入口
  - SQLite 建表能力
  - upsert 落库能力
- 当前真实生产库 `var/db/stock_data.db` 仍未实际落入以下表：
  - `research_reports`
  - `report_consensus`
  - `institutional_surveys`
  - `fund_portfolios`
- 因此当前问题不是“代码做不到”，而是“同步尚未真正执行到生产库”。

## 3. 资源与落库映射

### 3.1 统一同步入口

- 当前统一同步入口：
  - `POST /api/data-control/sync-tushare-market-data`
- 请求体核心字段：
  - `resource`
  - `requested_by`
  - `filters`
  - `fields`（可选）
  - `dry_run`
  - `timeout_seconds`

### 3.2 资源名与落库表

- `research_reports`
  - 资源名：`research_reports`
  - 落库表：`research_reports`
- `report_consensus`
  - 资源名：`report_consensus`
  - 落库表：`report_consensus`
- `institutional_surveys`
  - 资源名：`institutional_surveys`
  - 落库表：`institutional_surveys`
- `fund_portfolio`
  - 资源名：`fund_portfolio`
  - 落库表：`fund_portfolios`

说明：
- `fund_portfolio` 是同步资源名。
- `fund_portfolios` 是实际 SQLite 表名。

## 4. 运行前提

在真正发起同步前，必须先确认以下两项：

### 4.1 Tushare Token 已配置

- 依赖环境变量：
  - `TUSHARE_TOKEN`
- 如果未配置，同步接口会返回：
  - `status=skipped`
  - `reason=tushare_token_not_configured`

### 4.2 目标数据库路径正确

- 当前默认目标库：
  - `var/db/stock_data.db`
- 如有特殊库路径，则依赖环境变量：
  - `NEOTRADE3_STOCK_DB_PATH`
- 如果库文件不存在，同步接口会返回：
  - `code=stock_db_not_ready`

## 5. 建议的最小补齐顺序

本次建议按以下顺序执行，而不是 4 类资源并行全量灌入：

1. `research_reports`
2. `report_consensus`
3. `institutional_surveys`
4. `fund_portfolio`

原因：
- 前三项更直接影响 `institutional_attention` 的形成。
- `fund_portfolio` 主要影响 `config_leader` 路径，可放在第二阶段补。
- 这样可以更快判断“机构关注路径”是否先恢复产出。

## 6. 每类资源的最小请求建议

以下请求都建议先 `dry_run=true`，确认返回正常后再落库。

### 6.1 `research_reports`

建议先拉最近 90 天：

```json
{
  "resource": "research_reports",
  "requested_by": "market-intelligence-backfill",
  "filters": {
    "start_date": "近90天起始日",
    "end_date": "目标结束日"
  },
  "dry_run": true,
  "timeout_seconds": 20
}
```

### 6.2 `report_consensus`

建议先拉最近 180 天：

```json
{
  "resource": "report_consensus",
  "requested_by": "market-intelligence-backfill",
  "filters": {
    "start_date": "近180天起始日",
    "end_date": "目标结束日"
  },
  "dry_run": true,
  "timeout_seconds": 20
}
```

### 6.3 `institutional_surveys`

建议先拉最近 180 天：

```json
{
  "resource": "institutional_surveys",
  "requested_by": "market-intelligence-backfill",
  "filters": {
    "start_date": "近180天起始日",
    "end_date": "目标结束日"
  },
  "dry_run": true,
  "timeout_seconds": 20
}
```

### 6.4 `fund_portfolio`

建议先拉最近 365 天披露范围，避免先猜“最新季度”：

```json
{
  "resource": "fund_portfolio",
  "requested_by": "market-intelligence-backfill",
  "filters": {
    "start_date": "近365天起始日",
    "end_date": "目标结束日"
  },
  "dry_run": true,
  "timeout_seconds": 20
}
```

说明：
- 这一步的目标不是一次就做完最优口径，而是先确认真实库能成功接入。
- 后续如要提效，再考虑按 `period` 或 `ann_date` 做更精细同步。

## 7. 最小执行顺序

### 7.1 第一步：确认数据状态

调用：

```text
GET /api/data/status
```

重点看：
- `sources.research_reports.exists`
- `sources.report_consensus.exists`
- `sources.institutional_surveys.exists`
- `sources.fund_portfolios.exists`
- `integration_readiness.tushare_token_configured`

### 7.2 第二步：逐类 dry-run

对每类资源先发：

```text
POST /api/data-control/sync-tushare-market-data
```

要求：
- `dry_run=true`
- 观察：
  - `status`
  - `rows_prepared`
  - `sample`
  - `adapter_last_code`
  - `adapter_last_msg`

判定：
- 若 `rows_prepared=0`，不要直接落库，先核对时间窗口或 Tushare 返回情况。
- 若 `status=skipped`，先解决 token 问题。

### 7.3 第三步：逐类真实落库

在对应 dry-run 成功后，再把同一请求改为：

```json
"dry_run": false
```

观察返回：
- `status`
- `rows_fetched`
- `rows_upserted`

### 7.4 第四步：回看数据状态

再次调用：

```text
GET /api/data/status
```

确认：
- 对应 `exists=true`
- `range.min_date / max_date` 已出现
- `distinct_codes` 或等价统计不为 0

## 8. 数据库级验证

除 API 验证外，建议同步后再做一次 SQLite 核对。

### 8.1 检查表是否存在

```bash
sqlite3 /Users/mac/NeoTrade3/var/db/stock_data.db ".tables"
```

应出现：
- `research_reports`
- `report_consensus`
- `institutional_surveys`
- `fund_portfolios`

### 8.2 检查时间范围与股票覆盖

示例 SQL：

```sql
SELECT MIN(trade_date), MAX(trade_date), COUNT(*), COUNT(DISTINCT ts_code) FROM research_reports;
SELECT MIN(report_date), MAX(report_date), COUNT(*), COUNT(DISTINCT ts_code) FROM report_consensus;
SELECT MIN(surv_date), MAX(surv_date), COUNT(*), COUNT(DISTINCT ts_code) FROM institutional_surveys;
SELECT MIN(ann_date), MAX(ann_date), COUNT(*), COUNT(DISTINCT symbol) FROM fund_portfolios;
```

## 9. 候选恢复验证

数据落库成功后，不应只停在“表有了”，还要验证业务输出是否恢复。

建议依次检查：

### 9.1 候选层覆盖

```text
GET /api/market-intelligence/candidates?top_n=20
```

重点看：
- `coverage.config_seed_codes`
- `coverage.attention_seed_codes`
- `coverage.trading_seed_codes`

目标：
- 不再只有 `trading_seed_codes > 0`

### 9.2 统一候选分布

```text
GET /api/market-intelligence/unified-candidates?top_n=60
```

重点看：
- `candidate_type_count >= 2` 是否开始出现
- `candidate_types` 是否不再被 `trading_leader` 单一路径垄断

### 9.3 建议层分布

```text
GET /api/market-intelligence/recommendations?top_n=20
```

重点看：
- 是否仍然是“全观察、无推荐”
- 是否开始出现由多角色共振支撑的更高置信候选

## 10. 风险提示

- 不建议 4 类资源直接无验证全量落库。
- 不建议在数据源补齐前继续微调建议层规则。
- 不建议在候选恢复验证前，推进“建议层桥接模拟执行层”。

## 11. 当前最小成功标准

本轮补齐工作完成，可按以下标准判断：

- `TUSHARE_TOKEN` 已配置且 dry-run 返回正常
- 4 类资源已至少完成一轮真实落库
- `GET /api/data/status` 能看到 4 张表的 `exists=true`
- `candidates / unified-candidates / recommendations` 不再表现为纯 `trading-only`

## 12. 一句话结论

- 当前不是缺设计，而是缺把现有同步能力真正跑进生产库。
- 正确顺序是：
  - 先 dry-run
  - 再分资源落库
  - 再做候选恢复验证
  - 最后才继续桥接层讨论
