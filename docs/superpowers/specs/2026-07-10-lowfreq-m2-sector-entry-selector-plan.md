# Lowfreq M2 Sector Entry Selector Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-entry-selector-design.md`

## 1. Goal

本计划只处理 `E4: M2 legacy recognition zone` 的第四刀实现步骤。

本轮只处理：

- `get_sector_candidates()` 这条 `sector entry selector`

目标是：

- 在 `cycle_intelligence` 下新增 `sector entry selector` owner 模块
- 把 engine 当前直接持有的板块内 stock-level selector、最小结构识别 gate 与 `StockCandidate` shaping 迁入该模块
- 保持 `get_global_candidates()`、`generate_buy_signals()` 与 consumer contract 不变

本轮不做：

- `get_global_candidates()` 的迁移或去重
- `generate_buy_signals()` 主链流程改写
- `StockCandidate` dataclass 定义位置迁移
- `apps/api/main.py`、workbench、report consumers 改造
- `_weekly_series_view()` / `_get_fundamentals_batch()` 的 data adapter 重写

## 2. Starting Point

当前这条链分散在两层：

- `lowfreq_engine_v16_advanced.py`
  - `get_sector_candidates()`
  - `_structure_confirm()`
  - `check_weekly_duck_head()`
  - `StockCandidate`
  - `_weekly_series_view()`
  - `_get_fundamentals_batch()`
- `neotrade3/cycle_intelligence`
  - 已有 `legacy_recognition.py`
  - 已有 `sector_cooldown.py`
  - 已有 `sector_heat.py`
  - 但尚未承接 `sector entry selector`

根据已批准 design，本轮只迁移 sector-local selector owner，不重写 global scanner 或主链。

## 3. Implementation Strategy

采用以下策略：

- 新增文件：
  - `neotrade3/cycle_intelligence/sector_entry_selector.py`
- 在该文件中收口：
  - `build_sector_candidates(...)`
  - `confirm_structure(...)`
  - `check_weekly_duck_head(...)`
  - 必要的内部 helper，用于 top rows / history view / role assignment
- `lowfreq_engine_v16_advanced.py` 只做四类改动：
  - 引入新 facade
  - 将 `get_sector_candidates()` 改成 thin facade
  - 将 `_structure_confirm()` 改成 thin facade
  - 将 `check_weekly_duck_head()` 改成 thin facade
- `StockCandidate` 不迁移，由 engine 通过 `stock_candidate_factory=StockCandidate` 注入
- `_weekly_series_view()`、`_get_fundamentals_batch()`、`_market_focus_snapshot()` 继续留在 engine，通过 loader 注入消费
- 测试面采用：
  - 新增一份 owner-focused test
  - 复用 `workbench_formal_consumption` 做 consumer regression
  - 如 facade 注入面触及主链，再补跑 `signal_convergence`

## 4. Execution Steps

### E4-S1：冻结文件边界与 contract

实现前先锁定本轮允许改动的文件：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/sector_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`
- 如确有必要，`tests/unit/test_lowfreq_workbench_formal_consumption.py`

同时冻结输出面：

- `get_sector_candidates()` 继续返回 `list[StockCandidate]`
- `StockCandidate` 字段集合保持不变
- `capture-first` 的 soft retain 语义保持不变

完成判定：

- 本轮不会改动 `StockCandidate` consumer 的字段读取方式

### E4-S2：实现 `sector_entry_selector.py`

在新模块中实现：

- `build_sector_candidates(...)`
- `confirm_structure(...)`
- `check_weekly_duck_head(...)`

必要的内部 helper 至少包括：

- `load_sector_top_rows(...)`
- `load_history_views_for_codes(...)`
- `assign_sector_roles(...)`

实现要求：

- 输入输出 contract 保持与 engine 当前一致
- 允许通过参数显式注入：
  - `fundamentals_loader`
  - `weekly_series_loader`
  - `cup_handle_loader`
  - `market_focus_snapshot_loader`
  - `stock_candidate_factory`
- 不在该模块中引入：
  - `StockCandidate` dataclass 定义
  - `get_global_candidates()` 逻辑
  - `generate_buy_signals()` 逻辑

完成判定：

- `sector entry selector` owner 能在 `cycle_intelligence` 下独立表达

### E4-S3：切换 engine 到 thin facade

在 `lowfreq_engine_v16_advanced.py` 中：

- 引入：
  - `build_sector_candidates(...)`
  - `confirm_structure(...)`
  - `check_weekly_duck_head(...)`
- 将 `get_sector_candidates()` 改成 facade：
  - 继续暴露同名 engine 方法
  - 只负责注入：
    - `cursor`
    - `sector`
    - `target_date`
    - `top_n`
    - market-cap 配置
    - cup handle / weekly duck head / relative strength / release 配置
    - `self._get_fundamentals_batch`
    - `self._weekly_series_view`
    - `self._cup_handle_picks`
    - `self._market_focus_snapshot`
    - `StockCandidate`
- 将 `_structure_confirm()` 与 `check_weekly_duck_head()` 改成 thin facade

明确禁止：

- 不修改 `get_global_candidates()`
- 不修改 `generate_buy_signals()` 主链
- 不修改 `apps/api/main.py`
- 不修改 `sector_heat.py` / `sector_cooldown.py`

完成判定：

- engine 不再直接拥有 `sector entry selector` 的核心实现，只保留兼容入口

### E4-S4：补 focused tests

新增：

- `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`

最小要求：

- 历史样本不足时保留 soft retain 降权语义
- structure 未确认时降权保留
- fundamentals 未通过时降权保留
- role 分配与 relative strength bonus 正确
- 排序与 `top_n` 截断正确
- 输出对象 shape 不漂移

复用：

- `tests/unit/test_lowfreq_workbench_formal_consumption.py`

最小要求：

- workbench 侧继续消费 `StockCandidate` 风格对象

明确不把以下测试当主护栏：

- `signal_convergence`

但若实现触及 `get_sector_candidates()` 的 facade 注入层，可额外补跑最小回归。

完成判定：

- 本轮既保护新 owner，也保护现有 consumer

### E4-S5：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`
- `python3 -m pytest tests/unit/test_lowfreq_workbench_formal_consumption.py`

并补充：

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/sector_entry_selector.py`

如实现触及 `get_sector_candidates()` facade 注入路径，再补跑：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

完成判定：

- `sector entry selector` owner 无回归
- workbench consumer 无回归
- 生产代码语法通过

### E4-S6：窄提交

提交前只允许暂存：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/sector_entry_selector.py`
- `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`
- 如确有必要，本轮触达的 `tests/unit/test_lowfreq_workbench_formal_consumption.py`

必须排除：

- `neotrade3/cycle_intelligence/sector_heat.py`
- `neotrade3/cycle_intelligence/sector_cooldown.py`
- `get_global_candidates()` 改动
- `generate_buy_signals()` 改动
- `StockCandidate` dataclass 迁移
- `apps/api/main.py`
- 其他任何既有工作区改动

## 5. Risks And Guards

风险 1：

- 为了迁移 `get_sector_candidates()`，顺手把 `get_global_candidates()` 一起带走

保护：

- 第四刀只允许碰 `get_sector_candidates()` 及其新 owner 文件

风险 2：

- 因为要凑齐依赖，把 `_weekly_series_view()` / `_get_fundamentals_batch()` 一起迁走，导致边界扩大成 selector + data adapter

保护：

- 数据视图在第四刀只通过 loader 注入消费

风险 3：

- 只迁 selector 主循环，不迁 `_structure_confirm()` / `check_weekly_duck_head()`，导致 owner 继续模糊

保护：

- 第四刀必须把最小识别 gate 一起认账

风险 4：

- 继续只依赖 consumer 载体，owner 无 focused 护栏

保护：

- 必须新增 `test_lowfreq_engine_v16_sector_entry_selector.py`

## 6. Success Criteria

本轮完成后，应满足：

- `get_sector_candidates()` 的核心 owner 已迁入 `cycle_intelligence`
- `_structure_confirm()` 与 `check_weekly_duck_head()` 的核心实现不再继续滞留在 engine
- `StockCandidate` consumer shape 保持不变
- `get_global_candidates()` 仍留作下一刀，不被第四刀误伤
- 后续仍可继续拆 parallel slice：`global scanner`

## 7. Commit Boundary

本轮 plan 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-entry-selector-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
