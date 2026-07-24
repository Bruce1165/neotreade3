Status: active
Owner: lowfreq / chaos-model / m4
Scope: 混沌模型中期有效性验证口径
Canonical: PROJECT_STATUS.md
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-23

# 2026-07-23 混沌模型中期验证口径

## 0. 目的

本文件只定义当前阶段混沌模型“中期有效性”验证的最小口径：

- 验证目标
- 验证窗口
- 验证对象
- 对照方式
- 指标集合
- 通过条件

本文件不定义：

- 具体回测实现
- 动作规则实现细节
- 参数搜索策略
- 展示页面实现

## 1. 当前阶段为什么要单独冻结中期验证口径

当前最强的已有证据主要来自：

- `5D/10D` 的 `M4` 监测
- `regime_combo` 对比 `point(net_energy)` 的短窗差异
- `120D` 后验分桶的滤噪观察

但当前正式业务目标不是短窗，而是：

- `20–60` 个交易日内的强增长机会

因此，当前阶段不能继续用短窗结果替代中期主目标；必须单独冻结一套中期验证口径。

## 2. 验证目标

当前阶段，中期验证只回答以下 3 个问题：

1. `stock_state_context` 是否在 `20D/40D/60D` 窗口上具备稳定分层能力
2. 加入 `theme_state_context / market_state_context` 之后，`stock_state_context` 的中期有效性是否改善
3. 中期验证方向是否与短窗结果大体一致，而不是出现根本冲突

当前阶段不回答：

- 是否已经足以切换到混沌动作主线
- 最终买卖规则是什么
- 哪组参数是长期最优

## 3. 验证对象

### 3.1 主验证对象

当前阶段主验证对象冻结为：

- `stock_state_context`

原因：

- 当前阶段的主要问题是“个股主语义在中期窗口是否真的有效”
- `theme_state_context / market_state_context` 当前阶段只作为上下文分层与增益验证对象，不作为主验证对象

### 3.2 上下文验证对象

当前阶段允许引入的上下文对象为：

- `theme_state_context`
- `market_state_context`

它们的角色仅限：

- 做分层解释
- 做增益对比

当前阶段禁止：

- 把上下文对象直接当成主预测对象
- 用上下文对象替代 `stock_state_context`

### 3.3 当前阶段的 L2 桥接规则

当前阶段，中期验证允许使用 **验证阶段临时投影的 `theme_state_context`**，但必须显式标记其来源，不得误表述为“已完全正式化的 persisted truth-source”。

当前允许的最小桥接来源为：

- 行业/板块侧：来自正式数据库中的稳定行业/板块事实
- 概念侧：来自 `ths_concept_daily` persisted 日表与 cache 预热成员关系的混合来源

当前阶段每次中期验证运行，必须在元信息中显式记录：

- `theme_context_source_mode`
- `theme_context_source_details`

其中应至少能回答：

- 行业/板块侧是否使用正式 DB 字段
- 概念侧是否使用 `ths_concept_daily + cache` 混合来源

当前阶段禁止：

- 把上述桥接来源写成“统一、成熟、独立的主题 persisted truth-source”
- 在未显式记录来源的情况下使用 `stock + theme` 或 `stock + theme + market` 对照

## 4. 验证窗口

当前阶段正式冻结的中期窗口为：

- `20D`
- `40D`
- `60D`

说明：

- `5D/10D` 继续保留为辅助短窗对照，不再作为主结论口径
- `120D` 继续保留为后验滤噪辅助观察，不作为当前阶段主验证窗口

## 5. 验证 universe

### 5.1 正式主 universe

当前阶段正式主 universe 冻结为：

- **全 A 股 ready universe**

定义原则：

- 标的属于当前 A 股可交易股票范围
- 对应日期必须存在可用价格事实
- 对应日期必须存在 `chaos_status = ready` 的混沌快照

### 5.2 辅助 universe

允许保留辅助观察切片，例如：

- `top_by_amount`
- 其他已有窄切片

但这些切片只能作为：

- 诊断视角
- 辅助 sanity check

不能替代全 A 股主 universe 形成正式结论。

## 6. 验证输入口径

当前阶段验证输入必须满足：

- 严格 no-look-ahead
- 版本锁定
- Fail-closed

### 6.1 No-look-ahead

验证中的当日状态读数只能使用：

- `trade_date <= T` 的状态对象与事实

未来窗口收益只能作为评估标签，不得回灌在线状态对象。

### 6.2 版本锁定

每次验证必须显式记录：

- `registry_version`
- `weights_version`
- `thresholds_version`
- `signal_mode`
- 如有组合权重，还需记录组合参数版本

补充说明：

- 本轮要求的是**运行级版本锁定**
- 这不等于项目级“统一版本体系”已经完成收口

### 6.3 Fail-closed

当状态对象缺失或质量不满足条件时：

- 该样本不得进入正式 evaluable 集合
- 必须单独计入 skipped 统计

## 7. 对照方式

当前阶段冻结两层对照：

### 7.1 层内主对照

比较：

- `point(net_energy)` 基线
- `regime_speed`
- `regime_combo`
- 后续基于 `stock_state_context` 的正式中期读法

目的：

- 判断“只看单点”与“结合历史参照/速度”在中期窗口上的差异

### 7.2 上下文增益对照

比较：

- 仅使用 `stock_state_context`
- `stock + theme`
- `stock + theme + market`

目的：

- 判断引入 `L2/L3` 后，中期效果是否真的改善

当前阶段禁止：

- 一上来比较过多复杂组合
- 在没有主效应的情况下过早做复杂交互解释

## 8. 指标集合

当前阶段正式指标分为 3 组：

### 8.1 分层能力指标（主指标）

- `avg_return_pred_up`
- `avg_return_pred_down`
- `return_spread`
- `pred_up_count`
- `pred_down_count`

用途：

- 判断预测向上与预测向下在中期窗口上是否能稳定拉开差距

### 8.2 方向一致性指标

- `accuracy_direction`
- `sign_consistency_vs_short_window`

用途：

- 判断中期方向结论是否和短窗完全冲突

### 8.3 覆盖与缺失指标

- `evaluable_count`
- `skipped_missing_snapshot`
- `skipped_missing_price`
- `skipped_quality_gate`

用途：

- 判断结果是否建立在足够覆盖上
- 避免覆盖不足时误判模型有效性

### 8.4 当前阶段不纳入主指标

当前阶段不把以下作为主通过指标：

- 交易收益曲线
- 持仓净值
- 夏普
- 最大回撤

原因：

- 这些指标更接近完整动作链评估
- 当前阶段的主问题是“状态识别是否具备中期分层能力”

## 9. 通过条件

当前阶段，中期验证口径的“通过”只表示值得进入下一阶段，不表示可以直接切主线。

通过至少应满足：

1. 在至少一个正式中期窗口上，`return_spread > 0`
2. `pred_up / pred_down` 分组样本量均不过低，不能只靠极小样本撑结果
3. 引入 `theme / market` 上下文后，结果不显著恶化
4. 中期结论与短窗方向不出现系统性反转
5. skipped 统计可解释，覆盖不足不能被忽略

## 10. 失败判定

出现以下任一情况，应视为当前阶段“中期未被证明”：

- `20D/40D/60D` 全部无法拉开正向分层
- 上下文增益后结果显著变差
- 中期与短窗方向系统性冲突
- evaluable 覆盖过低，结果不可解释

失败不等于模型无价值，只表示：

- 当前阶段不能把它上升为中期主判断依据

## 11. 产物要求

当前阶段正式验证至少需要输出：

- 一份版本锁定的中期验证结果表
- 一份短窗 vs 中期的对照摘要
- 一份 `stock only / stock+theme / stock+theme+market` 的增益对照摘要
- 一份 skipped/coverage 统计摘要

当前阶段不要求：

- 复杂 PDF 报告
- 动作级别详细交易明细

## 12. 当前阶段不展开的内容

本验证口径当前阶段不展开：

- `theme_state_context` 的复杂聚合算法
- `market_state_context` 的最终字段细化
- 中期动作链具体持有/离场策略
- 参数自动搜索与自动调优

## 13. 文档通过条件

本文件在当前阶段视为通过，需同时满足：

- 主验证对象明确
- horizon 明确
- universe 主辅关系明确
- 指标集合明确
- 通过/失败标准明确
- 不与当前专项基线冲突

在以上条件未被满足前，不进入更深的中期实现与动作主线讨论。
