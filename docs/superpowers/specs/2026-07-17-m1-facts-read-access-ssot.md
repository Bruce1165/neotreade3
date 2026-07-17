# M1 关键事实只读读取入口（单一真相源）

日期：2026-07-17

## 1. 范围与边界

本文件冻结并声明 `M1` Phase 1 “关键事实”的只读读取入口（对外 API 与内部稳定访问入口），以及其错误语义锚点，作为单一真相源（SSOT）。

边界：

- 本文件仅覆盖 Phase 1 的四个正式对象族：`d1_daily_price_fact`、`d7_security_master_minimal`、`d7_trading_day_status`、`pf1_trading_profile`。
- 本文件冻结的是“读取入口与错误语义锚点”，不扩展到数据同步写链路。

## 2. 对外只读 API（正式入口）

Phase 1 的正式读取入口由 router 分发到 `BootstrapApiService.m1_*_view` 系列 handler。

端点集合：

- `GET /api/data-control/m1/d1/daily-price-facts?date=YYYY-MM-DD[&codes=...][&limit=...]`
- `GET /api/data-control/m1/d7/security-master[?codes=...][&limit=...]`
- `GET /api/data-control/m1/d7/trading-day-status?date=YYYY-MM-DD`
- `GET /api/data-control/m1/d8/trading-profiles?date=YYYY-MM-DD[&codes=...][&limit=...]`

证据（路由分发）：[router.py:L1197-L1277](file:///Users/mac/NeoTrade3/apps/api/router.py#L1197-L1277)

证据（实现态对象族清单锚点）：[main.py:L16273-L16299](file:///Users/mac/NeoTrade3/apps/api/main.py#L16273-L16299)

## 3. 错误语义（对外）

### 3.1 参数校验（400）

- `date` 必填端点：`d1_daily_price_fact`、`d7_trading_day_status`、`pf1_trading_profile`，缺失或非 ISO 日期返回 400 `invalid_date`。

证据（router 参数校验）：[router.py:L1197-L1215](file:///Users/mac/NeoTrade3/apps/api/router.py#L1197-L1215)、[router.py:L1231-L1248](file:///Users/mac/NeoTrade3/apps/api/router.py#L1231-L1248)、[router.py:L1253-L1270](file:///Users/mac/NeoTrade3/apps/api/router.py#L1253-L1270)

### 3.2 依赖未就绪（503）

- stock db 不存在/不可用：503 `stock_db_not_ready`。
- 必需表列缺失：D1/D8 依赖 `daily_prices` 必需列缺失 → 503 `daily_prices_not_ready`；D7 依赖 `stocks` 必需列缺失 → 503 `stocks_not_ready`。

证据（handler 错误语义）：

- D1：stock db/required columns：[main.py:L16304-L16322](file:///Users/mac/NeoTrade3/apps/api/main.py#L16304-L16322)
- D7 security master：stock db/stocks columns：[main.py:L16406-L16423](file:///Users/mac/NeoTrade3/apps/api/main.py#L16406-L16423)
- D8：stock db/daily_prices columns：[main.py:L16543-L16567](file:///Users/mac/NeoTrade3/apps/api/main.py#L16543-L16567)

## 4. 内部稳定访问入口（engine 消费）

为低频引擎提供的内部读取入口为 `load_formal_m1_inputs(...)`，从 SQLite cursor 读取并返回稳定结构：

- `d1_by_code`
- `security_by_code`
- `trading_day_status`
- `history_by_code`

证据（facade 定义与返回结构）：[formal_input_adapter.py:L235-L253](file:///Users/mac/NeoTrade3/neotrade3/data_control/formal_input_adapter.py#L235-L253)

证据（engine 侧消费入口）：[formal_front.py:L14-L88](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L14-L88)

## 5. 变更流程（最小门禁）

变更“只读读取入口/错误语义”必须同时满足：

1. 更新本文件。
2. 更新 router 或 handler 的实现（如端点、参数校验、错误码）。
3. 补齐单测或端到端证据，锁定端点与错误语义不漂移。
