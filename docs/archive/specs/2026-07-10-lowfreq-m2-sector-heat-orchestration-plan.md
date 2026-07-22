# Lowfreq M2 Sector Heat Orchestration Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-heat-orchestration-design.md`

## 1. Goal

本计划只处理 `E4: M2 legacy recognition zone` 的第三刀实现步骤。

本轮只处理：

- `get_hot_sectors()` 这条 `hot sectors` heat orchestration

目标是：

- 在 `cycle_intelligence` 下新增 `sector heat` orchestration 模块
- 把 engine 当前直接持有的 sector-level aggregation、skip policy、bonus、sorting 与 `SectorHeat` shaping 迁入该模块
- 保持 `sector cooldown kernel`、`get_sector_candidates()` 与 consumer contract 不变

本轮不做：

- `sector_cooldown` 算法与输出字段改写
- `get_sector_candidates()` / `get_global_candidates()` 的 stock-level 选择迁移
- `SectorHeat` dataclass 定义位置迁移
- `apps/api/main.py`、workbench、report consumers 改造

## 2. Starting Point

当前这条链分散在两层：

- `lowfreq_engine_v16_advanced.py`
  - `get_hot_sectors()`
  - `SectorHeat`
  - `_recent_trading_dates()`
- `neotrade3/cycle_intelligence`
  - 已有 `sector_cooldown.py`
  - 但尚未承接 `hot sectors` orchestration

根据已批准 design，本轮只迁移 sector-level heat orchestration owner，不重写 stock-level selection。

## 3. Implementation Strategy

采用以下策略：

- 新增文件：
  - `neotrade3/cycle_intelligence/sector_heat.py`
- 在该文件中收口：
  - `build_hot_sectors(...)`
  - 若干内部 helper，用于 sector display name / recent avg / daily aggregate / scoring
- `lowfreq_engine_v16_advanced.py` 只做三类改动：
  - 引入新 facade
  - 将 `get_hot_sectors()` 改成 thin facade
  - 删除原方法中的核心实现
- `SectorHeat` 不迁移，由 engine 通过 `sector_heat_factory=SectorHeat` 注入
- 日志行为不硬编码在新模块内，通过 `skip_logger` 注入
- 测试面采用：
  - 新增一份 owner-focused test
  - 复用 workbench formal consumption 做 consumer regression

## 4. Execution Steps

### E4-H1：冻结文件边界与 contract

实现前先锁定本轮允许改动的文件：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/sector_heat.py`
- `tests/unit/test_lowfreq_engine_v16_sector_heat.py`
- 如确有必要，`tests/unit/test_lowfreq_workbench_formal_consumption.py`

同时冻结输出面：

- `get_hot_sectors()` 继续返回 `list[SectorHeat]`
- `SectorHeat` 字段集合保持不变：
  - `sector`
  - `name`
  - `heat_score`
  - `momentum_5d`
  - `stock_count`
  - `trend_state`
  - `leader_strength`
  - `follower_weakness`

完成判定：

- 本轮不会改动 `SectorHeat` consumer 的字段读取方式

### E4-H2：实现 `sector_heat.py`

在新模块中实现：

- `build_hot_sectors(...)`

必要的内部 helper 至少包括：

- `load_sector_display_names(...)`
- `load_recent_avg_by_sector(...)`
- `load_sector_daily_aggregates(...)`
- `score_sector_heat(...)`

实现要求：

- 输入输出 contract 保持与 engine 当前一致
- 允许通过参数显式注入：
  - `recent_trading_dates_loader`
  - `sector_cooldown_loader`
  - `sector_heat_factory`
  - `skip_logger`
- 不在该模块中引入：
  - `SectorHeat` dataclass 定义
  - `sector_cooldown` 算法实现
  - `get_sector_candidates()` 逻辑

完成判定：

- `hot sectors` owner 能在 `cycle_intelligence` 下独立表达

### E4-H3：切换 engine 到 thin facade

在 `lowfreq_engine_v16_advanced.py` 中：

- 引入：
  - `build_hot_sectors(...)`
- 将 `get_hot_sectors()` 改成 facade：
  - 继续暴露同名 engine 方法
  - 只负责注入：
    - `cursor`
    - `target_date`
    - `top_n`
    - market-cap 配置
    - accel 配置
    - `self._recent_trading_dates`
    - `self.detect_sector_cooldown`
    - `SectorHeat`
    - logger hook

明确禁止：

- 不修改 `get_sector_candidates()`
- 不修改 `generate_buy_signals()` 主链
- 不修改 `apps/api/main.py`
- 不修改 `sector_cooldown.py`

完成判定：

- engine 不再直接拥有 `hot sectors` 的核心编排实现，只保留兼容入口

### E4-H4：补 focused tests

新增：

- `tests/unit/test_lowfreq_engine_v16_sector_heat.py`

最小要求：

- cooldown 命中时板块被跳过
- accel bonus 生效时 `heat_score` 正确上浮
- `trend_state == "rising"` 时加分生效
- 排序与 `top_n` 截断正确
- 输出对象 shape 不漂移

复用：

- `tests/unit/test_lowfreq_workbench_formal_consumption.py`

最小要求：

- workbench 侧继续消费 `SectorHeat` 风格对象

明确不把以下测试当主护栏：

- `signal_convergence`

但若实现触及 `get_hot_sectors()` 的 facade 注入层，可额外补跑最小回归。

完成判定：

- 本轮既保护新 owner，也保护现有 consumer

### E4-H5：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_heat.py`
- `python3 -m pytest tests/unit/test_lowfreq_workbench_formal_consumption.py`

并补充：

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/sector_heat.py`

如实现触及 `get_hot_sectors()` facade 注入路径，再补跑：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

完成判定：

- `sector heat` owner 无回归
- workbench consumer 无回归
- 生产代码语法通过

### E4-H6：窄提交

提交前只允许暂存：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/sector_heat.py`
- `tests/unit/test_lowfreq_engine_v16_sector_heat.py`
- 如确有必要，本轮触达的 `tests/unit/test_lowfreq_workbench_formal_consumption.py`

必须排除：

- `neotrade3/cycle_intelligence/sector_cooldown.py`
- `get_sector_candidates()` / `get_global_candidates()` 改动
- `SectorHeat` dataclass 迁移
- `apps/api/main.py`
- 其他任何既有工作区改动

## 5. Risks And Guards

风险 1：

- 为了迁移 `get_hot_sectors()`，顺手把 `get_sector_candidates()` 一起带走

保护：

- 第三刀只允许碰 `get_hot_sectors()` 及其新 owner 文件

风险 2：

- 因为要构造 `SectorHeat`，在新模块里直接 import engine，形成反向依赖

保护：

- 使用 `sector_heat_factory` 注入，不迁移 dataclass 定义

风险 3：

- 将 `sector_cooldown` 算法复制进 `sector_heat.py`

保护：

- 新模块只消费 `sector_cooldown_loader`

风险 4：

- 继续只依赖 consumer 载体，owner 无 focused 护栏

保护：

- 必须新增 `test_lowfreq_engine_v16_sector_heat.py`

## 6. Success Criteria

本轮完成后，应满足：

- `get_hot_sectors()` 的核心编排 owner 已迁入 `cycle_intelligence`
- `SectorHeat` consumer shape 保持不变
- `sector_cooldown` 继续只是上游依赖，不被重新混回新模块
- `get_sector_candidates()` 仍留在 engine，不被第三刀误伤
- 后续仍可继续拆下一刀 `sector entry chain`

## 7. Commit Boundary

本轮 plan 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-heat-orchestration-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
