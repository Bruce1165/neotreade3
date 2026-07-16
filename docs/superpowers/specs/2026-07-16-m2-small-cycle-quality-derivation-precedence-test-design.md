Status: active
Owner: cycle_intelligence
Scope: 为 build_small_cycle 的质量派生规则增加优先级回归：invalidation.triggered 优先于 state_stability_level=insufficient_evidence
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-16

# M2 build_small_cycle 质量派生优先级单测

## 1. 目标

- 锁定 `build_small_cycle(...)` 的优先级：当 `invalidation.status == "triggered"` 时，应优先走 triggered 分支，而不是被 `state_stability_level == "insufficient_evidence"` 覆盖。
- 尤其在 triggered + `price_and_continuity_broken` 场景，应输出：
  - `quality_status == "invalidated"`
  - `quality_reasons == ["price_and_continuity_broken"]`

## 2. 非目标

- 不改生产代码逻辑，仅补充单测回归。
- 不覆盖其它优先级组合矩阵（保持本刀窄）。

## 3. 测试策略

- 在 `tests/unit/test_m2_small_cycle_quality_derivation.py` 追加 1 条用例：
  - 构造：
    - `invalidation.status="triggered"`
    - `invalidation.reasons=[price_and_continuity_broken]`
    - `state_stability_level="insufficient_evidence"`
  - 断言输出仍为 invalidated（触发优先级）。

## 4. 验收

- `python3 -m pytest -q tests/unit/test_m2_small_cycle_quality_derivation.py` 通过。
