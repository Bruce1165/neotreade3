# NeoTrade3 数据源收敛到 Tushare 主源、腾讯日线 safety-net（设计定稿）

日期：2026-06-16  
范围：`daily_prices` 主源切换、Tushare 唯一来源资源失败语义、生产入口与运维文档同步

> 说明：本设计文档记录的是该轮收敛设计与实施基线。文中“当前生产入口仍为 `update_daily_prices_tencent`”等表述仅代表设计当时的起始事实；当前正式生产入口已收敛为 `update_daily_prices_authoritative`。

## 1. 背景与问题

### 1.1 已确认事实
- 当前生产自动任务里，`daily_prices` 的正式入口仍是 `update_daily_prices_tencent`。
- 当前 `daily_prices` 链路中，Tushare 主要承担“非当日补洞/历史回补”角色，不是生产主源。
- 当前系统已经接入一组可直接落库的 Tushare 资源：
  - `daily`
  - `daily_basic`
  - `fina_indicator`
  - `anns_d`
  - `npr`
  - `research_report`
  - `report_rc`
  - `stk_surv`
  - `etf_basic`
  - `fund_daily`
  - `etf_share_size`
  - `etf_index`
  - `fund_basic`
  - `fund_portfolio`
  - `index_announcements`
  - `index_weight`
  - `ths_index`
  - `ths_member`
  - `trade_cal`
- 当前部分 Tushare 入口在上游失败、Token 未配置、结果为空时，会返回 `status=skipped`，而不是明确失败。
- 当前已有粗粒度 `tushare_status` 记录机制，但只覆盖“最近成功”和“积分不足”两类全局状态，不能支持“按资源判定唯一主源是否失效”。

### 1.2 当前问题
- 生产数据源口径没有收敛：
  - `daily_prices` 仍以腾讯为主。
  - 其它资源虽然多数已接入 Tushare，但失败语义并不统一。
- `skipped` 语义混杂：
  - 有的 `skipped` 实际代表主源失败。
  - 有的 `skipped` 只是 `dry_run`、盘未收、区间无有效 period 这类前置条件不满足。
- 生产入口、代码实现、运维文档还没有围绕“Tushare 主源、腾讯只作 safety-net”形成统一口径。
- `daily_prices` 虽然已有覆盖率门禁，但在主源切到 Tushare 后，还需要增加严格的格式一致性校验，确保最终写入格式与现有表契约一致。

### 1.3 本次要解决的问题
- 把本轮范围内的数据源口径收敛到：
  - `Tushare 主源`
  - `腾讯仅作 daily_prices 的 safety-net`
- 对 `Tushare 唯一来源` 的资源，一旦主源失效，相关 API 必须立刻硬失败。
- 明确哪些 `skipped` 属于源失败，哪些属于业务前置条件，并分别处理。
- 明确任何代码修改必须同步对应文档，且生产入口相关变更要分阶段执行并保持代码、配置、文档一致。

## 2. 根因分析

### 2.1 根因不是“多数据源”本身
- Tencent 与 Tushare 同时存在并不天然错误。
- 错误在于当前没有明确定义：
  - 哪个是主源
  - 哪个只在什么场景下兜底
  - 主源失败后 API 应如何表达

### 2.2 真正失控点
- `daily_prices` 的生产入口历史上以腾讯为主，Tushare 主源能力虽已存在，但没有进入正式主链。
- 多个 Tushare 入口把“主源失败”宽松表达成 `skipped`，调用方容易误以为是正常跳过。
- 现有状态记录过于粗粒度，无法支撑“唯一来源资源一失效就立即提示”的目标。
- 生产任务、代码入口、运维文档尚未同步收敛，容易再次出现“代码口径”和“生产口径”漂移。

## 3. 设计目标

### 3.1 目标
- 将本轮已确认资源的主源统一收敛到 Tushare。
- 将 Tencent 限定为 `daily_prices` 的唯一 fallback，不扩展到其它资源。
- 将 Tushare 唯一来源资源的失败语义统一为 `API 硬失败`。
- 将 `skipped` 语义拆分为“源失败”和“业务前置条件未满足”两类，避免继续混用。
- 保留 `daily_prices` 的质量门禁，并新增格式一致性门禁。
- 将“代码的修改/编写，必须同步对应的文档”写成硬约束。

### 3.2 非目标
- 不在本轮引入一套新的大型配置系统。
- 不为公告、研报、概念、ETF 等资源增加腾讯 fallback。
- 不改动 `market-intelligence` 的消费逻辑、主题逻辑、推荐逻辑。
- 不在本轮引入前端提示改造；“立即提示”以 API 硬失败为准。
- 不把调度系统整体改造成新的统一常驻调度器。

## 4. 方案对比与选型

### 4.1 方案 A：代码内最小策略表，Tushare 主源，Tencent 仅作 daily_prices safety-net
- 定义：
  - 在 `BootstrapApiService` 内维护一份最小资源策略表。
  - 显式声明每个逻辑资源的：
    - `primary_provider`
    - `fallback_provider`
    - `hard_fail_on_primary_only`
- 优点：
  - 与当前代码结构兼容，落地成本最低。
  - 能同时解决主源收敛和失败语义收紧两个核心问题。
  - 风险边界清晰，不引入新的配置系统。
- 缺点：
  - 资源策略先落在代码里，不是完全配置驱动。

### 4.2 方案 B：新增配置驱动的数据源注册表
- 优点：
  - 长期看最规范。
  - 文档、调度、API 可以共同读取同一份策略。
- 缺点：
  - 本轮改动面过大。
  - 需要额外定义配置加载、校验、回归验证机制。

### 4.3 方案 C：只切生产调度入口，不调整 API 失败语义
- 优点：
  - 变更最快。
- 缺点：
  - 无法满足“唯一来源失效立刻提示”。
  - 无法统一 `skipped` 口径。
  - 不能从根本上完成主源收敛。

### 4.4 结论
- 采用方案 A。
- 原因：它在本轮范围内改动最小，但足以完整满足：
  - `Tushare 主源`
  - `Tencent 仅作 daily_prices safety-net`
  - `唯一来源失效 API 硬失败`
  - `代码与文档同步收敛`

## 5. 单一策略定义

### 5.1 资源分组
- `daily_prices`
  - `primary_provider = tushare`
  - `fallback_provider = tencent`
  - `hard_fail_on_primary_only = false`
- `concept_theme_cache`
  - `primary_provider = tushare`
  - `fallback_provider = none`
  - `hard_fail_on_primary_only = true`
- 以下资源全部视为 `Tushare 唯一来源`：
  - `company_announcements`
  - `policy_documents`
  - `research_reports`
  - `report_consensus`
  - `institutional_surveys`
  - `etf_basic`
  - `fund_daily`
  - `etf_share_size`
  - `etf_index`
  - `fund_basic`
  - `fund_portfolio`
  - `index_announcements`
  - `index_weight`
  - `stock_fundamentals_daily_basic`
  - `financial_reports`

### 5.2 策略表达要求
- 每个资源必须能回答以下问题：
  - 主源是谁
  - 是否允许 fallback
  - 若没有 fallback，主源失败时是否硬失败
- 不允许再存在“实现上用了 Tushare，但文档没说明是否唯一来源”的模糊状态。

## 6. skipped 语义收敛

### 6.1 必须改成硬失败的 skipped
- 以下场景属于“主源失败被吞掉”，必须改成 `ApiError`：
  - `tushare_token_not_configured`
  - `tushare_not_installed`
  - `tushare_daily_failed`
  - `tushare_has_no_rows_for_target_date`
  - `tushare_rows_filtered_out`
  - `tushare_daily_basic_failed`
  - `tushare_daily_basic_empty`
  - `concept_list_unavailable`
- 对 Tushare 唯一来源资源，上述情形都必须表现为：
  - `HTTP 失败`
  - `error.code = authoritative_source_unavailable`
  - `details` 至少包含 `resource`、`provider`、`reason`、`requested_by`

### 6.2 允许保留非失败语义的 skipped
- 以下情形不属于数据源失效，不应并入“立即提示”：
  - `dry_run`
  - `market_not_closed`
  - `no_periods_in_range`
  - `no_valid_ts_codes`
- 这类返回语义应显式重命名为：
  - `dry_run`
  - 或 `precondition_not_met`
- 不再继续使用含糊的 `skipped` 误导调用方。

### 6.3 concept cooldown 的特殊规则
- `concept_list_cooldown` 本身不自动等于主源失效。
- 但若当前请求必须获取概念列表且本地缓存不可用，则应直接按主源失败处理。
- 只有在以下条件同时满足时，才允许 `cooldown` 期间继续服务：
  - 已存在可用本地缓存
  - 缓存 provider 与当前 token/provider 一致
  - 缓存满足当前请求所需最小字段和最小完整性

## 7. daily_prices 主源切换设计

### 7.1 统一入口
- 新增一个统一的 `daily_prices` 同步入口，由它决定主源和 fallback 顺序。
- 固定顺序：
  1. 先执行 Tushare 主源
  2. 若主源失败，再执行 Tencent safety-net
  3. 若两者都失败，接口最终失败

### 7.2 Tushare 主源成功判定
- 只有在以下条件同时满足时，Tushare 才算成功：
  - 上游调用成功
  - 返回记录可写入
  - 覆盖率门禁通过
  - 格式一致性门禁通过
- 若任一条件不满足，都视为主源失败，再决定是否允许 fallback。

### 7.3 Tencent fallback 约束
- Tencent 只允许用于 `daily_prices`。
- Tencent fallback 仅在 Tushare 主源失败时触发。
- Tencent 不得再被描述成 `daily_prices` 的生产主源。

## 8. daily_prices 格式一致性门禁

### 8.1 设计原则
- 本轮不假设 Tushare 数据质量会更差。
- 但主源切换后，必须用统一契约确保最终入库格式一致。
- 校验目标不是比较谁更好，而是确保写入 `daily_prices` 的结果保持稳定、可解释、可回归。

### 8.2 统一目标字段
- 最终写入字段契约保持不变：
  - `open`
  - `high`
  - `low`
  - `close`
  - `volume`
  - `amount`
  - `turnover`
  - `preclose`
  - `pct_change`

### 8.3 必须增加的校验
- 字段存在性校验：
  - `code`
  - `trade_date`
  - `close`
  - `open/high/low` 至少应满足现有日线表的最小可用要求
- 类型校验：
  - 价格字段必须可安全转换为 `float`
  - 数量字段必须可安全转换为 `float` 或显式为空
- 单位归一校验：
  - Tushare `vol` 必须统一换算为股
  - Tushare `amount` 必须统一换算为元
- 关系校验：
  - `high >= max(open, close, low)` 的基本区间关系必须成立
  - `low <= min(open, close, high)` 的基本区间关系必须成立
  - `preclose > 0` 时，`pct_change` 与 `close/preclose` 的方向和量级应基本一致
  - `amount > 0`、`volume > 0`、`close > 0` 时，`amount / volume` 与 `close` 的量级应合理

### 8.4 门禁结果
- 若覆盖率通过但格式一致性不通过：
  - 仍视为 Tushare 主源失败
  - 不得当作主源成功
  - 可继续进入 Tencent fallback
- 若 Tencent fallback 也未通过同一套门禁：
  - 最终接口失败
  - 不写入“表面成功”的产物

## 9. Tushare 状态记录扩展

### 9.1 现状不足
- 当前 `tushare_status` 只能表达：
  - 最近一次成功
  - 最近一次积分不足
- 这不足以支撑“按资源立刻提示”。

### 9.2 新状态模型
- 状态记录扩展为按资源维护：
  - `resource`
  - `provider`
  - `last_ok_at`
  - `last_failure_at`
  - `last_failure_reason`
  - `last_api_name`
  - `last_error_code`
  - `last_error_message`
- 对 `daily_prices` 还应记录：
  - `last_format_gate_passed`
  - `last_quality_gate_passed`
  - `last_fallback_used`

### 9.3 使用方式
- API 在抛出 `authoritative_source_unavailable` 时，直接从对应资源状态中取证据。
- 任务层在主源失败时也写入相同状态，保证人工排查与 API 错误口径一致。

## 10. 分阶段执行与文档同步

### 10.1 分阶段执行原则
- 本轮必须分阶段执行，不允许一次性把代码、生产入口、文档混改后再补解释。
- 每一阶段都必须有明确的交付边界和验收口径。

### 10.2 阶段划分
- 第 1 阶段：服务层收敛
  - 引入资源策略表
  - 收敛 `skipped` 语义
  - 实现唯一来源硬失败
  - 实现 `daily_prices` 的统一入口与格式门禁
- 第 2 阶段：生产入口收敛
  - 调整调度任务或调度调用顺序
  - 把 `daily_prices` 的正式生产触发语义切换到统一入口
- 第 3 阶段：文档与运行口径复核
  - 更新运维文档
  - 复核生产触发器
  - 确认代码、配置、文档三者一致

### 10.3 文档同步硬约束
- 任何代码的修改/编写，必须同步对应文档。
- 本轮至少需要同步更新以下文档：
  - `docs/operations/production_task_registry.md`
  - `docs/operations/bootstrap_runbook.md`
  - 本设计文档
- 若涉及生产触发器定义变化，还必须同步核对：
  - `config/launchd/`
- 任何阶段如果出现“代码已改但对应文档未同步”，视为该阶段未完成。

## 11. 错误返回契约

### 11.1 新错误码
- 新增统一错误码：
  - `authoritative_source_unavailable`

### 11.2 details 要求
- `details` 至少包含：
  - `resource`
  - `provider`
  - `reason`
  - `requested_by`
- 如可用，还应补充：
  - `api_name`
  - `last_failure_at`
  - `last_error_code`
  - `last_error_message`
  - `fallback_attempted`
  - `fallback_provider`

### 11.3 daily_prices 特例
- 若 Tushare 失败但 Tencent 成功，接口应明确说明：
  - 主源失败
  - 已使用 fallback
  - fallback 是否通过相同质量/格式门禁
- 这不是硬失败，但必须可审计。

## 12. 本轮实施内容

### 12.1 要做
- 新增本设计文档。
- 在服务层新增资源策略表和统一的源判定逻辑。
- 将唯一来源资源的源失败从 `skipped` 收紧为 `ApiError`。
- 为 `daily_prices` 增加统一入口、主源优先和格式一致性门禁。
- 扩展 `tushare_status` 的按资源状态记录。
- 同步更新运行和生产任务文档。

### 12.2 不做
- 不新增新的外部数据提供方。
- 不给其它资源增加 Tencent fallback。
- 不更改 `market-intelligence` 的排序、推荐和主题逻辑。
- 不在本轮接入新的前端错误展示层。

## 13. 验收标准

1. `daily_prices` 的主执行顺序变为 `Tushare -> Tencent fallback`，且 Tencent 不再被表述为主源。
2. 本轮定义的 Tushare 唯一来源资源，在主源失效时全部表现为 `API 硬失败`。
3. `dry_run`、`market_not_closed`、`no_periods_in_range`、`no_valid_ts_codes` 不再伪装成“主源失效”。
4. `daily_prices` 在覆盖率门禁之外，新增格式一致性门禁并参与主源成功判定。
5. `tushare_status` 可按资源记录最近一次成功/失败及关键原因。
6. 任一代码变更对应的运维文档同步更新，不存在代码、配置、文档三方口径漂移。

## 14. 风险与边界

### 14.1 本次接受的剩余风险
- 本轮策略表先落在代码中，后续若资源继续增多，可能需要再配置化。
- `daily_prices` 的格式一致性校验阈值需要基于现有真实数据样本谨慎设定，避免误伤正常数据。

### 14.2 本次不接受的风险
- 不接受把主源失败继续包装成 `skipped`。
- 不接受代码先改、文档后补。
- 不接受生产入口语义已切换，但 `launchd`、运行文档、任务注册表仍保留旧口径。
