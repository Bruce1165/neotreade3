# Phase 1 数据抓取健壮性审查报告（数据链 robustness）

> 日期：2026-07-24
> 依据：接管章程 §4.2 Phase 1（owner 第一硬要求："没有及时的数据更新，其它都是瞎扯"）
> 方法：全链路代码审查（file:line 证据）+ 7/21–22 事故日志/台账重建 + 依赖声明全面审计 + .venv 实测
> 状态：**证据收集完成，修复方案待 owner 按 §5 决策门裁决**

## 1. 事故重建（7/21–7/22，来自日志与台账）

| 时间 | 事实 | 证据 |
|---|---|---|
| 7/21 11:29 | 手动晨跑正常（up-to-date） | scheduler err.log |
| 7/21 15:45 | 管线第 1 步 `trading_day_check` 失败，但任务照常 exit 0 | err.log；`task_scheduler.py:190` |
| 7/22 15:45 | **零日志**——任务要么没开火要么解释器起不来，系统对此完全无感 | err.log 无任何 7/22 行 |
| 7/23 15:45 | catch-up 自动补跑 7/21/22/23：历史两天各烧 ~10 分钟重试后失败（tushare 缺失），当日被 Tencent 实时行情救回 | err.log；`daily_runs/2026-07-23.json`（`fallback_used=true, primary_final_reason=tushare_not_installed`） |
| 全程 | **零告警**。唯一告警通道 `NEOTRADE3_ALERT_WEBHOOK_URL` 从未配置，且三处调用点全部丢弃返回值 | `main.py:27914-27916, 28402/28453/28568` |
| 7/24 02:51 | 手动补采成功（4819 行×2），但**按日期覆盖写台账，原始失败证据已被销毁** | `main.py:27890-27891` |

## 2. 静默失败点清单（按 可能性×影响 排序，共 17 项）

| # | 问题 | 位置 |
|---|---|---|
| 1 | **调度器无论管线成败一律返回成功**（exit 0），launchd 永远看到绿灯——7/21–22 不可见的第一原因 | `task_scheduler.py:190` |
| 2 | 唯一告警通道未配置且结果被丢弃；webhook 发送失败也被吞 | `main.py:27914-16, 27935-36` |
| 3 | 任务根本没开火时无任何心跳检测（7/22 零日志无人知） | launchd plist 无 retry/heartbeat |
| 4 | **Tencent 兜底无法补历史日期**（非当日目标转回 tushare）——tushare 多天故障时 catch-up 空转 | `main.py:6505-6551` |
| 5 | catch-up 读库/日历异常时静默降级为"只跑今天" | `task_scheduler.py:111-112, 145-146` |
| 6 | 交易日历过期 → `is_trading_day=None` → 管线照常继续（只拦 False 不拦 None） | `main.py:17242-45, 28409` |
| 7 | 抓取失败时 `_meta.status` 仍报 ok（假绿），下游读 meta 的消费者被误导 | `main.py:28704-28706` |
| 8 | `tushare_concept_health` 假绿：探针走 urllib 适配器而非 tushare 包，7/23 报 ok 时包根本没装 | `main.py:25928-26002` |
| 9 | 无依赖前置检查：缺包要到具体数据源调用时才以"skipped"软状态暴露 | `python_runtime.py:49-51` |
| 10 | 15:45–16:00 重试窗口只覆盖"当日无行"一种原因，其余原因直接进兜底/抛错 | `main.py:12395-12401` |
| 11 | `env.secrets` 缺失时调度器静默 no-op → token 静默缺失 → tushare 永久静默跳过 | `task_scheduler.py:44-45` |
| 12 | 台账按日期覆盖写，销毁取证现场（7/21 原始失败已不可考） | `main.py:27890-27891` |
| 13 | 仓库模板的日志路径（var/log）与已安装 plist（~/Library/Logs）漂移，按文档排查会盯着死文件 | 模板 :70-74 |
| 14 | 覆盖率门容忍静默部分丢失（chunk 失败 continue；0.99 阈值允许 ~1% 缺口算绿）；停牌合成行无标记 | `main.py:6689-90, 6842-54, 623-664` |
| 15 | 全部下游步骤（筛选/模拟盘/回测/优化）失败只记台账不告警 | `main.py:28708-28987` |
| 16 | **隐藏跨依赖**：Tencent 实时路径要求 `stocks.total_market_cap/sector_lv1` 非空，而维护它们的 `update_financial_data` 并未生产启用——元数据腐烂会慢慢勒死兜底路径 | `main.py:6603-6612`；registry §3 |
| 17 | catch-up 无回看上限，每个缺失日最多烧 ~10 分钟重试，多日缺失会挤占当日窗口 | `task_scheduler.py:116-146` |

## 3. 依赖声明审计（第二颗、第三颗定时炸弹）

实测当前 .venv：`joblib / sklearn / apscheduler / mootdx` 全部 **MISSING**；`tushare/numpy/requests/reportlab` 正常。

| 包 | 声明状态 | 生产路径 | 现状 |
|---|---|---|---|
| **joblib** | ❌ 完全未声明（只是 sklearn 的传递依赖，代码却直接 import） | `/api/prediction/signals` 加载模型 `var/models/autore_v2_best.pkl`（4.8MB 在案） | **该端点此刻已坏**（ImportError → HTTP 500），tushare 同类炸弹 |
| **scikit-learn** | ⚠️ 仅在 `ml` extra，不在核心依赖 | 同上（反序列化 RandomForest 需要） | 同上，重建 venv 即复发 |
| **APScheduler** | ⚠️ 仅在 `scheduler` extra | 当前 launchd --run-once 不触发（侥幸） | 潜伏：常驻模式会静默降级为零任务调度器 |
| **mootdx** | ❌ 未声明 | `update_financial_data`（未生产启用，但见失败点 #16） | 一旦接入 launchd 立即重演 tushare 事故 |
| matplotlib | ❌ 未声明 | 仅手动研究脚本，try/except 软降级 | 低危 |

防复发机制：CI 应加一道"仅按 pyproject 建环境 + 生产入口模块 import 冒烟"——把这类炸弹挡在仓库外。

## 4. 深层语义问题（不在本 Phase 修，登记进 Phase 2/4 与混沌专项）

- 交易日历与 daily_prices 循环互证（缺数据的日子会从日历里消失，进一步骗过 catch-up）
- Tencent 兜底的历史日期能力缺失（失败点 #4）与 #16 元数据依赖，涉及数据源策略，需与 R2（Tushare 配额）一并决策
- catch-up 成本无界（#17）需定义回看窗口与单日重试预算

## 5. 修复方案（决策门，请逐项裁决）

### D1 止血包（小改动、纯增益，建议今天实施；预计 1–2 小时 + 测试）

| 项 | 内容 | 位置 |
|---|---|---|
| D1-1 | 调度器诚实退出：任一步骤失败 → exit 1 | `task_scheduler.py:190` |
| D1-2 | 跑完后新鲜度复查：重查 MAX(trade_date) 对不上 → exit 1 | 同函数循环后 |
| D1-3 | 告警函数加日志（未配置/发送失败都留痕）+ 三处调用点把结果写进台账 | `main.py:27906-27936` |
| D1-4 | `_meta.status` 诚实化：抓取步骤失败时 meta 不再报 ok | `main.py:28704-28706` |
| D1-5 | 调度器入口依赖前置检查（import tushare/pandas 失败 → 响亮失败） | `task_scheduler.py:82` 后 |
| D1-6 | `fallback_used=True` 时记 warning 级日志（主源降级当日可见） | `main.py:12478-12497` |
| D1-7 | 健康探针补 `tushare_package_importable` 检查 | `main.py:25994-26001` |

**需要 owner 提供（R7）**：一个可接收告警的 webhook——Bark（iPhone 推送最简）、Server 酱（微信）、企业微信或 Telegram 均可。配上后 `NEOTRADE3_ALERT_WEBHOOK_URL` 写入 env.secrets，三处既有告警点（交易日检查/收盘/权威更新三重试失败）+ D1 新增点即刻生效。**这是"断更 30 分钟内告警到人"的最后一公里。**

### D2 取证与卫生包（建议随 D1 同上）

- D2-1 台账改为 `<date>_<started_at>.json` 不再覆盖（保全失败现场）
- D2-2 仓库 launchd 模板日志路径与线上一致
- D2-3 `skipped_days>0` 时记 warning（全跳过目前静默返回 ok）

### D3 依赖治理包（owner 裁决）

- D3-1 **joblib + scikit-learn 移入核心依赖** → 修复当前已坏的 `/api/prediction/signals`（裁决点 A：修；B：该端点已废弃则下掉模型与路由——需要 owner 确认这个预测信号端点是否还在业务上使用）
- D3-2 mootdx：声明入核心，或删除适配器（取决于 `update_financial_data` 是否计划生产化，与失败点 #16 联动）
- D3-3 apscheduler：声明入核心，或在常驻模式入口加响亮报错（防静默降级）
- D3-4 CI 加依赖冒烟门（防复发，强烈建议无论 A/B 都做）

### D4 本 Phase 不修（已登记）

失败点 #4/#6/#14/#16/#17 涉及数据源策略与语义，进 Phase 2/4 与混沌专项议程。

### 过渡期监控（D1 上线前）

从明天起我每天上午人工核查前日 ledger + 备份日志 + 调度日志，直到 D1 告警链路实测通过。

## 6. 仍待 owner 的资源

- **R2**：Tushare token 权限等级与限流配额（设计重试预算与补采速率的前提）
- **R7**：告警 webhook（见 D1）

---

*本报告证据均带 file:line；17 项失败点与 13 个挂钩点的完整版（含逐点细节）留存在审查工作底稿，需要时可展开任何一项。*
