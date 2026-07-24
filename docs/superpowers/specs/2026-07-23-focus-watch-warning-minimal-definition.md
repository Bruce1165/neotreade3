Status: active
Owner: lowfreq / chaos-model
Scope: 输出 A 的团队会议优先对象定义
Canonical: PROJECT_STATUS.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-23

# 2026-07-23 focus_list / watch_list / short_pulse_warning 最小定义

## 0. 目的

本文件只定义输出 A 的 3 个团队会议优先对象：

- `focus_list`
- `watch_list`
- `short_pulse_warning`

本文件只解决以下问题：

- 这 3 个对象分别代表什么
- 它们之间是什么关系
- 一只股票为什么进入其中之一
- 团队会议应该如何消费这些对象

本文件不定义：

- 买入动作
- 卖出动作
- 最终 API 契约
- 页面布局
- 最终排序公式细节

## 1. 对象定位

这 3 个对象都属于：

- 团队会议消费对象

其优先目标不是让程序最先消费，而是让团队在讨论、复盘、分配注意力时：

- 一眼看懂
- 能解释
- 能追问
- 能追责

因此，当前阶段这 3 个对象首先服务：

- 当前应该专注哪些股票

而不是：

- 明天应该买入哪些股票
- 明天应该卖出哪些股票

## 2. 三个对象分别是什么

### 2.1 focus_list

含义：

- 团队当前主线关注名单

它回答的问题是：

- 哪些股票当前最值得进入主线研究、盯盘、复盘和会议重点讨论

### 2.2 watch_list

含义：

- 团队观察名单

它回答的问题是：

- 哪些股票当前值得继续观察，但证据还不足以进入主线关注

### 2.3 short_pulse_warning

含义：

- 团队短脉冲警示名单

它回答的问题是：

- 哪些股票当前可能显得很强，但更像短平快、高 hazard、退潮残余或不适合中低频主线的对象

## 3. 三个对象的关系

### 3.1 强互斥

这 3 个对象在同一交易日必须强互斥：

- 同一股票、同一时点，只能出现在一个名单里

这样做的原因不是表达力最大，而是：

- 会议决策最清楚
- 不会出现“一只票既重点关注又高风险警示”的口径混乱

### 3.1A 数据质量排除项不是第四桶

当前阶段允许存在：

- `exclusions.missing_fundamentals`

它的语义是：

- 当前状态可能成立
- 但缺少 `Durability Gate` 所需的最小增长类基本面证据
- 因此本轮不进入正式三桶名单

该对象不是：

- 第四个会议名单
- `focus_list / watch_list / short_pulse_warning` 的重叠标签

它只是：

- 数据质量排除项

### 3.2 判定顺序

一只股票进入哪个对象，顺序冻结为：

1. 先读 `stock_state_context`
2. 再读 `Durability Gate`
3. 再完成最终落桶

### 3.3 当前阶段固定落桶规则

- `状态成立 + durable_pass -> focus_list`
- `状态成立 + durable_watch -> watch_list`
- `状态成立 + durable_reject -> short_pulse_warning`
- `状态不成立 -> 不进入这 3 个对象`

当前阶段禁止：

- 只靠 `Durability Gate` 落桶
- 只靠短期涨幅落桶
- 先有名单再回头拼理由

## 4. 每条记录的最小字段

当前阶段，这 3 个对象都使用统一的最小会议字段：

- `trade_date`
- `code`
- `name`
- `list_type`
- `state_summary`
- `durability_status`
- `primary_reasons`
- `main_risks`
- `why_here`
- `why_not_other_lists`

对于 `exclusions.missing_fundamentals`，当前阶段最小字段为：

- `trade_date`
- `code`
- `name`
- `state_summary`
- `exclusion_reason`
- `required_fields`
- `why_excluded`

### 4.1 字段语义

- `trade_date`
  - 当前名单对应的交易日
- `code`
  - 证券代码
- `name`
  - 证券名称
- `list_type`
  - `focus_list / watch_list / short_pulse_warning`
- `state_summary`
  - 对当前状态主证据的一句话总结
- `durability_status`
  - `durable_pass / durable_watch / durable_reject`
- `primary_reasons`
  - 本次上榜的主因，控制在 `3-5` 条
- `main_risks`
  - 当前最关键风险，控制在 `1-3` 条
- `why_here`
  - 为什么进入当前这个名单
- `why_not_other_lists`
  - 为什么不是另外两类名单

## 5. 三个对象的最小进入条件

### 5.1 focus_list

进入条件：

- `stock_state_context` 为正向主证据
- `Durability Gate = durable_pass`
- 当前没有被明显短脉冲、高 hazard、退潮残余主导

### 5.2 watch_list

进入条件：

- `stock_state_context` 为正向主证据
- `Durability Gate = durable_watch`

它表达的不是“差”，而是：

- 当前值得继续看，但还不够硬，不应直接进入核心专注

### 5.3 short_pulse_warning

进入条件：

- `stock_state_context` 可能仍不弱
- 但 `Durability Gate = durable_reject`

它表达的是：

- 当前可能很热，很强，甚至很吸睛
- 但不应被误判成中低频团队主线对象

## 6. 会议展示顺序

为避免会议顺序混乱，当前阶段固定按以下顺序展示：

1. `focus_list`
2. `watch_list`
3. `short_pulse_warning`

原因：

- 先看主线注意力放在哪里
- 再看哪些值得继续盯
- 最后看哪些需要明确警示，避免误判

## 7. 名单内部排序逻辑

当前阶段只冻结排序方向，不冻结最终数值公式。

统一排序方向为：

1. `state_strength` 优先
2. `durability_quality` 优先
3. `risk_penalty` 逆序压低

当前阶段禁止：

- 只按涨幅排序
- 只按热度排序
- 只按机构关注排序

原因：

- 输出 A 的主语义仍是状态证据
- `Durability Gate` 只是过滤层，不是主公式替代品

## 8. 三个对象的会议解释模板

### 8.1 focus_list

必须能回答：

- 为什么值得主线关注
- 为什么更适合中低频团队跟踪
- 当前最大风险是什么

### 8.2 watch_list

必须能回答：

- 为什么值得继续观察
- 为什么当前还不够资格进入核心专注
- 还缺哪类证据

### 8.3 short_pulse_warning

必须能回答：

- 为什么它可能很强但不适合主线
- 当前最关键的短脉冲或退潮风险是什么
- 为什么不能误判成 `focus_list`

## 9. 升档、降档、剔除规则

### 9.1 升入 focus_list

满足以下条件时，允许升入 `focus_list`：

- 状态主证据成立
- `Durability Gate` 从 `durable_watch` 升为 `durable_pass`，或直接判定为 `durable_pass`

### 9.2 从 focus_list 降到 watch_list

满足以下条件时，降到 `watch_list`：

- 状态证据仍成立
- 但耐持有证据弱化，或出现新的局部疑点

### 9.3 进入 short_pulse_warning

满足以下条件时，进入 `short_pulse_warning`：

- `Durability Gate = durable_reject`
- 或出现明确的高脉冲、高 hazard、退潮残余主导

### 9.4 从三个对象中剔除

满足以下条件时，从 3 个对象中剔除：

- `stock_state_context` 主证据不再成立
- 或当前已不具备会议关注价值

## 10. 会议纪律

这 3 个对象当前阶段都不是：

- 买入指令
- 卖出指令
- 神谕式答案

因此必须明确：

- `focus_list` 不等于“明天必买”
- `watch_list` 不等于“可以忽略”
- `short_pulse_warning` 不等于“必须卖出或做空”

这 3 个对象当前阶段的职责只有一个：

- 帮团队分配注意力，并统一语言

同时必须明确：

- `exclusions.missing_fundamentals` 只用于说明“为什么这只股票本轮没有资格进入正式三桶”
- 它不参与会议主线排序
- 它不应被误读成第四个正式会议对象

## 11. 当前阶段通过标准

本文件当前阶段视为通过，至少同时满足：

1. 三个对象定义清楚
2. 三个对象关系清楚且互斥
3. 每条记录都有最小解释字段
4. 数据质量排除项与正式三桶边界清楚
5. 进入、降级、剔除规则清楚
6. 没有把买卖动作偷偷混入对象定义

## 12. 当前阶段显式尾巴

### 12.1 Deferred

- 最终 API 字段契约后置
- 页面展示后置
- 精确排序公式后置
- `L2/L3` 正式增益接入后置

### 12.2 Rejected

- 不允许名单重叠
- 不允许只凭“涨得快”进入 `focus_list`
- 不允许把这 3 个会议对象包装成直接交易指令

## 13. 下一步接口

本文件通过后，输出 A 当前阶段最小闭环即告完成：

- `CB1`：总控图
- `CB2`：`Durability Gate`
- `CB3`：`focus_list / watch_list / short_pulse_warning`

此后若继续推进，应转向：

- 输出 A 的落地实现
- 或进入输出 B 的最小对象定义

## 14. 文档通过条件

本文件通过条件为：

- 三个会议对象语义明确
- 强互斥规则明确
- 会议使用顺序明确
- 最小字段明确
- 升降档规则明确
- 显式尾巴明确

在以上条件未满足前，不进入输出 A 的实现落地。
