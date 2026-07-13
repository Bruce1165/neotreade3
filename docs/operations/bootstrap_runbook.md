# NeoTrade3 Bootstrap Runbook

## 1. 文档目的

这份文档只描述 `NeoTrade3` 当前 bootstrap 阶段已经存在的本地运行入口与联调顺序。

它不声明以下能力已经实现:

- 真实生产任务执行
- 正式数据写入切换
- 真实数据库持久化
- 完整前端工程化 dashboard

## 2. 当前可用入口

当前仓库当前以 3 个主要本地入口为准:

1. `apps/worker/main.py`
2. `apps/api/main.py`
3. `neotrade3-dashboard/`

旧入口:

- `apps/dashboard/main.py`
  - 已退役
  - 当前返回 `410 Gone`
  - 仅保留为历史兼容壳，不应视为现用 dashboard

它们的职责边界:

- `worker`
  - 统一构建 bootstrap 快照
  - 当前是 bootstrap/orchestration 主链的唯一执行真相源
  - 可把快照写入 `var/ledgers/` 与 `var/artifacts/`
- `api`
  - 暴露 bootstrap / 研究 / orchestration 相关 API
  - 直接复用 worker 的快照构建能力
  - 会把 worker 结果投影为兼容的 `orchestration_runs` / `lab_runs` 产物
- `neotrade3-dashboard`
  - 当前在用前端
  - 通过 Vite dev server 代理 `/api` 到本地 API

## 3. 运行前提

- 当前项目根目录:
  - `/Users/mac/NeoTrade3`
- 当前本地命令使用:
  - `./.venv/bin/python`
- 当前测试环境实际验证过的 Python 版本:
  - `3.10`

说明:

- `pyproject.toml` 当前声明 `>=3.10,<3.11`
- 当前正式支持版本固定为 Python `3.10.x`
- 正式本地运行解释器统一为 `./.venv/bin/python`
- CI 与本地工具口径均按 Python `3.10` 维护

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
./.venv/bin/python -m apps.worker.main --date 2026-05-19 --dry-run
```

### 5.2 写入本地快照

构建并写入本地文件:

```bash
./.venv/bin/python -m apps.worker.main --date 2026-05-19
```

如果要在构建计划时把 publish-gated 任务从 `blocked` 切换为非阻塞计划态，可加:

```bash
./.venv/bin/python -m apps.worker.main --date 2026-05-19 --publish-succeeded
```

说明:

- `--publish-succeeded` 只影响计划阶段的初始 gate 状态。
- snapshot 根字段里的 `publish_succeeded` 现在表示本次运行的实际 publish 结果。
- snapshot 根字段里的 `requested_publish_succeeded` 记录是否传入了该 planning hint。

### 5.3 Worker 当前落盘位置

当不使用 `--dry-run` 时，当前会写入:

- `var/ledgers/bootstrap_runs/<date>/data_control_plan_ledger.json`
- `var/ledgers/bootstrap_runs/<date>/orchestration_run_snapshot.json`
- `var/artifacts/bootstrap_runs/<date>/issue_center_snapshot.json`
- `var/artifacts/bootstrap_runs/<date>/learning_snapshot.json`
- `var/artifacts/bootstrap_runs/<date>/bootstrap_run_summary.json`

其中:

- `bootstrap_runs` 是主事实源
- `bootstrap_run_summary.json` 现在包含:
  - `target_date`
  - `publish_succeeded`
  - `requested_publish_succeeded`
  - `summary`
  - `orchestration.task_results` 摘要片段

### 5.4 Governance reject 按需执行

当前 `worker` 还支持一个显式的治理拒绝执行入口:

```bash
./.venv/bin/python -m apps.worker.main \
  --mode governance_reject \
  --date 2026-05-20 \
  --source-run-id benchmark-run-1 \
  --validation-id validation-final-reject
```

说明:

- 该入口是 `M5 governance` 的按需路径，不属于日常 `daily` 自动编排。
- `--source-run-id` 与 `--validation-id` 都是必填；当前不会自动推导 `validation_id`。
- 如只想验证参数与计划链路、而不写入 reject 结果，可加 `--dry-run`。
- 该路径的正式 reject 产物使用独立命名空间，不覆盖 bootstrap 主链:
  - `var/artifacts/governance_rejections/<validation_id>/governance_reject_execution.json`
  - `var/ledgers/governance_rejections/<validation_id>/governance_reject_execution_run.json`

### 5.5 Governance status transition 按需执行

当前 `worker` 还支持一个显式的治理状态转移入口:

```bash
./.venv/bin/python -m apps.worker.main \
  --mode governance_status_transition \
  --date 2026-05-20 \
  --source-run-id benchmark-run-1 \
  --validation-id validation-final-reject
```

说明:

- 该入口是 `M5 governance` 的按需路径，不属于日常 `daily` 自动编排。
- `--source-run-id` 与 `--validation-id` 都是必填；当前不会自动推导 `validation_id`。
- 如只想验证参数与计划链路、而不写入 transition 结果，可加 `--dry-run`。
- 该路径的正式 transition 产物使用独立命名空间，不覆盖 bootstrap 主链:
  - `var/artifacts/governance_status_transitions/<validation_id>/governance_status_transition.json`
  - `var/ledgers/governance_status_transitions/<validation_id>/governance_status_transition_run.json`

### 5.6 Governance candidate validation outcome 按需执行

当前 `worker` 还支持一个显式的 candidate validation outcome 物化入口:

```bash
./.venv/bin/python -m apps.worker.main \
  --mode governance_candidate_validation_outcome \
  --date 2026-05-20 \
  --source-run-id benchmark-run-1 \
  --validation-result '{"validation_id":"validation-final-reject","source_run_id":"benchmark-run-1","baseline_run_id":"benchmark-baseline-run","candidate_run_id":"candidate-run-1","outcome":"rejected","status":"completed","summary":{"decision":"reject","reason":"manual audit"},"validation_result_count":1,"decision_record_count":1}'
```

说明:

- 该入口是 `M5 governance` 的按需路径，不属于日常 `daily` 自动编排。
- `--source-run-id` 与 `--validation-result` 都是必填。
- `--validation-result` 必须是一个显式 JSON payload，且必须匹配 `ValidationResult` contract；当前不会从 `validation_id` 自动推导完整结果。
- 如只想验证参数与计划链路、而不写入 outcome 结果，可加 `--dry-run`。
- 该路径的正式 outcome 产物使用独立命名空间，不覆盖 bootstrap 主链:
  - `var/artifacts/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome.json`
  - `var/ledgers/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome_run.json`

当前 `governance CLI` 也提供对称入口:

```bash
./.venv/bin/python -m neotrade3.governance.cli \
  candidate-validation-outcome \
  --source-run-id benchmark-run-1 \
  --validation-result '{"validation_id":"validation-final-reject","source_run_id":"benchmark-run-1","baseline_run_id":"benchmark-baseline-run","candidate_run_id":"candidate-run-1","outcome":"rejected","status":"completed","summary":{"decision":"reject","reason":"manual audit"},"validation_result_count":1,"decision_record_count":1}'
```

说明:

- `governance CLI` 与 `worker` 使用同一组显式输入 contract：
  - `source_run_id`
  - `validation_result`
- 该入口的作用是物化独立的 candidate validation outcome truth，不会替代或覆盖已有 handoff / reject / status transition 产物。

## 6. API 用法

### 6.1 启动命令

```bash
./.venv/bin/python -m apps.api.main --host 127.0.0.1 --port 18030
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

当前还提供一个写入型按需编排入口:

```text
POST /api/orchestration/run
```

说明:

- 默认 `mode="daily"`，走现有 bootstrap/orchestration 主链。
- 当 `mode="governance_reject"` 或 `mode="governance_status_transition"` 时，必须同时提供非空的 `source_run_id` 与 `validation_id`。
- 当 `mode="governance_candidate_validation_outcome"` 时，必须同时提供非空的 `source_run_id` 与 object 形态的 `validation_result`。
- `requested_by` 建议显式填写，便于后续审计；`dry_run` 可选，默认 `false`。
- 当 `dry_run=false` 时，该入口会额外物化一份 API 编排 envelope:
  - `var/ledgers/orchestration_runs/<date>/orchestrator_run.json`
  - `var/artifacts/orchestration_runs/<date>/orchestrator_result.json`
- 对于 `governance_reject` 模式，底层 reject 执行结果仍落在独立命名空间:
  - `var/artifacts/governance_rejections/<validation_id>/governance_reject_execution.json`
  - `var/ledgers/governance_rejections/<validation_id>/governance_reject_execution_run.json`
- 对于 `governance_status_transition` 模式，底层 transition 结果仍落在独立命名空间:
  - `var/artifacts/governance_status_transitions/<validation_id>/governance_status_transition.json`
  - `var/ledgers/governance_status_transitions/<validation_id>/governance_status_transition_run.json`
- 对于 `governance_candidate_validation_outcome` 模式，底层 outcome 结果仍落在独立命名空间:
  - `var/artifacts/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome.json`
  - `var/ledgers/governance_candidate_validations/<validation_id>/governance_candidate_validation_outcome_run.json`
- `governance_reject`、`governance_status_transition` 与 `governance_candidate_validation_outcome` 都是 on-demand surface，不属于日常 `daily` 自动编排。

`governance_reject` 最小调用样例:

```bash
curl -X POST "http://127.0.0.1:18030/api/orchestration/run" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-05-20",
    "mode": "governance_reject",
    "source_run_id": "benchmark-run-1",
    "validation_id": "validation-final-reject",
    "requested_by": "ops.manual",
    "dry_run": false
  }'
```

`governance_status_transition` 最小调用样例:

```bash
curl -X POST "http://127.0.0.1:18030/api/orchestration/run" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-05-20",
    "mode": "governance_status_transition",
    "source_run_id": "benchmark-run-1",
    "validation_id": "validation-final-reject",
    "requested_by": "ops.manual",
    "dry_run": false
  }'
```

`governance_candidate_validation_outcome` 最小调用样例:

```bash
curl -X POST "http://127.0.0.1:18030/api/orchestration/run" \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2026-05-20",
    "mode": "governance_candidate_validation_outcome",
    "source_run_id": "benchmark-run-1",
    "validation_result": {
      "validation_id": "validation-final-reject",
      "source_run_id": "benchmark-run-1",
      "baseline_run_id": "benchmark-baseline-run",
      "candidate_run_id": "candidate-run-1",
      "outcome": "rejected",
      "status": "completed",
      "summary": {
        "decision": "reject",
        "reason": "manual audit"
      },
      "validation_result_count": 1,
      "decision_record_count": 1
    },
    "requested_by": "ops.manual",
    "dry_run": false
  }'
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
- `authoritative_source_unavailable`

### 6.5 数据源口径（2026-06-16 起）

- 服务层当前已按以下口径收敛：
  - `daily_prices`：`Tushare` 主源，`Tencent` 仅作 safety-net
  - `company_announcements` / `policy_documents` / `research_reports` / `report_consensus` / `institutional_surveys` / `etf_*` / `fund_*` / `index_*`：`Tushare` 唯一来源
  - `concept/theme cache`：`Tushare` 唯一来源
- 对 `Tushare` 唯一来源资源：
  - 若主源失败，API 直接返回 `authoritative_source_unavailable`
  - 不再把主源失败包装成 `status=skipped`
- 对 `daily_prices`：
  - 先尝试 `Tushare`
  - 仅当 `Tushare` 失败时才允许切到 `Tencent`
  - `Tushare` 成功还必须同时通过覆盖率门禁和格式一致性门禁
- 当前仓库内生产调度入口已收敛为 authoritative 调用口径。
- 若本机已安装的 LaunchAgent 仍使用旧模板，需执行安装/校验脚本将本机触发器同步到 `update_daily_prices_authoritative`。

当前响应头行为:

- JSON 响应附带最小 CORS 头，允许 dashboard 从独立本地端口读取:
  - `Access-Control-Allow-Origin`: 按允许来源反射当前请求的 `Origin`
  - `Vary: Origin`
  - `Access-Control-Allow-Methods: GET, POST, OPTIONS`
  - `Access-Control-Allow-Headers: Content-Type, X-API-Key`

## 7. 前端用法

### 7.1 当前前端

- 当前前端工程位于 `neotrade3-dashboard/`
- 旧的 `apps/dashboard/main.py` 已退役，不再作为联调入口

### 7.2 启动命令

先启动本地 API，再在前端目录下启动 Vite:

```bash
cd neotrade3-dashboard
npm run dev
```

Vite 当前默认:

- 本地端口: `5173`
- `/api` 代理到: `http://127.0.0.1:18030`

### 7.3 当前页面

打开:

```text
http://127.0.0.1:5173/
```

当前页面包含:

- `Overview`
- `Screeners`
- `Stock Check`
- `Lowfreq`

当前页面会通过 `/api/...` 直接读取后端接口，例如:

- `Overview` 会读取 `data/status`、`sectors/hot`、`concepts/mainline`、`lowfreq/execution/queue` 等
- `Screeners` 会读取 `screeners`、`screeners/runs`、`screeners/bulk-runs`
- `Stock Check` 会读取 `check-stock`
- `Lowfreq` 会读取 `market-phase`、`sectors/hot`、`lowfreq-score/pool|events|summary`、`lowfreq/backtest/*`
- `Lowfreq` 会写入 `lowfreq-score/manual/buy-intent`、`lowfreq-score/manual/abandon`、`lowfreq/backtest/run`

### 7.4 当前限制

- 尚未补齐 lint/test 基线
- 本地 `vite dev` 入口没有业务登录页；正式外网入口由前端网关统一执行 `HTTP Basic Auth`
- 仍有部分 bootstrap/迁移相关接口是历史兼容视图

## 8. 推荐本地联调流程

### 8.1 第一步: 生成一轮本地快照

```bash
./.venv/bin/python -m apps.worker.main --date 2026-05-19
```

### 8.2 第二步: 启动 API

```bash
./.venv/bin/python -m apps.api.main --host 127.0.0.1 --port 18030
```

### 8.3 第三步: 启动前端

```bash
cd neotrade3-dashboard
npm run dev
```

### 8.4 第四步: 人工检查

至少检查:

- `http://127.0.0.1:18030/healthz`
- `http://127.0.0.1:18030/api/bootstrap-summary`
- `http://127.0.0.1:5173/`

## 9. 自动化回归基线

当前仓库已具备一组最小 HTTP 级回归，入口仍然统一在:

```bash
./.venv/bin/python -m pytest tests/unit/test_bootstrap_skeleton.py
```

这组回归当前不只覆盖骨架对象装配，也覆盖:

- API server 的 `live/stored` summary 路径
- API server 的无效日期错误路径
- API server 的 `config-contracts` 与现有域接口可访问性
- API server 的 `migration/feature-manual` 功能台账可访问性
- 旧 dashboard 的退役行为（返回 `410 Gone`）
- bootstrap 主链与 API 兼容投影路径

用途:

- 在修改 `worker -> api` 主链或兼容投影后，快速确认 HTTP 级联调没有回归
- 避免只靠对象级单元测试而漏掉 handler / server 生命周期问题

## 10. 当前不应误解的点

当前 runbook 只说明:

- 代码骨架已经可以统一启动
- 主链已经可以形成本地只读快照
- API 与 React 前端已经有最小联调路径

当前不应表述为:

- 3.0 已具备完整业务运行能力
- 3.0 已接管 NeoTrade2 正式职责
- learning loop 已具备自动改参与自动上线能力

## 11. 自动任务（LaunchAgents + Scheduler + Daily Pipeline）

### 11.1 LaunchAgents 与环境变量

本机当前通过 launchd 管理以下入口:

- `com.neotrade3.api`：API 服务（默认监听 `127.0.0.1:18031`，长期进程）
- `com.neotrade3.frontend_gateway`：V3 前端网关（默认监听 `127.0.0.1:5174`，长期进程，托管 `neotrade3-dashboard/dist` 并代理 `/api/*` 与 `/healthz`）
- `com.neotrade3.scheduler`：每日下载入口（`launchd` 定时触发 `--run-once update_daily_prices_authoritative`）
- `com.neotrade3.trade_execution_rt`：09:35 实时执行入口（`launchd` 定时触发 `--run-once trade_execution_rt_0935`）

两者都依赖 secrets 注入:

- 默认读取 `~/Library/Application Support/NeoTrade3/env.secrets`
- 或通过环境变量 `NEOTRADE3_ENV_FILE` 指定文件路径

常用变量:

- `TUSHARE_TOKEN`：用于 Tushare 数据补齐（历史日线 backfill、同花顺概念缓存预热）
- `NEOTRADE3_STOCK_DB_V2_PATH`：可选，用于从 NeoTrade2 行情库补齐缺口
- `DASHBOARD_PASSWORD`：仅供 `com.neotrade3.frontend_gateway` 使用；缺失时前端网关不得启动

LaunchAgent 模板与安装约定:

- 仓库模板目录：`config/launchd/`
- 安装/校验脚本：`scripts/install_launchagents.py`
- `ProgramArguments[0]` 默认写入 `PROJECT_ROOT/.venv/bin/python`，也可通过 `--python-bin` 显式覆盖
- `Node` 进程模板默认通过 `node` 自动探测，也可通过 `--node-bin` 显式覆盖
- 只允许修改仓库模板后再执行脚本同步到 `~/Library/LaunchAgents`
- 不要手工直接编辑 `~/Library/LaunchAgents/com.neotrade3.api.plist`
- 不要手工直接编辑 `~/Library/LaunchAgents/com.neotrade3.frontend_gateway.plist`
- 不要手工直接编辑 `~/Library/LaunchAgents/com.neotrade3.scheduler.plist`
- 不要手工直接编辑 `~/Library/LaunchAgents/com.neotrade3.trade_execution_rt.plist`
- `launchd Weekday` 语义：`1=周一 ... 5=周五，6=周六，0/7=周日`

### 11.1.1 `com.neotrade3.api` 的 `launchd` 真相源与恢复边界

`com.neotrade3.api` 的运行真相源不是“当前哪个 plist 文件名看起来最像正式文件”，而是：

- `launchctl print gui/$(id -u)/com.neotrade3.api`
  - 重点看 `path`
  - 重点看 `state`
  - 重点看 `pid`
- `http://127.0.0.1:18031/healthz`
- `http://127.0.0.1:5174/healthz`

2026-06-19 的实际排障结论：

- 旧的 `~/Library/LaunchAgents/com.neotrade3.api.plist` 在 `launchctl bootstrap` 时可直接返回 `Input/output error`
- 同一条启动命令、同一组环境变量、同一个 label `com.neotrade3.api`
  - 若改用一份全新写出的 plist 文件路径
  - 则可被 `launchd` 正常接管
- 因此该类异常不能简单判断为：
  - Python 解释器损坏
  - API 程序本身无法启动
  - `NEOTRADE3_ENV_FILE` 无法读取
  - `18031` 端口本身不可用

当前已确认的恢复口径：

- 若 `com.neotrade3.api` 的 canonical plist 在 `bootstrap` 时直接报 `Input/output error`
- 先不要重启全部 LaunchAgents
- 先核查：
  - `launchctl print gui/$(id -u)/com.neotrade3.api`
  - `curl http://127.0.0.1:18031/healthz`
  - `curl -u user:$DASHBOARD_PASSWORD http://127.0.0.1:5174/healthz`
- 若确认是“旧 plist 文件状态异常”，可用“全新生成的 same-label plist”恢复 `com.neotrade3.api`
- 恢复后必须重新执行 `scripts/install_launchagents.py check --target-dir "$HOME/Library/LaunchAgents" --launchctl --python-bin "$PROJECT_PYTHON"` 复核

当前机器上的已确认状态示例：

- label：`com.neotrade3.api`
- `launchctl` 当前 `path`：`~/Library/LaunchAgents/com.neotrade3.api.fresh.plist`
- `launchctl` 当前 `state`：`running`
- API 与前端网关健康检查：均返回 `ok`

本机前端网关联调口径:

- 网关入口：`http://127.0.0.1:5174/`
- 网关自身健康检查：`http://127.0.0.1:5174/_gateway/healthz`
- 通过网关访问 API 健康检查：`http://127.0.0.1:5174/healthz`
- 对外域名 `sanford.vip.cpolar.cn` 应指向前端网关端口 `5174`，不再指向旧 `V2` Flask 端口 `8765`
- 未携带 Basic Auth 访问网关任一路径时，返回 `401` 属于正常行为
- 认证口径固定为浏览器原生 Basic Auth 提示框，网关只校验密码，不关心用户名

常用验证命令:

```bash
curl -i http://127.0.0.1:5174/
curl -u user:$DASHBOARD_PASSWORD http://127.0.0.1:5174/_gateway/healthz
curl -u user:$DASHBOARD_PASSWORD http://127.0.0.1:5174/healthz
curl -u user:$DASHBOARD_PASSWORD https://sanford.vip.cpolar.cn/healthz
```

### 11.2 Scheduler 定时任务清单（APScheduler）

入口: `neotrade3/scheduler/task_scheduler.py`

说明:

- 本节描述的是代码内 APScheduler 注册定义
- 当前生产实际触发仍以 `launchd` 的 `--run-once` LaunchAgent 为准
- 若代码定义与 `config/launchd/` 模板不一致，应优先核对并修正模板与运维文档
- 任何生产任务的时间、工作日、启停状态，均不得只通过 APScheduler 注册来判断
- `task_scheduler.py` 在这里代表代码能力与本地调试入口，不等于生产启用清单

- `update_daily_prices_authoritative`（代码内定义：工作日 15:45）
  - 目标: 把“当日收盘后的日线”写入 `var/db/stock_data.db`
  - 机制: CN 时区判断收盘（默认 15:10 后），并具备 catch-up 能力（漏跑会从 DB 最新交易日追到 cutoff）
- `update_financial_data`（代码内定义：每天 18:00）
- `fetch_news`（代码内定义：工作日 9:00–14:59，每 30 分钟）
- `warm_tushare_theme_cache`（代码内定义：每 2 分钟）
  - 目标: 预热同花顺概念列表与成分缓存，避免刷新时触发频控

### 11.3 日线写库与质量闸门（Tushare 主源 → Tencent safety-net → 落库）

入口: `apps/api/main.py:update_daily_prices_authoritative_view`

流程要点:

- 首先使用 `Tushare pro.daily(trade_date=YYYYMMDD)` 作为主源抓取 `target_date`
- `Tushare` 成功还必须同时通过：
  - 覆盖率门槛（close/amount/turnover 等）
  - 格式一致性门禁（OHLC 区间、`pct_change` 与 `close/preclose` 基本一致等）
- 若当日 `Tushare daily` 返回空记录，会在 `16:00` 前按 `3` 分钟间隔短重试
- 仅当 `Tushare` 主源失败时，才允许切到腾讯 safety-net
- 腾讯 fallback 成功后仍需通过原有质量门禁，且结果会被记录为 fallback 路径
- 若目标日仍存在停牌缺口，会继续结合 `suspend_d` 合成零成交 bar 以保持矩阵完整
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
