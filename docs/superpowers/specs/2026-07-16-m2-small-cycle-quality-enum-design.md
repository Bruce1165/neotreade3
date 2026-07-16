Status: active
Owner: cycle_intelligence
Scope: M2 SmallCycle 增补 quality_status 与 quality_reasons 枚举，并通过 object_version=2 冻结契约与 fail-closed 读回语义
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-16

# M2 SmallCycle 质量状态枚举冻结（v2）

## 1. 目标

- 为 M2 `SmallCycle` 引入可对外输出、可审计、可强校验的质量状态字段 `quality_status` 与原因集合 `quality_reasons`。
- 将“周期质量状态可输出”从“自由字符串散落”收敛为“枚举集合 + allowlist 校验”的冻结契约。
- 维持 fail-closed：任何 `SmallCycle` payload 缺字段、字段不在枚举、版本不匹配，都必须在解析阶段抛错。

## 2. 非目标

- 不在本刀新增“模型未收敛”等尚无实现依据的原因判定逻辑，仅冻结当前已有的门禁/失效原因集合。
- 不引入新的对外 API；本刀以契约、持久化、读回与测试闭环为主。

## 3. 契约设计

### 3.1 字段新增（SmallCycle）

- 新增字段：
  - `quality_status: str`
  - `quality_reasons: list[str]`
- `to_payload()` 必须包含上述字段。

### 3.2 枚举集合（字符串枚举 + allowlist）

- `quality_status` 允许值集合（冻结）：
  - `ok`
  - `blocked`
  - `invalidated`
  - `insufficient_evidence`
- `quality_reasons` 允许值集合（冻结）：
  - `target_date_not_trading_day`
  - `security_delisted`
  - `pf1_window_not_ready`
  - `price_and_continuity_broken`
  - `insufficient_evidence`

说明：
- 采用“字符串枚举 + allowlist 校验”而不是 Python `Enum` 类型，避免 JSON 序列化/读写额外复杂度，且可在 `from_dict` 中严格 fail-closed。

## 4. 版本与兼容策略

- `SMALL_CYCLE_OBJECT_VERSION` 升级为 `2`。
- `SmallCycle.from_dict(...)`：
  - 若 `object_type != "small_cycle"` 或 `object_version != 2` → 直接抛错（拒绝旧版本与错误类型）。
  - 若缺少 `quality_status` / `quality_reasons` → 抛错。
  - 若枚举不在 allowlist → 抛错。

## 5. 生成与落盘语义

- `build_small_cycle_from_m1(...)` 与 `build_small_cycle(...)` 生成 `SmallCycle` 时必须赋值：
  - `blocked`：当交易日/退市/窗口就绪门禁失败导致不可用；
  - `invalidated`：当结构破坏（如 `price_and_continuity_broken`）触发；
  - `insufficient_evidence`：当仍为中性且证据不足；
  - 其他情况为 `ok`。
- `quality_reasons` 为原因枚举列表：
  - `blocked` / `invalidated` 必须至少包含一个原因；
  - `ok` 允许为空列表。

## 6. 测试策略

- 契约解析 fail-closed：
  - 缺字段（quality_status/quality_reasons）→ 抛错
  - 非法枚举值 → 抛错
  - object_version=1 → 抛错
- 生成逻辑：
  - `build_small_cycle_from_m1(...)` 在关键门禁分支输出正确的 `quality_status` 与 `quality_reasons`（例如窗口不足、非交易日、退市、结构破坏）。
- 持久化闭环：
  - `materialize_small_cycle` 写入 artifact/ledger 后可读回等值。

## 7. 文档与验收快照更新

- 更新当前状态快照 `docs/superpowers/specs/2026-07-16-m1-m6-checklist-current-status.md`：
  - 将 M2 “周期质量状态可输出”勾选为完成 `[x]`；
  - 证据指向：`SmallCycle` v2 契约、`build_small_cycle_from_m1` 输出、以及相关单测；
  - 边界写明：原因枚举覆盖现有门禁/失效集合，不包含“模型未收敛”等未来原因。
