# NeoTrade3 全自动化交易：双窗口触发、昨日闭环、取价兜底（设计定稿）

日期：2026-06-11  
范围：NeoTrade3（模拟执行通道 / lowfreq_sim）  

## 1. 背景与目标

### 1.1 背景问题
- 系统在“今日产生离场信号”后，卖出动作通常发生在“下一交易日”。如果系统只能从本地 `daily_prices` 取 `execute_date` 当天价格，则在“次日数据未入库”时无法完成卖出，导致离场动作被动延迟。
- 用户要求系统达到“全自动化运行目标”，包括：定时触发、交易日校验、数据获取重试、pending 任务调度执行、异常告警、日志与审计闭环。

### 1.2 目标
- 形成稳定的“双窗口自动化”：
  - **15:30（决策/数据/学习）**：当日数据获取、模型运行、信号生成、回测/参数迭代触发。
  - **次日 09:35（执行）**：对 `execute_date=当日` 的 pending 买卖任务执行成交记账，不依赖全量日线入库。
- 新增“昨日闭环”：
  - 处理**逾期未执行**的昨日任务：按规则顺延至下一交易日（涵盖涨跌停/不可成交等场景）。
  - 对**昨日已执行**任务做清算、复盘与归档，保证可追溯。

## 2. 现状与约束（事实来源）

### 2.1 交易意图与成交记账（模拟执行通道）
- 交易意图存储：`/Users/mac/NeoTrade3/var/ledgers/lowfreq_sim/state.json` 中 `manual.intents`。
- 意图字段（已存在）：`intent_id, intent_type(buy_intent/sell_intent/abandon), status(pending/executed/cancelled), requested_date, execute_date, created_at(UTC), executed_at(UTC), executed_price, executed_shares, sell_reason, sell_signal, attempt_count, last_attempt_reason`。

### 2.2 卖出意图的“次日执行”规则（已存在）
- 卖出意图生成：当日 `requested_date` 发现离场信号后，生成 `sell_intent`，其 `execute_date = next_trading_day(requested_date)`。
- 执行价格获取：当前执行逻辑从本地 `daily_prices(open)` 获取当日价格；取不到则记录 `no_open_price` 并顺延 `execute_date` 到下一交易日。

### 2.3 交易日判断能力（已存在）
- 交易日来源优先使用 `trading_calendar_cache`，并具备使用 Tushare `trade_cal` 进行覆盖补齐的能力（若 token 配置可用）。

### 2.4 本设计的关键约束
- 当前执行通道为 A（模拟执行），不接入券商真实下单接口。
- “次日执行窗口”要能在“次日全量日线未入库”时仍可执行，因此需要引入 **实时取价**（腾讯优先、Tushare RT 兜底）。

## 3. 总体架构：双窗口触发

### 3.1 触发窗口一：15:30（Mon–Fri）
目的：做“决策与学习”，不做“次日成交执行”。

顺序（强制）：
1) 今日交易日校验（A 股交易日 + 临时休市）
2) 昨日闭环（见第 4 节）
3) 今日数据获取（全量行情入库 + 完整性闸门；失败重试 3 次，每次间隔 5 分钟）
4) 模型运行 → 生成/更新意图（buy/sell）
5) 回测自动触发（数据达标触发）
6) 参数/因子迭代触发与生效（漂移/表现触发 → 验证闸门 → `effective_from` 延迟生效）
7) 写入当日运行 ledger + 告警汇总

### 3.2 触发窗口二：次日 09:35（Mon–Fri，交易日）
目的：对 `execute_date=当日` 的 pending 任务进行成交执行（模拟记账），不依赖全量日线入库。

顺序（强制）：
1) 今日交易日校验
2) 执行前置：对每个 pending 任务进行“取价”与“可执行性”校验（见第 5 节）
3) 执行成交记账：
   - 成功：写入 `executed_at(UTC), executed_price, executed_shares`，并更新 `status=executed`
   - 失败（可恢复/不可成交）：顺延至下一交易日，更新 `attempt_count/last_attempt_reason` 并归档原因
4) 写入 09:35 执行 ledger + 告警汇总

## 4. 新增模块：昨日闭环（清算/复盘/归档 + 逾期顺延）

### 4.1 输入/输出
输入：
- `state.json` 中 `manual.intents`
- `stock_data.db` 中昨日行情（用于复盘统计）
- 交易日历（用于判断昨日是否为交易日与下一交易日）

输出（新增 ledger）：
- `var/ledgers/trade_closeout/YYYY-MM-DD.json`：昨日闭环报告（以“昨日日期”为文件名）

### 4.2 处理对象
1) **逾期未执行（必须处理）**  
条件：`status=pending AND execute_date=昨日（上一交易日）`

规则：
- 默认：**顺延到下一交易日**（覆盖涨停/跌停/不可成交/取价失败等情况）。
- 记录字段：
  - `attempt_count += 1`
  - `last_attempt_date = 昨日`
  - `last_attempt_reason`（枚举：`no_price`, `limit_up_down_or_untradable`, `data_missing`, `other_blocked`）
  - `execute_date = next_trading_day(昨日)`
- 告警：当 `attempt_count` 超过阈值（建议 3）仍未执行，触发告警（避免无限顺延无感知）。

2) **昨日已执行（必须归档）**  
条件：`status=executed AND executed_date=昨日`

归档内容：
- 成交汇总：按 buy/sell 统计成交额、成交数量、均价、UTC 时间范围
- 复盘摘要：
  - sell：`sell_signal/sell_reason` 统计与样例
  - buy：`buy_score/role/sector/wave_phase` 统计与样例
- 资金与持仓变化摘要：基于 state 快照与 executed intents 生成差分摘要（模拟通道下为“本地账”口径）

异常：
- 若发现 `executed_date=昨日` 但缺失 `executed_at/price/shares`：标记为一致性错误并告警（不自动补写历史成交字段）。

## 5. 次日 09:35 执行：实时取价与执行规则

### 5.1 取价策略（必须）
对每个 `execute_date=当日` 的 pending 意图：
1) **腾讯实时/准实时取价（优先）**  
目标：获得当日可用成交参考价（至少 open/last/preclose）与交易日标识。
2) **Tushare 日线 RT 兜底**  
当腾讯取价失败或不可用时，使用 Tushare 兜底获取当日价格信息。
3) 两者都失败 → 视为 `no_price`，顺延到下一交易日，并告警（可配置是否仅记录不告警）。

### 5.2 可成交性规则（最小可运行版本）
由于模拟通道不接入真实盘口，涨跌停判断以“保守顺延”为主：
- 若取价成功但判断为不可成交（如封涨停无法买入、封跌停无法卖出），则顺延并记录 `limit_up_down_or_untradable`。
- 若无法判断，默认允许成交（以减少误阻塞），同时保留 `risk_note` 字段用于审计。

### 5.3 买入/卖出校验与执行
按 `created_at(UTC)` 排序逐笔处理：
- 买入：
  - 资金充足、仓位槽位充足、取价成功
  - 若不满足则顺延下一交易日，并记录原因（`no_cash/no_slots/no_price/...`）
- 卖出：
  - 持仓数量足额、取价成功
  - 若不满足则标记为异常并告警（持仓缺失属于一致性错误）

执行成功后写入：
- `executed_at`（UTC）
- `executed_date=execute_date`
- `executed_price`
- `executed_shares`
- `status=executed`

## 6. 自动化触发机制（全链路补全）

### 6.1 数据更新触发模型运行（15:30）
触发条件：
- 今日为交易日
- 数据获取完成且完整性闸门通过（coverage / rows gate）

动作：
- 运行模型生成 buy/sell intents（买入与卖出分别进入 `execute_date=next_trading_day(today)`）
- 触发回测/学习环节（见 6.2、6.3）

### 6.2 回测自动触发规则
触发来源：
- 定期：每个交易日数据达标后触发滚动回测（如 roll60）
- 数据达标触发：数据质量闸门通过才允许触发
- 参数调整触发：当参数 overrides 发生变化并到达 `effective_from` 时触发对照回测（旧参数 vs 新参数）

### 6.3 参数/因子迭代调整：触发、验证、延迟生效
触发场景：
- 定时（每 N 交易日）
- 漂移触发（因子/输出漂移超过阈值）
- 表现触发（策略表现指标连续恶化）

验证闸门：
- 对照回测必须通过（收益/回撤/交易次数/换手等约束）
- 不通过：不生效，记录失败原因并告警

生效逻辑：
- 使用 `effective_from` 延迟生效（避免当日决策口径污染）

## 7. 日志、ledger、告警（统一要求）

### 7.1 Ledger 要求
每次 15:30 与 09:35 的 run 都必须输出结构化 ledger（JSON），包含：
- trigger：触发时间（UTC+本地）、requested_by、run_id
- trading_day_check：交易日校验结果与来源
- data_fetch：每次尝试、耗时、失败原因、最终状态
- intents：处理的 intent 列表（每笔校验结果、执行结果、顺延原因）
- summary：执行数量、成功/失败/顺延统计

### 7.2 告警要求
- 交易日校验失败不告警（正常跳过）
- 数据获取重试耗尽必须告警
- 关键一致性错误（如卖出时持仓缺失、executed 缺字段）必须告警
- 逾期顺延连续超过阈值必须告警

## 8. 验收标准（可操作）
1) 今日 15:30：若交易日且数据达标，必须生成 intents，并产出当日运行 ledger
2) 次日 09:35：即使当日 `daily_prices` 全量未入库，也能通过实时取价执行 `execute_date=当日` 的 pending 卖出；失败则顺延并记录原因
3) 昨日闭环：对 `executed_date=昨日` 的意图生成清算归档；对 `execute_date=昨日 && pending` 的意图顺延到下一交易日
4) 任一关键失败（数据重试耗尽/一致性错误）必须可在 ledger 与告警中定位
