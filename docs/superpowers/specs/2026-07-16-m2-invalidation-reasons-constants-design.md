Status: active
Owner: cycle_intelligence
Scope: 将 M2 SmallCycle 的 invalidation.reasons 写入侧从字符串字面量收敛到 contracts 常量，并补齐单测以锁定原因集合
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-16

# M2 invalidation reasons 常量化 + 单测

## 1. 目标

- 将 `build_small_cycle_from_m1(...)` 内的 `invalidation.reasons` 写入从自由字符串字面量，收敛为 `neotrade3.cycle_intelligence.contracts` 中已冻结的原因常量集合。
- 维持 fail-closed 语义不变：本刀只做“写入侧常量化 + 单测锁定”，不引入兼容推导、不改变输出结构。

## 2. 非目标

- 不新增原因枚举项（原因集合已在上一刀 SmallCycle v2 中冻结）。
- 不调整 invalidation.type 的现有字符串语义（仍保持当前的分类文案）。
- 不新增对外 API 或额外落盘形态。

## 3. 设计与实现

### 3.1 常量来源

- 使用 contracts 中已有常量：
  - `SMALL_CYCLE_QUALITY_REASON_TARGET_DATE_NOT_TRADING_DAY`
  - `SMALL_CYCLE_QUALITY_REASON_SECURITY_DELISTED`
  - `SMALL_CYCLE_QUALITY_REASON_PF1_WINDOW_NOT_READY`
  - `SMALL_CYCLE_QUALITY_REASON_PRICE_AND_CONTINUITY_BROKEN`

### 3.2 修改点

- 文件：`neotrade3/cycle_intelligence/assembler.py`
- 修改：将
  - `"target_date_not_trading_day"` / `"security_delisted"` / `"pf1_window_not_ready"` / `"price_and_continuity_broken"`
  替换为对应常量。

## 4. 测试策略

- 更新或新增单测覆盖（只验证输出，不验证内部是否直接引用常量）：
  - 仅触发单一门禁时，`payload["invalidation"]["reasons"]` 必须等于对应常量字符串值；
  - 覆盖至少三类原因：
    - 非交易日
    - 退市
    - 窗口不足
- 测试文件优先复用：`tests/unit/test_m2_m3_contract_skeleton.py`

## 5. 验收

- 代码侧：`assembler.py` 中不再出现上述四个原因字符串字面量写入。
- 测试侧：相关单测通过，且断言以 contracts 常量为准。
