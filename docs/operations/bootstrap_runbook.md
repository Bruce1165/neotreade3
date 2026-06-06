# NeoTrade3 Bootstrap Runbook

## 1. 文档目的

这份文档只描述 `NeoTrade3` 当前 bootstrap 阶段已经存在的本地运行入口与联调顺序。

它不声明以下能力已经实现:

- 真实生产任务执行
- 正式数据写入切换
- 真实数据库持久化
- 完整前端工程化 dashboard

## 2. 当前可用入口

当前仓库已经具备 3 个本地入口:

1. `apps/worker/main.py`
2. `apps/api/main.py`
3. `apps/dashboard/main.py`

它们的职责边界:

- `worker`
  - 统一构建 bootstrap 快照
  - 可把快照写入 `var/ledgers/` 与 `var/artifacts/`
- `api`
  - 只读暴露 healthz、summary、snapshot
  - 当前直接复用 worker 的快照构建能力
- `dashboard`
  - 只读页面壳
  - 当前通过浏览器请求 `api` 获取 bootstrap 数据
- 静态资源当前已拆分到:
  - `apps/dashboard/static/dashboard.css`
  - `apps/dashboard/static/dashboard.js`

## 3. 运行前提

- 当前项目根目录:
  - `/Users/mac/NeoTrade3`
- 当前本地命令使用:
  - `python3`
- 当前测试环境实际验证过的 Python 版本:
  - `3.9.6`

说明:

- `pyproject.toml` 仍声明 `>=3.11`
- 但当前 bootstrap 代码已经按本地 `3.9.6` 环境完成兼容性验证

## 4. 推荐联调顺序

推荐顺序固定为:

1. 先跑 `worker`
2. 再启动 `api`
3. 最后启动 `dashboard`

原因:

- `worker` 是当前统一快照入口
- `api` 是当前统一只读暴露入口
- `dashboard` 依赖 `api` 才能展示内容

## 5. Worker 用法

### 5.1 dry-run

只构建快照，不落盘:

```bash
python3 -m apps.worker.main --date 2026-05-19 --dry-run
```

### 5.2 写入本地快照

构建并写入本地文件:

```bash
python3 -m apps.worker.main --date 2026-05-19
```

如果要把 publish-gated 任务从 `blocked` 切换为非阻塞计划态，可加:

```bash
python3 -m apps.worker.main --date 2026-05-19 --publish-succeeded
```

### 5.3 Worker 当前落盘位置

当不使用 `--dry-run` 时，当前会写入:

- `var/ledgers/bootstrap_runs/<date>/data_control_plan_ledger.json`
- `var/ledgers/bootstrap_runs/<date>/orchestration_run_snapshot.json`
- `var/artifacts/bootstrap_runs/<date>/issue_center_snapshot.json`
- `var/artifacts/bootstrap_runs/<date>/learning_snapshot.json`
- `var/artifacts/bootstrap_runs/<date>/bootstrap_run_summary.json`

## 6. API 用法

### 6.1 启动命令

```bash
python3 -m apps.api.main --host 127.0.0.1 --port 18030
```

### 6.2 当前端点

- 健康检查:

```text
GET /healthz
```

- bootstrap summary:

```text
GET /api/bootstrap-summary?date=2026-05-19&publish_succeeded=false
```

- bootstrap snapshot:

```text
GET /api/bootstrap-snapshot?date=2026-05-19&publish_succeeded=false&write_outputs=false
```

说明:

- `write_outputs=false` 时只返回结果，不写 `var/`
- `write_outputs=true` 时会触发与 worker 一致的本地落盘
- `source=live` 是默认行为，表示请求时即时构建
- `source=stored` 表示直接读取 `worker` 已落盘的快照文件
- API 当前带最小内存缓存:
  - `live/stored` snapshot 默认短 TTL
  - `labs/source registry` 默认较长 TTL
- API 当前允许 dashboard 所在本地端口跨域只读访问

示例:

```text
GET /api/bootstrap-summary?date=2026-05-19&source=stored
GET /api/issue-center?date=2026-05-19&source=stored
```

### 6.3 细粒度只读域接口

当前还提供以下只读域接口:

- `GET /api/data-control?date=2026-05-19`
- `GET /api/orchestration?date=2026-05-19`
- `GET /api/labs`
- `GET /api/config-contracts`
- `GET /api/migration/feature-manual`
- `GET /api/issue-center?date=2026-05-19`
- `GET /api/learning?date=2026-05-19`

用途:

- 让 dashboard 或后续调用方按域消费
- 避免每次都读取整包 `bootstrap snapshot`
- 对已落盘日期可结合 `source=stored` 直接读取文件快照
- `config-contracts` 可用于快速检查当前 `labs/orchestrator/source_registry` 的契约状态
- `migration/feature-manual` 可用于读取当前基于 NeoTrade2 代码抽取的功能说明书台账

### 6.4 当前错误返回结构

当前错误返回统一为:

```json
{
  "error": {
    "code": "bad_request",
    "details": {},
    "message": "..."
  }
}
```

当前已明确覆盖:

- `bad_request`
- `invalid_source_mode`
- `not_found`
- `snapshot_not_found`

当前响应头行为:

- JSON 响应附带最小 CORS 头，允许 dashboard 从独立本地端口读取:
  - `Access-Control-Allow-Origin: *`
  - `Access-Control-Allow-Methods: GET, OPTIONS`

## 7. Dashboard 用法

### 7.1 启动命令

默认依赖本地 API:

```bash
python3 -m apps.dashboard.main --host 127.0.0.1 --port 18031 --api-base-url http://127.0.0.1:18030
```

### 7.2 当前页面

打开:

```text
http://127.0.0.1:18031/
```

当前页面包含:

- `Overview`
- `Data Control`
- `Labs`
- `Daily Orchestration`
- `Issue Center`
- `Learning`

当前页面读取方式:

- `Overview` 读取 `bootstrap-summary`
- `Data Control` 读取 `data-control`
- `Labs` 读取 `labs`
- `Daily Orchestration` 读取 `orchestration`
- `Issue Center` 读取 `issue-center`
- `Learning` 读取 `learning`

当前页面支持通过 URL 查询参数切换读取模式:

- `http://127.0.0.1:18031/?source=live`
- `http://127.0.0.1:18031/?source=stored`

说明:

- `source=live` 透传到 API，按请求即时构建
- `source=stored` 透传到 API，读取 `worker` 已落盘快照
- 首页顶部会展示摘要卡片:
  - `target_date`
  - `snapshot_source`
  - `cache_status`
  - `planned_task_count`
  - `issue_case_count`
  - `learning_candidate_count`
- 各域区块会展示一行摘要与 `_meta` 元信息，同时保留可展开的原始 JSON payload
- `data-control` 的 `_meta` 现在会额外返回 `source_registry_cache_status`
- 当 API 返回结构化错误时，页面会把 `error.code` 与 `error.message` 显示在顶部错误条中

### 7.3 当前限制

- 不是正式 dashboard 工程
- 没有前端构建链
- 没有登录鉴权
- 没有写操作
- 当前展示的是 bootstrap 快照

## 8. 推荐本地联调流程

### 8.1 第一步: 生成一轮本地快照

```bash
python3 -m apps.worker.main --date 2026-05-19
```

### 8.2 第二步: 启动 API

```bash
python3 -m apps.api.main --host 127.0.0.1 --port 18030
```

### 8.3 第三步: 启动 Dashboard

```bash
python3 -m apps.dashboard.main --host 127.0.0.1 --port 18031 --api-base-url http://127.0.0.1:18030
```

### 8.4 第四步: 人工检查

至少检查:

- `http://127.0.0.1:18030/healthz`
- `http://127.0.0.1:18030/api/bootstrap-summary`
- `http://127.0.0.1:18031/`

## 9. 自动化回归基线

当前仓库已具备一组最小 HTTP 级回归，入口仍然统一在:

```bash
python3 -m pytest tests/unit/test_bootstrap_skeleton.py
```

这组回归当前不只覆盖骨架对象装配，也覆盖:

- API server 的 `live/stored` summary 路径
- API server 的无效日期错误路径
- API server 的 `config-contracts` 与现有域接口可访问性
- API server 的 `migration/feature-manual` 功能台账可访问性
- dashboard server 首页与静态资源可访问性

用途:

- 在修改 `worker -> api -> dashboard` 主链后，快速确认 HTTP 级联调没有回归
- 避免只靠对象级单元测试而漏掉 handler / server 生命周期问题

## 10. 当前不应误解的点

当前 runbook 只说明:

- 代码骨架已经可以统一启动
- 主链已经可以形成本地只读快照
- API 与 dashboard 已经有最小联调路径

当前不应表述为:

- 3.0 已具备完整业务运行能力
- 3.0 已接管 NeoTrade2 正式职责
- learning loop 已具备自动改参与自动上线能力

## 11. 自动任务（LaunchAgents + Scheduler + Daily Pipeline）

### 11.1 LaunchAgents 与环境变量

本机通过 launchd 管理 2 个长期进程:

- `com.neotrade3.api`：API 服务（默认监听 `127.0.0.1:18030`）
- `com.neotrade3.scheduler`：APScheduler 定时任务

两者都依赖 secrets 注入:

- 默认读取 `~/Library/Application Support/NeoTrade3/env.secrets`
- 或通过环境变量 `NEOTRADE3_ENV_FILE` 指定文件路径

常用变量:

- `TUSHARE_TOKEN`：用于 Tushare 数据补齐（历史日线 backfill、同花顺概念缓存预热）
- `NEOTRADE3_STOCK_DB_V2_PATH`：可选，用于从 NeoTrade2 行情库补齐缺口

### 11.2 Scheduler 定时任务清单（APScheduler）

入口: `neotrade3/scheduler/task_scheduler.py`

- `update_daily_prices_tencent`（工作日 18:05）
  - 目标: 把“当日收盘后的日线”写入 `var/db/stock_data.db`
  - 机制: CN 时区判断收盘（默认 15:10 后），并具备 catch-up 能力（漏跑会从 DB 最新交易日追到 cutoff）
- `update_financial_data`（每天 18:00）
- `fetch_news`（工作日 9:00–14:59，每 30 分钟）
- `warm_tushare_theme_cache`（每 2 分钟）
  - 目标: 预热同花顺概念列表与成分缓存，避免刷新时触发频控

### 11.3 日线写库与质量闸门（腾讯 → 回填 → 落库）

入口: `apps/api/main.py:update_daily_prices_tencent_view`

流程要点:

- 数据来源（腾讯）是实时行情快照，不等价于“收盘价”，因此引入质量闸门:
  - 覆盖率门槛（close/amount/turnover 等）
  - 交易日当天未到收盘窗口会阻止 publish（`market_not_closed`）
- 当腾讯返回的 `trade_date != target_date`（常见于漏跑或时区/时点不一致）时:
  - 优先用 `Tushare pro.daily(trade_date=YYYYMMDD)` 回填 `target_date`
  - 若回填后仍存在“较上一交易日缺口的 code”，且这些 code 在当日为停牌（`suspend_d`），则合成一条零成交 bar（OHLC=前收，volume/amount=0）以保持矩阵完整
  - 若配置了 `NEOTRADE3_STOCK_DB_V2_PATH` 且目标日仍缺失，则从 NeoTrade2 行情库同步补齐
- publish/backfill 成功后会重建 `trading_calendar_cache`

### 11.4 Daily Pipeline（自动化任务的前置条件）

入口: `apps/api/main.py:daily_pipeline_run_view`

前置条件:

- 必须先满足 `target_date` 的行情数据已经成功落库（并通过质量闸门）

若满足前置条件，会串联执行（示例，按 ledger 记录为准）:

- `team_theme_snapshot`（主题快照）
- `ths_concept_mainline`（同花顺概念主线落库）
- `screeners_bulk_run`
- `lowfreq_sim_daily`
- `confidence_daily`
- `lowfreq_backtest_roll60`
- `auto_optimize`

所有 step 的执行结果都会写入:

- `var/ledgers/daily_runs/<target_date>.json`
