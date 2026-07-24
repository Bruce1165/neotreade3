# NeoTrade3 Repository Code Wiki

> **Status**: adopted（校对纳入，含勘误）
> **Owner**: Kimi（NeoTrade3 接管 Agent）
> **Scope**: 仓库级架构 / 运行链路 / 模块地图 / 安装运行测试指引
> **Canonical**: no（当前状态真相源为 `PROJECT_STATUS.md`）
> **Supersedes**: none
> **Superseded_by**: none
> **Last_reviewed**: 2026-07-24
>
> ⚠️ **快照声明**：本文起草于 2026-07-23（外部 Agent），2026-07-24 由 Kimi 校对纳入。其中目录大小、文件清单、CI 版本等易漂移信息为当时快照值，不保证持续有效。若本文与 `PROJECT_STATUS.md`「当前运行边界」一节存在冲突，一律以 `PROJECT_STATUS.md` 为真相源；运行时事实以 `var/` 实际内容与 `launchctl print` 输出为准。

## 1. 文档定位

这是一份基于当前仓库代码与现有文档证据整理的仓库级 Code Wiki，目标是回答以下问题：

- 这个仓库的整体架构是什么。
- 当前主运行链路是什么。
- 每个主要模块负责什么。
- 核心类与关键函数分别在哪里。
- 模块之间允许怎样依赖。
- 项目应如何安装、启动、回填、回测与测试。

边界说明：

- 本文只描述当前仓库中可被代码、配置、README、runbook、CI 直接证明的事实。
- 本文不把历史设计稿当作“当前运行事实”，但会在需要解释模块分层时引用其已落地的结构共识。
- `legacy/` 与 `scripts/archive/` 被视为历史参考，不作为当前主线能力来源。

## 2. 仓库一句话理解

NeoTrade3 当前是一个以 Python 为核心的量化研究与执行工程，采用：

- `neotrade3/` 作为领域核心包。
- `apps/worker` 作为日常执行与编排总控入口。
- `apps/api` 作为后端 HTTP 服务与投影层。
- `neotrade3-dashboard/` 作为当前正式前端。
- `config/` 作为大部分运行配置与注册表真相源。
- `scripts/` 作为回填、回测、评估、报表和生产辅助脚本集合。

当前 README 明确给出的推荐本地启动顺序是：

1. 启动 `worker`
2. 启动 `api`
3. 启动 `neotrade3-dashboard`

## 3. 顶层架构图

```text
config/*.json
    |
    v
apps/worker/main.py
    |
    +--> neotrade3.data_control        (M1 事实/数据控制)
    +--> neotrade3.labs                (实验室运行)
    +--> neotrade3.orchestration       (日级编排与 ledger)
    +--> neotrade3.benchmark           (M4 基准评测)
    +--> neotrade3.governance          (M5 治理)
    +--> neotrade3.learning            (学习闭环)
    +--> neotrade3.issue_center        (问题聚合)
    |
    v
var/ledgers + var/artifacts + var/db
    ^
    |
apps/api/main.py + apps/api/router.py
    |
    +--> 读取配置、DB、ledger、artifact
    +--> 暴露 /healthz /api/... HTTP 接口
    |
    v
neotrade3-dashboard (React + Vite)
```

补充说明：

- `apps/api/main.py` 同时直接依赖多个领域包，也导入 `BootstrapWorkerApp`，说明 API 层不仅是纯路由层，还是面向前端和运维的聚合投影层。
- `lowfreq_engine_v16_advanced.py` 仍然是低频策略核心实现之一，虽然仓库整体主架构已迁移到 `neotrade3/` 包内。
- `scripts/` 负责把部分研究、报表、混沌模型和生产辅助能力以命令行脚本形式暴露出来。

## 4. 顶层目录地图

| 路径 | 角色 | 当前定位 |
| --- | --- | --- |
| `apps/` | 应用层入口 | API、Worker 入口（历史 Dashboard 入口 `apps/dashboard` 已于 2026-07-23 移除，见 §15.2 注） |
| `neotrade3/` | 领域核心包 | 当前主线业务逻辑所在 |
| `neotrade3-dashboard/` | 前端应用 | 当前正式浏览器 UI |
| `config/` | 配置中心 | orchestrator、screeners、strategies、chaos、launchd 等注册表与配置 |
| `scripts/` | 运维/研究脚本 | 回填、回测、评估、报表、安装 launchagents |
| `docs/` | 文档中心 | 架构、运维、迁移、交接、设计说明 |
| `legacy/` | 历史参考实现 | 保留旧低频与旧运行入口，不是当前主线 |
| `.github/workflows/` | CI | 后端 `pytest` 与前端 `lint/test/build` |
| `lowfreq_engine_v16_advanced.py` | 独立核心引擎文件 | 低频策略核心实现 |

## 5. 当前主运行链路

### 5.1 Worker

入口：`apps/worker/main.py`

作用：

- 读取 `config/labs/labs_registry.json`
- 读取 `config/orchestrator/daily_master_orchestrator.json`
- 读取 `config/data_control/source_registry.json`
- 构造并执行每日运行计划
- 驱动 Data Control、Labs、Benchmark、Governance、Learning、Issue Center
- 写出 `var/ledgers/bootstrap_runs` 与 `var/artifacts/bootstrap_runs`

核心对象：

- `BootstrapWorkerApp`
- `BootstrapWorkerApp.run()`
- `BootstrapWorkerApp.run_governance_*` 系列治理触发方法
- CLI `main()`

### 5.2 API

入口：`apps/api/main.py`

作用：

- 启动 `ThreadingHTTPServer`
- 读取环境变量与 `.env` 风格 secrets 文件
- 聚合读取配置、SQLite、ledgers、artifacts
- 暴露当前对前端与运维可见的 API
- 兼容多个 API 域：health、lowfreq、data-control、orchestration、labs、migration、issue-center、learning 等

核心对象：

- `BootstrapApiService`
- `BootstrapApiRouter`
- `ApiCacheEntry`

### 5.3 Frontend

入口：`neotrade3-dashboard/src/main.jsx`

主应用：`neotrade3-dashboard/src/App.jsx`

作用：

- 通过 React Router 暴露当前 UI 页面
- 当前主页面包括：
  - `Overview`
  - `MarketIntelligence`
  - `Lowfreq`
  - `OpsCenter`
  - `StockCheck`
  - `Screeners`
  - `LowfreqBacktestReport`
- 通过 `services/api.js` 调后端 `/api` 与 `/healthz`
- Vite 代理默认转发到 `http://127.0.0.1:18030`

### 5.4 运行事实载体

当前系统不是“纯内存系统”，其重要运行事实落在 `var/`：

- `var/db/`：SQLite 数据库
- `var/ledgers/`：运行账本、快照、状态
- `var/artifacts/`：报表、产物、导出内容

这意味着：

- `worker` 负责生产大量事实与运行结果
- `api` 负责把这些事实投影给前端与外部调用者
- `frontend` 主要消费 API，不直接计算领域真相

## 6. 领域分层与模块职责

项目现有代码和架构文档共同指向一个六层量化结构：

- `M1 事实层 Fact Layer`
- `M2 周期识别层 Cycle Intelligence`
- `M3 交易决策层 Decision Engine`
- `M4 Benchmark 层`
- `M5 治理层 Governance / Evolution Control`
- `M6 交付与观测层 Delivery / Observability`

虽然并非所有模块都用 `M1-M6` 命名，但仓库目录已经明显按这个方向收敛。

### 6.1 M1 事实层

主目录：

- `neotrade3/data_control/`
- `neotrade3/data_sources/`
- `neotrade3/data/`
- 部分 DB/源适配逻辑也被 API 和脚本直接消费

职责：

- 外部数据接入
- capture / compose / publish 数据控制流程
- 数据质量、freshness、attention item 生成
- 正式输入适配
- 基本面与交易日历等事实读取

关键对象：

- `DataControlPipeline`
- `SourceRegistry`
- `DataControlLedgerBuilder`
- `load_formal_m1_inputs()`
- `load_fundamentals()` / `load_fundamentals_batch()`

### 6.2 M2 周期识别层

主目录：

- `neotrade3/cycle_intelligence/`

职责：

- 从 M1 事实组装小周期与市场焦点对象
- 识别市场焦点、候选池、板块热度、周收益等状态
- 输出更偏“结构化识别”的对象，而不是直接下交易单

关键对象：

- `build_small_cycle_from_m1()`
- `build_shadow_cycle_intelligence_from_m1()`
- `build_market_focus_snapshot()`
- `build_global_candidates()`
- `build_sector_candidates()`

### 6.3 M3 交易决策层

主目录：

- `neotrade3/decision_engine/`
- `lowfreq_engine_v16_advanced.py`

职责：

- 把 M2 的状态和 M1 的执行事实翻译成交易决策链
- 当前决策语义围绕 `identify -> tracking -> entry -> hold -> exit`
- 管理信号去重、交易纪律、系统退出、风险与执行门控
- 维护正式前置上下文和生命周期日志

关键对象：

- `build_identify_state()`
- `build_tracking_state()`
- `build_entry_state()`
- `build_hold_state()`
- `build_exit_state()`
- `build_decision_lifecycle_log()`
- `build_chaos_snapshot_v0()`
- `compute_hazard_snapshots_v0_t2_for_series()`
- `LowFreqTradingEngineV16`

### 6.4 M4 Benchmark 层

主目录：

- `neotrade3/benchmark/`

职责：

- 独立评估 M2/M3 输出质量
- 执行 benchmark manifest
- 生成评测账本、产物与差距记录

关键对象：

- `run_benchmark_for_manifest()`
- `run_benchmark_manifest()`
- `build_benchmark_assessment_from_m2_shadow()`
- `BenchmarkSample`
- `BenchmarkAssessmentResult`

### 6.5 M5 治理层

主目录：

- `neotrade3/governance/`

职责：

- 接收 benchmark 结果
- 形成 handoff、reject、validation、status transition 等治理动作
- 输出治理台账、验证结论与阻塞项

关键对象：

- `run_governance_for_benchmark_run()`
- `run_governance_candidate_validation_outcome()`
- `run_governance_candidate_outcome_bridge()`
- `run_governance_final_validation_selection()`
- `DiagnosticChain`
- `ChangeRequest`
- `ValidationResult`

### 6.6 M6 交付与观测层

落点不是单一目录，而是横切式存在于：

- `apps/api/`
- `neotrade3-dashboard/`
- `neotrade3/orchestration/`
- `neotrade3/benchmark/*artifact*`
- `neotrade3/governance/*artifact*`
- `scripts/` 报告与输出脚本
- `var/ledgers/` 与 `var/artifacts/`

职责：

- 面向前端与运维暴露状态
- 输出运行摘要、报告、ledger、artifact
- 维持系统可观测性与可追溯性

## 7. 主要模块职责表

| 模块 | 路径 | 职责 | 主要输入 | 主要输出 |
| --- | --- | --- | --- | --- |
| Worker | `apps/worker/` | 总控与任务调度执行 | 配置、日期、运行模式 | bootstrap ledgers/artifacts |
| API | `apps/api/` | HTTP 服务与领域投影 | 配置、DB、ledgers、artifacts | `/api/*` 响应 |
| Dashboard | `neotrade3-dashboard/` | 浏览器端 UI | API 响应 | 页面、操作入口、状态展示 |
| Data Control | `neotrade3/data_control/` | capture/compose/publish 与事实适配 | 数据源、DB、日期 | 事实视图、ledger、质量结果 |
| Cycle Intelligence | `neotrade3/cycle_intelligence/` | 周期与候选识别 | M1 事实 | 小周期/市场焦点/候选 |
| Decision Engine | `neotrade3/decision_engine/` | 决策主链与审计 | M1 事实、M2 状态 | entry/hold/exit 决策与生命周期 |
| Analysis | `neotrade3/analysis/` | 分析、信号、回测、归因 | 市场与个股数据 | 信号、统计、归因报告 |
| Benchmark | `neotrade3/benchmark/` | 独立评测 | M1/M2/M3 与 manifest | benchmark result、gap record |
| Governance | `neotrade3/governance/` | 治理与验证闭环 | benchmark artifacts | handoff、validation、transition |
| Labs | `neotrade3/labs/` | 实验室注册与运行适配 | labs registry、任务请求 | lab runtime results |
| Learning | `neotrade3/learning/` | 结果汇总、演化候选、审计 | 运行结果、因子反馈 | 演化报告与调整候选 |
| Issue Center | `neotrade3/issue_center/` | 异常聚合 | 各域结果与失败信息 | 问题项、修复线索 |
| Chaos | `neotrade3/chaos/` | 混沌模型快照、回测、评估 | Chaos DB、日线事实 | snapshot、score、backtest artifacts |
| Screeners | `neotrade3/screeners/` | 筛选器注册与运行 | screener config、股票数据 | run ledgers/artifacts |
| Strategies | `neotrade3/strategies/` | 策略配置装配与导出 | config/strategies、SQLite store | engine config、导出结果 |

## 8. 关键类与函数索引

下面只列当前仓库中最关键、最能代表主链路的类与函数，不追求穷举。

### 8.1 应用层

| 符号 | 路径 | 作用 |
| --- | --- | --- |
| `BootstrapWorkerApp` | `apps/worker/main.py` | Worker 总控入口，装配并执行日常主流程 |
| `BootstrapWorkerApp.run()` | `apps/worker/main.py` | 每日主执行流程 |
| `main()` | `apps/worker/main.py` | Worker CLI 分发入口 |
| `BootstrapApiService` | `apps/api/main.py` | API 聚合服务对象，面向前端与运维提供读写入口 |
| `BootstrapApiRouter` | `apps/api/router.py` | URL 路由分发与请求校验 |
| `ApiCacheEntry` | `apps/api/main.py` | API 最小内存缓存单元 |
| `main()` | `apps/api/main.py` | API 服务器启动入口 |

### 8.2 数据与事实层

| 符号 | 路径 | 作用 |
| --- | --- | --- |
| `DataControlPipeline` | `neotrade3/data_control/pipeline.py` | capture / compose / publish 三段式数据流程核心类 |
| `SourceRegistry` | `neotrade3/data_control/source_registry.py` | 数据源注册与配置加载 |
| `DataControlLedgerBuilder` | `neotrade3/data_control/ledger.py` | 数据控制运行台账构建 |
| `load_formal_m1_inputs()` | `neotrade3/data_control/formal_input_adapter.py` | 从 SQLite 组装正式 M1 输入 |
| `load_fundamentals()` | `neotrade3/data_control/financial_report_adapter.py` | 基本面读取适配 |

### 8.3 周期识别层

| 符号 | 路径 | 作用 |
| --- | --- | --- |
| `build_small_cycle_from_m1()` | `neotrade3/cycle_intelligence/assembler.py` | 从 M1 输入组装小周期对象 |
| `build_shadow_cycle_intelligence_from_m1()` | `neotrade3/cycle_intelligence/assembler.py` | 构建 shadow 周期智能对象 |
| `build_market_focus_snapshot()` | `neotrade3/cycle_intelligence/market_focus_snapshot.py` | 构建市场焦点快照 |
| `build_global_candidates()` | `neotrade3/cycle_intelligence/global_entry_selector.py` | 全局候选筛选 |
| `build_sector_candidates()` | `neotrade3/cycle_intelligence/sector_entry_selector.py` | 板块候选筛选 |

### 8.4 决策层与低频引擎

| 符号 | 路径 | 作用 |
| --- | --- | --- |
| `build_identify_state()` | `neotrade3/decision_engine/assembler.py` | 识别态构建 |
| `build_tracking_state()` | `neotrade3/decision_engine/assembler.py` | 跟踪态构建 |
| `build_entry_state()` | `neotrade3/decision_engine/assembler.py` | 入场态构建 |
| `build_hold_state()` | `neotrade3/decision_engine/assembler.py` | 持有态构建 |
| `build_exit_state()` | `neotrade3/decision_engine/assembler.py` | 退出态构建 |
| `build_decision_lifecycle_log()` | `neotrade3/decision_engine/assembler.py` | 决策生命周期日志构建 |
| `LowFreqTradingEngineV16` | `lowfreq_engine_v16_advanced.py` | 低频交易主引擎 |
| `build_lowfreq_v16_config_from_strategy()` | `neotrade3/strategies/lowfreq_v16.py` | 把策略配置投影为低频引擎配置 |

### 8.5 分析、回测与归因

| 符号 | 路径 | 作用 |
| --- | --- | --- |
| `SignalGenerator` | `neotrade3/analysis/signal_generator.py` | 综合信号生成 |
| `detect_market_phase()` | `neotrade3/analysis/market_phase.py` | 市场阶段识别 |
| `SignalBacktester` | `neotrade3/analysis/backtest.py` | 通用信号回测器 |
| `BacktestResult` | `neotrade3/analysis/backtest.py` | 回测结果对象 |
| `load_global_top_bullstocks()` | `neotrade3/analysis/top200_bullstocks.py` | Top200 强势股载入 |
| `build_attribution_markdown_report()` | `neotrade3/analysis/attribution_markdown_report.py` | 归因 Markdown 报告生成 |

### 8.6 Benchmark 与治理

| 符号 | 路径 | 作用 |
| --- | --- | --- |
| `run_benchmark_for_manifest()` | `neotrade3/benchmark/runtime.py` | M4 benchmark 总入口 |
| `run_benchmark_manifest()` | `neotrade3/benchmark/batch_runner.py` | 批量 benchmark 执行 |
| `build_benchmark_assessment_from_m2_shadow()` | `neotrade3/benchmark/assembler.py` | 基于 shadow M2 结果做评估组装 |
| `run_governance_for_benchmark_run()` | `neotrade3/governance/runtime.py` | benchmark 后治理主入口 |
| `run_governance_candidate_validation_outcome()` | `neotrade3/governance/runtime.py` | 候选验证治理动作 |
| `run_governance_final_validation_selection()` | `neotrade3/governance/runtime.py` | 最终验证选择治理动作 |

### 8.7 Chaos 主链

| 符号 | 路径 | 作用 |
| --- | --- | --- |
| `ensure_chaos_schema()` | `neotrade3/chaos/store.py` | Chaos SQLite schema 初始化 |
| `upsert_daily_snapshot()` | `neotrade3/chaos/store.py` | Chaos 日快照写入 |
| `ChaosBacktestEngine` | `neotrade3/chaos/backtest/engine.py` | Chaos 全历史回测主实现 |
| `BacktestConfig` | `neotrade3/chaos/backtest/contracts.py` | Chaos 回测配置契约 |

## 9. 关键依赖关系

### 9.1 允许的主依赖方向

推荐从当前代码实际依赖关系抽象为：

```text
配置/数据源
  -> M1 Data Control / Facts
  -> M2 Cycle Intelligence
  -> M3 Decision Engine / Lowfreq Engine
  -> M4 Benchmark
  -> M5 Governance
  -> M6 API / Artifacts / Frontend
```

### 9.2 当前代码中的关键耦合点

以下耦合在当前仓库中是事实存在的：

- `apps/worker/main.py` 直接依赖 `benchmark`、`data_control`、`governance`、`issue_center`、`learning`、`labs`、`orchestration`
- `apps/api/main.py` 直接依赖 `apps.worker.main.BootstrapWorkerApp`
- `apps/api/main.py` 直接依赖 `data_control`、`governance`、`labs`、`lowfreq_score`、`orchestration`、`decision_engine`、`screeners`、`analysis`、`learning`
- 前端通过 `services/api.js` 间接依赖 API，不直接导入 Python 领域逻辑
- `lowfreq_engine_v16_advanced.py` 仍保留部分领域核心，说明低频链路尚未完全内聚进 `neotrade3/decision_engine` 或 `neotrade3/analysis`

### 9.3 应避免的反向依赖

从现有架构文档和代码组织看，应避免：

- 前端定义模型语义，再反向要求后端迎合
- API 重新发明领域真相，而不消费领域层已定义对象
- Benchmark 反向充当事实真值源
- Governance 直接改写 M1/M2 真相而不形成显式治理结果

## 10. 配置、数据与运行时边界

### 10.1 配置真相源

主要配置集中在 `config/`：

- `config/orchestrator/daily_master_orchestrator.json`
- `config/data_control/source_registry.json`
- `config/labs/labs_registry.json`
- `config/screeners/screeners_registry.json`
- `config/strategies/lowfreq_v16.json`
- `config/chaos/*.json`
- `config/benchmark/*.json`
- `config/launchd/*.plist.template`

### 10.2 运行时目录

主要运行时路径由代码与 README 共同指向：

- `var/db/stock_data.db`
- `var/imports/stock_data_v2.db`
- `var/ledgers/bootstrap_runs`
- `var/artifacts/bootstrap_runs`
- `var/artifacts/lowfreq_backtest`
- `var/ledgers/trading_calendar`
- `var/ledgers/lowfreq_sim`
- `var/ledgers/trade_execution_rt`

### 10.3 环境变量

当前代码和运行文档明确出现的环境变量包括：

- `NEOTRADE3_ENV_FILE`
- `TUSHARE_TOKEN`
- `NEOTRADE3_STOCK_DB_PATH`
- `NEOTRADE3_STOCK_DB_V2_PATH`
- `DASHBOARD_PASSWORD`
- `NEOTRADE3_API_BASE_URL`

## 11. 运行方式

### 11.1 后端安装

Python 基线：

- 版本要求：`>=3.10,<3.11`
- CI 安装方式：`pip install -e ".[dev]"`

### 11.2 前端安装

前端位于 `neotrade3-dashboard/`，使用 Node 24 的 CI 基线（`.github/workflows/ci.yml`，2026-07 起），安装方式为：

- `npm ci`

### 11.3 本地启动

推荐顺序：

1. Worker
2. API
3. Dashboard

典型命令：

```bash
./.venv/bin/python -m apps.worker.main
./.venv/bin/python -m apps.api.main --host 127.0.0.1 --port 18030
cd neotrade3-dashboard && npm run dev
```

### 11.4 调度器

调度器入口：

```bash
./.venv/bin/python -m neotrade3.scheduler.task_scheduler --help
```

该模块同时服务两种场景：

- 本地命令行调度
- 生产 `launchd` 通过 `config/launchd/*.plist.template` 触发 `--run-once`

### 11.5 低频与混沌相关脚本

低频与研究类脚本示例：

- `scripts/run_m6_full_backtest_top200_report.py`
- `scripts/run_lowfreq_top200_capacity_experiment.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `scripts/generate_lowfreq_top200_process_research_report.py`

Chaos 脚本示例：

- `scripts/build_chaos_daily_snapshot.py`
- `scripts/run_chaos_full_history_backtest.py`
- `scripts/run_chaos_m4_eval_monitor.py`
- `scripts/run_chaos_m5_tune_weights_v1.py`

## 12. 回填、回测与报告路径

### 12.1 回填

当前仓库可见的回填方式主要有两类：

- API 驱动的数据回补，例如 `data-control` 相关同步入口
- 脚本驱动的混沌快照批量回填，如 `scripts/build_chaos_daily_snapshot.py`

### 12.2 回测

低频回测：

- API 侧暴露 `POST /api/lowfreq/backtest/run`
- 相关状态和报告也通过 `/api/lowfreq/backtest/*` 暴露

Chaos 回测：

- 由 `scripts/run_chaos_full_history_backtest.py` 驱动
- 核心引擎在 `neotrade3/chaos/backtest/engine.py`

### 12.3 报告

当前报告产物既存在于：

- Python 领域模块内的 `artifact_writer.py`
- `analysis` 中的 attribution/report 生成器
- `scripts/` 中的 PDF、JSON、Markdown 导出脚本

## 13. 前端结构

前端技术栈：

- React 18
- React Router 6
- Vite 5
- Vitest
- ESLint
- Tailwind CSS

主要目录：

- `src/pages/`：页面级组件
- `src/components/`：可复用组件
- `src/services/`：API 调用层
- `src/context/`：全局上下文
- `server/gateway.js`：Node 网关，可用于受控访问

前端当前主页面由 `App.jsx` 中的路由声明可直接确认：

- `/` -> `Overview`
- `/market-intelligence` -> `MarketIntelligence`
- `/lowfreq` -> `Lowfreq`
- `/ops` -> `OpsCenter`

## 14. 测试与 CI

### 14.1 后端

测试基线：

```bash
./.venv/bin/python -m pytest tests -q
```

CI：

- GitHub Actions 使用 Python 3.10
- 安装 `.[dev]`
- 运行 `pytest tests -q`

### 14.2 前端

测试基线：

```bash
cd neotrade3-dashboard
npm run lint
npm run test
npm run build
```

CI：

- GitHub Actions 使用 Node 24（`.github/workflows/ci.yml`，2026-07 起）
- 运行 `npm ci`
- 运行 `lint`
- 运行 `test`
- 运行 `build`

## 15. Active 与 Legacy 边界

### 15.1 当前主线

- `apps/worker/main.py`
- `apps/api/main.py`
- `apps/api/router.py`
- `neotrade3/`
- `neotrade3-dashboard/`
- `config/`
- 活跃的 `scripts/`
- `lowfreq_engine_v16_advanced.py`

### 15.2 历史参考

- `legacy/`
- `scripts/archive/`

> 注：`apps/dashboard/` 曾列为历史参考，已于 2026-07-23 从仓库整体移除（commit `bb8843e`，含 3 个钉住它的测试），现仅存在于 git 历史中。

对这些目录的正确理解应是：

- 它们保留历史语义和对照价值
- 不应默认当作当前生产主链的一部分

## 16. 阅读顺序建议

如果目标是快速理解整个系统，建议按下面顺序读代码：

1. `README.md`
2. `apps/worker/main.py`
3. `neotrade3/orchestration/`
4. `neotrade3/data_control/`
5. `neotrade3/cycle_intelligence/`
6. `neotrade3/decision_engine/`
7. `lowfreq_engine_v16_advanced.py`
8. `neotrade3/benchmark/`
9. `neotrade3/governance/`
10. `apps/api/main.py`
11. `apps/api/router.py`
12. `neotrade3-dashboard/src/App.jsx`
13. `scripts/` 中与你当前任务对应的脚本

## 17. 修改代码时的定位建议

如果你要做的是：

- 改每日执行链路：优先看 `apps/worker/main.py`、`neotrade3/orchestration/`
- 改数据接入/数据质量：优先看 `neotrade3/data_control/`
- 改周期识别/候选装配：优先看 `neotrade3/cycle_intelligence/`
- 改交易决策与状态机：优先看 `neotrade3/decision_engine/`
- 改低频回测或核心策略：优先看 `lowfreq_engine_v16_advanced.py`、`neotrade3/analysis/`
- 改 benchmark：优先看 `neotrade3/benchmark/`
- 改治理闭环：优先看 `neotrade3/governance/`
- 改 HTTP 接口：优先看 `apps/api/main.py`、`apps/api/router.py`
- 改前端表现：优先看 `neotrade3-dashboard/src/pages/` 与 `src/components/`
- 改生产调度：优先看 `neotrade3/scheduler/task_scheduler.py` 与 `config/launchd/`

## 18. 当前仓库的几个重要事实

- 这不是一个只有单一引擎文件的项目，而是正在收敛为“领域包 + 应用层 + 前端 + 配置中心 + 运行账本”的系统工程。
- `worker` 是执行总控，`api` 是投影与访问层，`dashboard` 是消费层。
- `config/` 与 `var/` 对系统理解都非常关键；前者定义意图，后者承载运行事实。
- 低频能力与混沌能力并存，且二者的脚本、回测、产物路径相互独立但共处同一仓库。
- 当前仓库仍保留部分历史实现，因此理解“Active 与 Legacy 边界”比单纯看目录更重要。

## 19. 相关文档

建议与本 Wiki 配合阅读的文件：

- `README.md`
- `docs/operations/bootstrap_runbook.md`
- `docs/architecture/lowfreq_code_wiki.md`
- `docs/architecture/neotrade3_research_model_and_module_taxonomy_v1.md`
- `docs/superpowers/specs/2026-07-06-quant-model-top-level-architecture-design.md`
- `docs/wiki/repo_tree.md`

