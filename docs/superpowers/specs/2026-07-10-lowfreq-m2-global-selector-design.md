# Lowfreq M2 Global Selector Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E4: M2 legacy recognition zone` 的第五刀设计。

本轮只冻结：

- `get_global_candidates()` 这条 `global selector`

目标是：

- 把 engine 中已经独立成形的跨板块候选扫描、识别、降权保留和候选输出装配职责认账出来
- 把第五刀严格限制在 `cross-sector stock candidate selection` 这一层，不把主链 orchestration、API 消费层或前一刀的 `sector selector` 一起拖进来
- 与第四刀 `sector_entry_selector` 形成对称 owner 边界
- 补上当前 `get_global_candidates()` owner-focused 护栏缺口，而不是继续只依赖 consumer regression

本设计不是：

- `generate_buy_signals()` 的主链 orchestration 改造
- `get_sector_candidates()` 的再次改写
- `StockCandidate` dataclass 定义位置迁移
- API、workbench、report consumers 的 payload 改写
- 共享评分规则的大规模去重重写

## 2. Scope

Included:

- [get_global_candidates](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2672-L3050) 的职责认账与剥离设计
- 该链中的 cross-sector selector orchestration：
  - 全市场 seed rows 拉取
  - `exclude_sectors` / `exclude_codes` 过滤
  - fundamentals batch 读取
  - 历史视图装配
  - structure confirm
  - wave phase 判定
  - resonance / volume / price position / MA / 市值打分
  - 按 sector 分桶 role 分配
  - focus gate 消费
  - strong leader soft release 消费
  - `StockCandidate` 输出组装、全局排序与 `top_n` 截断
- 与第四刀 `sector_entry_selector` 的重复/差异边界
- 与现有 `signal_convergence` 的 consumer 兼容边界

Excluded:

- [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3051-L3188) 的流程改写
- [build_sector_candidates](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py#L14-L340) 的再次重构
- `StockCandidate` dataclass 定义迁移
- `_get_recent_price_history_batch(...)`、`_get_fundamentals_batch(...)`、`_market_focus_snapshot(...)` 这类数据视图/缓存入口的重写
- `apps/api/main.py`、workbench/report consumers 的读取方式改写
- 本轮就把 sector/global 两条 selector 强行合并成一个共享大内核

## 3. Existing Context

当前仓库已经给出七组直接证据：

- 第四刀后，`get_sector_candidates()` 已经收缩为 thin facade，而 `get_global_candidates()` 仍持有完整的 cross-sector selector 实现：
  - [get_global_candidates](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2672-L3050)
  - [build_sector_candidates](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_entry_selector.py#L14-L340)
- `get_global_candidates()` 当前混合了至少九类职责：
  - 全市场涨幅 seed SQL
  - `exclude_sectors` / `exclude_codes` 过滤
  - fundamentals batch 读取
  - 历史数据视图与 wave 检测
  - structure confirm
  - 共振 / 量价 / 均线 / 市值打分
  - 按 sector 分桶 role 分配
  - focus gate 与 strong leader soft release
  - `StockCandidate` shaping、排序与截断
- `generate_buy_signals()` 明确把 `get_global_candidates()` 当作一个上游 selector 来消费，而不是其内部子步骤：
  - [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L3051-L3188)
- API 和脚本也把它当作“候选提供者”消费：
  - [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L24152-L24160)
  - [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L24706-L24709)
  - [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L473-L487)
- 当前 focused tests 对 `get_global_candidates()` 只有少量直接保护：
  - [test_lowfreq_engine_v16_financial_report_visibility.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_financial_report_visibility.py#L153-L235)
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L1032-L1077)
- 当前 consumer tests 主要保护的是主链接线，而不是 `global selector` 本体：
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L299)
- `get_global_candidates()` 与 `sector_entry_selector` 已存在大面积平行重复，但差异点仍然真实存在：
  - 前者是跨板块扫描、按 sector 分桶 role、`signal_source="cross_sector"`
  - 后者是单板块扫描、板块内 role、`signal_source="hot_sector"`

现状问题不是“没有 global candidate 逻辑”，而是：

- owner 仍然混在 engine 主体里
- 直接测试只覆盖了其中两小块分支
- 与 sector selector 的重复开始变得显著，但尚未有安全的 owner 边界承接这些重复

## 4. Approach Options

### Option A: 迁移整条 `get_global_candidates()` selector 到独立模块（推荐）

- 在 `neotrade3/cycle_intelligence/` 下新增只承接跨板块 entry selector 的窄模块
- 把 `get_global_candidates()` 主体实现迁入该模块
- engine 只保留 facade，以及数据加载/缓存入口注入

Pros:

- 与第四刀形成对称边界，重组顺序清晰
- 能直接补 owner-focused test，而不是继续依赖 consumer regression
- 先固定 owner，再讨论与 `sector_entry_selector` 的安全复用点，风险最低

Cons:

- 需要处理多个 loader/hook 的注入面
- 暂时接受 sector/global 之间仍有一部分重复，不在第五刀强行一并去重

### Option B: 只迁 seed/filter 子切片

- 新模块只承接全市场 seed SQL 与 exclude 过滤
- 后半段评分、role、focus、candidate shaping 继续留在 engine

Pros:

- diff 更小

Cons:

- owner 仍然大面积留在 engine
- 价值主要是“拆前半段 SQL”，对核心识别 owner 收口不够

### Option C: 直接合并 sector/global 两条 selector

- 将 `sector_entry_selector` 与 `get_global_candidates()` 抽成共享大内核

Pros:

- 理论上能减少重复

Cons:

- 超出第五刀当前边界
- 容易把“owner 迁移”和“共享内核抽象”混成一刀
- 风险高于当前需要

Decision:

- 采用 Option A

## 5. Design

### 5.1 Ownership Decision

本轮要剥离的是以下职责：

- 全市场 seed rows 扫描
- excludes 过滤
- fundamentals / 历史视图消费
- structure confirm
- wave 检测
- resonance / volume / MA / position / 市值打分
- 按 sector 分桶的 role 调整
- focus gate 与 soft release 的消费接线
- `StockCandidate` 风格输出构造、排序与截断

这些职责应定义为：

- `M2 stock-level global selector`

而不是：

- `generate_buy_signals()` 主链
- `M2 hot sector selector`
- API / workbench consumer adapter
- “共享评分内核”抽象层

### 5.2 Recommended File Boundary

推荐新增一个窄模块：

- `neotrade3/cycle_intelligence/global_entry_selector.py`

该文件只承接：

- `build_global_candidates(...)`

可保留必要的内部 helper，例如：

- `load_global_seed_rows(...)`
- `filter_seed_rows(...)`
- `load_global_history_views(...)`
- `assign_global_roles_by_sector(...)`

不承接：

- `get_sector_candidates()`
- `generate_buy_signals()`
- `StockCandidate` dataclass 定义迁移
- `formal_front` 组装
- API/workbench/report payload 组装

推荐原因：

- 这一刀的语义已经不是 sector-local selector，而是典型的 global scanner
- 直接放进独立文件，可以先把 owner 认账清楚，再在后续判断 sector/global 哪些 helper 值得安全复用
- 避免在第五刀把“平行 owner 迁移”误做成“共享大内核改造”

### 5.3 Adapter Surface

推荐在新模块中暴露一个主 facade：

- `build_global_candidates(...)`

推荐的输入输出面：

- 输入：
  - `cursor`
  - `target_date`
  - `top_n`
  - `market_cap_min`
  - `market_cap_max`
  - `exclude_sectors`
  - `exclude_codes`
  - `cup_handle_enabled`
  - `cup_handle_bonus`
  - `relative_strength_bonus_cap`
  - `release_enabled`
  - `release_min_score`
  - `structure_confirm_loader`
  - `fundamentals_loader`
  - `history_batch_loader`
  - `wave_phase_loader`
  - `market_focus_snapshot_loader`
  - `stock_candidate_factory`
- 输出：
  - `list[StockCandidate-like object]`

关键设计决策：

- 新模块拥有 global selector 的输出 shaping
- 但为了避免新模块直接 import engine，本轮不迁移 `StockCandidate` 定义位置
- 由 engine facade 注入 `stock_candidate_factory=StockCandidate`
- `confirm_structure`、`passes_core_focus_gate(...)` 与 `apply_strong_leader_soft_release(...)` 继续作为既有算法依赖被消费，不在本轮改写

### 5.4 Relationship With Sector Selector

第五刀不应把重点放在“共享化”，但必须把边界说清楚。

与第四刀 `sector_entry_selector` 的重复部分：

- fundamentals 软降权
- structure 软降权
- 历史样本不足 soft retain
- resonance / volume / MA / position / 市值打分
- focus gate / follower soft / strong leader soft release
- `StockCandidate` 风格输出

与第四刀的真实差异：

- seed 来源不同：sector 内 top rows vs 全市场 seed rows
- 分组维度不同：单板块 role vs 按 sector 分桶 role
- history/wave 入口不同：sector selector 当前顺带产出 wave；global selector 直接走 batch history + wave loader
- 输出语义不同：`signal_source="hot_sector"` vs `signal_source="cross_sector"`

因此本轮不做：

- sector/global 两条 selector 的强行合并

本轮只做：

- 先把 global selector owner 从 engine 中认账出来

### 5.5 What Stays In Engine

第五刀后，以下职责仍留在 engine：

- `get_global_candidates()` 方法名本身，作为兼容 facade 暂留
- `StockCandidate` dataclass 定义位置
- `_get_recent_price_history_batch(...)`
- `_get_fundamentals_batch(...)`
- `_market_focus_snapshot(...)`
- `get_sector_candidates()`
- `generate_buy_signals()`

原因：

- 第五刀只认账 global selector，不顺手改主链
- 当前 consumers 已直接 import `StockCandidate`
- 数据适配入口在本轮可以通过 loader 注入稳定复用

### 5.6 Data Flow

推荐的数据流顺序是：

1. engine `get_global_candidates()` 建立 `cursor` 与配置注入
2. facade 调用 `build_global_candidates(...)`
3. `build_global_candidates(...)` 内部：
   - 拉取全市场 seed rows
   - 执行 `exclude_sectors` / `exclude_codes` 过滤
   - 批量读取 fundamentals
   - 批量读取 history / wave views
   - 执行 structure confirm
   - 计算 resonance / volume / MA / position / strength
   - 按 sector 分桶分配 role，并追加 relative strength bonus
   - 调用 focus gate 与 strong leader soft release
   - 用 `stock_candidate_factory` 构造输出
   - 全局排序并截断 `top_n`

保持不变的语义包括：

- `capture-first` 的 soft retain 逻辑
- `fundamentals_soft_fail` / `structure_soft_fail` / `focus_soft_fail`
- `signal_source="cross_sector"`
- 最终按 `buy_score` 排序并截断

### 5.7 Testing Strategy

本轮测试建议分两层：

- 新增 owner-level focused carrier：
  - `tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`
- 复用现有 consumer-level carrier：
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L132-L299)

新 focused carrier 至少保护：

- `exclude_sectors` / `exclude_codes` 过滤
- `history_short` 软保留
- `fundamentals_soft_fail` / `structure_soft_fail`
- 按 sector 分桶 role 分配
- `signal_source="cross_sector"` 输出 shape
- 全局排序与 `top_n` 截断

明确不把以下测试当主护栏：

- `signal_convergence`

原因：

- 当前它主要 stub `get_global_candidates()`，只能保护 consumer 接线，不能证明 owner 无回归

### 5.8 Validation Baseline

第五刀完成后，至少验证：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_global_entry_selector.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/global_entry_selector.py`

如实现触及 `generate_buy_signals()` 的 facade 注入面，再补跑：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

## 6. Risks And Guards

风险 1：

- 顺手把 `generate_buy_signals()` 一起改掉，导致第五刀扩大成 selector + 主链

保护：

- 第五刀只允许碰 `get_global_candidates()` 及其新 owner 文件

风险 2：

- 因为看到 sector/global 重复，就在第五刀强行抽共享大内核

保护：

- 第五刀只做 owner 迁移，不做跨 owner 共享抽象

风险 3：

- 为了迁移 `get_global_candidates()`，顺手把 data adapter 一起迁走，导致边界扩大成 selector + data adapter

保护：

- `_get_recent_price_history_batch()`、`_get_fundamentals_batch()` 等数据入口在第五刀只通过 loader 注入消费

风险 4：

- 继续只依赖 consumer tests，owner 无 focused 护栏

保护：

- 必须新增 `test_lowfreq_engine_v16_global_entry_selector.py`

## 7. Success Criteria

本轮完成后，应满足：

- `get_global_candidates()` 的核心 owner 已迁入 `cycle_intelligence`
- `signal_source="cross_sector"` consumer shape 保持稳定
- `generate_buy_signals()` 仍只作为 consumer，不被第五刀误伤
- sector/global 两条 selector 都已有清晰 owner 位点
- 后续若要处理 sector/global 共享评分内核，可以在 owner 明确后再单独设计

## 8. Commit Boundary

本轮 design 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-global-selector-design.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
