# NeoTrade3 fetch_news 交易日门禁（设计定稿）

> 归档说明：本文记录的是 `fetch_news` 交易日门禁设计。文中把 `update_daily_prices_tencent` 作为并列既有任务名的表述，仅代表当时系统状态；当前正式日线任务名为 `update_daily_prices_authoritative`。

日期：2026-06-16  
范围：`fetch_news` 自动任务的业务语义收敛

## 1. 背景与目标

### 1.1 背景问题
- 当前 `_run_fetch_news()` 只要被调度触发，就直接执行 `ClsNewsAdapter.fetch_telegraph(limit=20)`。
- 代码中的 APScheduler 注册将其定义为“工作日 9:00–14:59 每 30 分钟”，但没有校验当天是否为真实交易日。
- 如果未来重新启用 APScheduler 常驻模式，工作日节假日也会执行该任务。
- 这与“交易日盘中任务”的业务语义不一致。

### 1.2 目标
- 明确 `fetch_news` 属于“交易日盘中任务”。
- 非交易日不抓取财联社快讯。
- 复用已有交易日判断逻辑，避免再造一套口径。
- 保持当前调度时间不变，只修正任务函数的业务语义。

## 2. 当前事实

### 2.1 当前实现
- `_run_fetch_news()` 当前实现只做两件事：
  - 构造 `ClsNewsAdapter`
  - 调用 `fetch_telegraph(limit=20)`
- 当前没有任何交易日检查。

### 2.2 当前调度定义
- APScheduler 将其注册为：
  - 工作日 `09:00-14:59`
  - 每 `30` 分钟执行一次
- 这只是“工作日时钟条件”，不是交易日业务条件。

### 2.3 已有可复用能力
- 系统内已有 `BootstrapApiService.trading_day_view()` 用于判断指定日期是否为交易日。
- `trade_execution_rt` 和 `daily_pipeline` 已复用这套口径。
- 因而 `fetch_news` 最合适的做法是复用同一判断逻辑。

## 3. 方案对比

### 3.1 方案 A：任务函数内增加交易日校验（推荐）
- 在 `_run_fetch_news()` 开始处调用 `trading_day_view(target_date=today)`。
- 若非交易日，则记录跳过日志后返回。
- 若为交易日，则继续执行抓取。

优点：
- 业务语义绑定在任务本身，而不是依赖外部调度配置。
- 手工调用、未来改调度方式、改触发源时，语义都不变。
- 与已有关键任务的交易日判断口径一致。

缺点：
- 任务函数对 `BootstrapApiService` 多一层依赖。

### 3.2 方案 B：仅靠调度层避免触发
- 不改任务函数，只通过更细调度配置减少节假日执行。

优点：
- 改动小。

缺点：
- 无法覆盖手工调用或未来触发源变化。
- 业务语义仍然不在任务本身上。

### 3.3 方案 C：调度层 + 任务层双保险
- 调度层收窄触发，任务层再加交易日校验。

优点：
- 最稳。

缺点：
- 对当前尚未生产启用的任务来说偏重。

## 4. 采用方案

采用 `方案 A：任务函数内增加交易日校验`。

原因：
- 这最符合“任务定义准确无误”的要求。
- 交易日语义应属于任务定义的一部分，不应只藏在调度器里。

## 5. 设计细节

### 5.1 改动位置
- 仅改 `neotrade3/scheduler/task_scheduler.py` 中的 `_run_fetch_news()`。
- 不调整 APScheduler 的时间表达式。
- 不改 `launchd` 配置，因为当前生产尚未启用此任务。

### 5.2 执行流程
1. `_run_fetch_news()` 启动。
2. 构造 `BootstrapApiService(project_root=_PROJECT_ROOT)`。
3. 调用 `trading_day_view(target_date=today)`。
4. 若返回“非交易日”：
   - 记录 `info` 日志
   - 直接返回
   - 不调用 `ClsNewsAdapter.fetch_telegraph(...)`
5. 若返回“交易日”：
   - 继续按当前逻辑抓取财联社快讯。

### 5.3 日志语义
- 非交易日跳过不视为异常。
- 应记录一条可追踪但不告警的日志，例如：
  - `fetch_news skipped: non-trading day`
- 真正抓取异常仍按现有逻辑记录 `error`。

### 5.4 错误处理
- “正常非交易日”属于预期分支，不写 `error`。
- 若交易日判断过程本身抛出异常，则仍记 `error`，因为这是系统异常而非业务跳过。

## 6. 验收标准

1. 交易日执行时，`_run_fetch_news()` 会实际调用 `ClsNewsAdapter.fetch_telegraph(...)`。
2. 非交易日执行时，`_run_fetch_news()` 不会调用 `ClsNewsAdapter.fetch_telegraph(...)`。
3. 非交易日只记录 `info` 跳过日志，不写错误日志。
4. 现有 `update_daily_prices_tencent`、`trade_execution_rt_0935`、`warm_tushare_theme_cache` 逻辑不受影响。

## 7. 建议测试用例

### 7.1 必测
- 交易日时调用 `_run_fetch_news()`，确认会执行 `fetch_telegraph(...)`
- 非交易日时调用 `_run_fetch_news()`，确认不会执行 `fetch_telegraph(...)`
- 交易日判断抛异常时，确认写错误日志

### 7.2 非目标
- 不在本轮将 `fetch_news` 纳入生产 LaunchAgent
- 不在本轮改动 APScheduler 其他任务
- 不在本轮调整 `fetch_news` 的执行频率或抓取条数
