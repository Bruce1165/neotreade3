Status: active
Owner: lowfreq / chaos-model
Scope: 混沌模型（阴阳能量）定义、输出契约、落盘资产、治理闭环（不含实现）
Canonical: docs/architecture/lowfreq_v16_model_rulebook.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-20

# 2026-07-20 混沌模型（阴阳能量）设计稿 v0

## 0. 背景与动机

LowFreq V16 的 M1–M6 分层体系需要服务于一个统一的综合判定系统：混沌模型（Chaos Model）。其目标不是“再造一个分数”，而是把模型的所有因子统一投影为 **阳能量** 与 **阴能量**，形成每日可审计、可回放、可治理的阴阳关系序列，并基于阴阳关系的“量/速度/加速度/消耗”来驱动入池、持有、离场。

本设计强调三条硬边界：

- **统一刻度**：阴/阳能量的计算标准在时间轴上必须连续可比，不因入场/持有/离场而切换一套权重体系。
- **No-lookahead**：M3 日常运行只允许使用 target_date 当日及历史可得数据；M4/M5 允许使用未来窗口构造评估/训练标签，但其结果不得作为 M3 输入。
- **治理闭环**：M4 负责监测“混沌判断与走势不一致”的偏差定位；M5 负责批准版本化调整（注册表/权重/阈值）；M3 只消费已批准版本。

## 1. 目标与非目标

### 1.1 目标

- 对每只股票、每个交易日，产出：
  - `yin_value`、`yang_value`
  - `yin_yang_ratio`（展示用，例如 `15:34`）
  - `net_energy = yang_value - yin_value`（主动力序列）
  - 与该股票自身历史阴阳关系序列的对比指标（偏离度与突变标记）
- 因子体系覆盖三大类别（A 股经验先验）并引入“分类权重调节器”：
  - 综合层面：3
  - 资金/人气层面：4
  - 技术层面：3
- 支持“全市场每日计算 + 跟踪池重点分析”的运行方式：
  - 每日对全 A 股计算阴/阳（用于形成历史序列与全量矩阵）
  - 对跟踪池/持仓/观察名单进行重点解释与决策（M3 输出契约）
- 建立可治理的全量因子矩阵资产（EAV 长表），并可版本化复算。

### 1.2 非目标（v0 不做）

- 不在 v0 将混沌模型作为唯一买卖决策源，先以“并行证据与审计字段”的方式接入 M3。
- 不在 v0 承诺实时处理公告全文 NLP 或复杂事件抽取；仅定义“公告/财报等负面事实输入”的接口与落盘契约，具体实现需另立专项设计。

## 2. 分层归属（M3/M4/M5）

### 2.1 M3（在线决策）

职责：

- 每日对股票计算 `chaos_snapshot`（阴/阳/比/净能量/历史偏离），并将其纳入：
  - 入池（tracking）晋级/留存的证据束
  - 持有期滤噪与离场（重点）
  - 风控/异常加速离场提示（“阴消耗阳提速”）

硬约束：

- 只能读取 target_date 当日及历史数据（价格/量/财务可见项/因子派生事实等）。
- 只能读取 M5 审批后的版本化配置（因子注册表/权重/阈值）；不得读取 M4 标签与训练中间产物。

### 2.2 M4（评估与监测）

职责：

- 用未来窗口构造评估标签（仅用于训练/评估），并持续监测：
  - “当日混沌判断”与后验走势是否一致
  - 偏差来源：因子定义漂移 / 权重不稳 / 市场 regime 变化 / 数据质量问题

产物：

- 每日/每周评估摘要与偏差归因
- 候选权重/阈值调整建议（提交 M5）

### 2.3 M5（治理与回灌）

职责：

- 审批并落盘版本化配置：
  - `factor_registry_version`
  - `weights_version`
  - `thresholds_version`
- 形成治理记录与回灌策略，使 M3 的在线读取可机器验收。

## 3. 统一阴阳能量口径

### 3.1 输出契约（chaos_snapshot）

每个 `(code, trade_date)` 输出：

- `yin_value: float`
- `yang_value: float`
- `yin_yang_ratio: str`（展示字段；由 yin/yang 的整数化后拼接）
- `net_energy: float = yang_value - yin_value`（主动力序列）
- `self_history_reference`：
  - `regime_anchor_date: str`（本轮驱动关系锚点：最近一次“确认的阴→阳转折”发生的交易日）
  - `regime_day_index: int`（从 regime_anchor_date 到 target_date 的交易日序号，从 0 开始）
  - `within_regime_window_days: int`（用于对照的窗口天数；允许由回测校准，但不得写死为 5–10）
  - `net_energy_percentile_in_window: float | None`（相对同票“本轮驱动窗口”分布的分位数）
  - `net_energy_zscore_in_window: float | None`
  - `flip_count_in_window: int`（窗口内 `net_energy` 正负号翻转次数）
  - `flip_rate_in_window: float`（窗口内翻转频率）
  - `yang_speed_mean_in_window: float`（窗口内净能量的一阶差分均值，用于衡量升阳速度）
  - `regime_shift_flag: bool`（相对本轮驱动窗口出现显著驱动关系变化）
- `factor_registry_version: str`
- `weights_version: str`

Fail-closed：

- 若关键因子缺失/历史不足：`chaos_status=pending`，不得将其直接映射为强入场/强离场；只能进入观察与降权路径。

补充说明（历史“同阶段”的定义）：

- 本设计中“同阶段”指 **同一只股票从上一个“确认的阴→阳转折点（regime anchor）”到当前的驱动段**，而不是入场/持有/离场的业务阶段。
- 业务动作（入池/持有/离场）从阴阳序列的“量/速度/加速度/消耗”读出，不通过切换阴阳刻度实现。

### 3.2 因子值与权重的两层结构

为保持“统一刻度 + 可治理”：

1) 因子值（factor_value）
- 基于原始观测或标准化观测得到，保持因子语义本身。

2) 分类权重调节器（category_multiplier）
- 综合:资金/人气:技术 = 3:4:3
- 作为“投影前”的统一倍率，体现市场经验先验。

3) 因子权重（factor_weight）
- 在同一刻度下对因子贡献做细分，v0 允许粗粒度三档（核心/辅助/修饰），后续由 M4 校准 + M5 治理推进。

最终投影（示意）：

- `yang_value = Σ (category_multiplier(category) * factor_weight(factor) * norm(factor_value))` 对所有阳因子求和
- `yin_value = Σ (category_multiplier(category) * factor_weight(factor) * norm(factor_value))` 对所有阴因子求和

注：norm 必须是可审计的标准化方法（0–1、0–100、percentile 等之一），并登记在注册表中。

## 4. 因子框架（覆盖三大层面）

### 4.1 综合层面（3）

典型方向（示例，不等于已实现）：

- 市场与个股同频/异频（阳/阴由定义决定）
- 板块热度与退潮（与人气层可拆分，综合层只保留“宏观一致性”）
- 财报/公告/重大事件的事实输入（必须来自 M1 的可见口径事实；不允许前视）
  - v0 只定义接口：`news_event_facts` / `financial_report_facts`（结构化事实），具体抽取需要单独设计与成本评估
- 天时（农历/节气等）：作为比重很小的参考角度（planned），仅允许使用日历与已知时间映射，不得引入未来窗口信息

### 4.2 资金/人气层面（4）

典型方向：

- 成交量/成交额放大或缩量（阴阳属性由定义决定）
- 换手、量比、资金承接强弱
- 板块跟随股强弱、人气消散/回流
- 需尽量复用可获取的数据源（含 tushare）并遵循 no-lookahead 的可见口径

### 4.3 技术层面（3）

典型方向：

- 已定义的波段识别（1/3/5/B）与结构确认
- 已定义筛选器（老鸭头、杯柄等）必须纳入 Factor Registry，并作为技术层核心因子候选

## 5. 时间序列判定（统一刻度下读出动作）

关键点：时间窗口不是固定 5–10，而是：

- 作为可配置参数进入 `thresholds_version`
- 由回测与评估校准出更合理的交易日窗口集合（例如 5/10/20/60 的组合），并由 M5 批准后进入 M3
- 同时允许以 `regime_anchor_date` 定义的“本轮驱动窗口”作为主参照窗口（同票历史同阶段）

v0 关注三类可审计特征（全部只用历史到当日）：

- 量：`net_energy` 的窗口累积（溢出量/库存）
- 速度：`d_net = net_energy[t] - net_energy[t-1]`
- 加速度：`dd_net = d_net[t] - d_net[t-1]`

动作读出（示意，不等于阈值已定）：

- 入池倾向：确认“阴→阳转折”后，`net_energy` 上行 + 增量增强 + 翻转频率低（排除阴阳互换横盘）
- 回调/震仓：阳库存存在但短期转阴，且阴消耗速度温和
- 离场倾向：阴消耗速度突然提速（速度/加速度恶化）或出现极阳转阴结构

## 6. 数据落盘（全量因子矩阵：EAV 长表）

### 6.1 数据库与表

建议独立 DB（避免污染 stock_data 主库）：

- `var/db/chaos_factor_matrix.db`

表（设计稿层面）：

- `chaos_factor_registry`：注册表（版本化）
  - `factor_id`
  - `yin_or_yang`
  - `category`（综合/资金人气/技术）
  - `normalization`
  - `default_weight`
  - `version`

- `chaos_factor_values`：EAV 主表（全量矩阵）
  - `code`
  - `trade_date`
  - `factor_id`
  - `registry_version`
  - `factor_value`

- `chaos_daily_snapshot`
  - `code`
  - `trade_date`
  - `registry_version`
  - `weights_version`
  - `yin_value`
  - `yang_value`
  - `net_energy`
  - `yin_yang_ratio`
  - `self_history_reference`（结构化字段或拆列）

### 6.2 成本评估原则

必须用“可测量小样本外推”，不得凭感觉：

- 先跑基准：`N_codes_small × N_days_small × N_factors_initial`
- 测：
  - 每日计算耗时
  - DB 增长速度（MB/天）
- 再外推到全市场全历史规模，决定是否需要：
  - 分区
  - 压缩
  - 因子拆库
  - 或只对部分因子做全量落盘（治理决策）

## 7. 运行方式（每日全市场 + 跟踪池重点）

目标运行模式：

- 每日对全市场（全 A 股）生成：
  - 全量 `chaos_factor_values`
  - 全量 `chaos_daily_snapshot`
- M3 决策侧对：
  - tracking_pool
  - positions
  - watchlist
  输出更完整的解释字段与审计证据束（但不改变阴阳刻度）
- 复盘/看盘：混沌序列应支持每日复盘消费（不等同于“直接交易”），用于解释当日阴阳驱动关系与是否发生 regime shift

注：全市场计算属于资源密集任务，建议作为独立批处理步骤并纳入任务注册表与可重跑机制（具体编排另立实施计划）。

## 8. 训练/校准/治理闭环（2:5:3）

优化目标权重：

- 入场:持有:离场 = 2:5:3

流程：

1) M3 产出日度混沌序列（无前视）
2) M4 用未来窗口构造评估标签并评估：
   - 阳>阴 是否更常上涨
   - 阴>阳 是否更常下跌
   - 阴阳交错 是否更常震荡
   - 极阳转阴 / 极阴转阳 是否能提前捕捉“速度/加速度”异常
3) M5 审批调整：
   - 注册表修订（因子阴阳归类/标准化）
   - 分类权重（3:4:3 一般保持稳定，仅治理级变更）
   - 因子权重与阈值版本
4) 回灌到 M3 继续回测与线上运行

## 9. 合规闸门（必须）

需要新增同级别的合规闸门（与 hazard 的 Prediction/Label 分离同型）：

- M3 混沌计算代码不得读取任何离线标签表或未来窗口产物
- M3 只能读取 M5 审批后的版本化配置

## 10. 验收标准（设计层）

- rulebook 中新增混沌模型相关契约条目，并进入 Contract Registry（planned）
- spec 明确输出契约、数据落盘、治理闭环与禁止事项
- 后续实施阶段必须补齐可机器验收的闸门测试与最小回归测试
