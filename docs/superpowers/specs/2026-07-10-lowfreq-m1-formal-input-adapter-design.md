# Lowfreq M1 Formal Input Adapter Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E2: 剥离 M1 formal input adapters` 的实现设计。

目标是：

- 把 `lowfreq_engine_v16_advanced.py` 中“查询 formal 输入、投影正式对象、批量装配 M1 输入底座”的职责，从 `M3` 主核周边剥离出来
- 明确这批逻辑是 `M1 consumer adapter`，不是 `M3` 决策语义 owner
- 为后续 `E3 formal front attachment isolation` 保留清晰接缝，不在本轮把接线层一起混改
- 在不改写 `data_control` 正式 owner 语义的前提下，让 engine 只消费 adapter 输出

本设计不是：

- `M3 nucleus` 重组设计
- `formal front` 装配接线重组设计
- `M2 legacy recognition` 迁移设计
- `apps/api/main.py` 的去重设计
- `data_control` 正式对象 contract 改写

## 2. Scope

Included:

- `lowfreq_engine_v16_advanced.py` 中以下 `M1 consumer adapter` helper 的职责认账与剥离设计
  - [_get_recent_price_history_for_formal_m1_batch](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2817-L2877)
  - [_get_formal_d1_facts_batch](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2879-L2919)
  - [_get_formal_security_master_batch](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2921-L2953)
  - [_build_formal_trading_day_status](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2955-L3015)
- 这组 helper 在 [_build_formal_front_chain_payload](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3031-L3143) 中的消费关系
- `neotrade3/data_control` 中正式 projection owner 与现有测试承载

Excluded:

- [_build_formal_front_chain_payload](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3031-L3143) 的整体迁移
- [_attach_formal_front_payloads](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3017-L3029) 的迁移
- `build_m1_constraints_ref()`、`build_small_cycle_from_m1()` 与 `build_*_state_from_formal_inputs()` 的 owner 调整
- `apps/api/main.py` 的 query/projection 复用改造
- `M2/M3/M6` 的任何实现调整

## 3. Existing Context

根据已批准的总设计与计划：

- [2026-07-10-lowfreq-engine-six-layer-accounting-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-10-lowfreq-engine-six-layer-accounting-design.md#L197-L214) 已明确：
  - `project_d1_daily_price_fact`
  - `project_d7_security_master_minimal`
  - `project_pf1_trading_profile`
  是 `M1` 正式 owner 一侧的 projection helper
- [2026-07-10-lowfreq-engine-six-layer-accounting-plan.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-10-lowfreq-engine-six-layer-accounting-plan.md#L162-L185) 已把 `E2` 定义为：
  - 剥离 `M1 formal input adapters`
  - 不修改 `data_control` 的正式 owner 语义
  - 不顺带迁移 `M2`

现有代码已经给出三组直接证据：

- `data_control` 中已有正式投影 owner：
  - [project_d1_daily_price_fact](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L42-L56)
  - [project_d7_security_master_minimal](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L59-L68)
  - [project_d7_trading_day_status](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L71-L82)
  - [project_pf1_trading_profile](file:///Users/mac/NeoTrade3/neotrade3/data_control/projections.py#L85-L147)
- engine 当前确实在自己执行“查询 + 投影 + 组装”：
  - `_get_formal_d1_facts_batch()` 查询 `daily_prices` 后调用 `project_d1_daily_price_fact`
  - `_get_formal_security_master_batch()` 查询 `stocks` 后调用 `project_d7_security_master_minimal`
  - `_build_formal_trading_day_status()` 在 engine 内直接构造 `D7TradingDayStatus`
  - `_get_recent_price_history_for_formal_m1_batch()` 为 `project_pf1_trading_profile()` 预先整理批量价格序列
- 现有 `M1` 测试承载已经冻结 formal object 语义，不允许 `E2` 改写 owner：
  - [test_m1_phase1_formal_objects.py](file:///Users/mac/NeoTrade3/tests/unit/test_m1_phase1_formal_objects.py#L140-L208) 已保护 `PF1` 窗口语义和 `M1` API entrypoints
  - 同文件 [L237-L381](file:///Users/mac/NeoTrade3/tests/unit/test_m1_phase1_formal_objects.py#L237-L381) 已把 `M1 formal artifacts` 的 pipeline / worker / preflight 承载冻结为正式 contract

现状问题不是“没有 formal owner”，而是：

- engine 仍直接持有一组 `M1` 批量读取与 projection 适配 helper
- 这组 helper 又被包在 `formal front` 总装配函数内部，导致 `M1 adapter` 与 `E3` 接线层难以分账
- `_build_formal_trading_day_status()` 还绕开了 `project_d7_trading_day_status()`，使 `D7` 的 owner 路径在 engine 中出现旁路

## 4. Approach Options

### Option A: 提取到 `data_control` 的共享 read-side adapter 模块（推荐）

- 在 `neotrade3/data_control/` 下新增只服务 formal 输入消费的 adapter 模块
- 把 batch query、原始 payload 标准化、formal projection 调用集中到该模块
- engine 只保留调用 facade，并继续在 `E3` 之前持有 `formal front` 装配职责

Pros:

- 最符合现有 owner 证据：projection 与 contract 已在 `data_control`
- 能把“formal object owner”与“engine consumer”放在同一层边界里表达清楚
- 后续若 `apps/api/main.py` 需要复用，同一 read-side adapter 也有自然承接点

Cons:

- 需要在 `data_control` 下新增一个窄模块
- 必须严格克制范围，避免顺手做 API 复用

### Option B: 提取到 engine 邻近的私有 helper 模块

- 新增一个低频 engine 私有模块，只从原文件中搬走这四个 helper
- `data_control` 继续只暴露 projection helper

Pros:

- 对当前 engine 改动最直观
- 不会触碰 `data_control` 目录

Cons:

- `M1 consumer adapter` 仍然留在 engine 语义边界附近
- “formal owner 在 `data_control`、formal consumer adapter 在 engine 私有目录” 的表达更混杂

### Option C: 只在 engine 内重排方法，不新增模块

- 保留方法在 `lowfreq_engine_v16_advanced.py`
- 只通过重命名或聚拢注释来表达它们属于 adapter

Pros:

- 代码风险最低

Cons:

- 没有物理剥离
- 不满足 `E2` 的阶段目标
- 后续 `E3` 仍然很难与 `M1 adapter` 分界

Decision:

- 采用 Option A

## 5. Design

### 5.1 Ownership Decision

`E2` 要剥离的不是 formal object 本身，而是以下 consumer-side adapter 责任：

- 根据 `codes + target_date` 从数据库批量查询 `M1` 所需事实
- 把数据库行装配为 `project_*` 所需原始 payload
- 调用 `data_control.projections` 生成正式对象
- 以 engine 需要的批量索引结构返回

这些责任应定义为：

- `M1 read-side consumer adapter`

而不是：

- `M1 owner`
- `M3 decision logic`
- `formal front attachment`

### 5.2 Recommended File Boundary

推荐新增一个窄模块：

- `neotrade3/data_control/formal_input_adapter.py`

该模块只承接 engine 目前这组批量查询与投影适配逻辑，不承接：

- API view 层返回体组织
- quality / freshness / attention item 组织
- `formal front` 下游接线
- `M2/M3` 状态组装

推荐原因：

- `data_control` 已经拥有 projection owner 与 formal contract
- 本轮要表达的是“formal 输入底座的消费入口”归属于 `M1` 边界，而不是 engine 主核
- 新文件名直接体现它是 formal input adapter，不会误导成通用 pipeline 或 API service

### 5.3 Adapter Surface

推荐把当前四个 helper 收口为一个 facade + 若干私有批量读取函数。

对 engine 暴露的最小入口建议为：

- `load_formal_m1_inputs(...)`

返回内容保持与当前 engine 消费面一致，只包含：

- `d1_by_code`
- `security_by_code`
- `trading_day_status`
- `history_by_code`

设计意图：

- `E2` 只切断 engine 对 SQL 和 projection 细节的直接拥有
- 不提前合并 `E3` 的 `small_cycle / constraints / state` 组装
- 让 `_build_formal_front_chain_payload()` 在本轮之后仍可原样组织自己的下游逻辑，只是改为消费一个 adapter facade

### 5.4 Projection Rules

本轮必须统一遵守以下投影规则：

- `D1` 继续通过 `project_d1_daily_price_fact()` 生成
- `D7 security master` 继续通过 `project_d7_security_master_minimal()` 生成
- `PF1 trading profile` 继续通过 `project_pf1_trading_profile()` 生成
- `D7 trading day status` 不再在 engine 内直接实例化 `D7TradingDayStatus`，而是先构造 raw payload，再通过 `project_d7_trading_day_status()` 生成

最后一条是本轮最关键的 owner 对齐点，因为当前 engine 存在：

- formal owner 已在 `data_control.projections`
- 但 engine 仍直接构造 `D7TradingDayStatus`

这会让 `D7` 的正式投影路径出现双轨。

### 5.5 What Stays In Engine

以下职责在 `E2` 后仍然保留在 engine，留给 `E3`：

- `_build_formal_front_chain_payload()` 的异常包装与 `items_by_code` 汇总
- `project_pf1_trading_profile()` 之后的：
  - `build_m1_constraints_ref()`
  - `build_small_cycle_from_m1()`
  - `build_identify_state_from_formal_inputs()`
  - `build_tracking_state_from_formal_inputs()`
  - `build_entry_state_from_formal_inputs()`
- `_attach_formal_front_payloads()`
- `generate_buy_signals()` 中 formal payload 的消费与附着

原因：

- 这些职责不再是“读取 formal 输入底座”，而是“把 formal 输入接到 engine 运行链上”
- 这正是 `E3 formal front attachment isolation` 的边界

### 5.6 Error Boundary

`E2` 不改变现有对外错误语义。

这意味着：

- adapter 内可以抛出数据库或 projection 异常
- `_build_formal_front_chain_payload()` 仍保留当前 `try/except`，并继续返回：
  - `status = error`
  - `error_type = formal_projection_failed`
  - `message = 原始异常文本`

这样可以保证：

- 本轮只改变 ownership，不改变 `formal front` 的错误对外面

### 5.7 Testing Strategy

本轮测试不重写 `M1` owner 契约，而是增加最小 regression 保护以下两点：

1. engine 仍能从 adapter 获得与当前等价的 `d1/security/trading_day/history` 输入底座
2. `formal front` 的对外结果形状不因 adapter 迁移而漂移

建议测试形状：

- 新增 `tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`，直接保护 adapter 返回结构
- 补 `tests/unit/test_lowfreq_engine_v16_signal_convergence.py` 或新增一份等价 focused regression，只覆盖 `_build_formal_front_chain_payload()` 的最小成功/失败面

明确不需要：

- 重复 `test_m1_phase1_formal_objects.py` 中已经冻结的 formal object 语义
- 扩张成 `run_backtest()` 级别的 omnibus 回归

### 5.8 Validation Baseline

`E2` 完成后，至少验证：

- `python3 -m pytest tests/unit/test_m1_phase1_formal_objects.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/data_control/formal_input_adapter.py`

验证重点不是覆盖率，而是三件事：

- formal object owner 没变
- engine 不再直接拥有 query/projection 细节
- `formal front` 消费结果未漂移

## 6. Commit Boundary

本轮 design 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m1-formal-input-adapter-design.md`

后续 implementation 若按本设计推进，推荐最小文件边界为：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/formal_input_adapter.py`
- 与 `E2` 直接对应的 focused tests

必须排除：

- `apps/api/main.py`
- `neotrade3/data_control/projections.py`
- `neotrade3/data_control/contracts.py`
- `neotrade3/decision_engine/*`
- `M2/M3/M6` 其他生产逻辑
- 其他任何工作区既有改动

## 7. Success Criteria

本设计完成后，应达到：

- `E2` 的对象边界被明确冻结为“查询 + 投影 + 批量装配适配”
- `formal front` 明确保留到 `E3`，不再与 `E2` 混账
- `D7 trading day status` 的 formal projection 路径回到 `data_control.projections`
- 后续 implementation 可以在不触碰 `M3 nucleus` 的前提下，物理剥离 engine 对 `M1` 输入底座的直接拥有
