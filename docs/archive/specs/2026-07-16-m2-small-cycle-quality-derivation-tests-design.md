Status: active
Owner: cycle_intelligence
Scope: 为 build_small_cycle 的 quality_status/quality_reasons 派生规则补齐单测覆盖（4 分支全覆盖）
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-16

# M2 build_small_cycle 质量派生规则单测

## 1. 目标

- 为 `neotrade3.cycle_intelligence.assembler.build_small_cycle(...)` 的质量派生规则增加单测，锁定以下输出：
  - `quality_status`
  - `quality_reasons`
- 覆盖 4 分支：`ok / blocked / invalidated / insufficient_evidence`。

## 2. 非目标

- 不修改生产代码逻辑与优先级（只补测试）。
- 不验证 `cycle_state` 文案与 `invalidation.type` 文案（避免脆弱耦合）。

## 3. 测试策略

- 新增测试文件：`tests/unit/test_m2_small_cycle_quality_derivation.py`
- 每条用例通过显式构造入参来触发分支：
  - ok：`invalidation.status="not_triggered"` 且 `state_stability_level != "insufficient_evidence"`
  - blocked：`invalidation.status="triggered"` 且 `reasons` 不包含 `price_and_continuity_broken`
  - invalidated：`invalidation.status="triggered"` 且 `reasons` 包含 `price_and_continuity_broken`
  - insufficient_evidence：`invalidation.status="not_triggered"` 且 `state_stability_level == "insufficient_evidence"`
- 断言口径：
  - 仅断言 `quality_status` 与 `quality_reasons` 等值（按 constants）。

## 4. 验收

- `python3 -m pytest -q tests/unit/test_m2_small_cycle_quality_derivation.py` 通过。
