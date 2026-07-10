# Lowfreq M2 Sector Cooldown Kernel Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E4: M2 legacy recognition zone` 的第二刀设计。

本轮只冻结：

- `detect_sector_cooldown() + _sector_cooldown_confirmed()` 这条板块退潮识别内核

目标是：

- 把 engine 中跨买入侧、卖出侧、API 侧共同消费的 `sector cooldown` 识别逻辑先认账为 `M2 legacy recognition`
- 把真正的识别 owner 从 engine 主体中迁出，同时不给 `hot sectors` 编排和扫描链开口子
- 保持 `get_hot_sectors()`、`_sector_exit_snapshot()`、`apps/api/main.py` 的现有消费语义不变

本设计不是：

- `get_hot_sectors()` 的热度排序与过滤迁移
- `get_sector_candidates()` / `get_global_candidates()` 的扫描迁移
- `sell` 侧退出规则重写
- API consumer 的整体改造

## 2. Scope

Included:

- [detect_sector_cooldown](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2359-L2545) 的职责认账与剥离设计
- [_sector_cooldown_confirmed](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2187-L2211) 的职责认账与剥离设计
- `sector cooldown` 内核被以下消费者读取时的兼容边界：
  - [get_hot_sectors](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2852-L2961)
  - [_sector_exit_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L4171-L4215)
  - [apps/api/main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L17579-L17583)

Excluded:

- `get_hot_sectors()` 自身的评分、排序、跳过逻辑迁移
- `get_sector_candidates()` / `get_global_candidates()` 的候选扫描职责
- `_sector_exit_snapshot()` 的退出条件改写
- `apps/api/main.py` 的 consumer-side adapter 重写
- `cycle_intelligence/contracts.py` / `assembler.py` 的 formal object contract 改写

## 3. Existing Context

当前仓库已经给出五组直接证据：

- engine 仍直接持有板块退潮识别内核：
  - [detect_sector_cooldown](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2359-L2545)
  - [_sector_cooldown_confirmed](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2187-L2211)
- `detect_sector_cooldown()` 已不是单一买入侧私有工具，而是至少被三类消费者读取：
  - [get_hot_sectors](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2919-L2955)
  - [_sector_exit_snapshot](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L4175-L4193)
  - `_sector_cooldown_confirmed()`，其结果又被 [apps/api/main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L17579-L17583) 等多个接口消费
- `sector cooldown` 的返回 shape 已形成事实 contract：
  - `cooldown_detected`
  - `follower_weakness`
  - `leader_strength`
  - `trend_state`
  - `leader_avg`
  - `follower_avg`
- `sell` 侧已经对这条 shape 建立了 focused 行为护栏：
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L575-L615)
- 与 `wave/focus` 第一刀不同，这条内核目前缺少直接的 owner-level regression，现有测试更多是 consumer 层断言

现状问题不是“没有任何板块识别”，而是：

- engine 直接拥有了板块退潮识别 SQL、分组、归一化、确认窗口逻辑
- 上层消费者已经分散，但 owner 仍集中在 engine
- 如果直接先做 `get_hot_sectors()`，会把识别内核和编排层再次混在一起

## 4. Approach Options

### Option A: 先剥离 `sector cooldown` 内核到独立模块，并在 engine 保留兼容 facade（推荐）

- 在 `neotrade3/cycle_intelligence/` 下新增一个只承接板块退潮识别内核的窄模块
- 把 `detect_sector_cooldown()` 与 `_sector_cooldown_confirmed()` 的核心逻辑迁入新模块
- engine 只保留薄 facade，继续给 `get_hot_sectors()`、`_sector_exit_snapshot()`、`apps/api` 提供兼容入口

Pros:

- owner 位点迁出 engine，但不强迫同轮修改所有消费者
- 能把 `M2 legacy recognition kernel` 与 `hot sectors` 编排清楚分开
- 最符合当前“第二刀只做内核、不做买入侧整链”的已确认边界

Cons:

- engine 会暂时保留兼容 facade，而不是像第一刀那样完全删除入口
- 需要额外写一份 kernel-focused regression，避免只测 consumer 不测 owner

### Option B: 直接迁 `get_hot_sectors()`，把 `sector cooldown` 当内部依赖顺带带走

Pros:

- 看起来更像“完整的板块热度链”

Cons:

- 会把识别内核、热度编排、跳过规则、`SectorHeat` 输出混成一刀
- `sell` 侧与 API 侧共享依赖仍然没有单独认账

### Option C: 只迁 `detect_sector_cooldown()`，保留 `_sector_cooldown_confirmed()` 在 engine

Pros:

- 改动面更小

Cons:

- API 侧仍继续绑在 engine 私有 helper 上
- 第二刀无法完整认账“内核 + 确认窗口”这组共同语义

Decision:

- 采用 Option A

## 5. Design

### 5.1 Ownership Decision

本轮要剥离的是以下职责：

- 板块成员抓取与成员缓存读取
- 板块近 5 日收益批量读取
- 龙头/中军/跟随股分组
- `leader_strength / follower_weakness / trend_state` 计算
- `cooldown_detected` 判定
- 基于最近窗口的 `_sector_cooldown_confirmed()` 统计确认

这些职责应定义为：

- `M2 legacy recognition kernel`

而不是：

- `hot sectors` 编排层
- `sell` 侧退出规则
- API consumer adapter

### 5.2 Recommended File Boundary

推荐新增一个窄模块：

- `neotrade3/cycle_intelligence/sector_cooldown.py`

该文件只承接：

- `detect_sector_cooldown(...)`
- `confirm_sector_cooldown(...)`

不承接：

- `get_hot_sectors()` 的热度评分与过滤
- `SectorHeat` 组装
- `sell` 侧 `snapshot/details` 文案
- API payload 组装

推荐原因：

- 这条链已经明显比 `wave/focus` 更偏“板块级内核”，语义上不适合继续塞进 [legacy_recognition.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/legacy_recognition.py)
- 用独立文件可以避免 `cycle_intelligence` 再次形成“所有 legacy heuristics 都塞进一个袋子”的混账状态
- 文件名能直接表达它是 `sector cooldown` 内核，而不是板块热度编排

### 5.3 Adapter Surface

推荐在新模块中暴露两个 facade：

- `detect_sector_cooldown(...)`
- `confirm_sector_cooldown(...)`

推荐的输入输出面：

- `detect_sector_cooldown(...)`
  - 输入：`cursor / sector / target_date / market_cap_min / market_cap_max / caches`
  - 输出：保持当前 dict shape，不改字段名
- `confirm_sector_cooldown(...)`
  - 输入：`sector / current_date / window / required / trading_dates_loader / cooldown_loader`
  - 输出：保持当前 dict shape：
    - `confirmed`
    - `hits`
    - `checked`
    - `latest`

设计意图：

- 识别 owner 迁出 engine
- 但 consumer contract 暂时不变

### 5.4 What Stays In Engine

`E4` 第二刀后，以下职责仍留在 engine：

- `detect_sector_cooldown()` 方法名本身，作为兼容 facade 暂留
- `_sector_cooldown_confirmed()` 方法名本身，作为兼容 facade 暂留
- `get_hot_sectors()` 的评分、排序、过滤、`SectorHeat` 输出
- `_sector_exit_snapshot()` 的退出条件与 details 文案

原因：

- `apps/api/main.py` 当前直接读取 `_sector_cooldown_confirmed()`，本轮不改 consumer
- `get_hot_sectors()` 已被确认排除在第二刀之外
- 第二刀只认账 owner，不顺手改上层编排

### 5.5 Compatibility Strategy

为了避免把 consumer 一起拖进来，本轮采用：

- `new owner + engine thin facade`

即：

- engine 中的 `detect_sector_cooldown()` 与 `_sector_cooldown_confirmed()` 不再承载核心实现
- 它们只负责把现有 engine 依赖注入到新模块 facade

这样可以同时满足：

- owner 已迁出 engine
- `get_hot_sectors()` 不必同轮改写
- `_sector_exit_snapshot()` 不必同轮改写
- `apps/api/main.py` 不必同轮改写

### 5.6 Testing Strategy

本轮测试建议分两层：

- 复用现有 consumer 护栏：
  - [test_lowfreq_engine_v16_sell_logic.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_sell_logic.py#L575-L615)
  - 如有必要，补跑依赖 `get_hot_sectors()` 的最小主链测试
- 新增一份 owner-level focused test：
  - `tests/unit/test_lowfreq_engine_v16_sector_cooldown_kernel.py`

新 focused test 应至少保护：

- 数据不足时的 `unknown` 回退 shape
- `leader_strength / follower_weakness / trend_state` 的归一化与分支判定
- `confirm_sector_cooldown(...)` 的窗口确认逻辑

明确不需要：

- 扩张到 `get_hot_sectors()` 全量行为测试
- 改写 `sell` 侧 contract 测试
- 改写 `apps/api/main.py` 测试

### 5.7 Validation Baseline

第二刀完成后，至少验证：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_cooldown_kernel.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- 如实现触及买入主链，再补最小 `signal_convergence` 验证
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/sector_cooldown.py`

## 6. Risks And Guards

风险 1：

- 顺手把 `get_hot_sectors()` 一起迁走，导致第二刀扩大成买入侧整链

保护：

- `get_hot_sectors()` 明确排除，只允许继续消费 engine facade

风险 2：

- 为了去掉 engine helper，顺手改 `apps/api/main.py`

保护：

- 本轮允许 engine 保留兼容 facade，不做 API consumer 改造

风险 3：

- 只迁 `detect_sector_cooldown()`，遗漏 `_sector_cooldown_confirmed()`，导致 API 侧 owner 继续模糊

保护：

- 第二刀必须把“识别 + 窗口确认”一起认账

风险 4：

- 现有测试只验证 consumer，不验证新 owner

保护：

- 必须补一份 kernel-focused regression

## 7. Success Criteria

本轮完成后，应满足：

- `detect_sector_cooldown()` 与 `_sector_cooldown_confirmed()` 的核心 owner 已迁出 engine
- `get_hot_sectors()`、`_sector_exit_snapshot()`、`apps/api/main.py` 的现有消费语义保持不变
- `hot sectors` 编排仍留作下一刀，而不是被第二刀顺手吞掉
- `M2` 板块退潮识别内核与上层消费者的分界更清楚

## 8. Commit Boundary

本轮 design 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-cooldown-kernel-design.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `apps/api/main.py`
- `tests/unit/*`
- 其他任何工作区改动
