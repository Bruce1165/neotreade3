# Lowfreq M2 Sector Entry Selector Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E4: M2 legacy recognition zone` 的第四刀设计。

本轮只冻结：

- `get_sector_candidates()` 这条 `sector entry selector`

目标是：

- 把 engine 中已经独立成形的板块内个股扫描、识别、降权保留和候选输出装配职责认账出来
- 把第四刀严格限制在 `hot sector -> stock candidate selection` 这一层，不把跨板块扫描或买入主链一起拖进来
- 为后续 `get_global_candidates()` 的平行收口保留清晰接缝
- 补上当前缺失的 owner-focused 护栏，而不是继续只依赖 consumer regression

本设计不是：

- `get_global_candidates()` 的跨板块扫描迁移
- `generate_buy_signals()` 的主链 orchestration 改造
- `formal_front`、API、workbench、report consumers 的 payload 改写
- `StockCandidate` dataclass 定义位置迁移

## 2. Scope

Included:

- [get_sector_candidates](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2698-L3146) 的职责认账与剥离设计
- 该链中的 stock-level selector orchestration：
  - sector 内 top rows 拉取
  - fundamentals batch 读取
  - 30/60 日历史装配
  - wave phase 判定
  - weekly strength / relative strength 计算
  - role 分配
  - focus gate 消费
  - strong leader soft release 消费
  - `StockCandidate` 输出组装、排序与 `top_n` 截断
- 与 `_structure_confirm()` / `check_weekly_duck_head()` 的 owner 边界
- 与现有 `signal_convergence` / workbench consumer 的兼容边界

Excluded:

- [get_global_candidates](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3148-L3496) 的迁移或去重
- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3527-L3627) 的流程改写
- `passes_core_focus_gate(...)` / `apply_strong_leader_soft_release(...)` 的算法改写
- `_weekly_series_view(...)`、`_get_fundamentals_batch(...)`、`_market_focus_snapshot(...)` 这类数据视图/缓存入口的重写
- `apps/api/main.py`、`formal_front.py`、workbench/report consumers 的读取方式改写

## 3. Existing Context

当前仓库已经给出六组直接证据：

- 第三刀后，`get_hot_sectors()` 已经收缩为 thin facade，而 `get_sector_candidates()` 仍持有完整的 stock-level selector 实现：
  - [get_hot_sectors](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2671-L2693)
  - [get_sector_candidates](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2698-L3146)
- `get_sector_candidates()` 当前混合了至少八类职责：
  - SQL 拉取 sector 内候选池
  - fundamentals batch 读取
  - history / weekly view 装配
  - structure confirm
  - wave phase 判定
  - resonance / volume / price position / MA 打分
  - role 与 relative strength 调整
  - `StockCandidate` shaping 与排序
- `_structure_confirm()` 仍留在 engine，直接消费 [check_weekly_duck_head](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2082-L2144) 与 cup handle 结果，本质上仍属于 `M2 recognition gate`，不是 `M3` 主链动作：
  - [_structure_confirm](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1554-L1588)
- `generate_buy_signals()` 明确把 `get_sector_candidates()` 当作一个上游 selector 来消费，而不是其内部子步骤：
  - [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3527-L3627)
- 当前测试对 `get_sector_candidates()` 的 owner 保护明显不足：
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L180) 对 `get_sector_candidates()` 使用 stub，只保护 orchestrator 接线
  - [test_lowfreq_workbench_formal_consumption.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_workbench_formal_consumption.py#L11-L86) 也只证明 consumer 继续消费 `StockCandidate`
- 与之相对，`get_global_candidates()` 已经有少量 focused test，这进一步说明第四刀优先补 `get_sector_candidates()` 的 owner 护栏最有价值：
  - [test_lowfreq_engine_v16_financial_report_visibility.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py#L153-L235)

现状问题不是“没有 sector candidate 逻辑”，而是：

- owner 仍然混在 engine 主体里
- 相关识别 gate 没有被独立认账
- consumer regression 看起来稳定，但 selector 本体漂移时没有直接护栏

## 4. Approach Options

### Option A: 迁移整条 `get_sector_candidates()` selector 到独立模块，并把最小识别 gate 一并认账（推荐）

- 在 `neotrade3/cycle_intelligence/` 下新增只承接板块内 entry selector 的窄模块
- 把 `get_sector_candidates()` 主体实现迁入该模块
- 把 `_structure_confirm()` 与 `check_weekly_duck_head()` 作为该 selector 的最小识别 owner 一并迁入
- engine 只保留 facade，以及数据加载/缓存入口注入

Pros:

- 真正完成第四刀 owner 认账，而不是只搬外壳
- 与前三刀形成更清晰的层级关系：
  - `legacy_recognition -> sector_cooldown -> sector_heat -> sector_entry_selector`
- 可以直接补一份 owner-focused test，覆盖当前真实缺口

Cons:

- 需要处理多个 loader/hook 的注入面
- 需要决定 `_weekly_series_view()` 等数据视图留在 engine 还是继续下沉

### Option B: 只迁 `get_sector_candidates()` 外层编排，识别 gate 继续留在 engine

- 新模块只接 `get_sector_candidates()` 主循环
- `_structure_confirm()` / `check_weekly_duck_head()` 继续由 engine 提供回调

Pros:

- diff 更小

Cons:

- `M2` 的关键识别 owner 仍残留在 engine
- 只完成“半薄化”，后续还要回头再切同一主题

### Option C: 直接合并 `get_sector_candidates()` 和 `get_global_candidates()`

Pros:

- 可以同步处理重复逻辑

Cons:

- 明显超出第四刀已确认边界
- 会把 sector-local selector 和 global scanner 混成一刀
- 风险高于当前需要

Decision:

- 采用 Option A

## 5. Design

### 5.1 Ownership Decision

本轮要剥离的是以下职责：

- 板块内 top rows 扫描
- fundamentals / history / weekly return 视图消费
- structure confirm
- weekly duck head 结构 gate
- wave phase / resonance / volume / MA / price position 打分
- relative strength 与 role 调整
- focus gate 与 soft release 的消费接线
- `StockCandidate` 风格输出构造与排序

这些职责应定义为：

- `M2 stock-level sector entry selector`

而不是：

- `M2 sector heat orchestration`
- `global opportunity scanner`
- `generate_buy_signals()` 主链
- API / workbench consumer adapter

### 5.2 Recommended File Boundary

推荐新增一个窄模块：

- `neotrade3/cycle_intelligence/sector_entry_selector.py`

该文件只承接：

- `build_sector_candidates(...)`
- `confirm_structure(...)`
- `check_weekly_duck_head(...)`

可保留必要的内部 helper，例如：

- `load_sector_top_rows(...)`
- `load_history_views_for_codes(...)`
- `assign_sector_roles(...)`

不承接：

- `get_global_candidates()`
- `generate_buy_signals()`
- `StockCandidate` dataclass 定义迁移
- `formal_front` 组装
- API/workbench/report payload 组装

推荐原因：

- 这条链语义上已经不是 sector-level heat，也不是主链 orchestration，而是典型的 stock-level selector
- 用独立文件可以避免再次把多层职责塞回 `legacy_recognition.py`
- 后续第五刀若要切 `get_global_candidates()`，可以直接复用该文件的 selector 结构，而不是重新从 engine 拆第二次

### 5.3 Adapter Surface

推荐在新模块中暴露一个主 facade：

- `build_sector_candidates(...)`

推荐的输入输出面：

- 输入：
  - `cursor`
  - `sector`
  - `target_date`
  - `top_n`
  - `market_cap_min`
  - `market_cap_max`
  - `cup_handle_enabled`
  - `cup_handle_bonus`
  - `weekly_duck_head_config`
  - `relative_strength_bonus_cap`
  - `release_enabled`
  - `release_min_score`
  - `fundamentals_loader`
  - `weekly_series_loader`
  - `cup_handle_loader`
  - `market_focus_snapshot_loader`
  - `stock_candidate_factory`
- 输出：
  - `list[StockCandidate-like object]`

关键设计决策：

- 新模块拥有 selector 的输出 shaping
- 但为了避免新模块直接 import engine，本轮不迁移 `StockCandidate` 定义位置
- 由 engine facade 注入 `stock_candidate_factory=StockCandidate`
- `passes_core_focus_gate(...)` 与 `apply_strong_leader_soft_release(...)` 继续作为已存在算法依赖被消费，不在本轮改写

### 5.4 Recognition Gate Ownership

第四刀若只迁 `get_sector_candidates()` 外壳而不迁：

- `_structure_confirm()`
- `check_weekly_duck_head()`

则 owner 仍然是不完整的。

因此本轮明确把：

- [_structure_confirm](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1554-L1588)
- [check_weekly_duck_head](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2082-L2144)

一起认账为 `sector entry selector` 的最小识别 gate。

但本轮不继续下沉：

- `_weekly_series_view(...)`
- `_get_fundamentals_batch(...)`

原因：

- 这两者当前更像稳定的数据视图/缓存入口
- 先通过 loader 注入消费它们，可以避免第四刀扩大成“selector + data adapter”双主题

### 5.5 What Stays In Engine

`E4` 第四刀后，以下职责仍留在 engine：

- `get_sector_candidates()` 方法名本身，作为兼容 facade 暂留
- `StockCandidate` dataclass 定义位置
- `_weekly_series_view(...)`
- `_get_fundamentals_batch(...)`
- `_market_focus_snapshot(...)`
- `get_global_candidates()`
- `generate_buy_signals()`

原因：

- 第四刀只认账 sector-local selector，不顺手切 global scanner
- 当前 consumers 已直接 import `StockCandidate`
- 数据适配入口在本轮可以稳定通过 loader 注入复用，无需同时迁走

### 5.6 Data Flow

推荐的数据流顺序是：

1. engine `get_sector_candidates()` 建立 `cursor` 与配置注入
2. facade 调用 `build_sector_candidates(...)`
3. `build_sector_candidates(...)` 内部：
   - 拉取 sector top rows
   - 批量读取 fundamentals
   - 批量读取 history / weekly views
   - 执行 `confirm_structure(...)`
   - 计算 wave / resonance / volume / MA / position / strength
   - 分配 role 并追加 relative strength bonus
   - 调用 focus gate 与 strong leader soft release
   - 用 `stock_candidate_factory` 构造输出
   - 排序并截断 `top_n`

保持不变的语义包括：

- `capture-first` 的 soft retain 逻辑
- `fundamentals_soft_fail` / `structure_soft_fail` / `focus_soft_fail`
- 龙头 / 中军 / 跟随三类 role 调整
- 最终按 `buy_score` 排序并截断

### 5.7 Testing Strategy

本轮测试建议分两层：

- 新增 owner-level focused carrier：
  - `tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`
- 复用现有 consumer-level carrier：
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L180)
  - [test_lowfreq_workbench_formal_consumption.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_workbench_formal_consumption.py#L11-L86)

新 focused carrier 至少保护：

- 历史样本不足时的 soft retain 行为
- structure 未确认时的降权保留
- fundamentals 未通过时的降权保留
- role 分配与 relative strength bonus
- `top_n` 排序截断
- `StockCandidate-like` 输出 shape 不漂移

明确不把以下测试当主护栏：

- `signal_convergence`

原因：

- 当前它 stub 掉了 `get_sector_candidates()`，不能证明 owner 无回归

### 5.8 Validation Baseline

第四刀完成后，至少验证：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_entry_selector.py`
- `python3 -m pytest tests/unit/test_lowfreq_workbench_formal_consumption.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/sector_entry_selector.py`

如实现触及 `generate_buy_signals()` 的 facade 注入面，再补跑：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 6. Risks And Guards

风险 1：

- 顺手把 `get_global_candidates()` 一起带走，导致第四刀扩大成 selector 合并

保护：

- 第四刀只允许碰 `get_sector_candidates()` 及其新 owner 文件

风险 2：

- 为了凑齐识别链，把 `_weekly_series_view()` 和 fundamentals adapter 一起迁走，导致边界从 selector 扩大到 data adapter

保护：

- 这类数据视图在第四刀只通过 loader 注入消费，不认账为本轮 owner

风险 3：

- 只迁 selector 外壳，不迁 `_structure_confirm()` / `check_weekly_duck_head()`，导致 owner 继续模糊

保护：

- 第四刀必须把最小识别 gate 一起认账

风险 4：

- 继续只依赖 consumer tests，owner 无 focused 护栏

保护：

- 必须新增 `test_lowfreq_engine_v16_sector_entry_selector.py`

## 7. Success Criteria

本轮完成后，应满足：

- `get_sector_candidates()` 的核心 owner 已迁入 `cycle_intelligence`
- `_structure_confirm()` 与 `check_weekly_duck_head()` 不再继续滞留在 engine 作为未认账识别 gate
- `get_global_candidates()` 仍留作下一刀，而不是被第四刀顺手吞掉
- `StockCandidate` consumer shape 保持稳定
- 后续可继续把 `global scanner` 作为平行 slice 独立推进

## 8. Commit Boundary

本轮 design 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-entry-selector-design.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
