# NeoTrade3 生产自动任务注册表

日期：2026-06-16  
口径：以当前仓库代码、`config/launchd/` 模板与已核对的运行行为为准。
其中“生产是否启用”只以生产触发器为准，不以 `task_scheduler.py` 中是否存在 APScheduler 注册为准。

## 1. 目的

这份文档用于统一回答以下问题：

- 当前生产环境到底有哪些自动任务在跑
- 每个任务的真实触发源是什么
- 哪些任务必须依赖交易日，哪些属于维护型任务
- 非交易日时每个任务会怎样处理
- 当前定义是否准确，是否存在需要修正的语义问题

本表不替代代码实现，但作为“生产任务真相总表”使用。  
若本表与代码/模板不一致，应先核对：

1. `config/launchd/`
2. `neotrade3/scheduler/task_scheduler.py`
3. `apps/api/main.py`

## 2. 字段说明

- `是否生产启用`：当前是否存在已启用的生产触发入口，不等于“代码里是否注册过”
- `触发源`：当前实际生产触发器；若仅存在代码内 APScheduler 注册但无生产入口，则不应视为生产启用
- `是否要求交易日`：任务在业务语义上是否只应在正常交易日运行
- `非交易日行为`：当前代码真实行为，不是理想行为
- `当前定义是否准确`：基于当前代码与业务语义的判断

## 3. 生产任务注册表

| 任务名 | 是否生产启用 | 触发源 | 触发时间 | 代码入口 | 主要副作用 | 是否要求交易日 | 非交易日行为 | 当前定义是否准确 | 备注/风险 |
|---|---|---|---|---|---|---|---|---|---|
| `update_daily_prices_authoritative` | 是 | `launchd` | 周一到周五 `15:45` | `neotrade3.scheduler.task_scheduler:_run_update_daily_prices_authoritative` | 触发 `daily_pipeline`；`daily_prices` 按 `Tushare -> Tencent safety-net` 口径执行 | 是 | 通常因无新增交易日差额直接 `up-to-date`；若进入 pipeline，仍会做交易日检查 | 准确 | 当日 `Tushare daily` 为空时，会在 `16:00` 前按 3 分钟窗口短重试 |
| `trade_execution_rt_0935` | 是 | `launchd` | 周一到周五 `09:35` | `neotrade3.scheduler.task_scheduler:_run_trade_execution_rt_0935` | 修改模拟持仓、现金、意图状态，写 `trade_execution_rt` ledger | 是 | 业务层通过 `trading_day_view()` 检查，非交易日直接 `skipped_non_trading_day` | 准确 | 当前生产最关键的早盘执行任务，交易日门禁已实现 |
| `backup_daily` | 是 | `launchd` | 每天 `04:47` | `scripts/backup_neotrade_daily.py`（经 `.venv/bin/python` 启动，该二进制持有可移动磁盘 TCC 授权） | 将 NEO `var/` 增量镜像到 DATA（APFS 备份盘）`NeoTradeDB.daily/var/`（rsync `--delete-after`） | 否 | 照常运行（增量快照不依赖交易日） | 准确 | 2026-07-24 新增（owner 裁决 Q3）；fail-closed 护栏：NEO 核心库缺失/异常小时 EX_CONFIG 拒同步；DATA 未挂载则 skip 当日 |
| `update_financial_data` | 否 | APScheduler 代码定义（未生产启用） | 每天 `18:00` | `neotrade3.scheduler.task_scheduler:_run_update_financial_data` | 更新 `stocks` 财务字段 | 否 | 仍可运行 | 基本准确 | 更像维护型数据任务；当前未见生产 LaunchAgent |
| `fetch_news` | 否 | APScheduler 代码定义（未生产启用） | 工作日 `09:00-14:59` 每 30 分钟 | `neotrade3.scheduler.task_scheduler:_run_fetch_news` | 抓取财联社快讯 | 是 | 任务函数先检查 `trading_day_view()`，非交易日记录 `skip` 后返回 | 准确 | 当前未见生产 LaunchAgent；若未来启用，交易日语义已内置在任务函数 |
| `warm_tushare_theme_cache` | 否 | APScheduler 代码定义（未生产启用） | 每 2 分钟 | `neotrade3.scheduler.task_scheduler:_run_warm_tushare_theme_cache` | 预热概念/主题缓存 | 否 | 持续运行 | 基本准确 | 若定位为缓存维护任务则合理；不应与交易日业务任务混写 |

## 4. 关键判断

### 4.1 当前生产真正启用的自动任务

当前生产实际启用的自动任务有 3 个：

- `update_daily_prices_authoritative`（系统域 LaunchDaemon）
- `trade_execution_rt_0935`（用户域 LaunchAgent）
- `backup_daily`（用户域 LaunchAgent，2026-07-24 新增，数据备份）

它们由 `config/launchd/` 中的模板定义，并通过仓库脚本安装到对应 launchd 域。

补充口径：

- 当前仓库内的生产入口口径已收敛为：
  - 任务 id：`update_daily_prices_authoritative`
  - 主源：`Tushare`
  - fallback：`Tencent` 仅作 safety-net
- 若本机已安装的 LaunchAgent 仍是旧模板，需要重新执行安装/校验脚本，才能让本机实际运行口径与仓库定义一致。

### 4.2 代码中存在但当前未作为生产入口启用的任务

以下任务目前只存在于 `task_scheduler.py` 的 APScheduler 注册里，不能默认视为“生产每天会自动运行”：

- `update_financial_data`
- `fetch_news`
- `warm_tushare_theme_cache`

因此，“代码里注册过”不等于“生产里已经启用”。

### 4.3 交易日语义现状

已正确实现交易日门禁的核心生产任务：

- `trade_execution_rt_0935`
- `update_daily_prices_authoritative`（通过日历差额与 pipeline 检查间接保证）

维护型任务，不强制要求交易日：

- `update_financial_data`
- `warm_tushare_theme_cache`

## 5. 当前已确认的问题

### 5.1 任务定义真相源未完全收敛

当前仍同时存在两套定义：

- `launchd` 生产模板
- APScheduler 代码注册

这会带来以下风险：

- 容易误判“哪些任务真的会每天自动跑”
- 文档维护时容易混淆“代码定义”和“生产定义”
- 调整时间或工作日时，可能只改了一处

### 5.2 缺失日补跑后的意图冲突

该问题已完成第一阶段修复：

- 当前在新意图生成前，已增加“旧意图优先”的冲突检查
- 若存在同 `code`、同方向、且仍为 `pending` 的旧意图，则不再生成新的同类意图
- 生成结果会记录 `pending_conflict_older_intent_wins`

当前残余风险：

- 这次只解决同方向冲突
- 跨方向冲突与“同日已执行后是否允许再次生成同方向意图”仍未纳入本轮规则

### 5.3 `fetch_news` 的交易日门禁

该问题已修复：

- `_run_fetch_news()` 现在会先调用 `trading_day_view()`
- 非交易日直接记录 `info` 跳过日志，不抓取财联社快讯
- 因此该任务现在已符合“交易日盘中任务”的业务语义

## 6. 建议维护原则

### 6.1 生产任务真相源

生产自动任务的第一真相源应是：

1. `config/launchd/`
2. 本文档

代码里的 APScheduler 注册应被视为“可用实现定义”和“开发/手工入口”，而不是默认的生产任务真相源。

### 6.2 任务分类

建议始终将任务分为两类：

- `交易日业务任务`
  - `update_daily_prices_authoritative`
  - `trade_execution_rt_0935`
- `维护型任务`
  - `update_financial_data`
  - `warm_tushare_theme_cache`

`fetch_news` 当前已按交易日业务任务处理。

### 6.3 变更流程

涉及生产任务的任何修改，都应按以下顺序执行：

1. 修改 `config/launchd/` 模板
2. 如涉及业务语义，更新本文档
3. 如涉及代码说明口径，更新 `neotrade3/scheduler/task_scheduler.py`
4. 在项目根目录执行 `PROJECT_PYTHON="$PWD/.venv/bin/python"; "$PROJECT_PYTHON" scripts/install_launchagents.py install --python-bin "$PROJECT_PYTHON"`
5. 在项目根目录执行 `PROJECT_PYTHON="$PWD/.venv/bin/python"; "$PROJECT_PYTHON" scripts/install_launchagents.py check --target-dir "$HOME/Library/LaunchAgents" --launchctl --python-bin "$PROJECT_PYTHON"`

## 7. 后续待处理项

- 持续保持 APScheduler 代码说明与 `launchd` 生产口径分层，避免再次漂移
- 收敛意图冲突规则的剩余边界，例如跨方向冲突
- 如业务要求早盘任务为 `09:30` 而非 `09:35`，需单独发起配置修正
