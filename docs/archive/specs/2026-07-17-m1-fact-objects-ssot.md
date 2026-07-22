# M1 事实对象清单（单一真相源）

日期：2026-07-17

## 1. 范围与边界

本文件冻结并声明 `M1` 事实层的“正式输出对象（Formal Objects）”清单与命名，作为单一真相源（SSOT）。

边界：

- 本清单的“实现态正式对象”以 `apps/api/main.py` 的 `_m1_formal_contract_catalog()` 为准。
- 本清单不把底层数据库表结构直接等同于正式对象；正式对象以契约（contracts）与投影（projections）为准。
- 本清单仅冻结 `Phase 1` 已对外暴露的正式入口，不扩展到 `D2-D6` 的未来对象。

## 2. 命名体系

### 2.1 设计态分组（抽象命名）

`M1` 的正式输出对象分为四类：正式事实表（`F*`）、正式派生事实表（`PF*`）、数据质量状态（`Q*`）、任务契约状态（`T*`）。

证据：[2026-07-06-m1-fact-layer-design.md:L100-L145](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-06-m1-fact-layer-design.md#L100-L145)

### 2.2 实现态对象族（对外 contract family）

`Phase 1` 当前实现并对外提供只读 API 的对象族（object_family）如下：

- `d1_daily_price_fact`
- `d7_security_master_minimal`
- `d7_trading_day_status`
- `pf1_trading_profile`

证据（实现态清单）：[main.py:L16273-L16299](file:///Users/mac/NeoTrade3/apps/api/main.py#L16273-L16299)

## 3. Phase 1 正式对象清单（实现态冻结）

以下对象族为 `Phase 1` 正式对象的冻结清单；新增/移除必须以“更新本文件 + 更新 `_m1_formal_contract_catalog()` + 单测锁定”作为最小门禁。

### 3.1 d1_daily_price_fact

- 对外入口：`/api/data-control/m1/d1/daily-price-facts`
- 契约对象：`D1DailyPriceFact`
- 投影函数：`project_d1_daily_price_fact`
- 主来源表：`daily_prices`

证据：

- 对外入口与对象族清单：[main.py:L16273-L16299](file:///Users/mac/NeoTrade3/apps/api/main.py#L16273-L16299)
- 契约对象字段集合：[contracts.py:L9-L42](file:///Users/mac/NeoTrade3/neotrade3/data_control/contracts.py#L9-L42)
- 投影映射（`daily_prices.code`→`stock_code` 等）：[projections.py:L42-L56](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L42-L56)
- 来源表/列映射（文档契约）：[2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md:L38-L74](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md#L38-L74)

### 3.2 d7_security_master_minimal

- 对外入口：`/api/data-control/m1/d7/security-master`
- 契约对象：`D7SecurityMasterMinimal`
- 投影函数：`project_d7_security_master_minimal`
- 主来源表：`stocks`

证据：

- 对外入口与对象族清单：[main.py:L16273-L16299](file:///Users/mac/NeoTrade3/apps/api/main.py#L16273-L16299)
- 契约对象字段集合：[contracts.py:L45-L68](file:///Users/mac/NeoTrade3/neotrade3/data_control/contracts.py#L45-L68)
- 投影映射（`stocks.code/name/...`）：[projections.py:L59-L68](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L59-L68)
- 来源表映射（文档契约）：[2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md:L114-L139](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md#L114-L139)

### 3.3 d7_trading_day_status

- 对外入口：`/api/data-control/m1/d7/trading-day-status`
- 契约对象：`D7TradingDayStatus`
- 投影函数：`project_d7_trading_day_status`
- 底层依赖：`trading_calendar_cache` / `trading_calendar_meta`（以及运行路径 `trading_day_view()`）

证据：

- 对外入口与对象族清单：[main.py:L16273-L16299](file:///Users/mac/NeoTrade3/apps/api/main.py#L16273-L16299)
- 契约对象字段集合：[contracts.py:L71-L94](file:///Users/mac/NeoTrade3/neotrade3/data_control/contracts.py#L71-L94)
- 投影映射（含 `_meta.calendar_source`）：[projections.py:L71-L82](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L71-L82)
- 依赖边界（文档契约）：[2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md:L156-L188](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md#L156-L188)

### 3.4 pf1_trading_profile

- 对外入口：`/api/data-control/m1/d8/trading-profiles`
- 契约对象：`PF1TradingProfile`
- 投影函数：`project_pf1_trading_profile`
- 上游依赖：`d1_daily_price_fact`、`d7_trading_day_status`

证据：

- 对外入口与对象族清单：[main.py:L16273-L16299](file:///Users/mac/NeoTrade3/apps/api/main.py#L16273-L16299)
- 契约对象字段集合：[contracts.py:L97-L130](file:///Users/mac/NeoTrade3/neotrade3/data_control/contracts.py#L97-L130)
- 投影映射（窗口充足性与字段生成）：[projections.py:L85-L147](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L85-L147)
- 依赖边界（文档契约）：[2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md:L199-L245](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md#L199-L245)

## 4. 明确排除与兼容边界

以下内容在 `Phase 1` 只作兼容读取或明确排除，不属于 “M1 首批正式对象清单”：

- compatibility-only paths：`/api/signals`、`/api/market-phase`、`/api/sector-rotation`、`/api/stock-tiering`、`/api/factor-matrix/daily`
- explicit exclusions：`theme_momentum`、`market_phase`、`sector_rotation`、`stock_tiering`、`factor_matrix`、`config_leader_candidate`、`institutional_attention_candidate`、`trading_leader_candidate`

证据：[main.py:L16273-L16299](file:///Users/mac/NeoTrade3/apps/api/main.py#L16273-L16299)

## 5. 变更流程（新增一个正式对象族的最小门禁）

新增对象族必须同时满足：

1. 追加/修改本文件中的“实现态冻结清单”。
2. 在 `_m1_formal_contract_catalog()` 中加入 formal_entrypoints，并补充 compatibility/exclusions（如适用）。
3. 新增契约对象（contracts）与投影（projections）。
4. 补齐单测，锁定 object_family、端点、字段集与错误语义。
