# NeoTrade3 launchd 调度模板收敛与安装同步（设计定稿）

> 归档说明：本文记录的是当时 LaunchAgent 模板收敛与安装同步的设计事实。文中出现的 `update_daily_prices_tencent` 等旧正式入口名，仅代表设计发生时的生产状态；当前正式日线任务名已收敛为 `update_daily_prices_authoritative`。

日期：2026-06-16  
范围：NeoTrade3 运维调度层（`launchd` / LaunchAgents）

## 1. 背景与目标

### 1.1 背景问题
- 当前生产实际依赖 `launchd` 的 `LaunchAgent` 触发每日任务，而不是仅依赖代码中的 APScheduler 注册。
- `com.neotrade3.scheduler` 与 `com.neotrade3.trade_execution_rt` 的实际 `plist` 文件位于 `~/Library/LaunchAgents`，其 `StartCalendarInterval.Weekday` 配置写成了 `2..6`。
- macOS `launchd` 的 `Weekday` 语义是：`0` 和 `7` 为周日，`1` 为周一，`2` 为周二，依此类推。
- 因此当前实际效果是“周二到周六触发”，而不是预期的“周一到周五触发”，这直接导致 2026-06-15（周一）未触发每日下载与后续流水线，同时会在周六误触发。
- 当前还存在配置真相分裂：
  - 代码中的 APScheduler 定义了一套工作日语义。
  - 用户目录中的 `plist` 另有一套周几与时间配置。
  - 文档描述为“launchd 管理 APScheduler 长期进程”，但实际 `plist` 使用的是 `--run-once` 的一次性触发模式。

### 1.2 目标
- 修复 `launchd` 工作日配置错误，使两个任务均按“周一到周五”触发。
- 将 `LaunchAgent` 配置收敛为“仓库模板为唯一真相来源”。
- 提供标准安装脚本，将仓库模板同步到 `~/Library/LaunchAgents` 并执行重载。
- 建立最小防漂移机制，避免未来再次出现“仓库预期”和“本机实际配置”不一致。
- 本次不改动业务执行逻辑，只修复调度根因和配置管理方式。

## 2. 现状与事实依据

### 2.1 实际生产触发方式
- `com.neotrade3.scheduler` 当前实际执行命令为：
  - `/usr/bin/python3 -m neotrade3.scheduler.task_scheduler --run-once update_daily_prices_tencent`
- `com.neotrade3.trade_execution_rt` 当前实际执行命令为：
  - `/usr/bin/python3 -m neotrade3.scheduler.task_scheduler --run-once trade_execution_rt_0935`
- 这说明当前生产触发模式是“`launchd` 定时触发一次性任务”，不是“常驻 `--run-forever` 进程 + 内部 APScheduler 自行调度”。

### 2.2 每日主链路
- `update_daily_prices_tencent` 会调用 `daily_pipeline_run_view(...)`。
- `daily_pipeline_run_view(...)` 负责串行推进后续自动任务，包括：
  - `trading_day_check`
  - `yesterday_closeout`
  - `tencent_update`
  - `tushare_health`
  - `team_theme_snapshot`
  - `ths_concept_mainline`
  - `screeners_bulk_run`
  - `lowfreq_sim_daily`
  - `confidence_daily`
  - `lowfreq_backtest_roll60`
  - `auto_optimize`
- 因而每日下载入口若未触发，则后续任务也会一并缺失。

### 2.3 本次已确认的直接证据
- `launchd` 手册确认：`Weekday=1` 为周一，`0/7` 为周日。
- 当前 `plist` 实际写的是 `Weekday=2..6`，即周二到周六。
- `neotrade3_scheduler.err.log` 存在 2026-06-13（周六）执行记录。
- `2026-06-15` 没有对应 `daily_runs` / `trade_execution_rt` / `auto_optimization` 台账，和“周一未触发”相吻合。

## 3. 设计范围与非目标

### 3.1 本次范围
- 为两个 `LaunchAgent` 建立仓库内模板。
- 修正两个任务的工作日配置为周一到周五。
- 提供仓库内安装脚本，统一完成模板渲染、安装、重载、校验。
- 补充运维文档，说明唯一真相来源与 `launchd Weekday` 语义。

### 3.2 非目标
- 不修改 `daily_pipeline_run_view()` 的业务步骤。
- 不修改 `update_daily_prices_tencent` 或 `trade_execution_rt_0935` 的业务实现。
- 不将当前 `launchd run-once` 模式改造为常驻 `--run-forever` 模式。
- 不调整现有日志落盘路径、ledger 路径或数据库结构。
- 不在本次顺手调整触发时点，除非与修复所需配置生成机制直接相关。

## 4. 总体方案

### 4.1 单一真相来源
- 在仓库中新增 `launchd` 模板目录，作为 `LaunchAgent` 配置的唯一可编辑来源。
- 用户目录中的 `~/Library/LaunchAgents/com.neotrade3.scheduler.plist` 与 `~/Library/LaunchAgents/com.neotrade3.trade_execution_rt.plist` 不再手工维护。
- 后续如需修改任务时间、工作日、日志路径、环境变量或参数，只允许修改仓库模板，再执行仓库安装脚本。

### 4.2 模板覆盖范围
- 模板至少包含以下两个任务：
  - `com.neotrade3.scheduler`
  - `com.neotrade3.trade_execution_rt`
- 模板保留当前已验证可用的关键字段：
  - `Label`
  - `WorkingDirectory`
  - `ProgramArguments`
  - `RunAtLoad`
  - `StartCalendarInterval`
  - `ProcessType`
  - `StandardOutPath`
  - `StandardErrorPath`
  - `EnvironmentVariables`

### 4.3 工作日修正
- 两个模板中的 `StartCalendarInterval` 均使用 `Weekday=1,2,3,4,5`。
- 这代表周一到周五。
- 不再使用 `2..6`，以避免“漏周一、跑周六”的现象。

### 4.4 时间策略
- 本次保持当前生产 `plist` 中已使用的触发时点不变，仅修正错误的工作日集合。
- `com.neotrade3.scheduler` 维持当前 `15:30`。
- `com.neotrade3.trade_execution_rt` 维持当前 `09:35`。
- 原因：本次目标是止血并消除配置漂移，不额外引入时间口径变更风险。
- 文档中会明确记录：代码/文档中曾出现与 `plist` 不一致的时间描述，后续若要统一时间口径，应作为单独变更处理。

## 5. 目录与文件设计

### 5.1 仓库模板目录
- 新增仓库目录用于存放 `launchd` 模板。
- 目录只承载模板，不放运行日志和运行结果。
- 模板文件命名直接对应最终 `Label`，便于肉眼核对和脚本安装。

### 5.2 安装脚本
- 新增一个仓库脚本，负责：
  - 读取仓库模板
  - 渲染出最终 `plist`
  - 同步到 `~/Library/LaunchAgents`
  - 对对应服务执行 `launchctl bootout/bootstrap`
  - 打印关键校验信息
- 脚本只管理本次范围内的两个 `Label`，不做通用化运维平台抽象。

### 5.3 文档
- 在运维文档中新增或补充以下内容：
  - `launchd Weekday` 的真实语义
  - 仓库模板是唯一真相来源
  - 禁止手工直接编辑 `~/Library/LaunchAgents/*.plist`
  - 修改流程：改模板 -> 跑安装脚本 -> 验收

## 6. 安装脚本行为设计

### 6.1 输入
- 当前用户环境。
- 仓库内两个模板文件。

### 6.2 处理步骤
1. 确认目标目录 `~/Library/LaunchAgents` 存在，不存在则创建。
2. 将模板渲染为最终 `plist` 内容。
3. 写入到目标路径：
   - `~/Library/LaunchAgents/com.neotrade3.scheduler.plist`
   - `~/Library/LaunchAgents/com.neotrade3.trade_execution_rt.plist`
4. 使用当前用户 `uid` 作为 `launchctl` 目标域。
5. 对每个已存在的服务尝试 `bootout`。
6. 再执行 `bootstrap` 重新加载。
7. 输出每个服务的 `launchctl print` 关键信息。

### 6.3 幂等要求
- 多次执行安装脚本应得到相同结果。
- 若目标 `plist` 内容未变化，重复运行不应产生额外副作用，除重载本身外不引入新状态。
- 如果服务尚未加载，首次运行应能完成安装并成功进入受管状态。

### 6.4 失败处理
- 任一 `plist` 写入失败时，脚本立即停止并返回非零退出码。
- 任一 `bootstrap` 失败时，脚本返回非零退出码，并打印对应 `Label` 与原始错误信息。
- 脚本不负责吞掉错误或自动降级到手工模式。

## 7. 模板渲染与校验要求

### 7.1 最小模板化原则
- 本次只模板化确有环境差异的字段，避免引入无必要变量。
- 可以直接固化的路径保持显式写死，优先保证可读性与可审查性。
- 若路径依赖当前用户主目录，可由安装脚本在渲染时替换为当前用户绝对路径。

### 7.2 逻辑校验
- 安装脚本在写入前校验以下条件：
  - `com.neotrade3.scheduler` 的 `Weekday` 集合必须等于 `1..5`
  - `com.neotrade3.trade_execution_rt` 的 `Weekday` 集合必须等于 `1..5`
  - `ProgramArguments` 中的 job id 必须分别对应：
    - `update_daily_prices_tencent`
    - `trade_execution_rt_0935`
- 任一条件不满足即拒绝安装。

### 7.3 安装后校验
- 安装完成后，脚本读取 `launchctl print gui/<uid>/<label>` 输出，至少核验：
  - `path`
  - `program`
  - `arguments`
  - `stdout path`
  - `stderr path`
  - `event triggers` 中的 `Weekday/Hour/Minute`
- 若 `event triggers` 与模板不一致，脚本返回非零退出码。

## 8. 防漂移机制

### 8.1 运维规则
- 仓库模板是唯一可编辑配置。
- `~/Library/LaunchAgents` 中的实际 `plist` 视为部署产物，不允许手工直接修改。
- 所有变更必须经过：
  - 修改仓库模板
  - 执行仓库安装脚本
  - 验收 `launchctl print`

### 8.2 验收口径
- 调度验收不以“看起来应该会跑”为准，而以以下证据为准：
  - `launchctl print` 中 `event triggers` 的 `Weekday=1..5`
  - 周一有执行证据
  - 周六无新增执行证据
  - ledger 与日志继续正常落盘到现有路径

### 8.3 文档一致性
- 运维文档需明确说明当前生产模式是：
  - `launchd` 定时触发 `--run-once`
- 若文档仍需要保留 APScheduler 相关说明，必须标注“代码内定义”与“当前生产实际入口”的区别，避免再次误导。

## 9. 实施后的预期行为

### 9.1 `com.neotrade3.scheduler`
- 周一到周五 15:30 触发。
- 周六、周日不触发。
- 触发后继续调用 `update_daily_prices_tencent -> daily_pipeline_run_view`。

### 9.2 `com.neotrade3.trade_execution_rt`
- 周一到周五 09:35 触发。
- 周六、周日不触发。
- 触发后继续调用 `trade_execution_rt_0935`。

### 9.3 业务侧行为
- 周一恢复生成 `daily_runs/<date>.json` 等自动化产物。
- 后续自动任务随 `daily_pipeline` 恢复，而不需要为每个下游任务单独新增定时入口。

## 10. 验收标准

1. 仓库内存在两个 `LaunchAgent` 模板与一个安装脚本。
2. 安装脚本可将模板成功同步到 `~/Library/LaunchAgents`。
3. 安装后 `launchctl print` 显示两个任务的 `event triggers` 均为周一到周五。
4. 已安装的两个 `plist` 不再出现 `Weekday=6` 的周六触发配置。
5. 周一应可看到对应日志或 ledger 新增，周六不应再产生新增执行记录。
6. 不改动现有日志路径、台账路径和业务调用链路。

## 11. 风险与后续事项

### 11.1 本次已接受的风险
- 当前保留 `launchd run-once` 模式，与代码中的 APScheduler 定义仍存在并行概念。
- 这不会阻碍本次修复，但说明“调度统一到单一执行模型”仍是后续可独立讨论的议题。

### 11.2 本次不处理的后续事项
- 是否将 `15:30` 恢复或调整到文档曾写过的 `18:05`。
- 是否改回常驻 scheduler 模式。
- 是否为更多任务建立统一模板化管理。
- 是否增加自动化测试覆盖 `plist` 渲染与 `Weekday` 语义。
