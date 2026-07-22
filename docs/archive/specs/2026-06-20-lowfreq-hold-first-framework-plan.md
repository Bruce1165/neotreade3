# 低频长持优先主框架实施计划

日期：2026-06-20  
对应设计：`docs/superpowers/specs/2026-06-20-lowfreq-hold-first-framework-design.md`

## 1. 目标

按已批准设计，将当前低频模型的正式离场主链从“市场回撤 + 个股回撤 + `market_top` 观察确认”重构为：

1. 买入价 `-5%` 硬止损
2. `大盘见顶确认`
3. `板块见顶确认`

并同步完成：

- 将现有旧卖出规则从正式主链降级为观察证据或审计信息
- 引入 `大盘见顶 / 板块见顶` 的统一状态机语义
- 为“核心牛股 + 板块龙头”提供更高确认门槛
- 补齐新的序列化、审计、测试、归因与回测口径

## 2. 当前代码现实

### 2.1 当前正式卖出主链

`lowfreq_engine_v16_advanced.py` 里 `check_sell_signal_v2()` 当前仍是：

1. `market_drawdown <= -10%`
2. `stock_drawdown <= -20%`
3. `market_top watch -> confirm`

这与已批准设计直接冲突，因为：

- `market_drawdown` 仍是正式卖点
- `stock_drawdown` 仍是正式卖点
- `板块见顶确认` 尚未进入主链
- `market_top` 仍是单一路径，而非“大盘见顶”的多方法综合确认

### 2.2 当前可复用基础设施

已有可复用基础设施包括：

- `TradeRecord` 已支持 `market_top watch` 状态字段
- `sell_signal_audit` 已接入 `run_backtest()`
- `get_config_snapshot()` 已支持新参数落盘
- `apps/api/main.py` 已能恢复 `TradeRecord` 扩展字段
- `detect_sector_cooldown()` 与 `_sector_cooldown_confirmed()` 可作为 `板块见顶` 的候选证据源

### 2.3 当前回归测试现实

`tests/unit/test_lowfreq_engine_v16_sell_logic.py` 当前主要锁定的是：

- `market_drawdown` 优先于其他卖点
- `stock_drawdown` 直接触发
- `market_top` 的 watch / confirm / expire 行为

这些测试不能直接沿用，必须在主链重构时整体重写语义。

### 2.4 当前归因脚本现实

`scripts/generate_lowfreq_top200_attribution_report.py` 当前仍按以下卖出原因映射：

- `market_top`
- `market_drawdown`
- `stock_drawdown`

若不同步改造，后续回测与 `Top200 attribution` 会再次口径漂移。

## 3. 实施原则

- 先改正式主链，再处理旧规则降级，避免新旧逻辑并存打架。
- 先抽象统一状态机，再接入 `大盘见顶` 与 `板块见顶` 两条路径。
- 每轮只引入与已批准设计直接相关的结构，不额外扩展资金管理、减仓或买入逻辑。
- 龙头增强持有只提高确认门槛，不增加新的卖出豁免特权。
- 所有新行为必须可审计、可序列化、可回测、可归因。

## 4. 实施分解

### Phase 0：基线锁定与落点核对

目标：

- 锁定当前实现与测试落点，防止在重构过程中误判回归来源。

任务：

- 核对 `check_sell_signal_v2()` 当前正式卖出顺序
- 核对 `TradeRecord`、`config_snapshot`、`sell_signal_audit` 现有字段
- 核对 `apps/api/main.py` 的序列化与反序列化入口
- 核对 `Top200 attribution` 当前卖出原因映射

完成判定：

- 能清晰列出必须替换的旧正式卖点
- 能清晰列出可复用的状态机与审计基础设施

### Phase 1：状态模型重构

目标：

- 从当前仅支持 `market_top watch` 的局部状态，升级为支持 `大盘见顶` 与 `板块见顶` 的统一状态机框架。

任务：

- 扩展 `TradeRecord`，把当前局部 `market_top_watch_*` 状态升级为：
  - 大盘见顶状态
  - 板块见顶状态
  - 龙头增强持有相关标记
- 为 `LowFreqV16Config` 与 `LowFreqTradingEngineV16` 新增主框架参数族：
  - 买入价硬止损参数
  - 大盘见顶状态机参数
  - 板块见顶状态机参数
  - 龙头增强持有确认门槛参数
- 在 `get_config_snapshot()` 中输出新参数

边界：

- 本阶段只改状态与配置，不改正式卖出顺序
- 保留现有 `market_top watch` 逻辑直到 Phase 2 正式替换

完成判定：

- 新状态字段能完整表达 `观察态 -> 复核态 -> 确认离场`
- 配置快照能完整记录新框架参数

### Phase 2：正式卖出主链替换

目标：

- 将 `check_sell_signal_v2()` 替换为已批准设计的三出口主链。

任务：

- 新增买入价 `-5%` 硬止损信号函数
- 新增 `大盘见顶` 统一证据快照函数
- 新增 `板块见顶` 统一证据快照函数
- 抽象统一的系统性状态机推进函数：
  - 观察态
  - 复核态
  - 确认离场
- 将 `check_sell_signal_v2()` 改为：
  1. 买入价 `-5%` 硬止损
  2. `大盘见顶确认`
  3. `板块见顶确认`
- 移除 `market_drawdown` 与 `stock_drawdown` 作为正式卖出分支
- 移除当前 `market_top` 作为单独正式卖出路径

边界：

- 本阶段不做减仓
- 本阶段不引入新的买入或仓位逻辑
- 本阶段不做收益导向参数优化

完成判定：

- 正式卖出链只剩三个出口
- `market_drawdown` / `stock_drawdown` / 旧 `market_top` 不再拥有正式卖出权

### Phase 3：旧规则降级与证据归位

目标：

- 将现有旧卖点改造为“观察证据 / 复核证据 / 审计信息”。

任务：

- 将 `market_drawdown` 的硬阈值逻辑改造为 `大盘见顶` 的候选证据之一
- 将 `detect_sector_cooldown()` 与 `_sector_cooldown_confirmed()` 改造为 `板块见顶` 的候选证据源
- 将 `stock_drawdown` 从正式卖点降级为：
  - 个股观察证据
  - 或仅审计信息
- 梳理其他短期弱化、单日破坏类信号的职责，确保它们只参与证据判断

完成判定：

- 旧规则仍保留信息价值，但不再直接触发卖出
- `大盘见顶` 与 `板块见顶` 的证据族开始具备多方法输入

### Phase 4：龙头增强持有接入

目标：

- 对“核心牛股 + 板块龙头”应用更高确认门槛。

任务：

- 明确持仓级“龙头增强持有”标记来源：
  - 复用买入时已有 `role`
  - 增补后续所需的龙头/核心判定字段
- 在系统性状态机中加入更高确认门槛：
  - 观察态更难升级到复核态
  - 复核态更难升级到确认离场
- 保证这只是提高确认门槛，而不是无条件豁免

边界：

- 本阶段不扩大到新的评分体系重构
- 若需要补充对象判定字段，只补最小闭环字段

完成判定：

- 龙头样本与普通样本在系统性离场上体现出不同确认敏感度

### Phase 5：审计、序列化与归因口径同步

目标：

- 保证新框架的状态和结果能被完整复盘。

任务：

- 扩展 `sell_signal_audit`，记录：
  - 大盘见顶观察 / 复核 / 确认
  - 板块见顶观察 / 复核 / 确认
  - 龙头增强持有导致的门槛提升信息
- 更新 `TradeRecord` 在 `apps/api/main.py` 的反序列化
- 如需新增状态字段，补齐 payload 往返保真测试
- 更新 `scripts/generate_lowfreq_top200_attribution_report.py` 的卖出原因映射：
  - 新框架原因桶
  - 旧原因桶降级后的兼容处理

完成判定：

- 回测 payload、API payload、Top200 attribution 三条链路口径一致

### Phase 6：测试重写与验证

目标：

- 用新的低频长持语义重写回归保护。

任务：

- 重写 `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- 补充以下测试组：
  - 买入价 `-5%` 硬止损直接触发
  - 单日大盘 / 板块信号只进入观察态
  - 多方法持续恶化后才确认离场
  - 龙头增强持有比普通持仓更难被打出
  - 旧 `stock_drawdown` 不再直接卖出
  - 旧 `market_drawdown` 不再直接卖出
- 更新 `tests/unit/test_lowfreq_intent_conflicts.py`
  - 锁住新状态字段 payload 保真
- 如有必要，补充归因脚本单测或定向脚本校验

完成判定：

- 所有旧语义测试已替换为新框架语义
- 新状态字段和新卖出链有稳定回归保护

### Phase 7：回测与归因验收

目标：

- 按已批准设计的验收口径评估框架是否真正落地。

任务：

- 运行定向 `pytest`
- 运行 `py_compile` 与诊断检查
- 重跑近端窗口回测，检查交易结构
- 重跑 `18个月` 回测，检查：
  - 交易数
  - 平均持仓天数
  - 持仓天数分布
  - 系统性离场占比
  - 龙头样本持有质量
- 重跑 `2025 Top200 attribution`
- 对比新旧：
  - `bought_count`
  - `held_to_top_count`
  - 提前离场样本
  - 卖出原因分布

完成判定：

- 能以已批准框架口径回答“是否真正进入低频长持”

## 5. 代码变更清单

本计划预期至少涉及以下文件：

- `lowfreq_engine_v16_advanced.py`
  - `TradeRecord`
  - `LowFreqV16Config`
  - `LowFreqTradingEngineV16`
  - `check_sell_signal_v2()`
  - 系统性状态机辅助函数
  - 审计输出
- `apps/api/main.py`
  - `_lowfreq_trade_from_payload()`
- `tests/unit/test_lowfreq_engine_v16_sell_logic.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

如验证过程中发现必要落点，还可能涉及：

- 相关定向测试文件
- 运行实验脚本，但不改变其职责边界

## 6. 风险与控制

### 风险 1：主链替换后过度迟钝

控制：

- 先保留观察 / 复核 / 确认的完整审计
- 先跑近端窗口，再跑长窗
- 明确监控 `held_to_top` 与回撤，不只看收益

### 风险 2：龙头增强持有对象定义过宽

控制：

- 第一轮只采用最小闭环对象判定
- 严格排除补涨、跟风、脉冲、普通强势股

### 风险 3：旧原因桶未同步，导致归因漂移

控制：

- 回测与归因脚本必须同轮修改
- 新旧原因桶映射要明确兼容策略

### 风险 4：状态字段扩展后 payload 丢失

控制：

- API payload 往返保真测试必须同步更新

## 7. 成功标准

- 正式卖出链只剩三个出口
- `stock_drawdown`、`market_drawdown`、旧 `market_top` 不再直接卖出
- 回测交易数明显下降
- 平均持仓天数明显上升，并向 `40-60` 个交易日靠近
- 系统性离场成为主因
- “核心牛股 + 板块龙头”样本持有质量改善
- `Top200 attribution` 与回测口径保持一致

## 8. 执行顺序

推荐按以下顺序实施，不跳步：

1. Phase 0：基线锁定与落点核对
2. Phase 1：状态模型重构
3. Phase 2：正式卖出主链替换
4. Phase 3：旧规则降级与证据归位
5. Phase 4：龙头增强持有接入
6. Phase 5：审计、序列化与归因口径同步
7. Phase 6：测试重写与验证
8. Phase 7：回测与归因验收

## 9. 备注

本计划的核心不是“让模型卖得更聪明一点”，而是：

- 先把低频模型的离场哲学彻底改成“长持优先”
- 再在这个正确框架里优化见顶确认质量

因此，实施过程中若出现“为了短期收益重新恢复个股过程震荡型卖点”的倾向，应直接视为偏离设计。
