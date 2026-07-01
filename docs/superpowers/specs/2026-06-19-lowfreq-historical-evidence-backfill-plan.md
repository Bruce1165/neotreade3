# 低频回测历史证据补齐实施计划

日期：2026-06-19  
对应设计：`docs/superpowers/specs/2026-06-19-lowfreq-historical-evidence-backfill-design.md`

## 1. 目标

按已确认设计，优先补齐低频正式买入主链与 18 个月长窗回测所依赖的历史证据数据，并修正财报在回测中的可见时点：

- 先恢复配置证据链：
  - `fund_portfolio`
  - `etf_basic`
  - `etf_index`
  - `index_weight`
- 再修正：
  - `financial_reports` 的公告时点可见性
- 最后补：
  - `research_reports`
  - `report_consensus`
  - `institutional_surveys`

本计划不直接修改买入评分逻辑，不在本轮直接扩大旧收敛层清理范围。

## 2. 当前落地约束

### 2.1 已有可复用能力

- 当前已有统一 Tushare 市场数据同步入口：
  - `BootstrapApiService.sync_tushare_market_data_view(...)`
- 已支持资源：
  - `fund_portfolio`
  - `etf_basic`
  - `etf_index`
  - `index_weight`
  - `research_reports`
  - `report_consensus`
  - `institutional_surveys`
- 当前已有财报同步入口：
  - `BootstrapApiService.financial_reports_update_tushare_view(...)`
- 当前已有数据状态检查入口：
  - `GET /api/data/status`
- 当前已有表结构与 upsert 逻辑：
  - `fund_portfolios`
  - `etf_basic_info`
  - `etf_index_basic`
  - `index_weights`
  - `financial_reports`

### 2.2 当前缺口

- 配置证据链历史覆盖严重不足：
  - `fund_portfolios` 仅单日
  - `index_weights` 为空
  - `etf_basic_info` 为空
  - `etf_index_basic` 为空
- `financial_reports` 当前按 `report_date` 使用，不能反映公告可见性。
- 当前没有“低频回测专用”的执行顺序与验收清单，只有偏市场情报视角的基础回补文档。

## 3. 实施原则

- 先恢复影响 `focus gate` 的配置证据链，再动增强项。
- 每一类资源都先 `dry_run`，后真实落库。
- 每一阶段都必须回看：
  - `/api/data/status`
  - SQLite 时间范围
  - distinct code/symbol 覆盖
- 财报修正不做“查询层临时兜底补丁”，而是以可回放、可解释为目标。
- 在数据链恢复前，不把长窗交易稀疏继续归咎于旧链路。

## 4. 实施分解

### Phase 1：建立基线与索引清单

目标：
- 固化当前数据基线，并产出后续 `index_weight` 所需的指数代码清单。

任务：
- 记录当前数据状态：
  - `/api/data/status`
  - SQLite 覆盖范围
- 从已补齐或待补齐的 ETF 基础映射中整理：
  - 需要回补的 `index_code` 列表
- 明确回测窗口：
  - `2024-12-18 ~ 2026-06-18`
- 明确缓冲策略：
  - 向前至少多保留一个季度或同等公告缓冲

完成判定：
- 有一份明确的基线快照
- 有一份待执行的 `index_code` 清单

### Phase 2：配置证据链 dry-run

目标：
- 确认各资源真实可拉取，避免直接落库后才发现空返回或过滤范围错误。

任务：
- 对以下资源逐类执行 `dry_run=true`：
  - `etf_basic`
  - `etf_index`
  - `fund_portfolio`（按 `period` / `ann_date` 分片）
  - `index_weight`
- 记录：
  - `rows_prepared`
  - `sample`
  - `adapter_last_code`
  - `adapter_last_msg`

完成判定：
- 各资源 dry-run 能返回非零准备行
- `index_weight` 的资源调用参数与索引代码列表匹配
- `fund_portfolio` 已确认不能只依赖 `start_date/end_date`
- `fund_portfolio` 的季度 / 公告日分片策略已验证可用

### Phase 3：配置证据链真实落库

目标：
- 让 `focus gate` 依赖的 ETF / 基金配置 / 指数证据在长窗内可用。

任务：
- 依顺序真实落库：
  1. `etf_basic`
  2. `etf_index`
  3. `fund_portfolio`（按 `period` / `ann_date` 分片）
  4. `index_weight`
- 每类完成后立即验证：
  - `/api/data/status`
  - `MIN(date) / MAX(date)`
  - `COUNT(*)`
  - `COUNT(DISTINCT code/symbol)`

完成判定：
- `fund_portfolios` 不再是单日数据
- `etf_basic_info` 非空
- `etf_index_basic` 非空
- `index_weights` 非空且覆盖回测窗口

### Phase 4：财报公告时点修正设计落地

目标：
- 将财报可见性从“报告期末日”修正为“公告可见日”。

任务：
- 为 `financial_reports` 扩展公告日期字段
- 确定同步来源中可用的公告日期字段映射
- 调整读取逻辑：
  - 从 `report_date <= target_date`
  - 改为 `ann_date <= target_date`
- 明确历史缺失公告日时的兜底策略与可视化说明

完成判定：
- 公告前交易日不能读到对应财报
- 公告后交易日能读到对应财报

### Phase 5：机构关注增强项补齐

目标：
- 恢复 `attention_score` 的历史连续性，但不抢占主链配置证据优先级。

任务：
- 逐类 `dry_run` 与真实落库：
  - `research_reports`
  - `report_consensus`
  - `institutional_surveys`

完成判定：
- 三类资源均有早于 `2026-05` 的历史覆盖

### Phase 6：长窗重跑与归因确认

目标：
- 在数据证据链恢复后，重新判断交易稀疏到底来自数据缺口还是旧收敛层。

任务：
- 重跑 `2024-12-18 ~ 2026-06-18` 长窗回测
- 对比：
  - 当前结果
  - 数据补齐后结果
- 重点观察：
  - 交易数
  - 交易时间分布
  - `focus gate` 通过数与最终成交数的落差

完成判定：
- 可以明确给出“下一轮旧链路清理”是否需要扩大尺度

## 5. 代码与数据变更清单

本计划预期涉及：

- 修改：
  - `apps/api/main.py`
  - 如需财报字段扩展，可能涉及数据表结构定义与同步逻辑
- 使用现有接口：
  - `sync_tushare_market_data_view(...)`
  - `financial_reports_update_tushare_view(...)`
- 验证对象：
  - `var/db/stock_data.db`
  - `/api/data/status`

## 6. 测试与验收

### 6.1 数据状态验收

- `fund_portfolios`：
  - `MIN(ann_date)` 早于回测起点
  - `MAX(ann_date)` 覆盖回测终点附近公告
- `index_weights`：
  - 非空
  - 时间范围覆盖回测窗口
- `etf_basic_info / etf_index_basic`：
  - 非空
- `financial_reports`：
  - 具备公告可见性字段或等效机制

### 6.2 业务验收

- `focus gate` 不再长期因配置证据空缺而整体失效
- 长窗交易不再只集中在 `2026-05 ~ 2026-06`
- 数据补齐后可以清晰判断旧收敛层是否仍是主瓶颈

## 7. 风险与控制

### 风险 1：`index_weight` 资源并非全市场一键补齐

控制：
- 在执行前明确 `index_code` 清单
- 先做 dry-run 再落库

### 风险 2：财报时点修正只改查询，不改数据语义

控制：
- 不接受只在读取层做“模糊兜底”
- 必须让表结构与同步结果体现公告可见性

### 风险 3：补齐数据后仍误判问题来源

控制：
- 数据补齐完成后先重跑长窗
- 再决定旧收敛层清理尺度

## 8. 成功标准

- 低频正式买入主链依赖的历史证据链在长窗内连续可用
- 财报在回测中的可见性符合公告时点
- 长窗重跑后，旧链路清理可以基于完整证据推进，而不是基于缺数窗口做放宽判断
