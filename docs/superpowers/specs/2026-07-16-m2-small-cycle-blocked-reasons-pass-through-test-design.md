Status: active
Owner: cycle_intelligence
Scope: 为 build_small_cycle 的 blocked 分支增加 reasons 透传回归，锁定多原因保序等值语义
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-16

# M2 build_small_cycle blocked reasons 透传单测

## 1. 目标

- 锁定 `build_small_cycle(...)` 在 blocked 分支（`invalidation.status="triggered"` 且不含结构破坏原因）时：
  - `quality_status == "blocked"`
  - `quality_reasons` 与输入的 `invalidation.reasons` **保序等值**（多原因透传）

## 2. 非目标

- 不锁定 `_copy_text_list` 的去空/strip 行为（避免扩大语义约束）。
- 不锁定 `cycle_state` 或 `invalidation.type` 文案。

## 3. 测试策略

- 在 `tests/unit/test_m2_small_cycle_quality_derivation.py` 新增 1 条用例：
  - `invalidation.status="triggered"`
  - `invalidation.reasons=[security_delisted, pf1_window_not_ready]`（顺序固定）
  - 断言 `quality_reasons` 与该列表完全相等（含顺序）

## 4. 验收

- `python3 -m pytest -q tests/unit/test_m2_small_cycle_quality_derivation.py` 通过。
