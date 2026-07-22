# Lowfreq M1 Formal Input Adapter Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m1-formal-input-adapter-design.md`

## 1. Goal

本计划只处理 `E2: 剥离 M1 formal input adapters` 的实现步骤。

本轮目标是：

- 新增一个只服务 formal 输入消费的 `M1 read-side consumer adapter` 模块
- 把 engine 当前直接拥有的 query/projection 细节迁移到该模块
- 让 `lowfreq_engine_v16_advanced.py` 只消费 adapter facade，而不再直接查询并投影 `M1` 输入底座
- 保持 `formal front`、`M3 nucleus`、`M1 owner contract` 与现有错误返回面不变

本轮不做：

- `_build_formal_front_chain_payload()` 的整体迁移
- `_attach_formal_front_payloads()` 的迁移
- `apps/api/main.py` 的 query/projection 去重
- `neotrade3/data_control/projections.py` 与 `contracts.py` 的 contract 改写
- `M2/M3/M6` 的任何实现调整

## 2. Starting Point

当前 engine 在同一文件内直接持有以下 helper：

- `_get_recent_price_history_for_formal_m1_batch()`
- `_get_formal_d1_facts_batch()`
- `_get_formal_security_master_batch()`
- `_build_formal_trading_day_status()`

它们被 `_build_formal_front_chain_payload()` 直接调用，随后进入：

- `project_pf1_trading_profile()`
- `build_m1_constraints_ref()`
- `build_small_cycle_from_m1()`
- `build_identify_state_from_formal_inputs()`
- `build_tracking_state_from_formal_inputs()`
- `build_entry_state_from_formal_inputs()`

根据已批准 design，本轮只移动前一段“formal 输入底座读取与投影适配”，后一段 `formal front` 装配仍留在 engine。

## 3. Implementation Strategy

采用以下策略：

- 新增文件：
  - `neotrade3/data_control/formal_input_adapter.py`
- 在该文件中收口：
  - batch query
  - raw payload 组装
  - `project_*` 调用
  - 对 engine 暴露的 facade：`load_formal_m1_inputs(...)`
- `lowfreq_engine_v16_advanced.py` 只做两类改动：
  - 引入新 facade
  - 将 `_build_formal_front_chain_payload()` 中原有四个 helper 调用改为单次 facade 调用
- 原有四个 helper 从 engine 中删除

## 4. Execution Steps

### E2-R1：冻结文件边界与输出面

实现前先锁定本轮允许改动的文件：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/formal_input_adapter.py`
- `tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`
- 如确有必要，补一份 `formal front` focused regression

同时冻结 adapter 对 engine 的输出面，只允许返回：

- `d1_by_code`
- `security_by_code`
- `trading_day_status`
- `history_by_code`

完成判定：

- 本轮不会把 `small_cycle / constraints / state` 一起吸入 adapter

### E2-R2：实现 `formal_input_adapter.py`

在新模块中实现：

- 私有 codes 规范化 helper
- `daily_prices` 的最近价格历史批量读取
- `D1` 批量读取与 `project_d1_daily_price_fact()` 投影
- `D7 security master` 批量读取与 `project_d7_security_master_minimal()` 投影
- `D7 trading day status` 的 raw payload 构造与 `project_d7_trading_day_status()` 投影
- 对外 facade：`load_formal_m1_inputs(...)`

实现要求：

- 输入仍使用 `sqlite3.Cursor`、`codes`、`target_date`
- 返回结构与 engine 当前消费面兼容
- 不在该模块内引入任何 `M3` 判断
- 不在该模块内组织 `formal front` 错误返回体

完成判定：

- adapter 文件自身就能完整表达“查询 + 投影 + 批量装配适配”

### E2-R3：切换 engine 到 facade

在 `lowfreq_engine_v16_advanced.py` 中：

- 引入 `load_formal_m1_inputs(...)`
- 将 `_build_formal_front_chain_payload()` 内：
  - `d1_by_code = ...`
  - `security_by_code = ...`
  - `trading_day_status = ...`
  - `history_by_code = ...`
  四段改成一次 facade 调用后的解包
- 保留现有 `try/except` 与错误返回结构
- 删除 engine 中被替代的四个 helper

明确禁止：

- 不修改 `_build_formal_front_chain_payload()` 的输出 shape
- 不修改 `project_pf1_trading_profile()` 之后的装配逻辑
- 不顺手改 `generate_buy_signals()` 或其他 `M3` 链路

完成判定：

- engine 不再直接拥有这组 SQL/projection 细节
- `formal front` 仍由 engine 负责

### E2-R4：补 focused tests

新增：

- `tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`

建议保护的最小场景：

- `load_formal_m1_inputs()` 在完整数据下返回四类输出
- `trading_day_status` 通过 `project_d7_trading_day_status()` 投影，不再依赖 engine 直接构造
- `history_by_code` 仍保持按 code 分桶、按 trade_date 倒序
- 空 `codes` 或非法 `limit` 时返回空结构

如 engine 侧仍需一份 focused regression，可二选一：

- 在 `tests/unit/test_lowfreq_engine_v16_signal_convergence.py` 中补最小断言
- 或新增一份只覆盖 `_build_formal_front_chain_payload()` 成功/失败面的 focused test

完成判定：

- adapter 有独立护栏
- `formal front` 消费结果仍有最小回归保护

### E2-R5：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_m1_phase1_formal_objects.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`

如新增或修改了 engine 侧 focused regression，再补跑对应测试文件。

并补充：

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/data_control/formal_input_adapter.py`

完成判定：

- `M1` owner contract 无回归
- adapter focused tests 通过
- 生产代码语法通过

### E2-R6：窄提交

提交前只允许暂存：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/formal_input_adapter.py`
- `tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`
- 本轮实际新增或改动的 engine focused regression 文件

必须排除：

- `apps/api/main.py`
- `neotrade3/data_control/projections.py`
- `neotrade3/data_control/contracts.py`
- `neotrade3/decision_engine/*`
- 其他任何既有工作区改动

## 5. Risks and Guards

风险 1：

- adapter 越界，把 `formal front` 或 `M3` 状态组装一起吸进去

保护：

- 对外输出面只允许四项：`d1_by_code / security_by_code / trading_day_status / history_by_code`

风险 2：

- `D7 trading day status` 迁移时改变现有语义

保护：

- 只允许把直接构造改成 `raw payload -> project_d7_trading_day_status()`
- 不修改 target_date、calendar_source、coverage 字段逻辑

风险 3：

- 顺手扩张到 `apps/api/main.py`，把本轮变成“共享读层大重构”

保护：

- API 去重明确排除；即使发现可复用，也留到后续单独切片

风险 4：

- 测试写成 formal object contract 的重复拷贝

保护：

- `test_m1_phase1_formal_objects.py` 继续守 owner；`E2` 新测试只守 adapter 返回结构和 engine 消费边界

## 6. Success Criteria

本轮完成后，应满足：

- engine 不再直接拥有 `M1` formal 输入底座的 query/projection 细节
- `formal front` 仍留在 engine，等待 `E3`
- `D7 trading day status` 的投影路径回到 `data_control.projections`
- 本轮改动可被一个窄提交完整表达

## 7. Commit Boundary

本轮 plan 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m1-formal-input-adapter-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/*`
- `neotrade3/decision_engine/*`
- `apps/api/main.py`
- `scripts/*`
- `neotrade3-dashboard/*`
- 其他任何工作区改动
