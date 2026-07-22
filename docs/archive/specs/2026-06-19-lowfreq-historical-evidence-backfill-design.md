# 低频回测历史证据补齐设计（设计定稿）

日期：2026-06-19  
范围：低频正式买入主链与 18 个月历史回测所依赖的 ETF / 基金配置 / 指数成分 / 财报可见性数据

## 1. 背景与目标

- 当前低频买入主链已经接入：
  - 第二大类硬科技 / AI / 渗透率重点赛道
  - ETF / 指数 / 基金配置证据
  - 5 日买入信号记忆窗口
  - 放宽后的候选收敛层
- 但 18 个月长窗回测结果仍只产生 `5` 笔交易，且交易集中在 `2026-05 ~ 2026-06`。
- 现有证据表明，当前问题不只来自旧收敛层，也来自历史证据覆盖不足，导致新逻辑在长窗大部分区间无法完整生效。

目标：
- 补齐低频回测所需的历史证据数据，而不是只补市场情报展示所需数据。
- 让 `focus gate` 中的 ETF / 指数 / 基金配置证据在 18 个月窗口内具备连续历史可用性。
- 修正财报在回测中的可见时点，避免把季末数据当成季末当日即可见。
- 为后续“清理旧链路、让新逻辑全面生效”提供可归因的历史数据基础。

## 2. 当前证据

基于当前真实库 `var/db/stock_data.db` 的时间覆盖检查，现状如下：

- `daily_prices`
  - 覆盖：`2024-09-02 ~ 2026-06-18`
  - 结论：足以支撑本轮回测窗口。
- `financial_reports`
  - 覆盖：`2024-03-31 ~ 2026-03-31`
  - 结论：覆盖存在，但当前仅按 `report_date` 使用，不等同于公告时点可见。
- `fund_portfolios`
  - 覆盖：仅 `2026-04-22`
  - 结论：远不足以支撑 18 个月窗口。
- `index_weights`
  - 覆盖：`0` 行
  - 结论：当前指数成分证据实际上不可用。
- `etf_basic_info`
  - 覆盖：`0` 行
  - 结论：当前无法稳定识别基金持仓中的 ETF。
- `etf_index_basic`
  - 覆盖：`0` 行
  - 结论：ETF 与指数映射底座缺失。
- `research_reports / report_consensus / institutional_surveys`
  - 覆盖仅从 `2026-05 ~ 2026-06`
  - 结论：可作为增强项，但不足以支撑整段长窗解释。

## 3. 问题归因

### 3.1 `focus gate` 依赖的配置证据链并未完整历史化

- 当前 `focus gate` 的关键判断来自：
  - `fund_portfolios`
  - `etf_basic_info`
  - `index_weights`
- 这些值共同形成：
  - `holder_fund_count`
  - `holder_etf_count`
  - `index_count`
  - `config_score`
  - `fund_config_evidence`
  - `etf_index_evidence`
- 代码读取逻辑本身已经按历史时点取最近可见值：
  - `fund_portfolios` 按 `ann_date <= target_date`
  - `index_weights` 按 `trade_date <= target_date`
- 当前问题不是“代码不会按历史时点用”，而是“真实库里缺少可用的历史数据”。

### 3.2 财报覆盖存在，但可见性口径不严格

- 当前 `financial_reports` 的读取逻辑按 `report_date <= target_date` 取最近财报。
- 同步逻辑中，`report_date` 表示财报期末日，而不是公告披露日。
- 因此当前回测可能在季末后过早使用了后验可见的财务数据。

### 3.3 注意力增强项不是当前第一瓶颈

- `research_reports / report_consensus / institutional_surveys` 主要进入 `attention_score`。
- 当前 `attention_score` 已降为参考项，不再是硬门槛。
- 因此它们应该补，但优先级低于配置证据链。

## 4. 方案比较

### 4.1 方案 A：只补市场情报增强项

- 先补：
  - `research_reports`
  - `report_consensus`
  - `institutional_surveys`

优点：
- 操作简单。
- 对市场情报展示链路也有收益。

缺点：
- 不能解决当前 `focus gate` 的核心证据缺口。
- 对“为什么 18 个月只有 5 笔交易”解释力不足。

### 4.2 方案 B：优先补配置证据链，再修财报时点

- 先补：
  - `fund_portfolio`
  - `etf_basic`
  - `etf_index`
  - `index_weight`
- 再修：
  - `financial_reports` 的公告可见性
- 最后补：
  - `research_reports`
  - `report_consensus`
  - `institutional_surveys`

优点：
- 与当前低频主链的核心问题最匹配。
- 能最大程度提高长窗回测的解释力。
- 有利于后续判断旧链路是否真的还过紧。

缺点：
- 执行复杂度高于只补市场情报增强项。

### 4.3 方案 C：先清理旧链路，不先补历史数据

- 暂不补历史数据。
- 先继续放宽或拆除旧收敛层。

优点：
- 最快看到交易数变化。

缺点：
- 极易把数据缺口误判为模型问题。
- 长窗结果无法可靠归因。

结论：
- 本次采用方案 B。

## 5. 设计原则

- 不用“补齐所有可拿到的数据”作为目标，而只补当前低频主链真正依赖的数据。
- 数据补齐优先服务低频回测与正式买入主链，而不是先服务市场情报展示页。
- 一切历史数据都要以“目标交易日之前可见”为准。
- 在数据链未恢复前，不继续扩大旧链路清理范围。
- 每补完一个阶段，都需要重新校验 `GET /api/data/status` 与数据库覆盖范围。

## 6. 数据补齐设计

### 6.1 P0：配置证据链

#### `fund_portfolio -> fund_portfolios`

目的：
- 恢复 `holder_fund_count / holder_etf_count / total_mkv / avg_ratio`。

时间范围：
- 至少覆盖 `2024-12-18 ~ 2026-06-18` 的全部公告窗口。
- 为避免回测起点取不到最近一期，建议向前再留一个季度缓冲。

执行方式：
- 走统一入口 `sync_tushare_market_data_view(resource="fund_portfolio")`。
- 但该资源不能仅按 `start_date/end_date` 直接全量拉取。
- Tushare 侧要求至少提供：
  - `ts_code`
  - `ann_date`
  - `period`
  之一。
- 因此实际执行按“季度 / 公告日批次”分片：
  - 优先按 `period` 回补回测窗口相关报告期
  - 必要时按 `ann_date` 补回缺失批次
- 先 `dry_run=true`，再真实落库。

验收：
- `fund_portfolios` 的 `MIN(ann_date)` 早于回测起点。
- `MAX(ann_date)` 不早于回测终点附近最近一次公告。
- `COUNT(DISTINCT symbol)` 显著大于当前值。

#### `etf_basic -> etf_basic_info`

目的：
- 识别基金持仓中哪些 `ts_code` 属于 ETF。

执行方式：
- 走统一入口 `sync_tushare_market_data_view(resource="etf_basic")`。

验收：
- `etf_basic_info` 非空。
- ETF 基础表能覆盖后续 `fund_portfolios.ts_code` 的主样本。

#### `etf_index -> etf_index_basic`

目的：
- 建立 ETF 与指数映射底座，为后续指数成分回补提供范围依据。

执行方式：
- 走统一入口 `sync_tushare_market_data_view(resource="etf_index")`。

验收：
- `etf_index_basic` 非空。
- 核心 ETF 具备可关联的指数信息。

#### `index_weight -> index_weights`

目的：
- 恢复 `index_count`，让 ETF / 指数证据分支真正可用。

执行方式：
- 按 `index_code` 分批调用 `sync_tushare_market_data_view(resource="index_weight")`。
- `index_code` 清单来自：
  - `etf_index_basic`
  - 必要时补充低频主线相关宽基 / 行业指数代码

验收：
- `index_weights` 非空。
- `MIN(trade_date)` 早于回测起点。
- `MAX(trade_date)` 覆盖到回测终点附近。

### 6.2 P1：财报公告时点修正

目标：
- 让财报在回测中按“公告可见日”而不是“报告期末日”进入主链。

设计：
- 为 `financial_reports` 增加公告日期字段。
- 同步逻辑保留 `report_date`，但新增并维护 `ann_date`。
- 读取逻辑从：
  - `WHERE report_date <= target_date`
- 改为：
  - `WHERE ann_date <= target_date`
  - 若 `ann_date` 缺失，再按明确兜底规则处理，且需在结果中可见化。

验收：
- 任意季度财报在公告前交易日不可被回测读取。
- 任意季度财报在公告后交易日可被回测读取。

### 6.3 P2：机构关注增强项

资源：
- `research_reports`
- `report_consensus`
- `institutional_surveys`

目标：
- 恢复 `attention_score` 的历史连续性。

说明：
- 这一层不是当前硬门槛，不应抢占配置证据链优先级。

## 7. 执行顺序

### 7.1 第一步：状态快照

- 调用 `GET /api/data/status`
- 记录：
  - `sources.etf_basic_info`
  - `sources.etf_index_basic`
  - `sources.index_weights`
  - `sources.fund_portfolios`
  - `sources.financial_reports`

### 7.2 第二步：配置证据链 dry-run

- 依次 dry-run：
  - `etf_basic`
  - `etf_index`
  - `fund_portfolio`（按 `period` / `ann_date` 分片）
  - `index_weight`

要求：
- 每类 dry-run 都记录：
  - `rows_prepared`
  - `sample`
  - `adapter_last_code`
  - `adapter_last_msg`
- 对 `fund_portfolio` 额外确认：
  - 不能只用 `start_date/end_date`
  - 季度 / 公告日分片策略可以返回非零样本

### 7.3 第三步：真实落库

- 在 dry-run 成功后，按同顺序真实落库。
- 建议实际顺序：
  - `etf_basic`
  - `etf_index`
  - `fund_portfolio`（按 `period` / `ann_date` 分片）
  - `index_weight`
- 每一类完成后立即回查数据状态和 SQLite 范围。

### 7.4 第四步：财报时点修正

- 完成表结构与读取逻辑设计后，再执行一次财报同步或重建。

### 7.5 第五步：补机构关注增强项

- 作为第二优先级执行。

### 7.6 第六步：重跑 18 个月回测

- 只有在 P0 与财报时点修正完成后，才重新评估旧链路清理尺度。

## 8. 验收口径

### 8.1 数据覆盖验收

- `fund_portfolios` 非单日数据。
- `index_weights` 非空且覆盖回测窗口。
- `etf_basic_info / etf_index_basic` 非空。
- `financial_reports` 能按公告时点回放。

### 8.2 业务验收

- `focus gate` 在 `2024-12 ~ 2026-04` 这段不再因配置证据整体缺失而长期失效。
- 长窗回测结果不再高度集中于 `2026-05 ~ 2026-06`。
- 后续若交易数仍显著偏低，才能把问题继续归因到旧收敛层。

## 9. 风险与边界

- `index_weight` 资源是按 `index_code` 拉取，不是一次性全市场资源，执行时需要明确指数清单。
- 财报公告时点修正可能涉及表结构变更与旧数据回填，不能只做查询层补丁。
- 本设计不包含新的模型评分逻辑，也不直接放宽旧收敛层。
- 本设计不解决北向资金、龙虎榜、L2 等当前 `coverage_gaps` 未覆盖资源。

## 10. 成功标准

- 历史配置证据链在长窗内具备连续可用性。
- 财报在回测中的可见性与真实公告时点一致。
- 重新回测后，能够更清晰判断：
  - 交易稀疏主要是数据缺口导致
  - 还是旧收敛层仍然压制新逻辑
