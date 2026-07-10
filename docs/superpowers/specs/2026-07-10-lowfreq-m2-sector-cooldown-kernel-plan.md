# Lowfreq M2 Sector Cooldown Kernel Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-cooldown-kernel-design.md`

## 1. Goal

本计划只处理 `E4: M2 legacy recognition zone` 的第二刀实现步骤。

本轮只处理：

- `detect_sector_cooldown() + _sector_cooldown_confirmed()` 这条板块退潮识别内核

目标是：

- 在 `cycle_intelligence` 下新增 `sector cooldown` 内核模块
- 把 engine 当前直接持有的板块退潮识别与确认窗口逻辑迁入该模块
- 保持 `get_hot_sectors()`、`_sector_exit_snapshot()`、`apps/api/main.py` 的现有消费 contract 不变

本轮不做：

- `get_hot_sectors()` 的热度评分、排序、跳过逻辑迁移
- `get_sector_candidates()` / `get_global_candidates()` 的扫描迁移
- `_sector_exit_snapshot()` 的退出条件与 details 改写
- `apps/api/main.py` 的 consumer-side 改造
- `cycle_intelligence` formal object contract 改写

## 2. Starting Point

当前这条内核分散在两层：

- `lowfreq_engine_v16_advanced.py`
  - `detect_sector_cooldown()`
  - `_sector_cooldown_confirmed()`
  - 以及它们被 `get_hot_sectors()`、`_sector_exit_snapshot()`、`apps/api/main.py` 读取的现状
- `neotrade3/cycle_intelligence`
  - 已有 `legacy_recognition.py`
  - 但尚未承接板块退潮识别内核

根据已批准 design，本轮只迁移 owner，不重写上层消费者。

## 3. Implementation Strategy

采用以下策略：

- 新增文件：
  - `neotrade3/cycle_intelligence/sector_cooldown.py`
- 在该文件中收口：
  - `detect_sector_cooldown(...)`
  - `confirm_sector_cooldown(...)`
- `lowfreq_engine_v16_advanced.py` 只做三类改动：
  - 引入新 facade
  - 将 engine 原方法改为 thin facade
  - 删除原方法中的核心实现
- 测试面采用：
  - 新增一份 kernel-focused test
  - 复用 `sell_logic` 做 consumer regression

## 4. Execution Steps

### E4-S1：冻结文件边界与输出面

实现前先锁定本轮允许改动的文件：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/sector_cooldown.py`
- `tests/unit/test_lowfreq_engine_v16_sector_cooldown_kernel.py`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

同时冻结这条内核的输出面：

- `detect_sector_cooldown(...)` 继续返回：
  - `cooldown_detected`
  - `follower_weakness`
  - `leader_strength`
  - `trend_state`
  - `leader_avg`
  - `follower_avg`
- `confirm_sector_cooldown(...)` 继续返回：
  - `confirmed`
  - `hits`
  - `checked`
  - `latest`

完成判定：

- 本轮不会改动上层 consumer 的读取字段

### E4-S2：实现 `sector_cooldown.py`

在新模块中实现：

- `detect_sector_cooldown(...)`
- `confirm_sector_cooldown(...)`

实现要求：

- 输入输出 contract 保持与 engine 当前一致
- 允许通过参数显式注入成员缓存、冷却缓存和依赖 loader
- 不在该模块中引入 `SectorHeat` 组装
- 不在该模块中引入 `sell` 侧 details 文案
- 不在该模块中引入 API payload 逻辑

完成判定：

- 板块退潮识别 owner 能在 `cycle_intelligence` 下独立表达

### E4-S3：切换 engine 到 thin facade

在 `lowfreq_engine_v16_advanced.py` 中：

- 引入：
  - `detect_sector_cooldown(...)`
  - `confirm_sector_cooldown(...)`
- 将 `detect_sector_cooldown()` 改成 facade：
  - 继续暴露同名 engine 方法
  - 只负责注入 cursor、market-cap 配置与 cache
- 将 `_sector_cooldown_confirmed()` 改成 facade：
  - 继续暴露同名 engine 方法
  - 只负责注入窗口参数、交易日 loader 与 cooldown loader

明确禁止：

- 不修改 `get_hot_sectors()` 自身的热度哲学
- 不修改 `_sector_exit_snapshot()` 的判定逻辑
- 不改 `apps/api/main.py`

完成判定：

- engine 不再直接拥有这两段核心实现，只保留兼容入口

### E4-S4：补 focused tests

新增：

- `tests/unit/test_lowfreq_engine_v16_sector_cooldown_kernel.py`

最小要求：

- 数据不足时返回 `unknown` / 默认值的 shape 不漂移
- `leader_strength / follower_weakness / trend_state` 的分支判定不漂移
- `confirm_sector_cooldown(...)` 的窗口命中逻辑不漂移

复用：

- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

最小要求：

- `_sector_exit_snapshot()` 继续消费相同字段语义
- observation-only contract 不漂移

完成判定：

- 本轮既保护新 owner，也保护现有 consumer

### E4-S5：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_cooldown_kernel.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py`

并补充：

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/sector_cooldown.py`

如实现触及买入主链，再补跑：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_convergence.py`

完成判定：

- `sector cooldown` 内核无回归
- `sell` 侧 consumer 无回归
- 生产代码语法通过

### E4-S6：窄提交

提交前只允许暂存：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/sector_cooldown.py`
- `tests/unit/test_lowfreq_engine_v16_sector_cooldown_kernel.py`
- 如确有必要，本轮触达的 `tests/unit/test_lowfreq_engine_v16_sell_logic.py`

必须排除：

- `apps/api/main.py`
- `get_hot_sectors()` 的额外行为改写
- `get_sector_candidates()` / `get_global_candidates()` 改动
- `neotrade3/cycle_intelligence/contracts.py`
- `neotrade3/cycle_intelligence/assembler.py`
- 其他任何既有工作区改动

## 5. Risks And Guards

风险 1：

- 为了迁移内核，顺手改 `hot sectors` 编排

保护：

- engine 只保留 thin facade；`get_hot_sectors()` 明确不做主题扩张

风险 2：

- 为了清掉 engine 私有 helper，顺手修改 `apps/api/main.py`

保护：

- 保留 `_sector_cooldown_confirmed()` facade，API consumer 本轮不动

风险 3：

- 新模块吸进 `sell` 侧退出语义，导致 `M2` 与 `sell` 边界混账

保护：

- 新模块只返回识别结果，不返回退出结论或 details

风险 4：

- 只测 facade，不测真正的内核算法

保护：

- 必须新增 `sector_cooldown_kernel` focused test

## 6. Success Criteria

本轮完成后，应满足：

- `detect_sector_cooldown()` 与 `_sector_cooldown_confirmed()` 的核心 owner 已迁入 `cycle_intelligence`
- engine 仅保留兼容 facade，而不是继续持有核心实现
- `get_hot_sectors()`、`_sector_exit_snapshot()`、`apps/api/main.py` 的消费语义保持不变
- 后续仍可继续拆下一刀 `hot sectors` 编排，而不会被第二刀拖成整链混改

## 7. Commit Boundary

本轮 plan 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-cooldown-kernel-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
