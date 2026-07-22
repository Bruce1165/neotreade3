# Lowfreq M2 Global Selector Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-global-selector-design.md`

## 1. Goal

本计划只处理 `E4: M2 legacy recognition zone` 的第五刀实现步骤。

本轮只处理：

- `get_global_candidates()` 这条 `global selector`

目标是：

- 在 `cycle_intelligence` 下新增 `global entry selector` owner 模块
- 把 engine 当前直接持有的跨板块 seed 扫描、过滤、评分、role 分桶、focus gate 消费和 `StockCandidate` shaping 迁入该模块
- 保持 `get_sector_candidates()`、`generate_buy_signals()` 与 consumer contract 不变

本轮不做：

- `get_sector_candidates()` 的再次重构
- `generate_buy_signals()` 主链流程改写
- `StockCandidate` dataclass 定义位置迁移
- `apps/api/main.py`、workbench、report consumers 改造
- `_get_recent_price_history_batch()`、`_get_fundamentals_batch()`、`_market_focus_snapshot()` 等 data adapter 重写
- sector/global 两条 selector 的共享大内核抽象

## 2. Starting Point

当前这条链分散在两层：

- `lowfreq_engine_v16_advanced.py`
  - `get_global_candidates()`
  - `StockCandidate`
  - `_get_recent_price_history_batch()`
  - `_get_fundamentals_batch()`
  - `_market_focus_snapshot()`
- `neotrade3/cycle_intelligence`
  - 已有 `legacy_recognition.py`
  - 已有 `sector_cooldown.py`
  - 已有 `sector_heat.py`
  - 已有 `sector_entry_selector.py`
  - 但尚未承接 `global selector`

根据已批准 design，本轮只迁移 cross-sector selector owner，不重写主链，也不顺手做 sector/global 去重抽象。

## 3. Implementation Strategy

采用以下策略：

- 新增文件：
  - `neotrade3/cycle_intelligence/global_entry_selector.py`
- 在该文件中收口：
  - `build_global_candidates(...)`
  - 必要的内部 helper，用于 seed rows / excludes / history views / role assignment
- `lowfreq_engine_v16_advanced.py` 只做两类改动：
  - 引入新 facade
  - 将 `get_global_candidates()` 改成 thin facade
- `StockCandidate` 不迁移，由 engine 通过 `stock_candidate_factory=StockCandidate` 注入
- `_structure_confirm()`、`passes_core_focus_gate(...)` 与 `apply_strong_leader_soft_release(...)` 继续作为既有算法依赖被消费，不在本轮改写
- `_get_recent_price_history_batch()`、`_get_fundamentals_batch()`、`_market_focus_snapshot()` 继续留在 engine，通过 loader 注入消费
- 测试面采用：
  - 新增一份 owner-focused test
  - 复用 `signal_convergence` 做最小 consumer regression

## 4. Execution Steps

### E4-S1：冻结文件边界与 contract

实现前先锁定本轮允许改动的文件：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/global_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

同时冻结输出面：

- `get_global_candidates()` 继续返回 `list[StockCandidate]`
- `StockCandidate` 字段集合保持不变
- `signal_source="cross_sector"` 保持不变
- `capture-first` 的 soft retain 语义保持不变

完成判定：

- 本轮不会改动 `StockCandidate` consumer 的字段读取方式

### E4-S2：实现 `global_entry_selector.py`

在新模块中实现：

- `build_global_candidates(...)`

必要的内部 helper 至少包括：

- `load_global_seed_rows(...)`
- `filter_seed_rows(...)`
- `load_global_history_views(...)`
- `assign_global_roles_by_sector(...)`

实现要求：

- 输入输出 contract 保持与 engine 当前一致
- 允许通过参数显式注入：
  - `structure_confirm_loader`
  - `fundamentals_loader`
  - `history_batch_loader`
  - `market_focus_snapshot_loader`
  - `stock_candidate_factory`
- 不在该模块中引入：
  - `StockCandidate` dataclass 定义
  - `get_sector_candidates()` 逻辑
  - `generate_buy_signals()` 逻辑

完成判定：

- `global selector` owner 能在 `cycle_intelligence` 下独立表达

### E4-S3：切换 engine 到 thin facade

在 `lowfreq_engine_v16_advanced.py` 中：

- 引入：
  - `build_global_candidates(...)`
- 将 `get_global_candidates()` 改成 facade：
  - 继续暴露同名 engine 方法
  - 只负责注入：
    - `cursor`
    - `target_date`
    - `top_n`
    - market-cap / cross-sector scan / cup handle / relative strength / release 配置
    - `exclude_sectors`
    - `exclude_codes`
    - `self._structure_confirm`
    - `self._get_fundamentals_batch`
    - `self._get_recent_price_history_batch`
    - `self._market_focus_snapshot`
    - `StockCandidate`

明确禁止：

- 不修改 `get_sector_candidates()`
- 不修改 `generate_buy_signals()` 主链
- 不修改 `apps/api/main.py`
- 不修改 `sector_entry_selector.py`、`sector_heat.py`、`sector_cooldown.py`

完成判定：

- engine 不再直接拥有 `global selector` 的核心实现，只保留兼容入口

### E4-S4：补 focused tests

新增：

- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

最小要求：

- `exclude_sectors` / `exclude_codes` 过滤正确
- 历史样本不足时保留 soft retain 降权语义
- `fundamentals_soft_fail` / `structure_soft_fail` 正确保留
- 按 sector 分桶的 role 分配与 relative strength bonus 正确
- `signal_source="cross_sector"` 输出 shape 不漂移
- 全局排序与 `top_n` 截断正确

复用：

- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

最小要求：

- 主链继续消费 `get_global_candidates()` 返回的 `StockCandidate` 风格对象

完成判定：

- 本轮既保护新 owner，也保护现有 consumer

### E4-S5：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/global_entry_selector.py`

并补充：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

完成判定：

- `global selector` owner 无回归
- 主链接线无回归
- 生产代码语法通过

### E4-S6：窄提交

提交前只允许暂存：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/global_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`

必须排除：

- `neotrade3/cycle_intelligence/sector_entry_selector.py`
- `neotrade3/cycle_intelligence/sector_heat.py`
- `neotrade3/cycle_intelligence/sector_cooldown.py`
- `get_sector_candidates()` 改动
- `generate_buy_signals()` 改动
- `StockCandidate` dataclass 迁移
- `apps/api/main.py`
- 其他任何既有工作区改动

## 5. Risks And Guards

风险 1：

- 为了迁移 `get_global_candidates()`，顺手把 `generate_buy_signals()` 一起改掉

保护：

- 第五刀只允许碰 `get_global_candidates()` 及其新 owner 文件

风险 2：

- 因为看到 sector/global 重复，就在第五刀强行抽共享大内核

保护：

- 第五刀只做 owner 迁移，不做跨 owner 共享抽象

风险 3：

- 为了迁移 `get_global_candidates()`，把 data adapter 一起迁走，导致边界扩大成 selector + data adapter

保护：

- `_get_recent_price_history_batch()`、`_get_fundamentals_batch()`、`_market_focus_snapshot()` 在第五刀只通过 loader 注入消费

风险 4：

- 继续只依赖 consumer 载体，owner 无 focused 护栏

保护：

- 必须新增 `test_lowfreq_engine_v16_global_entry_selector.py`

## 6. Success Criteria

本轮完成后，应满足：

- `get_global_candidates()` 的核心 owner 已迁入 `cycle_intelligence`
- `signal_source="cross_sector"` consumer shape 保持稳定
- `generate_buy_signals()` 仍只作为 consumer，不被第五刀误伤
- sector/global 两条 selector 都已有清晰 owner 位点
- 后续若要处理 sector/global 共享评分内核，可以在 owner 明确后再单独设计

## 7. Commit Boundary

本轮 plan 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-global-selector-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
