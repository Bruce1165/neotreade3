# 早窗龙头系统性退出降级设计

## 目标

在不修改买入链、止损链、追高硬禁和容量结构的前提下，收敛一条最小可验证规则：

- 对早窗/前置布局且已经形成明显利润垫的强势龙头持仓，
- 当 `market_top_confirmed` 或 `sector_top_confirmed` 首次成立时，
- 不直接清仓，而是给予一次性的“保护性继续持有”机会。

本轮目标不是放宽所有卖出，而是只修正被研究证据确认的“强势龙头被系统性确认过早一刀切卖出”的问题。

## 证据基础

来自 `Top200` 全过程研究产物：

- `603119 浙江荣泰`
  - 基线版本因 `market_top_confirmed` 退出
  - 退出后到事实顶仍有 `237.56%` 剩余上涨空间
- `688519 南亚新材`
  - 基线版本因 `sector_top_confirmed` 退出
  - 退出后到事实顶仍有 `182.38%` 剩余上涨空间
- `301345 涛涛车业`
  - 首段收益 `270.20%`
  - 首次退出后到事实顶仍有 `26.63%` 剩余上涨空间

研究结论是：

- 当前主问题不是买点识别过晚
- 也不是 `-5%` 止损过紧
- 而是早窗龙头在系统性扰动中的退出动作过重

## 范围

本轮只改正式卖出主链中的系统性确认动作：

- `_apply_system_exit_state()`
- `check_sell_signal_v2()`

本轮不改：

- `entry_stop_loss`
- 买入评分、候选生成、追高硬禁
- 仓位数、容量控制、部分减仓
- 再介入逻辑

## 规则语义

### 1. 保护对象

仅允许以下持仓使用一次性系统退出保护：

- `leader_hold_active = True`
- 历史峰值收益达到利润垫门槛
- 当前持仓仍处于盈利状态
- 触发的不是 `entry_stop_loss`

建议参数：

- `SYSTEM_EXIT_GRACE_MIN_PEAK_RETURN_PCT = 20.0`
- `SYSTEM_EXIT_GRACE_REQUIRE_POSITIVE_RETURN = True`

### 2. 保护动作

当 `market_top_confirmed` 或 `sector_top_confirmed` 达成时：

- 若该持仓满足保护资格，且尚未使用过保护：
  - 不返回 `SellSignal`
  - 记录一次 `system_exit_downgraded`
  - 清空当前市场/板块退出状态机
  - 标记该持仓已使用过保护
- 若该持仓已使用过保护：
  - 按现有逻辑正常卖出

### 3. 保护次数

采用全局一次性保护，而不是 `market` / `sector` 各一次。

理由：

- 双保护容易在真实系统性退潮中拖延退出
- 当前证据只支持“第一次别卖得太绝”，不支持多次反复宽容

## 数据结构

在 `TradeRecord` 中新增字段：

- `system_exit_grace_used: bool = False`
- `system_exit_grace_date: str = ""`
- `system_exit_grace_scope: str = ""`
- `system_exit_grace_reason: str = ""`

这些字段仅服务于：

- 防止重复保护
- 回测后审计保护效果
- API 序列化一致性

## 审计

新增审计事件：

- `system_exit_downgraded`
- `system_exit_downgraded_then_confirmed`
- `system_exit_downgraded_then_stop_loss`
- `system_exit_downgraded_then_end_flat`

最低要求：

- 必须能在回测摘要中看到保护发生次数
- 必须能追踪每笔保护最终结局

## 实现建议

### 1. 新增资格判断函数

新增一个小函数，例如：

- `_eligible_for_system_exit_grace(trade, snapshot, scope, sell_price)`

职责只做一件事：

- 判断本次系统性确认是否允许降级为保护性继续持有

### 2. 落点

在 `_apply_system_exit_state()` 即将确认卖出时，插入资格判断：

- 若不符合资格，维持现有确认卖出逻辑
- 若符合资格且未使用过保护，则执行降级逻辑并返回 `None`

### 3. 状态处理

保护发生后：

- 同时重置当前 `market` 和 `sector` 退出状态
- 避免旧状态延续导致次日立即再次确认

## 风险控制

本轮必须坚持两个硬边界：

- 只允许保护一次
- 只保护已有利润垫的强势龙头

这样做是为了控制最大风险：

- 把真实系统性退潮拖成更晚退出，导致回撤扩大

## 验证方案

### 1. 定向样本

优先验证：

- `603119`
- `688519`
- `301345`

重点看：

- 首次系统性确认是否从“直接卖出”变成“保护继续持有”
- 后续是否仍能在真正退潮中退出
- 是否避免了明显“卖后还有巨大上涨空间”的情况

### 2. 回归测试

新增/改写测试覆盖：

- 满足保护资格时首次确认不卖出
- 保护后再次确认正常卖出
- 不满足利润垫时不保护
- `entry_stop_loss` 永不保护
- 保护发生后退出状态被正确重置

### 3. 长窗 A/B

必须复核：

- 总收益
- 最大回撤
- 平均持仓
- `market_top_confirmed / sector_top_confirmed` 卖出数
- `system_exit_downgraded` 次数
- `Top200 bought_count / held_to_top_count`

优先验收指标：

- “卖出后仍有巨大剩余上涨空间”的样本是否下降
- 收益改善是否没有显著以回撤恶化为代价

## 非目标

本轮明确不解决：

- 主升段再介入机制
- 高置信早窗容量保护
- 分形态卖出体系
- 部分减仓

这些属于后续独立迭代。
