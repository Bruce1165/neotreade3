# 2026-07-07 M1 Phase 1 Formal Objects Handoff

## 1. 这份文档的用途

本 handoff 只服务于 `M1 Phase 1` 首批正式对象实现态续接。

目标：

- 让新会话或新 agent 直接恢复本轮实现边界
- 明确当前已经落地到哪一层
- 明确哪些对象仍不能宣称为正式产物
- 明确下一步该从哪里继续，而不是重新做设计审计

## 2. 当前工作范围

当前已经完成并进入实现态的范围仅限：

- `M1`
- `Phase 1`
- `D1 / D7 / D8`

更具体地说，只覆盖以下首批正式对象：

- `d1_daily_price_fact`
- `d7_security_master_minimal`
- `d7_trading_day_status`
- `pf1_trading_profile`

当前不在本轮实现范围内：

- `M2 small_cycle` 正式对象
- `M3 identify_state / tracking_state / entry_state / hold_state / exit_state`
- `D2-D6`
- 高阶分析对象迁入 `M1`

## 3. 已确认边界

以下边界已经确认，不应在新会话里重新漂移：

1. `D1` 的真实主链已经可正式冻结：
   - `launchd -> update_daily_prices_authoritative -> daily_pipeline_run_view() -> update_daily_prices_authoritative_view() -> daily_prices`
2. `D7` 当前可正式消费，但不是完全独立权威源：
   - 当前运行主消费面是 `trading_calendar_cache`
   - 覆盖不足时可回退到 ledger
   - 其形成过程仍与 `D1` 高度耦合
3. `D8` 首批只允许 primitive derived facts，不允许高阶分析语义混入
4. `theme_momentum`、`market_phase`、`sector_rotation`、`stock_tiering`、`factor_matrix`、candidate tags 都不属于首批 `M1`
5. `D8` 的 5 日/20 日窗口必须严格语义化：
   - 样本不足返回 `null`
   - 不允许 partial window 冒充正式窗口值

## 4. 已落地代码位置

### 4.1 正式对象层

- `neotrade3/data_control/contracts.py`
- `neotrade3/data_control/projections.py`
- `neotrade3/data_control/quality.py`
- `neotrade3/data_control/__init__.py`

### 4.2 API 正式读取层

- `apps/api/main.py`
- `apps/api/router.py`

当前正式入口：

- `GET /api/data-control/m1/d1/daily-price-facts?date=YYYY-MM-DD`
- `GET /api/data-control/m1/d7/security-master?codes=...`
- `GET /api/data-control/m1/d7/trading-day-status?date=YYYY-MM-DD`
- `GET /api/data-control/m1/d8/trading-profiles?date=YYYY-MM-DD`

当前四个正式入口都会返回：

- `quality_status`
- `freshness_proof`
- `attention_items`
- `_meta.formal_object`

### 4.3 Data Control 运行产物层

- `neotrade3/data_control/pipeline.py`

当前 `capture / compose / publish` 的 ledger / artifact 已写入：

- `m1_formal_artifacts.catalog`
- `m1_formal_artifacts.objects`
- `m1_formal_artifacts.summary`

### 4.4 Worker 汇总层

- `apps/worker/main.py`

当前 `BootstrapWorkerApp._load_data_control_stage_summary()` 已将：

- `m1_formal_artifacts.summary`

带入：

- `snapshot["data_control"]["stage_summary"]`

### 4.5 最小治理消费层

- `neotrade3/issue_center/collector.py`
- `neotrade3/orchestration/preflight.py`

当前行为：

- `IssueCenterCollector.collect()` 可消费 `data_control.stage_summary`
- `PreflightRunner.build_report()` 已新增 `m1_formal_contract_check`

## 5. 当前运行语义

### 5.1 API 总览边界

`/api/data-control` 当前已显式暴露：

- `m1_formal_contracts`
- `compatibility_boundaries`

其含义是：

- 正式消费入口已经切到 `/api/data-control/m1/...`
- 旧接口如 `/api/signals`、`/api/market-phase`、`/api/sector-rotation`、`/api/stock-tiering`、`/api/factor-matrix/daily` 只保留兼容读取语义
- 新逻辑不应继续把这些旧接口当作首批正式对象真相源

### 5.2 Freshness / Attention 语义

首批正式对象当前统一暴露：

- `quality_status`
- `freshness_proof`
- `attention_items`

其中：

- `not_ready / unknown` 是强退化信号
- `partial` 是弱退化信号
- `attention_count > 0` 说明当前正式对象已有结构化问题暴露

### 5.3 Preflight 语义

`m1_formal_contract_check` 当前规则：

- 如果当日还没有 `data_control` 产物，不阻塞首次运行
- 如果当日已有 `data_control` 产物：
  - `not_ready / unknown` -> `failed`
  - `partial` -> `warning`
  - 全 `ready` -> `passed`

## 6. 当前仍未完成的部分

以下内容仍未完成，不应误表述为“已实现”：

1. `M2` 正式对象切换到只消费 `/api/data-control/m1/...`
2. `M3` 正式对象切换到只消费 `/api/data-control/m1/...`
3. `Attention Item` 与 `Freshness Proof` 的跨层升级策略（例如进入更正式的治理台账）
4. `PROJECT_STATUS.md` 之外更完整的 `docs/handoffs/` 系列收口与提交
5. 当前实现尚未提交，仍处于 working tree 状态

## 7. 已有验证

当前已新增并通过聚焦测试：

- `tests/unit/test_m1_phase1_formal_objects.py`

最近一次验证结果：

- `python3 -m pytest -q tests/unit/test_m1_phase1_formal_objects.py` -> `8 passed`
- `python3 -m py_compile ...` 已通过本轮涉及文件语法校验

## 8. 新会话续接建议

如果新会话继续推进本条实现链，建议顺序如下：

1. 先读：
   - `CLAUDE.md`
   - `PROJECT_STATUS.md`
   - 本文件
2. 再读：
   - `docs/superpowers/specs/2026-07-07-m1-phase0-repo-audit.md`
   - `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md`
   - `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-implementation-plan.md`
   - `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-task-list.md`
3. 然后只从以下方向继续，不要重新发散：
   - 让 `M2/M3` 最小消费面切到正式 `M1`
   - 继续增强 `Freshness Proof` / `Attention Item` 的治理语义
   - 在确认边界后再考虑提交

## 9. 一句话提醒

当前最重要的事实不是“图纸已全”，而是：

- `M1 Phase 1` 首批正式对象已经从文档态进入实现态
- 但系统仍未进入 `M2/M3` 的正式消费切换阶段
- 所以后续工作重点应是“消费切换与边界固化”，而不是重新定义 `M1`
