# Lowfreq M2 Sector Heat Orchestration Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E4: M2 legacy recognition zone` 的第三刀设计。

本轮只冻结：

- `get_hot_sectors()` 这条 `hot sectors` heat orchestration

目标是：

- 把 engine 中已经独立成形的板块热度编排职责先认账出来
- 明确这条链消费 `sector cooldown` 内核，但不再拥有该内核
- 保持 `get_sector_candidates()`、stock-level buy-side 选择链与 API consumer contract 不变
- 为后续继续拆 `sector entry chain` 留下干净接缝

本设计不是：

- `sector cooldown` 算法的再次迁移
- `get_sector_candidates()` / `get_global_candidates()` 的 stock-level 选择迁移
- `SectorHeat` consumer contract 的扩张式改写
- `apps/api/main.py` 或 workbench payload 的消费侧改造

## 2. Scope

Included:

- [get_hot_sectors](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2689-L2779) 的职责认账与剥离设计
- 该链中的 sector-level orchestration：
  - sector code -> display name 映射读取
  - recent trading date 平均涨幅读取
  - target-date sector aggregate 读取
  - cooldown skip policy 消费
  - accel bonus / rising-trend bonus
  - `SectorHeat` 输出组装、排序与 `top_n` 截断
- 与 `sector cooldown kernel` 的 owner 边界
- 与现有 consumer 的兼容边界

Excluded:

- [detect_sector_cooldown](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_cooldown.py#L9-L133) / [confirm_sector_cooldown](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_cooldown.py#L137-L166) 的算法与 contract 改写
- [get_sector_candidates](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2781-L2999) 的 stock-level score assembly
- `generate_buy_signals()` / `candidate_signals` 主链
- `apps/api/main.py`、workbench、report consumers 的 payload shape 改写
- `SectorHeat` dataclass 定义位置迁移

## 3. Existing Context

当前仓库已经给出六组直接证据：

- engine 仍直接持有完整的 `hot sectors` 编排链：
  - [get_hot_sectors](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2689-L2779)
- 该链已明显不是 `sector cooldown` 算法本体，而是其上层消费者：
  - 它调用 [detect_sector_cooldown](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2737-L2743)
  - 决定是否跳过板块
  - 再继续做 `heat_score` 计算与 `SectorHeat` 输出
- 这条链当前混合了至少五类职责：
  - 板块名称映射读取
  - recent average aggregation
  - target-date sector aggregation
  - orchestration scoring policy
  - `SectorHeat` 实例化与排序
- `sector cooldown kernel` 已在上一刀迁入：
  - [sector_cooldown.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/sector_cooldown.py)
  因此第三刀不应再把内核逻辑复制或重混进新模块
- 当前间接 consumer 证据存在，但 owner-level 测试明显不足：
  - [test_lowfreq_workbench_formal_consumption.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_workbench_formal_consumption.py#L11-L86)
    只证明 workbench 仍消费 `SectorHeat` 风格对象
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py#L136-L139)
    对 `get_hot_sectors()` 使用 stub，并不保护真实 owner
- 这说明第三刀若不新增 focused carrier，仍会出现“consumer 看起来没坏，但 owner 漂移没人守”的问题

现状问题不是“`hot sectors` 逻辑太小，不值得拆”，而是：

- `sector cooldown` owner 已迁出
- 但 `get_hot_sectors()` 仍在 engine 中同时拥有数据聚合、策略编排和输出构造
- 如果继续把它留在 engine，会让 `M2 sector-level orchestration` 与 engine orchestration 继续混在一起

## 4. Approach Options

### Option A: 迁移整条 `get_hot_sectors()` orchestration 到独立模块，engine 保留 thin facade（推荐）

- 在 `neotrade3/cycle_intelligence/` 下新增只承接 sector-level heat orchestration 的窄模块
- 把 sector aggregation、bonus、skip policy、sorting 和 `SectorHeat` shaping 收到该模块
- engine 只保留 cursor/config/loader 注入层

Pros:

- 真正完成第三刀的 owner 认账
- 与第二刀形成清晰上下游关系：`sector_cooldown kernel -> sector_heat orchestration`
- 不会把 `get_sector_candidates()` 一起拖进来

Cons:

- 需要处理 `SectorHeat` 构造而不引入 engine -> module 的反向依赖
- 需要补一份 owner-focused regression

### Option B: 只迁 `cooldown skip policy`

- 仅把 `cooldown_detected + follower_weakness` 的跳过规则抽走

Pros:

- diff 更小

Cons:

- ownership 仍然是混合的
- `avg_change` / accel / rising bonus / sorting 依然留在 engine
- 第三刀完成后无法明确谁拥有 `hot sectors` 编排

### Option C: 直接把 `get_hot_sectors() + get_sector_candidates()` 合并成 sector entry chain

Pros:

- 从 buy-side 角度更像一条完整主链

Cons:

- 会把 sector-level orchestration 与 stock-level candidate selection 混成一刀
- 超出当前第三刀窄边界
- 会增加 `M3` / stock score 装配误伤风险

Decision:

- 采用 Option A

## 5. Design

### 5.1 Ownership Decision

本轮要剥离的是以下职责：

- 读取 sector code -> display name 映射
- 读取 recent trading dates 的 sector average
- 读取 target-date sector aggregate
- 消费 `sector cooldown` 结果并执行 skip policy
- 计算 accel bonus / rising-trend bonus / heat score
- 组装 `SectorHeat` 风格输出并排序/截断

这些职责应定义为：

- `M2 sector-level heat orchestration`

而不是：

- `M2 sector cooldown kernel`
- stock-level `sector entry chain`
- API consumer adapter

### 5.2 Recommended File Boundary

推荐新增一个窄模块：

- `neotrade3/cycle_intelligence/sector_heat.py`

该文件只承接：

- `build_hot_sectors(...)`
- 必要的内部 helper：
  - `load_sector_display_names(...)`
  - `load_recent_avg_by_sector(...)`
  - `load_sector_daily_aggregates(...)`
  - `score_sector_heat(...)`

不承接：

- `detect_sector_cooldown(...)` 算法
- `get_sector_candidates()` 的 stock-level 评分
- `generate_buy_signals()` 主链
- workbench/API payload 组装

推荐原因：

- 这条链语义上已经比 `legacy_recognition.py` 更偏 sector orchestration，不应继续塞进 legacy heuristic 混合文件
- 用独立文件可以明确它是 `M2` 的 sector-level orchestration，而不是 kernel 或 stock selector
- 后续若要继续拆 `sector entry chain`，可以直接以它为上游输入，不会再次返工边界

### 5.3 Adapter Surface

推荐在新模块中暴露一个主 facade：

- `build_hot_sectors(...)`

推荐的输入输出面：

- 输入：
  - `cursor`
  - `target_date`
  - `top_n`
  - `market_cap_min`
  - `market_cap_max`
  - `sector_accel_bonus_enabled`
  - `sector_accel_lookback_trading_days`
  - `sector_accel_bonus_high`
  - `sector_accel_bonus_low`
  - `recent_trading_dates_loader`
  - `sector_cooldown_loader`
  - `sector_heat_factory`
  - 可选 `skip_logger`
- 输出：
  - `list[SectorHeat-like object]`

这里的关键设计决策是：

- 新模块拥有 `SectorHeat` 输出 shaping
- 但为了避免新模块直接 import engine，本轮不迁移 `SectorHeat` dataclass 定义
- 由 engine thin facade 注入 `sector_heat_factory=SectorHeat`

这使得：

- owner 迁出 engine
- `SectorHeat` consumer shape 保持稳定
- 第三刀不额外打开“shared contract type relocation”新主题

### 5.4 What Stays In Engine

`E4` 第三刀后，以下职责仍留在 engine：

- `get_hot_sectors()` 方法名本身，作为兼容 facade 暂留
- `SectorHeat` dataclass 定义位置
- `get_sector_candidates()` stock-level 评分与 role/wave/fundamental 选择
- `generate_buy_signals()` 主链 orchestration

原因：

- 当前 consumer 已经从 engine import `SectorHeat`
- 第三刀只认账 `hot sectors` orchestration，不顺手打开 contract type 搬迁
- `get_sector_candidates()` 是下一刀或后续 slice，而不是本轮范围

### 5.5 Data Flow

推荐的数据流顺序是：

1. engine `get_hot_sectors()` 建立 `cursor` 与配置注入
2. facade 调用 `build_hot_sectors(...)`
3. `build_hot_sectors(...)` 内部：
   - 读取 sector code/name 映射
   - 读取 recent averages
   - 读取 target-date sector daily aggregates
   - 对每个 sector 调用 `sector_cooldown_loader`
   - 执行 skip policy
   - 计算 heat score 与 bonus
   - 用 `sector_heat_factory` 构造输出
   - 排序并截断 `top_n`

保持不变的语义包括：

- `cooldown_detected and follower_weakness > 0.7` 时跳过
- `avg_change` 的基础加分规则
- `sector_accel_bonus` 的阈值与高低加分
- `trend_state == "rising"` 的 bonus

### 5.6 Logging Strategy

当前 `get_hot_sectors()` 会在 cooldown 跳过时输出：

- `logger.info(f"板块 {sector} 人气消散...")`

本轮不应把 logger 变成新模块的硬依赖。

推荐方式：

- `build_hot_sectors(...)` 接收一个可选 `skip_logger`
- 当命中 skip policy 时，若 `skip_logger` 存在则调用
- engine facade 继续传入当前 logger 行为

这样可以：

- 保持日志语义
- 不让 `sector_heat.py` 反向依赖 engine logger

### 5.7 Testing Strategy

本轮测试建议分两层：

- 新增 owner-level focused carrier：
  - `tests/unit/test_lowfreq_engine_v16_sector_heat.py`
- 复用现有 consumer-level carrier：
  - [test_lowfreq_workbench_formal_consumption.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_workbench_formal_consumption.py#L11-L86)

新 focused carrier 至少保护：

- cooldown 命中时板块被跳过
- accel bonus 生效时 `heat_score` 上浮
- rising trend bonus 生效
- 最终排序与 `top_n` 截断正确
- `SectorHeat` 输出 shape 不漂移

明确不把以下测试当主护栏：

- `signal_convergence`

原因：

- 当前它 stub 掉了 `get_hot_sectors()`，不能证明 owner 无回归

### 5.8 Validation Baseline

第三刀完成后，至少验证：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_sector_heat.py`
- `python3 -m pytest tests/unit/test_lowfreq_workbench_formal_consumption.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/cycle_intelligence/sector_heat.py`

如实现触及 `SectorHeat` 输出 contract，再补跑依赖 hot-sector snapshot 的最小 API regression。

## 6. Risks And Guards

风险 1：

- 顺手把 `get_sector_candidates()` 一起带走，变成 sector entry chain

保护：

- 第三刀只允许碰 `get_hot_sectors()` 及其新 owner 文件

风险 2：

- 因为要构造 `SectorHeat`，反向 import engine，形成新循环依赖

保护：

- 用 `sector_heat_factory` 注入，不迁移 dataclass 定义位置

风险 3：

- 把 `sector_cooldown` 算法再次复制进 `sector_heat.py`

保护：

- 新模块只消费 cooldown loader，不重写 kernel

风险 4：

- 继续只依赖 consumer 测试，owner 无 focused 护栏

保护：

- 必须新增 `test_lowfreq_engine_v16_sector_heat.py`

## 7. Success Criteria

本轮完成后，应满足：

- `get_hot_sectors()` 的核心编排 owner 已迁入 `cycle_intelligence`
- `sector cooldown` 继续只是上游输入，而不是被重新混回新模块
- `get_sector_candidates()` 仍留在 engine，不被第三刀误伤
- `SectorHeat` consumer shape 保持稳定
- 后续可继续把 `sector entry chain` 作为下一刀独立推进

## 8. Commit Boundary

本轮 design 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-m2-sector-heat-orchestration-design.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/cycle_intelligence/*`
- `tests/unit/*`
- `apps/api/main.py`
- 其他任何工作区改动
