# Lowfreq M3 Nucleus Contract Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m3-nucleus-contract-design.md`

## 1. Goal

本计划只处理 `E0: 冻结 M3 nucleus` 的实现步骤。

本轮目标是：

- 新增一份独立 `M3 nucleus contract` 测试载体
- 把 `tracking / execution / exit / runtime` 主核的最小回归锚点冻结下来
- 不修改任何生产代码
- 不把现有 lowfreq engine 测试重新打散成 omnibus

本轮不做：

- `M1 formal input adapter` 抽离
- `formal front attachment` 抽离
- `M2 legacy recognition` 重组
- `M6 delivery` 相关测试追加
- 任何生产逻辑改动

## 2. Starting Point

当前仓库已有三份低频 engine 测试载体：

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

它们分别覆盖：

- exit 状态机
- tracking runtime 推进
- signal contract / convergence 输出

但缺少一份显式声明 `M3 nucleus` 保护边界的统一载体。

## 3. Implementation Strategy

采用以下策略：

- 新增独立测试文件：
  - `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- 在新文件内只抽取 `M3 nucleus` 的最小 contract 锚点
- 现有三份测试文件原则上不改
- 只有当新载体必须复用已有构造 helper 时，才允许对现有测试做最小抽样复用调整

## 4. Execution Steps

### E0-R1：冻结新载体边界

只允许新载体保护以下对象/输出：

- `TradeRecord`
- `_tracking_snapshot_from_signal()`
- `_decorate_signal_with_phase1_contracts()`
- `_record_tracking_candidate_events()`
- `check_sell_signal_v2()`
- `run_backtest()` 的最小输出锚点

明确排除：

- `M1 formal input adapter`
- `formal front attachment`
- `M2 recognition`
- `M6 delivery`

完成判定：

- 新文件的每条断言都能明确归属到 `M3 nucleus`

### E0-R2：构造最小断言集

在新载体里只保留以下几类断言：

- `tracking snapshot` 关键字段：
  - `tracking_state`
  - `tracking_days`
  - `tracking_transition_reason`
  - `tracking_contract.source_layer`
  - `tracking_contract.decision`
- `phase1 contract` 关键字段：
  - `candidate_contract.source_layer`
  - `tracking_contract.source_layer`
  - `entry_contract.source_layer`
  - `candidate_tier`
- `tracking runtime` 关键事件：
  - `tracking_started`
  - `tracking_promoted_to_entry`
  - `tracking_dropped`
- `exit` 主链：
  - `thesis_invalidated`
  - `trend_exhausted`
  - `market/sector exit` 的 observe/review/hit
- `run_backtest` 输出锚点：
  - `buy_signal_audit`
  - `execution_action_summary`
  - `config_snapshot`
  - `all_trades` 的最小形状

完成判定：

- 断言集足够保护 `M3 nucleus`
- 但没有扩张成候选识别或 formal 输入的全量行为回归

### E0-R3：控制与现有测试的职责重叠

实现时遵守：

- 不复制现有测试的大段场景
- 只抽取每个主题中最能代表 `M3 nucleus` 的最小场景
- 如果新载体能独立构造 stub，就不共享旧测试 helper

完成判定：

- 新测试文件能读出“这是 M3 主核护栏”
- 现有三份测试仍保留原有主题角色

### E0-R4：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

如有必要补跑：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

并补充：

- `python3 -m py_compile lowfreq_engine_v16_advanced.py`

完成判定：

- 新载体通过
- 现有低频主核相关测试无回归

### E0-R5：窄提交

默认提交边界只包含：

- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

若确实有最小复用调整，可额外包含：

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_engine_v16_tracking_runtime.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

但必须满足：

- 不改 `lowfreq_engine_v16_advanced.py`
- 不改 `M1/M2/M6` 相关生产逻辑
- 不混入无关清理

## 5. Risks and Guards

风险 1：

- 新载体失控，变成“把现有三份测试再抄一遍”

保护：

- 每条断言都必须能解释为 `M3 nucleus` 护栏，而不是普通 lowfreq 行为覆盖

风险 2：

- 为了方便写测试，顺手改生产代码

保护：

- 本轮禁止修改 `lowfreq_engine_v16_advanced.py`

风险 3：

- 在 `run_backtest` 锚点上断言过多，导致未来 `E2/E3` 难以推进

保护：

- 只锁最小输出锚点，不锁与 `M1/M2/M6` 强耦合的字段细节

## 6. Success Criteria

本轮完成后，应满足：

- 仓库里有一份独立 `M3 nucleus contract` 测试载体
- 后续 `E2/E3/E4` 都能把它当成统一护栏
- 当前主核边界被正式冻结，但未提前进入 `M1/M2` 迁移

## 7. Commit Boundary

本轮计划提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m3-nucleus-contract-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/data_control/*`
- `neotrade3/cycle_intelligence/*`
- `neotrade3/decision_engine/*`
- `apps/api/main.py`
- `scripts/*`
- `neotrade3-dashboard/*`
- 其他任何工作区改动
