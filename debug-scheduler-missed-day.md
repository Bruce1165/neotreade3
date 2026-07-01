# Debug Session: scheduler-missed-day
- **Archive Note**: 本文件为历史调试记录，保留当时的问题定位与修复证据。文中出现的旧任务名或旧入口口径不代表当前生产真相源；当前正式日线任务名为 `update_daily_prices_authoritative`。
- **Status**: [OPEN]
- **Issue**: 定时任务未触发导致交易日数据缺失；同时 Tushare 在部分环境下走本机代理端口导致请求超时。
- **Debug Server**: http://127.0.0.1:7777/event
- **Log File**: .dbg/trae-debug-log-scheduler-missed-day.ndjson

## Reproduction Steps
1. 在未加载 `com.neotrade3.scheduler` 的情况下等待到收盘后（15:30），观察 `daily_prices` 的 `MAX(trade_date)` 未推进到最新交易日。
2. 运行需要访问 Tushare 的路径（例如 `pro.daily(trade_date=YYYYMMDD)`），在存在系统代理但未设置 `NO_PROXY` 的场景下可能出现连接 `127.0.0.1:<port>` 超时。

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | macOS 系统代理导致外部请求走本机代理（127.0.0.1:17890），当代理不可用时 Tushare/外部数据源超时 | High | Med | Confirmed（`scutil --proxy` 显示启用本机代理；设置 `NO_PROXY` 后 Tushare 可稳定返回） |
| B | `com.neotrade3.scheduler` 未被 launchctl 加载，导致 15:30 不触发 run-once 任务 | High | Low | Confirmed（`launchctl print gui/501/com.neotrade3.scheduler` 为 `not_loaded`） |
| C | 即便任务触发，更新链路对“交易日缺失”缺少强校验与兜底回补（例如 Tencent 失败后未自动切换权威源） | Med | Med | Partially addressed（已在 scheduler 路径中补齐 `NO_PROXY`；日线可通过 Tushare 回补） |
| D | 调度输出日志未写入/不可见（输出路径、权限、日志级别、stderr/stdout 混用）导致问题被掩盖 | Med | Low | Rejected（日志文件存在且记录了 pipeline steps） |
| E | 环境变量/代理设置在不同入口（IDE/launchctl/shell）不一致，导致“手工可用、定时不可用” | Med | Med | Confirmed（系统代理启用且 launchctl 未加载；不同入口行为不一致） |

## Log Evidence
- System Proxy（macOS）：
  - `scutil --proxy` 显示 `HTTP(S)Proxy=127.0.0.1:17890` 且启用（HTTPEnable/HTTPSEnable=1）
- LaunchAgent 加载状态：
  - `launchctl print gui/501/com.neotrade3.scheduler` 返回 `not_loaded`
  - 在当前受限运行环境中尝试 `launchctl bootstrap/load` 均返回 `Load/Bootstrap failed: 5: Input/output error`（需要在本机真实终端执行）
- LaunchAgent 已加载后的状态（用户终端输出节选）：
  - `state = not running`
  - `runs = 0`
  - `program = <configured-python>`，参数为 `-m neotrade3.scheduler.task_scheduler --run-once update_daily_prices_tencent`
  - `stderr path = /Users/mac/NeoTrade3/var/log/neotrade3_scheduler.err.log`
  - 环境变量包含 `NEOTRADE3_ENV_FILE=/Users/mac/Library/Application Support/NeoTrade3/env.secrets`
- 数据缺口（已补齐后验证）：
  - `daily_prices MAX(trade_date)` 已推进到 `2026-06-08`，且 `2026-06-08` 行数为 `4819`
- Scheduler 近期手工执行日志（用户终端）：
  - `2026-06-09 13:52:03,351 INFO update_daily_prices_tencent: up-to-date (latest=2026-06-08 cutoff=2026-06-08)`
- Debug Server 采集（节选）：
  - `scheduler run_once start`（B）
  - `tushare.daily request`（A），且在 `NO_PROXY` 被补齐后可稳定返回

## Verification Conclusion
- Tushare 连接与回补：
  - 在显式清空 `NO_PROXY/no_proxy` 后，调用日线回补接口仍可成功，并自动补齐 `NO_PROXY=127.0.0.1,localhost,api.waditu.com,api.tushare.pro`
  - `tushare_concept_health_view` 在清空 `NO_PROXY/no_proxy` 后仍可成功，并自动补齐 `NO_PROXY`
- 昨日缺口：
  - `daily_prices` 已补齐到 `2026-06-08`（4819 行），不再缺失
- 定时任务：
  - 根因是 LaunchAgent 未加载；当前受限运行环境无法完成 `launchctl load/bootstrap`，需要在本机真实终端执行加载/启用
  - 用户侧已验证：`launchctl print gui/501/com.neotrade3.scheduler` 显示 `state=running`、`runs=3`、`last exit code=0`（已被 launchd 成功触发）
  - 最终验收：需等待今日 15:30 的 calendarinterval 触发后再次核验 `runs` 递增、`last exit code=0`、以及当日 `daily_prices` 是否推进到最新交易日

## Verification Script (15:31~15:35)
```bash
launchctl print gui/$(id -u)/com.neotrade3.scheduler | egrep "state =|runs =|last exit code|pid ="

tail -n 60 /Users/mac/NeoTrade3/var/log/neotrade3_scheduler.err.log

python3 - <<'PY'
import sqlite3
from pathlib import Path
db=Path('/Users/mac/NeoTrade3/var/db/stock_data.db')
conn=sqlite3.connect(str(db)); cur=conn.cursor()
print('daily_prices MAX(trade_date)=', cur.execute('SELECT MAX(trade_date) FROM daily_prices').fetchone()[0])
conn.close()
PY
```
