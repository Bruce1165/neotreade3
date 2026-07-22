# Lowfreq M2 Wave Focus Recognition Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-wave-focus-recognition-design.md`

## 1. Goal

本计划只处理 `E4: M2 legacy recognition zone` 的第一刀实现步骤。

本轮只处理：

- `wave_phase + core_focus_gate + strong_leader_soft_release -> candidate_tier`

目标是：

- 新增一个 `cycle_intelligence` 侧的 legacy recognition 模块
- 把 engine 当前直接持有的 `wave/focus` 遗留识别判定迁移到该模块
- 保持 `candidate_signals`、`candidate_tier`、`tracking / entry` 接续与现有测试 contract 不变

本轮不做：

- `sector cooldown` 识别链
- `get_hot_sectors()` / `get_sector_candidates()` / `get_global_candidates()` 的板块扫描迁移
- `SmallCycle` formal object contract 改写
- `_candidate_tier_from_signal()` 的 `M3` 接续语义改写
- API / report consumers 的消费改造

## 2. Starting Point

当前这条遗留识别链分散在两层：

- `lowfreq_engine_v16_advanced.py`
  - `_detect_wave_phase_from_series()`
  - `_passes_core_focus_gate()`
  - `_apply_strong_leader_soft_release()`
  - 以及它们在 `generate_buy_signals()` 收敛链中的调用
- `neotrade3/cycle_intelligence`
  - 已正式拥有 `SmallCycle`
  - 但还没有接住这组 legacy heuristics

根据已批准 design，本轮只移动这组三个遗留识别 helper 的 owner 位点，不动 `candidate_tier` 之后的 `M3` 接续。

## 3. Implementation Strategy

采用以下策略：

- 新增文件：
  - `neotrade3/cycle_intelligence/legacy_recognition.py`
- 在该文件中收口：
  - `detect_wave_phase_from_series(...)`
  - `passes_core_focus_gate(...)`
  - `apply_strong_leader_soft_release(...)`
- `lowfreq_engine_v16_advanced.py` 只做三类改动：
  - 引入新 facade
  - 用 facade 替换本地 helper 调用
  - 删除已被替代的本地 helper

## 4. Execution Steps

### E4-R1：冻结文件边界与输出面

实现前先锁定本轮允许改动的文件：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/legacy_recognition.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- 如确有必要，补一份 `legacy_recognition.py` focused test

同时冻结这条链的输出面：

- `wave_phase` 继续返回字符串枚举
- `passes_core_focus_gate(...)` 继续返回：
  - `passed`
  - `reasons`
  - `snapshot`
- `apply_strong_leader_soft_release(...)` 继续返回：
  - `score`
  - `soft_flags`
  - `reasons`

完成判定：

- 本轮不会改动 `candidate_tier` 的对外语义

### E4-R2：实现 `legacy_recognition.py`

在新模块中实现：

- `detect_wave_phase_from_series(...)`
- `passes_core_focus_gate(...)`
- `apply_strong_leader_soft_release(...)`

实现要求：

- 输入输出 contract 保持与 engine 当前一致
- `passes_core_focus_gate(...)` 仍允许消费现有 market-focus snapshot helper
- 不在该模块中引入板块扫描 SQL
- 不在该模块中引入 `tracking / entry` 运行态逻辑

完成判定：

- 三个遗留识别 facade 能在 `cycle_intelligence` 下独立表达

### E4-R3：切换 engine 到 facade

在 `lowfreq_engine_v16_advanced.py` 中：

- 引入：
  - `detect_wave_phase_from_series(...)`
  - `passes_core_focus_gate(...)`
  - `apply_strong_leader_soft_release(...)`
- 将现有调用点切换到新 facade
- 删除 engine 中已被替代的三个本地 helper

明确禁止：

- 不修改 `_candidate_tier_from_signal()` 的逻辑
- 不改 `tracking / entry` 接续
- 不顺手改 `sector cooldown` 或板块扫描链

完成判定：

- engine 不再直接拥有这组三个遗留识别 helper 的 owner 身份

### E4-R4：补 focused tests

优先复用：

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

最小要求：

- `wave_phase` 判定不漂移
- `core_focus_gate` 通过/失败行为不漂移
- `strong_leader_soft_release` 的 score / flags / reasons 不漂移
- `candidate_tier -> tracking / entry` 接续不漂移

如确有必要，允许新增：

- `tests/unit/test_lowfreq_legacy_recognition.py`

但只有在现有 carrier 无法清晰保护模块边界时才新增。

完成判定：

- `E4` 第一刀优先复用现有正式 carrier，不制造测试主题膨胀

### E4-R5：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`

并补充：

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/legacy_recognition.py`

如新增了专门 focused test，再补跑对应文件。

完成判定：

- `wave/focus` 收敛链无回归
- `M3` 接续无回归
- 生产代码语法通过

### E4-R6：窄提交

提交前只允许暂存：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/legacy_recognition.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- 如确有必要，本轮新增的 `legacy_recognition` focused tests

必须排除：

- `sector cooldown` 相关改动
- `neotrade3/cycle_intelligence/assembler.py`
- `neotrade3/cycle_intelligence/contracts.py`
- `neotrade3/data_control/*`
- `neotrade3/decision_engine/*`
- `apps/api/main.py`
- 其他任何既有工作区改动

## 5. Risks and Guards

风险 1：

- 把 `candidate_tier` 或 `tracking / entry` 接续一起吸进新模块，导致 `M2/M3` 边界再次混账

保护：

- 新模块只承接遗留识别 heuristics，不承接 `candidate_tier` 之后的运行态逻辑

风险 2：

- 为了实现 `passes_core_focus_gate(...)` 顺手把 market-focus snapshot 一起大改

保护：

- 允许继续消费现有 snapshot helper，本轮不重写 snapshot owner

风险 3：

- 顺手扩张到 `sector cooldown` 或板块扫描主链

保护：

- 本轮只处理 `wave/focus`，板块链明确排除

风险 4：

- 测试面不必要膨胀

保护：

- 优先复用 `test_lowfreq_engine_v16_signal_convergence.py` 与 `test_lowfreq_engine_v16_m3_nucleus_contract.py`

## 6. Success Criteria

本轮完成后，应满足：

- `wave_phase / core_focus_gate / strong_leader_soft_release` 被正式认账为 `M2 legacy recognition`
- engine 不再直接拥有这组三个 helper 的 owner 身份
- `candidate_tier` 与 `tracking / entry` 接续保持不变
- `E4` 后续仍可继续拆第二刀，而不会被第一刀拖成全域大改

## 7. Commit Boundary

本轮 plan 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-wave-focus-recognition-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `neotrade3/data_control/*`
- `neotrade3/decision_engine/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
