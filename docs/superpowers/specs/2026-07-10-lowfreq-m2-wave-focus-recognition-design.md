# Lowfreq M2 Wave Focus Recognition Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E4: M2 legacy recognition zone` 的第一刀设计。

本轮只冻结：

- `wave_phase + role + core_focus_gate + candidate_tier` 这条遗留识别收敛链

目标是：

- 把 engine 中最活跃、测试最集中、最接近 `M2` 识别语义的遗留判定簇先认账出来
- 明确这一簇是 `M2 legacy recognition`，不是 `M1` adapter、`formal front` 或 `M3 nucleus` 本体
- 为后续继续处理 `sector cooldown / hot sectors / global candidates` 等其他遗留识别簇提供干净接缝
- 保持当前 `generate_buy_signals()`、`candidate_signals`、`candidate_tier` 与 `tracking` 接续行为不变

本设计不是：

- `E4` 全域识别逻辑的一次性重构
- `sector cooldown` 识别链设计
- `get_hot_sectors()` / `get_sector_candidates()` / `get_global_candidates()` 的整体迁移
- `M3 tracking / entry / exit` 的 contract 改写

## 2. Scope

Included:

- [_detect_wave_phase_from_series](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2947-L2975) 的职责认账与剥离设计
- [_passes_core_focus_gate](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1473-L1518) 的职责认账与剥离设计
- [_apply_strong_leader_soft_release](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1520-L1587) 的职责认账与剥离设计
- `generate_buy_signals()` 内这组识别结果如何汇入 `candidate_tier / reasons / entry_ready`
- 现有 focused tests 对这条链的承载边界

Excluded:

- `detect_sector_cooldown()` 与 `_sector_cooldown_confirmed()` 的迁移
- `get_hot_sectors()` / `get_sector_candidates()` / `get_global_candidates()` 的板块扫描职责
- `SmallCycle` formal object 的 contract 改写
- `_decorate_signal_with_phase1_contracts()`、`_tracking_snapshot_from_signal()`、`_candidate_tier_from_signal()` 的 `M3` 运行态 contract 语义改写
- `apps/api/main.py`、workbench、report consumers 的消费侧变更

## 3. Existing Context

当前仓库已经给出五组直接证据：

- engine 仍直接持有遗留识别链的关键判定：
  - [_detect_wave_phase_from_series](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2947-L2975)
  - [_passes_core_focus_gate](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1473-L1518)
  - [_apply_strong_leader_soft_release](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1520-L1587)
- 这条链的输出直接影响 `candidate_signals` 收敛面：
  - `wave_phase`
  - `role`
  - soft flags / reasons
  - `candidate_tier`
  - `entry_ready`
- 现有 `cycle_intelligence` 只正式承接了 `SmallCycle`：
  - [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/contracts.py)
  - [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/assembler.py#L71-L299)
  它已经拥有 formal `M2 small-cycle` owner，但还没有承接 engine 内这组遗留识别判定
- 现有测试承载高度集中在本轮目标链：
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
    已大量保护：
    - `wave_phase`
    - `role`
    - `core_focus_gate`
    - `candidate_tier`
    - `strong_leader_soft_release`
  - [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)
    已冻结 `candidate_tier -> tracking / entry` 的 `M3` 接续 contract
- 相比之下，`sector cooldown` 一簇虽然存在，但当前 formal owner 不足、测试承载也更分散，不适合作为 `E4` 第一刀

现状问题不是“没有任何 `M2` owner”，而是：

- formal `M2 small-cycle` 已有 owner
- 但 engine 中仍残留一组先于 formal object 的 legacy recognition heuristics
- 其中最活跃的一条正是 `wave/focus -> candidate tier` 收敛链

## 4. Approach Options

### Option A: 先剥离 `wave/focus` 收敛链到 `cycle_intelligence` 邻近模块（推荐）

- 在 `neotrade3/cycle_intelligence/` 下新增一个只承接 legacy recognition 的窄模块
- 把波段识别、focus gate 与 strong-leader soft release 从 engine 中收口到该模块
- engine 保留 orchestration，不改输出 shape

Pros:

- 最符合当前测试承载与活跃主链
- 能把 `M2 formal owner` 与 `M2 legacy recognition` 放到同层目录表达清楚
- 不必等 `sector cooldown` 全部理顺才开始 `E4`

Cons:

- 需要在 `cycle_intelligence` 下新增一个 legacy 模块
- 必须明确这只是 `E4` 第一刀，不是假装清完全部 `M2`

### Option B: 先做 `sector cooldown` / `hot sectors` 板块识别链

- 先处理板块热度、退潮和跨板块扫描门控

Pros:

- 更像“板块周期识别”

Cons:

- formal owner 还不清晰
- 当前测试承载更分散
- 更容易把扫描 orchestration 与 recognition owner 混在一起

### Option C: 只写 `E4` 总设计，不冻结第一刀

- 只输出全域识别地图，不进入子簇设计

Pros:

- 范围最保守

Cons:

- 无法继续实现推进
- `E4` 会停留在概念层，不能转成原子切片

Decision:

- 采用 Option A

## 5. Design

### 5.1 Ownership Decision

本轮要剥离的是以下遗留识别职责：

- 根据价格序列识别 `wave_phase`
- 根据角色与市场主线/渗透率/配置证据判断 `core_focus_gate`
- 针对龙头 1/3 浪样本做 `strong_leader_soft_release`
- 形成收敛后的 soft blocker / reasons / score 变化，并影响 `candidate_tier`

这些职责应定义为：

- `M2 legacy recognition heuristics`

而不是：

- `M2 formal small-cycle object`
- `M3 tracking / entry runtime`
- `sector scanning orchestration`

### 5.2 Recommended File Boundary

推荐新增一个窄模块：

- `neotrade3/cycle_intelligence/legacy_recognition.py`

该文件只承接：

- `wave_phase` 识别
- `core_focus_gate` 判定
- `strong_leader_soft_release`

不承接：

- `SmallCycle` formal builder
- `sector cooldown`
- 板块扫描 SQL
- `candidate_tier` 之后的 `M3` 运行态 contract

推荐原因：

- `cycle_intelligence` 已是正式 `M2` owner 所在层
- 这组逻辑本质上是 legacy recognition，而不是 engine 私有工具
- 文件名能明确表达它还不是 formal object，而是 legacy heuristics

### 5.3 Adapter Surface

推荐对 engine 暴露三个 facade：

- `detect_wave_phase_from_series(...)`
- `passes_core_focus_gate(...)`
- `apply_strong_leader_soft_release(...)`

保持当前调用面尽量不变：

- `detect_wave_phase_from_series(...)`
  - 输入：`closes / highs / lows`
  - 输出：`(wave_phase, confidence)`
- `passes_core_focus_gate(...)`
  - 输入：`cursor / code / stock_name / role / target_date`
  - 输出：`(passed, reasons, snapshot)`
- `apply_strong_leader_soft_release(...)`
  - 输入：`score / role / wave_phase / soft_flags / reasons / config`
  - 输出：`(score, soft_flags, reasons)`

设计意图：

- engine 只替换 owner 位点，不改变这条链的输入输出 contract
- `candidate_tier` 的最终判定仍暂留在 engine 侧，与 `M3` 接续边界保持清晰

### 5.4 What Stays In Engine

以下职责在 `E4` 第一刀后仍留在 engine：

- `generate_buy_signals()` 的整体 orchestrator
- `candidate_signals` 的收敛排序与去重
- `_candidate_tier_from_signal()` 及其与 `tracking / entry` 的接续
- `get_hot_sectors()` / `get_sector_candidates()` / `get_global_candidates()` 的扫描逻辑
- `sector cooldown` 相关 detection

原因：

- 本轮只切出最活跃的遗留识别判定簇
- 不把板块扫描和 `M3` runtime 接续混进第一刀

### 5.5 Error Boundary

本轮不引入新的对外错误面。

这意味着：

- 波段识别继续使用当前保守回退：
  - 数据不足时返回 `WavePhase.UNKNOWN`
- focus gate 继续返回：
  - `passed`
  - `reasons`
  - `snapshot`
- strong-leader soft release 继续只做分数/soft flags/reasons 的窄收口

不允许：

- 引入新的异常类型
- 改写现有 soft-fail 文案语义

### 5.6 Testing Strategy

本轮优先复用现有 focused carrier：

- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)
  - 继续作为 `wave/focus -> candidate tier` 的主护栏
- [test_lowfreq_engine_v16_m3_nucleus_contract.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py)
  - 继续作为 `candidate_tier -> tracking/entry` 的接续护栏

如确有必要，只允许新增：

- 一份 `legacy_recognition.py` 的 unit-level focused test

明确不需要：

- 扩张到 `sector cooldown` 全链路回归
- 改写 `SmallCycle` formal object tests

### 5.7 Validation Baseline

`E4` 第一刀完成后，至少验证：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_m3_nucleus_contract.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/legacy_recognition.py`

验证重点：

- `wave_phase` 判定未漂移
- `focus gate` 与 `soft release` 行为未漂移
- `candidate_tier` 与 `tracking / entry` 接续未漂移

## 6. Commit Boundary

本轮 design 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-wave-focus-recognition-design.md`

后续 implementation 若按本设计推进，推荐最小文件边界为：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/legacy_recognition.py`
- 如确有必要，对应 focused tests

必须排除：

- `neotrade3/cycle_intelligence/assembler.py`
- `neotrade3/cycle_intelligence/contracts.py`
- `neotrade3/data_control/*`
- `neotrade3/decision_engine/*`
- `apps/api/main.py`
- `sector cooldown` 相关其他文件
- 其他任何工作区既有改动

## 7. Success Criteria

本设计完成后，应达到：

- `wave/focus -> candidate tier` 这条活跃遗留识别链被正式认账为 `M2 legacy recognition`
- engine 不再直接拥有这组判定 helper 的 owner 身份
- `M3` 接续 contract 与外部消费形状保持不变
- `E4` 后续还能继续拆第二刀，而不会把第一刀做成全域大重构
