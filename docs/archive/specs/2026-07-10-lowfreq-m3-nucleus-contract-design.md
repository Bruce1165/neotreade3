# Lowfreq M3 Nucleus Contract Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E0: 冻结 M3 nucleus` 的保护性实现设计。

目标是：

- 把 `lowfreq_engine_v16_advanced.py` 中绝对不能被误拆的 `M3 nucleus` 变成正式、可执行的回归保护边界
- 在进入 `E2 / E3 / E4` 之前，先建立一组只保护 `M3` 主核的最小 contract 载体
- 避免后续对 `M1 formal input adapter`、`formal front attachment`、`M2 legacy recognition` 的改动，误伤 `tracking / execution / exit / runtime` 主状态机

本设计不是：

- `M3` 代码迁移设计
- 新目录结构设计
- `M1/M2` 重组设计
- `M6` 继续收口
- 针对 `generate_buy_signals()` 全量行为的 omnibus 测试扩张

## 2. Scope

Included:

- `tests/unit/` 中 lowfreq engine 现有测试载体的职责审计
- 新增一份独立 `M3 nucleus` contract 测试载体
- 只覆盖 `M3 nucleus` 的核心运行时 contract

Excluded:

- `lowfreq_engine_v16_advanced.py` 生产代码修改
- `M1 formal input adapter` 相关测试
- `formal front attachment` 相关测试
- `M2 legacy recognition zone` 相关测试
- `M6 delivery mixin` 相关测试
- API / scripts / frontend 消费测试

## 3. Existing Context

根据已批准的 lowfreq 六层设计与计划：

- [2026-07-10-lowfreq-engine-six-layer-accounting-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-10-lowfreq-engine-six-layer-accounting-design.md#L236-L256) 已明确：
  - `TradeRecord`
  - `SellSignal`
  - `LayerContract`
  - `_tracking_snapshot_from_signal()`
  - `_decorate_signal_with_phase1_contracts()`
  - `_record_tracking_candidate_events()`
  - `check_sell_signal_v2()`
  - `run_backtest()`
  属于当前 engine 的 `M3` 主核
- [2026-07-10-lowfreq-engine-six-layer-accounting-plan.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-10-lowfreq-engine-six-layer-accounting-plan.md#L103-L135) 已把 `E0` 定义为：
  - 在任何迁移前，先冻结 `M3 nucleus`

当前仓库里已经存在三份 lowfreq engine 测试载体，但职责是分散的：

- [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py)
  - 主要保护 `check_sell_signal_v2()` 与 `TradeRecord` 的 exit 状态机
- [test_lowfreq_engine_v16_tracking_runtime.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_tracking_runtime.py)
  - 主要保护 `run_backtest()` 中 `tracking -> entry -> buy audit` 推进链
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
  - 主要保护 `generate_buy_signals()` 输出面、tracking contract 与部分 `_calc_metrics()` 基线

现状问题不是“完全没测试”，而是：

- 还没有一份显式声明 `M3 nucleus` 保护边界的独立载体
- 现有断言按主题分散，后续很难一眼判断“哪些断言是在保护主核，哪些断言是在保护邻层行为”
- 如果继续只在现有测试上零散补断言，`E0` 会退化成模糊加固，而不是正式冻结主核边界

## 4. Approach Options

### Option A: 新增独立 `M3 nucleus` contract 载体（推荐）

- 新建一份聚焦测试文件
- 只冻结 `M3 nucleus` 的核心 contract
- 明确排除 `M1 / M2 / formal front / M6`

Pros:

- 责任最清晰
- 后续 `E2 / E3 / E4` 都能直接把它当成统一护栏
- 符合“测试职责归位”的现有治理方式

Cons:

- 需要精心挑选最小断言集，避免变成 omnibus

### Option B: 在现有三份测试上补强断言

- 不新增文件
- 分别在 `sell_logic / tracking_runtime / signal_convergence` 中追加 nucleus 断言

Pros:

- 改动最少

Cons:

- `M3 nucleus` 保护边界继续分散
- 后续重组时不利于快速判断护栏是否被误伤

### Option C: 只写文档，不新增测试

- 只在 spec / plan 里写保护名单，不增加自动回归

Pros:

- 零代码风险

Cons:

- 保护力最弱
- 进入 `E2/E3/E4` 后无法自动发现误伤

Decision:

- choose Option A

## 5. Design

### 5.1 Carrier Boundary

新增一份独立测试载体，主题只叫：

- `M3 nucleus contract`

该载体只负责保护以下五类锚点：

1. `TradeRecord` 作为运行态实体的关键字段语义
2. `_tracking_snapshot_from_signal()` / `_decorate_signal_with_phase1_contracts()` 的核心 contract
3. `_record_tracking_candidate_events()` 的运行时推进 contract
4. `check_sell_signal_v2()` 的优先级主链与 exit 状态机
5. `run_backtest()` 的最小输出锚点：
   - `all_trades`
   - `buy_signal_audit`
   - `execution_action_summary`
   - `config_snapshot`

### 5.2 What This Carrier Explicitly Excludes

本载体必须明确排除：

- `M1 formal input adapters`
- `formal front attachment`
- `M2 legacy recognition`
- `M6 delivery`
- 与前端、报告、CLI 展示相关的任何断言

排除原因：

- `E0` 的目标是冻结主核，而不是顺手把整个 engine 全量覆盖
- 一旦把 `M1/M2/M6` 混进来，后续迁移时会看不清到底是主核被误伤，还是邻层改动带来的预期漂移

### 5.3 Assertion Strategy

本载体不追求覆盖率，而追求“主核不漂移”的最小保护力。

断言策略：

- 只断言 `M3 nucleus` 的正式语义字段和状态推进结果
- 不断言无关的细碎 helper 内部实现
- 能以现有测试断言复用就复用，不复制整份现有测试

建议断言类型：

- `tracking snapshot` 的关键字段：
  - `tracking_state`
  - `tracking_days`
  - `tracking_transition_reason`
  - `tracking_contract.source_layer`
  - `tracking_contract.decision`
- `phase1 contract` 的关键字段：
  - `candidate_contract.source_layer`
  - `tracking_contract.source_layer`
  - `entry_contract.source_layer`
  - `candidate_tier`
- `tracking runtime` 的关键事件：
  - `tracking_started`
  - `tracking_promoted_to_entry`
  - `tracking_dropped`
- `exit` 的优先级主链：
  - `thesis_invalidated`
  - `trend_exhausted`
  - `market/sector exit` 的 observe/review/hit 语义
- `run_backtest` 最小锚点：
  - `execution_action_summary`
  - `buy_signal_audit`
  - `config_snapshot`
  - `all_trades` 的最小形状

### 5.4 Reuse Strategy

为了避免变成 omnibus，本设计采用“现有载体抽样复用 + 独立核保护”的策略：

- 从 `sell_logic` 里抽取最小 exit 优先级锚点
- 从 `tracking_runtime` 里抽取最小 tracking 推进锚点
- 从 `signal_convergence` 里抽取最小 tracking/contract 输出锚点
- 在新载体中重新组合为一套“只看 M3 主核”的最小断言集

这意味着：

- 现有三份测试文件继续保留各自主题职责
- 新载体不替代它们，而是作为“跨主题但只保护主核”的保护层

### 5.5 File Strategy

建议新增文件：

- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

命名原则：

- 明确说明这是 lowfreq engine
- 明确说明对象是 `M3 nucleus`
- 明确说明性质是 `contract`

### 5.6 Validation Design

本轮验证只需要满足三点：

1. 新载体能独立运行
2. 新载体不依赖 `M1/M2/M6` 行为细节
3. 新载体与现有三份测试不形成明显重复职责

最小验证命令：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- 如新增断言与现有载体共享素材，再补跑：
  - `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py`
  - `python3 -m pytest tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`
  - `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 6. Commit Boundary

本轮提交应只包含：

- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

如实现中确实需要对现有测试做最小抽样复用调整，则可额外包含：

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

但必须满足：

- 不修改 `lowfreq_engine_v16_advanced.py`
- 不修改任何 `M1/M2/formal front/M6` 生产代码
- 不把现有测试职责打散成新的 omnibus

## 7. Success Criteria

本设计完成后，应达到：

- `M3 nucleus` 有一份独立、可运行、边界清楚的 contract 保护载体
- 后续 `E2/E3/E4` 可以把这份载体当成统一护栏
- 即使后续进行 adapter / attachment / recognition 重组，也能快速判断是否误伤主核
