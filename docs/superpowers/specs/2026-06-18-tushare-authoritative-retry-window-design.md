# NeoTrade3 日线主源优先落库修正设计（设计定稿）

日期：2026-06-18  
范围：`daily_prices` 的生产自动任务时点与 `Tushare -> Tencent` 主备切换逻辑

## 1. 背景与目标

- 当前 `daily_prices` 的主源配置已经明确是 `Tushare`，fallback 是 `Tencent`。
- 但实际生产自动任务中，2026-06-18 当天最终仍然走了 `Tencent fallback`。
- 现有证据表明，这不是配置漂移，而是当天自动任务触发时点上，`Tushare daily` 尚未返回目标日数据。

目标：
- 保持 `Tushare` 作为 `daily_prices` 的主源口径不变。
- 让生产自动任务更大概率以 `Tushare` 作为当天正式落库来源。
- 保留 `Tencent fallback`，避免主源暂时不可用时当天完全断更。
- 用最小改动修正当前“15:30 即判断主源失败”的时点问题。

## 2. 当前证据

### 2.1 当前生产调度时点

- `update_daily_prices_authoritative` 当前生产/本地对齐时间为：工作日 `15:30`。
- 见 `task_scheduler.py` 中的 cron 注册。

### 2.2 当前 authoritative 主备逻辑

- `daily_prices` 的 authoritative 逻辑先执行：
  - `update_daily_prices_tushare_view()`
- 只有当：
  - `format_gate.passed == true`
  - 且 `quality_gate.passed == true`
- 才判定 `Tushare` 成功。
- 否则即进入 `Tencent fallback`。

### 2.3 当天失败的直接原因

- `_backfill_daily_prices_from_tushare_daily()` 在调用 `ts.pro_api(...).daily(...)` 后，
  如果返回记录为空，会直接返回：
  - `status = "skipped"`
  - `reason = "tushare_has_no_rows_for_target_date"`

- 2026-06-18 的状态文件也记录了：
  - `last_failure_reason = "tushare_has_no_rows_for_target_date"`
  - `last_fallback_used = true`

结论：
- 当天不是 token、接口异常或 gate 配置问题。
- 而是 `15:30` 这个时点，`Tushare daily` 尚未给出当天记录。

## 3. 问题归因

当前问题的核心不是“主备策略错误”，而是：

- 自动任务触发时间过早。
- 一旦 `Tushare daily` 在该时点为空，当前逻辑会立刻判定主源失败。
- 然后立即切换到 `Tencent`，从而使当天正式落库来源偏离主源口径。

也就是说，当前缺的不是 fallback，而是“给主源一个合理的等待窗口”。

## 4. 方案比较

### 4.1 方案 A：仅把自动任务延后到更晚

- 把 `15:30` 调整到 `15:45` 或 `16:00`。

优点：
- 改动最小。
- 调度简单。
- 最直接针对当前已知问题。

缺点：
- 如果新时点仍拿不到数据，当天仍会 fallback。
- 没有为主源提供窗口内重试机会。

### 4.2 方案 B：保留 `15:30`，但在 fallback 前增加重试窗口

- `15:30` 首次尝试 `Tushare`
- 若为空，不立刻 fallback
- 在窗口内多次短重试
- 到截止时间仍失败，再切 `Tencent`

优点：
- 更符合“主源优先”。

缺点：
- 逻辑复杂度增加。
- 需要额外定义重试窗口状态与 ledger 口径。
- 仍默认认为 `15:30` 是合理起点，而当前证据并不支持这一点。

### 4.3 方案 C：延后触发 + 短重试窗口

- 首次 authoritative 触发时间从 `15:30` 延后到 `15:45`
- 如果 `Tushare daily` 仍为空，则：
  - 每 `3` 分钟重试一次
  - 截止到 `16:00`
  - 仍失败再切 `Tencent`

优点：
- 同时解决“起点过早”和“没有等待窗口”两个问题。
- 仍属于小范围改动，不改主备配置。
- 对当天断更风险最小。

缺点：
- 比单纯延后多一层重试控制逻辑。

结论：
- 本次采用方案 C。

## 5. 设计原则

- `Tushare` 主源口径不变。
- `Tencent fallback` 不移除。
- 先修正触发时点，再补短重试窗口。
- 重试窗口只针对“`Tushare daily` 无数据”这类可等待场景。
- 不把窗口无限拉长，避免任务拖到晚间。

## 6. 调度口径调整

### 6.1 新的自动任务时间

- `update_daily_prices_authoritative`
  - 从工作日 `15:30`
  - 调整为工作日 `15:45`

### 6.2 同步范围

需要同步以下口径：
- `task_scheduler.py` 中本地/dev 对齐 cron
- 生产 `launchd` 模板
- 运维文档
- 任务注册文档

要求：
- 生产与本地调度口径保持一致
- 不再出现代码、模板、文档三处时间不一致

## 7. 重试窗口设计

### 7.1 触发条件

只有在以下条件同时满足时，才进入重试窗口：

- 当前 authoritative 主源仍为 `Tushare`
- `Tushare daily` 返回空记录
- 对应 backfill 结果为：
  - `status = "skipped"`
  - `reason = "tushare_has_no_rows_for_target_date"`

以下情况不进入重试窗口，仍按现有失败路径处理：
- token/权限类错误
- 接口异常抛错
- 数据格式异常
- 质量门禁失败但数据已返回

说明：
- 本次窗口只针对“主源尚未出数”的场景，不把所有失败都重试。

### 7.2 重试策略

- 首次尝试时间：`15:45`
- 重试间隔：`3` 分钟
- 最晚截止：`16:00`

等价尝试序列：
- `15:45`
- `15:48`
- `15:51`
- `15:54`
- `15:57`
- `16:00`

一旦任意一次 `Tushare` 通过：
- 立即停止重试
- 不进入 `Tencent fallback`

如果到 `16:00` 仍为 `tushare_has_no_rows_for_target_date`：
- 执行现有 `Tencent fallback`

### 7.3 实现位置

重试窗口逻辑应放在 authoritative 层，而不是调度层。

原因：
- 调度层只负责“何时触发”
- authoritative 层才知道：
  - 主源是否真的为空
  - 失败原因是否属于可等待场景
  - 何时该切 fallback

因此应在：
- `update_daily_prices_authoritative()`
内完成“空数据重试 -> 截止后 fallback”的控制。

## 8. ledger / 状态口径

### 8.1 需要新增或明确记录的信息

authoritative 结果中应可体现：
- 首次尝试时间
- 重试次数
- 最终是否在窗口内由 `Tushare` 成功
- 是否在窗口结束后才切到 `Tencent`

建议新增字段：
- `retry_window_used`
- `retry_attempts`
- `retry_deadline`
- `primary_final_reason`

### 8.2 保持现有关键字段语义

以下现有字段语义不变：
- `provider`
- `fallback_used`
- `fallback_provider`

说明：
- `provider` 仍表示 authoritative 主源口径，即 `tushare`
- `fallback_used = true` 仍表示最终实际发布使用了 fallback
- 不修改现有对下游已依赖字段的含义

## 9. 状态文件口径

`_tushare_status.json` 需要继续准确反映：
- 最近主源失败原因
- 最近是否使用 fallback

如果最终在窗口内由 `Tushare` 成功：
- `last_fallback_used` 应为 `false`

如果窗口结束后切 `Tencent`：
- `last_fallback_used` 应为 `true`
- `last_failure_reason` 保持为 `tushare_has_no_rows_for_target_date`

## 10. 非目标

- 不移除 `Tencent fallback`
- 不修改 `daily_prices` 的主备配置结构
- 不改变 `quality_gate` / `format_gate` 判定规则
- 不处理 `financial_data`、`news`、`theme cache` 等其他调度任务
- 不在本次范围内引入异步任务队列系统

## 11. 实施顺序

严格顺序如下：

1. 调整 `update_daily_prices_authoritative` 的生产/本地调度时间到 `15:45`
2. 在 authoritative 层加入“空数据短重试窗口”
3. 更新 ledger 与状态字段记录
4. 更新 `launchd` 模板
5. 更新运维文档与任务注册文档
6. 执行定点验证

## 12. 验证

### 12.1 代码级验证

至少覆盖：
- `Tushare` 一次成功时，不进入 fallback
- `Tushare` 首次为空、窗口内后续成功时，不进入 fallback
- `Tushare` 到截止仍为空时，进入 `Tencent fallback`
- 非空数据但 gate 失败时，不误走“空数据重试窗口”

### 12.2 调度验证

- 渲染后的 `launchd` 调度时间为 `15:45`
- 本地 APScheduler 定义与生产模板时间一致

### 12.3 运行验证

在下一交易日重点核查：
- ledger 中是否记录了重试窗口
- 最终落库来源是否变回 `Tushare`
- 若仍 fallback，原因是否仍为 `tushare_has_no_rows_for_target_date`

## 13. 完成标准

- 生产自动任务时点从 `15:30` 调整为 `15:45`
- `Tushare daily` 空数据不再在首次尝试后立即触发 fallback
- 系统只在重试窗口截止后才切 `Tencent`
- ledger 和状态文件可追踪本次是否使用重试窗口
- 生产、本地、模板、文档的时间口径一致
