Status: active
Owner: lowfreq / chaos-model
Scope: 输出 A 的中低频可持有价值过滤层最小定义
Canonical: PROJECT_STATUS.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-23

# 2026-07-23 Durability Gate 最小定义

## 0. 目的

本文件只定义 `Durability Gate` 的最小语义：

- 它解决什么问题
- 它服务哪个最终团队输出
- 它读取哪些类型的证据
- 它输出什么最小结论
- 它不负责什么

本文件不定义：

- 最终打分公式
- 最终阈值数值
- 代码落盘结构
- 买入/卖出动作

## 1. 为什么必须单独定义 Durability Gate

当前专项已经获得的正式证据是：

- `L1 stock_only` 在全 A 股正式中期验证中对 `20D/40D/60D` 具备正向分层能力

这说明：

- 当前混沌状态读法已经能回答“哪些股票更可能处于有效驱动状态”

但它还不能自动回答：

- 这些股票是否适合中低频团队持续关注与持有

当前如果直接把“状态强”翻译成“应重点专注”，会有一个明显风险：

- 挑出来的标的可能更偏短平快脉冲，而不是适合中低频轨道持有的股票

因此，必须在状态信号之外，再单独定义一层：

- `Durability Gate`

它的职责不是替代状态信号，而是回答：

- 这只股票即使当前状态强，是否也具备“更耐拿、更不容易只是短脉冲”的证据

## 2. Durability Gate 服务哪个最终输出

`Durability Gate` 当前阶段只服务输出 A：

- 当前应该专注哪些股票

它在控制板中的角色是：

- `CB2`

它的使用顺序固定为：

1. 先读 `stock_state_context`
2. 再读 `Durability Gate`
3. 再决定该股进入：
   - 核心专注名单
   - 观察候选名单
   - 短脉冲警示名单

当前阶段明确禁止：

- 用 `Durability Gate` 直接替代状态信号
- 用 `Durability Gate` 直接产出买入指令
- 用 `Durability Gate` 直接产出卖出指令

## 3. 它回答的问题

`Durability Gate` 当前阶段只回答 3 个问题：

1. 这只股票是否具备中低频可持有价值的基本证据
2. 这只股票是否更像“短期脉冲/噪声型强势”，而不适合作为团队主线关注对象
3. 这只股票当前即使状态强，是否应该被降级为“观察而非核心专注”

它当前阶段不回答：

- 明天要不要买
- 明天要不要卖
- 目标收益率是多少
- 最终持有多少天

## 4. 它不是什么

`Durability Gate` 不是：

- 价值投资选股器
- 单独的基本面模型
- 对 `stock_state_context` 的替代品
- 对价格走势的拟合器

它只是一个：

- 中低频可持有价值过滤层

## 5. 最小输入证据

当前阶段，`Durability Gate` 只允许读取“较慢、较稳定、较适合中低频持有解释”的证据。

### 5.1 基本面质量证据

当前优先读取：

- `roe`
- `pe_ratio`
- `pb_ratio`
- 如可用，可补充 `profit_growth`
- 如可用，可补充 `revenue_growth`

现有代码证据：

- [factor_contract.py](file:///Users/mac/NeoTrade3/neotrade3/analysis/factor_contract.py#L95-L131)
- [fundamental_gate.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/fundamental_gate.py#L6-L62)

当前阶段的理解不是：

- 低估值就一定更好

而是：

- 至少不能明显缺乏中低频持有所需的基本质量地板

### 5.2 结构性配置证据

当前优先读取：

- `holder_etf_count`
- `holder_fund_count`
- `index_count`
- `config_score`

现有代码证据：

- [market_focus_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/market_focus_snapshot.py#L262-L323)

这些字段表达的不是短期涨跌，而是：

- 这只股票是否被 ETF / 基金 / 指数等结构性配置所承接

### 5.3 研究与关注度证据

当前优先读取：

- `attention_score`
- `research_inst`
- `consensus_orgs`
- `survey_orgs`
- `survey_count`

现有代码证据：

- [market_focus_snapshot.py](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/market_focus_snapshot.py#L325-L420)

这些字段的角色不是“情绪加热”，而是：

- 反映该股是否具备持续研究覆盖和机构关注

### 5.4 反脉冲与反退潮证据

当前阶段，`Durability Gate` 必须允许显式压制以下对象：

- 高脉冲、低持续性标的
- 高 hazard 风险标的
- 板块明显退潮但个股短期仍被拉动的标的

这部分当前优先读取：

- `hazard_score_5d_high`
- `sector_cooldown_detected`
- `sector_trend_deteriorating`
- `sector_leader_rollover`

现有规则证据：

- [chaos_rulebook.md](file:///Users/mac/NeoTrade3/docs/architecture/chaos_rulebook.md#L187-L212)

## 6. 最小输出结论

当前阶段，`Durability Gate` 只允许输出 3 档最小结论：

1. `durable_pass`
2. `durable_watch`
3. `durable_reject`

### 6.0 数据完整性前置规则

在进入上述 3 档结论之前，必须先检查最小基本质量证据是否完整。

当前阶段，以下字段视为 `Durability Gate` 的最小增长类证据：

- `profit_growth`
- `revenue_growth`

如果这两类字段缺失，则当前阶段：

- 不允许直接给出 `durable_pass / durable_watch / durable_reject`
- 不允许把该股放入 `focus_list / watch_list / short_pulse_warning`
- 必须把该股放入单独的数据质量排除列表 `exclusions.missing_fundamentals`

这样做的原因是：

- `Durability Gate` 可以做过滤，但不能用“缺证据”伪装成“已通过证据”

`exclusions.missing_fundamentals` 的语义是：

- 当前状态可能成立
- 但缺少最小增长类基本面证据
- 因此本轮不进入正式三桶名单

它不是第四个正式会议对象，只是数据质量排除项。

### 6.1 durable_pass

含义：

- 当前状态强，同时具备基本质量、结构性配置、研究关注中的最小持有价值证据
- 没有明显被短脉冲/退潮/高 hazard 风险主导

它允许进入：

- 核心专注名单

### 6.2 durable_watch

含义：

- 当前状态强，但“可持有价值证据”还不够强，或者存在局部疑点

它允许进入：

- 观察候选名单

它当前阶段不允许直接进入：

- 核心专注名单

### 6.3 durable_reject

含义：

- 当前状态即使强，也更像短脉冲、退潮残余、风险偏高或缺乏持有价值地板

它应进入：

- 短脉冲警示名单

## 7. 最小解释字段

为避免团队再次质疑“为什么又挑出不适合拿的票”，`Durability Gate` 当前阶段的每个结论都必须可解释。

最小解释字段只需要 4 类：

- `quality_reasons`
- `configuration_reasons`
- `attention_reasons`
- `pulse_risk_reasons`

要求：

- `durable_pass` 必须能说清楚“为什么耐拿”
- `durable_watch` 必须能说清楚“为什么先观察”
- `durable_reject` 必须能说清楚“为什么更像短平快或高风险”

## 8. 与状态信号的关系

`Durability Gate` 和 `stock_state_context` 的关系冻结为：

- `stock_state_context` 负责回答“当前驱动状态是否有效”
- `Durability Gate` 负责回答“这个有效状态是否值得中低频团队重点拿来关注”

因此：

- `stock_state_context` 是主语义
- `Durability Gate` 是过滤层

当前阶段禁止：

- `Durability Gate` 覆盖 `stock_state_context`
- 用 `Durability Gate` 否定全部状态证据

更准确地说：

- `Durability Gate` 只能做“升档 / 降档 / 拒绝进入核心专注”
- 不能反向改写状态对象本身

## 9. 当前阶段通过标准

`Durability Gate` 当前阶段视为通过，至少应满足：

1. 能把“状态强但不耐拿”的标的显式降级
2. 能把“状态强且更适合中低频跟踪”的标的显式升为核心专注
3. 每个结论都有最小证据解释
4. 缺少增长类基本面证据的标的不进入正式三桶名单，而进入数据质量排除列表
5. 不把买卖动作规则偷偷混入过滤层

## 10. 当前阶段显式尾巴

### 10.1 Deferred

- 不在本轮定义最终公式与阈值
- 不在本轮定义页面表现
- 不在本轮定义和 `buy_candidate / sell_candidate` 的直接接口
- 不在本轮引入 `L2/L3` 正式增益逻辑

### 10.2 Rejected

- 不把“涨得快”直接当成“值得中低频重点关注”
- 不把“被团队热议”直接当成“耐持有价值证据”
- 不把 `Durability Gate` 变成另一个独立选股系统

## 11. 下一步接口

本文件通过后，下一步只允许进入：

- `CB3`：定义 `focus_list / watch_list / short_pulse_warning` 最小对象

原因：

- `Durability Gate` 已经回答“耐不耐拿”
- 下一步才应该把它接到团队可消费的正式关注名单对象上

## 12. 文档通过条件

本文件在当前阶段视为通过，需同时满足：

- 过滤层职责清楚
- 服务对象清楚
- 最小输入证据清楚
- 最小输出档位清楚
- 与状态信号边界清楚
- Deferred / Rejected 清楚

在以上条件未被满足前，不进入 `focus_list` 正式对象定义。
