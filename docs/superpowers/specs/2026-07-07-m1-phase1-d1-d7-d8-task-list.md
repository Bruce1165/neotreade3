# M1 Phase 1 执行任务清单（D1 / D7 / D8）

日期：2026-07-07  
对应计划：

- `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-implementation-plan.md`

对应契约：

- `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md`

## 1. 清单目标

本清单只服务于 `M1 Phase 1` 的实际落地，目标是把本轮工作压缩到：

- 明确的文件级改动范围
- 明确的对象级交付物
- 明确的测试级动作
- 明确的阻塞项与决策点

本清单不覆盖：

- `M2` 正式对象编码
- `M3` 正式对象编码
- 前端接线
- 高阶分析模块重构
- 与本轮无关的历史遗留治理

## 2. 文件级改动边界

### 2.1 首批建议可改

- `neotrade3/data_control/`
- `apps/api/main.py`
- `config/data_control/`
- 必要时新增正式对象定义位置：
  - `neotrade3/data_control/contracts.py`
  - `neotrade3/data_control/schemas.py`
  - `neotrade3/data_control/projections.py`
  - 或同等语义位置
- 测试文件：
  - `tests/unit/test_bootstrap_skeleton.py`
  - 或新增更聚焦的 `M1` 单元测试文件

### 2.2 首批建议暂不大改

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/analysis/`
- 前端页面
- `neotrade3/labs/`
- `neotrade3/learning/`
- 调度模板与 launchd 配置

### 2.3 完成判定

- 本轮实现不出现全仓库扩散式修改
- 任何超出上述范围的改动，都必须有单独理由

## 3. 任务组 A：正式对象落点建立

### Task A1：确定正式对象承载文件

目标：

- 冻结 `D1 / D7 / D8` 正式对象的代码位置，避免继续散落在 API 临时逻辑中。

动作：

- 选定首批正式对象定义文件
- 选定对象构造函数或投影函数文件
- 确定是否需要独立 `contracts / schemas / projections` 拆分

产出：

- 正式对象代码落点表
- 模块职责说明

完成判定：

- 后续实现时不再临时决定对象放哪

### Task A2：落首批正式对象定义

目标：

- 将文档中的首批对象名和字段边界落到代码级定义。

必须定义：

- `d1_daily_price_fact`
- `d7_security_master_minimal`
- `d7_trading_day_status`
- `pf1_trading_profile`

至少包含：

- 字段名
- 字段类型
- 可空性
- 对象版本字段或版本常量

产出：

- 首批正式对象定义代码

完成判定：

- 代码中已有正式对象，不再只存在文档命名

## 4. 任务组 B：D1 生成链收口

### Task B1：实现 `d1_daily_price_fact` 映射

目标：

- 从 `daily_prices` 稳定生成正式 `D1` 对象。

动作：

- 固定 `daily_prices` 到正式字段的映射
- 将 `code -> stock_code`
- 将 `open/high/low/close -> open_price/high_price/low_price/close_price`
- 将 `preclose -> preclose_price`
- 将 `amount -> amount_cny`
- 将 `volume -> volume_shares`
- 将 `turnover -> turnover_rate`
- 将 `updated_at -> updated_at`

产出：

- `d1_daily_price_fact` 构造函数或投影函数

完成判定：

- 任意目标交易日可由统一函数投影出 `D1` 对象

### Task B2：固定 `D1` 字段语义

目标：

- 将当前底层列语义收紧成正式对象语义。

重点：

- 固定 `volume_shares` 为股数语义
- 固定 `turnover_rate` 为可空正式字段
- 明确 `close_price` 为首批硬核心字段

产出：

- 代码注释或对象注释中的正式语义说明

完成判定：

- 不再存在“手/股不确定”“turnover 是否硬必填不明确”这类口径漂移

## 5. 任务组 C：D7 生成链收口

### Task C1：实现 `d7_security_master_minimal`

目标：

- 从 `stocks` 生成首批最小证券主数据对象。

动作：

- 收口以下字段：
  - `stock_code`
  - `stock_name`
  - `asset_type`
  - `is_delisted`
  - `sector_lv1`
  - `sector_lv2`
  - `last_trade_date`

产出：

- `d7_security_master_minimal` 构造函数或投影函数

完成判定：

- 下游获取最小证券主数据时，不再需要到处直接查 `stocks`

### Task C2：实现 `d7_trading_day_status`

目标：

- 从 `trading_day_view()` 收口首批正式交易日状态对象。

动作：

- 固定以下字段：
  - `target_date`
  - `is_trading_day`
  - `nearest_trading_day`
  - `min_trading_day`
  - `max_trading_day`
  - `calendar_covered_until`
  - `calendar_source`

产出：

- `d7_trading_day_status` 构造函数或投影函数

完成判定：

- 交易日状态对象已有统一来源，不再让下游直接依赖 API 原始 payload 结构

### Task C3：固化 `D7` 的未知状态语义

目标：

- 防止覆盖不足时被误判为非交易日。

动作：

- 定义 `is_trading_day = unknown/null` 时的正式语义
- 明确覆盖不足时的返回形态
- 明确下游禁止静默降级

产出：

- `D7` 未知状态处理规则

完成判定：

- 后续任何消费方都不能把“未知”直接当作 `False`

## 6. 任务组 D：D8 生成链收口

### Task D1：实现 `pf1_trading_profile` 正式生成路径

目标：

- 将 `signals["trading_profile"]` 从 API 临时计算提升为正式 `M1` 对象生成链。

动作：

- 固定 `stock_code`
- 固定 `as_of_trade_date`
- 固定以下派生字段：
  - `latest_amount`
  - `avg_amount_5d`
  - `avg_amount_20d`
  - `latest_turnover`
  - `avg_turnover_5d`
  - `median_turnover_20d`
  - `return_20d`
  - `avg_pct_change_5d`
  - `positive_days_5d`

产出：

- `pf1_trading_profile` 构造函数或投影函数

完成判定：

- 下游获取 primitive trading profile 时，不再依赖 market intelligence 临时结构

### Task D2：收紧 5 日 / 20 日窗口语义

目标：

- 防止 partial window 冒充正式窗口指标。

动作：

- 明确 5 日窗口不足时返回 `null`
- 明确 20 日窗口不足时返回 `null`
- 明确 `return_20d` 只在满足正式窗口条件时输出

产出：

- `D8` 窗口充分性规则实现

完成判定：

- 正式 `5d/20d` 字段不再依赖“能算多少算多少”的弱语义

### Task D3：阻断高阶语义混入 `D8`

目标：

- 保护 `D8` 边界不再次漂移。

明确排除：

- `theme_momentum`
- `market_phase`
- `sector_rotation`
- `stock_tiering`
- `factor_matrix`
- `config_leader_candidate`
- `institutional_attention_candidate`
- `trading_leader_candidate`

产出：

- `D8` 排除清单的代码级边界体现

完成判定：

- 首批 `D8` 不再成为新的杂物层

## 7. 任务组 E：质量状态与 Freshness Proof

### Task E1：定义首批质量状态对象

目标：

- 为 `D1 / D7 / D8` 建立统一的最小质量状态对象。

首批至少包括：

- `source_status`
- `freshness_status`
- `coverage_status`
- `replay_status`

产出：

- 质量状态对象定义
- 每类状态的最小字段

完成判定：

- 后续消费方能结构化判断对象是否正式可消费

### Task E2：实现首批 `Freshness Proof`

目标：

- 将“有数据”与“可正式消费”拆开。

动作：

- 为 `D1` 实现 freshness 判断
- 为 `D7` 实现覆盖充分判断
- 为 `D8` 实现窗口充分判断

产出：

- `Freshness Proof` 首批实现

完成判定：

- 不再出现“抓到数据就默认可消费”的隐式假设

### Task E3：建立首批 `Attention Item`

目标：

- 把本轮 `M1` 问题结构化暴露，而不是只留在日志里。

首批模板至少覆盖：

- 数据缺失
- 数据过期
- 覆盖不足
- 窗口不足
- 无法回放

产出：

- `Attention Item` 最小模板
- 严重度与影响层说明

完成判定：

- 首批 `M1` 问题已可正式暴露给后续 `M2/M3`

## 8. 任务组 F：API 投影与消费边界

### Task F1：增加正式对象最小投影路径

目标：

- 让 API 至少能稳定返回首批正式对象。

动作：

- 增加或收口正式对象投影入口
- 保持现有能力不被破坏
- 明确兼容路径与正式路径

产出：

- 首批正式对象 API 投影

完成判定：

- 后续 `M2/M3` 可以规划为只消费正式对象投影入口

### Task F2：阻断继续消费临时结构

目标：

- 防止首批正式对象上线后，后续逻辑仍默认去抓临时 payload。

动作：

- 明确哪些路径仍是兼容读法
- 明确新路径的正式消费优先级
- 在代码中减少新逻辑对临时拼装结构的依赖

产出：

- 消费边界说明

完成判定：

- API 层不再继续放大临时结构的正式语义地位

## 9. 任务组 G：测试与验证

### Task G1：补对象结构测试

目标：

- 验证 `D1 / D7 / D8` 正式对象结构稳定。

测试重点：

- 必填字段
- 可空字段
- 字段命名
- 对象版本字段或版本常量

完成判定：

- 首批对象不会因临时重构而静默变形

### Task G2：补边界状态测试

目标：

- 验证质量门禁与边界状态真实生效。

测试重点：

- `D1` 目标交易日数据缺失
- `D7` 覆盖不足导致 `is_trading_day` 未知
- `D8` 5 日 / 20 日窗口不足返回 `null`
- `D8` 不接受高阶分析对象回填

完成判定：

- “unknown / null / insufficient coverage” 不再只是文档口径

### Task G3：补 API 投影回归

目标：

- 验证正式对象投影路径稳定可用。

测试重点：

- 正式对象投影返回结构
- 兼容路径未被意外破坏
- 失败状态可结构化返回

完成判定：

- 本轮收口未破坏当前主链

## 10. 实施顺序

建议按以下顺序执行：

1. Task A1
2. Task A2
3. Task B1
4. Task B2
5. Task C1
6. Task C2
7. Task C3
8. Task D1
9. Task D2
10. Task D3
11. Task E1
12. Task E2
13. Task E3
14. Task F1
15. Task F2
16. Task G1
17. Task G2
18. Task G3

顺序原因：

- 先有正式对象，后有生成链
- 先有生成链，后有质量门禁
- 先有对象与门禁，后做 API 投影
- 先稳定边界，再做测试与回归

## 11. 当前阻塞项与决策点

### 决策点 1：正式对象定义文件放置方式

需要确认：

- 是集中放在单文件中
- 还是拆成 `contracts / projections / quality` 多文件

建议：

- 首批优先集中或轻拆分，避免一开始过度设计

### 决策点 2：D8 窗口不足的返回策略

需要确认：

- 首批是否严格返回 `null`

当前建议：

- 严格返回 `null`

原因：

- 这与契约文档一致，也能避免 partial window 语义漂移

### 决策点 3：首批 API 投影入口形式

需要确认：

- 复用现有接口增加正式投影字段
- 还是增加独立正式对象接口

当前建议：

- 首批优先增加独立正式对象投影入口或明确正式子路径

原因：

- 能更清楚地区分兼容 payload 与正式对象

## 12. 验收条件

本清单执行完成后，应满足：

- `D1 / D7 / D8` 已有代码级正式对象
- `D1 / D7 / D8` 已有统一生成链
- 质量状态与 `Freshness Proof` 已正式落地
- `Attention Item` 已能暴露本轮 `M1` 问题
- API 已有最小正式对象投影
- 本轮未误把高阶分析对象纳入 `D8`
