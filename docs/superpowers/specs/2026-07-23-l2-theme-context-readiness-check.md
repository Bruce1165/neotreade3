Status: active
Owner: lowfreq / chaos-model / m1-m2
Scope: L2 theme_state_context 最小承接能力核实
Canonical: PROJECT_STATUS.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-23

# 2026-07-23 L2 theme_state_context 最小承接能力核实

## 0. 目的

本文件只回答一个问题：

- 当前仓库与运行态，是否已经具备支撑 `theme_state_context` 的最小事实能力？

本文件不展开：

- `theme_state_context` 的具体实现
- 多主题融合算法
- 行业/概念拆对象
- 传播图设计

## 1. 结论

当前结论为：

- **L2 现在可以立“最小对象”，但只能以“最小可用、双源并存、能力受限”的方式成立。**

更准确地说：

- 行业/板块事实侧已经具备较稳定的最小承接能力
- 概念事实侧已经有真实数据链与日表，但其成员来源仍依赖 cache 预热，稳定性弱于行业/板块侧
- 因此，`theme_state_context` 可以成立，但当前阶段必须显式承认其内部存在“稳定层”和“半稳定层”，不能误表述为“主题上下文已完全成熟”

## 2. 核实范围

本轮核实仅覆盖：

- 当前代码中已经存在的板块/概念事实来源
- 当前数据库中已经存在的相关表
- 当前混沌快照构建链是否已消费这些事实

本轮不核实：

- 未来主题传播关系
- 多主题权重策略
- 主题最终 ID 体系

## 3. 已核实的稳定事实

### 3.1 行业/板块主事实存在

`stocks` 表当前已稳定包含：

- `sector_lv1`
- `sector_lv2`

并已建立：

- `idx_stocks_sector_lv1`

这说明“行业/板块”不是临时缓存字段，而是数据库正式字段。

### 3.2 混沌快照已消费板块事实

`build_chaos_daily_snapshot.py` 当前已经直接使用板块相关事实构建混沌输入，包括：

- `sector_total_amount_today`
- `sector_amount_ratio_today_over_avg20`
- `sector_avg_pct_today`
- `sector_avg_pct_20d`
- `sector_rps_120`
- `sector_cooldown_detected`
- `sector_trend_deteriorating`
- `sector_leader_rollover`

这说明板块/行业上下文已经不只是理论存在，而是已进入混沌快照构建链。

### 3.3 板块相关分析能力已存在

当前仓库中，与板块/行业上下文直接相关的模块至少包括：

- `cycle_intelligence/sector_heat.py`
- `cycle_intelligence/sector_entry_selector.py`
- `cycle_intelligence/sector_cooldown.py`
- `analysis/factor_matrix.py`

这说明行业/板块上下文并不是“零基础待建”，而是已有多处活跃消费与聚合逻辑。

## 4. 已核实的概念事实

### 4.1 概念日表已存在

当前数据库中已存在：

- `ths_concept_daily`

并且当前库内已有实际数据，范围覆盖：

- `2024-09-02 -> 2026-07-23`

说明“概念主线/热度/排名”不是纯规划，而是已有 persisted 日表事实。

### 4.2 API 已具备概念主线计算与读取链

当前 API 已具备：

- 概念主线计算
- 概念主线读取
- 相关 detail 读取

这说明概念上下文已经不是纯研究脚本产物，而是进入了 API 可消费层。

### 4.3 概念成员来源仍依赖 cache 预热

当前 `ths_concept_mainline_compute_view()` 依赖：

- `_load_ths_concept_caches()`

而 `_load_ths_concept_caches()` 又依赖：

- `_tushare_concepts_cache.json`
- `_tushare_concept_members_cache.json`

这些 cache 由：

- `warm_tushare_theme_cache_view()`

负责预热与刷新。

因此，概念成员关系当前不是纯数据库自足真相源，而是：

- “DB persisted 日表 + cache 预热成员关系”的混合形态

## 5. 当前 L2 的真实能力边界

### 5.1 当前已经成立的能力

当前 L2 已经成立的最小能力是：

- 能为单只股票提供行业/板块层的上下文事实
- 能提供概念主线的 persisted 日表结果
- 能为混沌上下文提供最小主题侧的能量/趋势代理

### 5.2 当前尚未成立的能力

当前 L2 仍未正式成立的能力包括：

- 一个统一、权威、独立的 `theme_state_context` persisted truth-source
- 完整的主题成员真相源（不依赖 cache）
- 多主题冲突/优先级治理
- 行业对象与概念对象的分拆与统一桥接
- 主题传播图或邻接图

## 6. 结论解释

因此，当前对 `theme_state_context` 的最准确表述不是：

- “L2 还完全不能立”

也不是：

- “L2 已经完全成熟”

而是：

- **L2 现在可以立最小对象，但当前必须把它视为“最小可用的主题上下文对象”，且显式承认其内部稳定性不均衡：行业/板块侧较稳定，概念侧为 persisted 日表 + cache 预热混合承接。**

## 7. 当前阶段建议口径

当前阶段对 L2 的正式口径应冻结为：

- `theme_state_context` 可以成立
- 但当前阶段只允许承载最小字段类别
- 不允许把 L2 误表述为“已具备完整主题真相源”
- 不允许在此基础上继续扩展传播图、多主题融合等远端设计

## 8. 当前缺口

当前 L2 最需要补的缺口只有两类：

1. **主题事实真相源缺口**
   - 概念成员关系当前仍依赖 cache 预热
   - 尚未形成统一 persisted owner

2. **对象收口缺口**
   - 虽已有行业/板块事实与概念日表，但尚未正式收口成统一的 `theme_state_context`

## 9. 通过条件

本文件当前阶段视为通过，需同时满足：

- 已明确 L2 不是空心概念
- 已明确 L2 不是完全成熟对象
- 已明确当前最小可用边界
- 已明确当前主要缺口

在以上条件被满足后，可进入 `M6` 最小承接口径的讨论；不应继续在 L2 结构层面发散。
