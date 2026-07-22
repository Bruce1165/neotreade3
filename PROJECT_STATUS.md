# NeoTrade3 Project Status

**Last Updated**: 2026-07-22

---

## 项目核心逻辑（已在对话中确认）

### 0) 当前正式业务依据（2026-06-18 纠偏）

- 当前正式模型依据必须按四层同时理解，不能只摘取其中一段单独使用：
  1. 用户最初给出的五维模型调整依据：
     - 周期位置
     - 主流指数择时
     - 行业渗透率
     - 技术层面
     - 资金与情绪面
  2. 后续两份补充信息对五维框架的细化修正。
  3. 随后口头确认的执行约束：
     - 回撤止损 `-5%` 是硬性指标
     - `确定性 > 85` 仅作参考，不再是硬门槛
     - 其他旧指标可为调整后的模型逻辑让步
  4. 2026-06-12 证监会改革相关政策指导材料，以及团队对该材料的重点范围修正。
- 对政策材料的正式吸收方式不是“四大主线平均看待”，而是：
  - 第一、第三、第四、第五大类大多属于 `K 型向下` 或低优先级观察范围；
  - 真正重点范围是第二大类硬科技；
  - 第二大类必须买龙头，且是细分赛道龙头；
  - `ETF 高配 + 机构高配` 是关键增强证据；
  - 人工智能龙头优先级最高。
- 因此，当前正式对标重点不是“是否严格保留所有旧确定性/旧评分定义”，而是：
  - 是否按五维框架先确定主线与景气度；
  - 是否把重点范围收敛到第二大类硬科技细分龙头；
  - 是否把 `-5%` 回撤止损作为硬性指标落实；
  - 其余旧指标若与上述逻辑冲突，应让位于调整后的模型逻辑。

### 1) 数据主链（Data Control）

- 目标：保证每天数据可用、可追溯、可回放。
- 验收：昨天数据在、交易日历更新、质量检查结果可见。

### 2) 选股主链（Screeners → Pools → 候选集）

- 目标：每天产生“候选股集”，并进入监控池/跟踪池。
- 验收：每天能跑、能下载 CSV、池成员变化可见、池成员列表可见。

### 3) 研究主链（QuantMatrix / 因子矩阵）

- 目标：把筛选器结果和其它因子沉淀成“可解释的矩阵”，并能看增长/演进。
- 验收：矩阵结构可视化 + 历史增长曲线/表 + 单只股票的因子解释。

### 4) 闭环主链（Issue Center + Learning）

- 目标：异常、退化、无效筛选器能被发现、定位、调整并可审计。
- 验收：问题列表、证据链、调整候选、决策记录。

## Dashboard 交互原则（团队可用）

- 默认中文与结论优先：先给出“能不能跑 / 下一步做什么”，再给可展开的细节。
- 团队模式默认收敛操作：筛选器只保留“一键运行启用筛选器”；单筛选器入口用于参数调整。
- 下载以 CSV 为准：筛选器与监控池的对外下载为 CSV；JSON 仅作为开发者模式下的原始数据。
- 数据未就绪时要直说：显示“数据没准备好，先更新数据/交易日历”，并阻止下游运行按钮。

## 当前运行边界（2026-06 代码现状）

- `apps/worker/main.py` 是 bootstrap 主链的唯一执行真相源；`/api/orchestration/run` 已改为复用 worker 结果，不再维护独立执行语义。
- `var/ledgers/bootstrap_runs/<date>/` 与 `var/artifacts/bootstrap_runs/<date>/` 是当前 bootstrap 主事实源。
- `var/ledgers/orchestration_runs/<date>/` 与 `var/artifacts/orchestration_runs/<date>/` 现在是 API 为兼容 orchestration 运行记录读取链路而写出的投影产物，不是独立执行源。
- `var/ledgers/lab_runs/<date>/` 与 `var/artifacts/lab_runs/<date>/` 现在是 API 为兼容既有 lab 结果读取链路而补写的投影产物，不是独立执行源。
- `M5 candidate validation outcome` 已完成 `runtime -> CLI -> worker -> API` 闭环；当前显式输入 contract 固定为 `source_run_id` 与 `validation_result`，且仍属于 on-demand 触发面，不属于 `daily` scheduled task。
- `M5 final validation selection` 已完成 `runtime -> artifact/ledger -> worker/orchestrator on-demand` 基线；当前显式输入 contract 固定为 `source_run_id`，且仍不属于 `daily` scheduled task，也未暴露为独立 CLI / API mode。
- `M5 governance status transition` 已完成 `runtime -> CLI -> worker -> API` 闭环；当前属于 on-demand 触发面，不属于 `daily` scheduled task。
- `M5 governance reject execution` 与 `status transition` 当前已消费 persisted `candidate validation outcome` truth，不再依赖 handoff payload 直接承载最终 validation 结论。
- snapshot 根字段 `publish_succeeded` 表示本次运行的实际 publish 结果；`requested_publish_succeeded` 保留请求侧传入的 planning hint。
- `apps/dashboard/main.py` 已退役，当前会返回 `410 Gone`；在用前端是 `neotrade3-dashboard/` React + Vite 工程。
- `com.neotrade3.scheduler` 已迁移为 system 域 LaunchDaemon（仅迁移 scheduler，不动 `api/frontend_gateway/trade_execution_rt`）
  - `launchctl print system/com.neotrade3.scheduler` 为真相源
  - stdout/stderr 已从 `var/log` 切到系统盘：`~/Library/Logs/NeoTrade3/neotrade3_scheduler.{out,err}.log`
  - 根因闭环：当 stdout/stderr 指向外置盘 `var/log`（exFAT + `noowners`）时，launchd 可能触发 `EX_CONFIG (78)` 导致漏跑；迁移到系统盘日志落点后恢复

## Code-Wiki（以代码事实为准）

### 1) 终极目标与边界（对齐交接文档）

- 终极目标：预判未来 20-60 个交易日有 80%+ 机会涨幅达到 30% 以上的股票（低频/中低频，不做高频/日内）。
- 核心概念：确定性（Certainty）= 可衡量置信度；以因子矩阵 + 证据链解释“为什么买/为什么不买”。
- 自进化原则：受约束的自调整（候选变更→评估→可审计→可回滚），不允许黑箱自动改参直接上线。

### 2) 当前“版本/模型”地图（避免口径混乱）

- 低频引擎（根目录脚本线）：当前正式代码真相源是 `lowfreq_engine_v16_advanced.py`，但不能沿用历史文档对其能力的宽泛描述；正式卖出逻辑与历史会话中的“分批止盈/目标止盈/max_hold 已完整生效”口径存在偏差，必须以现行代码与回测产物核对。
- 系统内实验室（V3 集成线）：`quant_trading_lab` 对外返回 `analysis_version: "v2_enhanced"`（候选+信号生成，不等价于低频脚本的完整交易执行/回测）。
- 现状结论：当前仓库同时存在“脚本策略引擎线”和“V3 分析/信号线”，两者尚未统一为一个可配置、可复现、可审计的单一策略版本体系。

### 3) 关键链路（从数据到结果）

- 数据更新（API 写入）：`update_daily_prices_authoritative_view` → `Tushare` 主源写入 `daily_prices`，必要时由 `Tencent` 仅作 safety-net；成功后重建交易日历；必要时可从 V2 sqlite 通过 `sync_daily_prices_view(target_date=...)` 补齐指定日期。
- 数据就绪（Data Control）：`DataControlPipeline.capture/compose/publish`（capture 负责交易日历生成与单位校验；publish 以“单位校验 + compose 产物存在”为发布闸门）。
- 选股/因子矩阵：`FactorMatrixBuilder` 生成 `factor_matrix_daily.json`（包含 market_context、tiers、signals 等）；筛选器通过 registry 运行并对外以 CSV 交付。
- 实验室：`LabRuntimeAdapter` 统一入口（杯柄/量化交易等），由 `DailyMasterOrchestrator` 在 worker 中按 phases/tasks 调度执行。
- 问题与学习闭环：`IssueCenterCollector` 基于任务状态生成 issue cases；`LearningLoopPipeline` 当前主要输出 review/stable 建议（尚未把“进化建议”自动写回策略/权重/参数）。

### 4) 已知差距（按阻断性排序）

- 版本体系未统一：低频脚本（v16 等）未纳入 V3 的统一配置、统一回测与统一审计台账；系统内 `analysis_version` 与脚本版本号并行。
- 学习闭环未落地到执行：有进化报告/权重建议能力，但 Daily 学习流水线未形成“评估→候选变更→审批→落地→回归”的可复现流程。
- 交易/回测约束不足：交易日、涨跌停、流动性、手续费滑点、不可成交等真实约束仍是简化或缺失（未形成“可实盘”的执行层）。

### 5) 下阶段工作计划（可验收）

1. 版本与策略统一（最高优先级）
   - 将低频 v16 的“参数/规则/版本号”抽成可配置对象，并在 V3 侧形成唯一入口（同一套配置可驱动：信号生成、回测、报告产物）。
   - 产物：同一份配置在任意机器上可复现回测结果（给出固定输入 DB + 固定起止日期 + 固定输出路径）。
2. 回测与报告交付链路打通（面向团队）
   - 输出每笔交易明细（代码/名称/板块/龙头中军跟随/买入日/确定性/买入价/卖出日/收益）与汇总（总交易次数、买入日期汇总、总收益、初始资本 100 万）。
   - 产物：单一命令生成结果 JSON + PDF（PDF 作为交付物，JSON 作为审计与复验依据）。
3. 学习闭环最小落地（受约束）
   - 将进化报告（factor/weight 建议）接入“候选变更台账”，仅产出建议与证据，不自动上线；形成审批闸门与回归对照。
   - 产物：每次迭代有可追溯的建议、证据、对比基线、是否采纳与原因。

## Session Handoff

**Rules**
- 交接内容只写事实、约束、证据路径，不写愿景口号。
- NeoTrade3 的 handoff 只记录 3.0 项目本身，不把 NeoTrade2 的运行细节整段复制进来。
- 每次会话结束前更新一次；如果 3.0 的边界、目录、接口、迁移策略发生变化，应即时更新。
- 新会话开始时，优先按本文档和 `docs/handoffs/2026-05-19_session_resume_handoff.md` 恢复上下文。
- 新会话开始时，若任务与 `M1 Phase 1` 首批正式对象实现相关，优先再阅读：
  - `docs/handoffs/2026-07-07_m1_phase1_formal_objects_handoff.md`

## Document Governance

- 当前文档体系只按 4 层理解：
  - `PROJECT_STATUS.md`：当前状态真相源
  - `docs/handoffs/`：活跃续接层
  - `docs/superpowers/specs/`：design / plan / task-list 层
  - `docs/archive/`：历史留存层
- 除 `PROJECT_STATUS.md` 外，任何文档如果没有显式声明自己仍是当前正式口径，则默认不得替代当前状态真相源。
- 从现在开始，新增或实质更新的第一方 Markdown 文档应补齐最小生命周期头：
  - `Status`
  - `Owner`
  - `Scope`
  - `Canonical`
  - `Supersedes`
  - `Superseded_by`
  - `Last_reviewed`
- 从现在开始，新增目录必须同时满足：
  - 目录下存在 `README.md`
  - `README.md` 写明 owner、用途、允许文档类型、退出条件
  - 该目录无法被现有层级承接
- 任何新文档替代旧文档时，必须在同一刀完成：
  - 新文档落地
  - 旧文档标注 `Superseded_by`
  - 如旧文档不再活跃，则迁入 `docs/archive/`
  - 更新相关目录索引
- 当前文档与目录治理规范见：
  - `docs/governance/document-lifecycle.md`

**Current Handoff**
- 会话主题：NeoTrade3 已开始首批 3.0 Python 骨架实现
- 当前目标：在 NeoTrade3 中固化 data_control、orchestration 与 labs registry 的最小接口与配置结构
- 已确认约束：
  - NeoTrade2 保持运行基线
  - NeoTrade3 使用独立项目目录（本仓库根目录）
  - NeoTrade3 与 NeoTrade2 最终是完全独立系统，且该独立性要求立即生效
  - NeoTrade3 不得依赖 NeoTrade2 的运行时数据、数据库、服务、脚本、调度器或产物
  - NeoTrade2 仅可作为迁移参考、回归对照与功能梳理输入
  - NeoTrade3 v1 首批目标包括：数据主链、Daily Master Orchestrator、四个实验室统一注册、学习闭环最小版本
  - BaoStock 先不进入同日例行编排
- 已完成：
  - 创建了 NeoTrade3 独立项目骨架
  - 创建了 NeoTrade3 独立 `CLAUDE.md`
  - 创建了 NeoTrade3 独立 `PROJECT_STATUS.md`
  - 播种了 3.0 架构方案到 `docs/architecture/`
  - 播种了 orchestrator 和实验室注册配置骨架到 `config/`
  - 创建了新会话续接文档 `docs/handoffs/2026-05-19_session_resume_handoff.md`
  - 实现了 `neotrade3/data_control/` 最小骨架:
    - `models.py`
    - `pipeline.py`
    - `source_registry.py`
    - `ledger.py`
  - 新增 `config/data_control/source_registry.json`
  - `data_control` 已可加载 source registry，并生成 capture / compose / publish 的 plan ledger 占位台账
  - 实现了 `neotrade3/orchestration/` 最小骨架:
    - `models.py`
    - `config_loader.py`
    - `daily_master_orchestrator.py`
    - `preflight.py`
    - `ledger.py`
  - 实现了 `neotrade3/labs/registry.py` 并扩展了 `config/labs/labs_registry.json`
  - 实现了 `neotrade3/labs/runtime.py` 占位 runtime adapter
  - `labs_registry.json` 已升级为统一契约结构，明确每日任务入口、触发方式、依赖、产物与健康检查
  - `labs` 契约已与 `config/orchestrator/daily_master_orchestrator.json` 对齐
  - 扩展了 `config/orchestrator/daily_master_orchestrator.json` 的 phases + tasks 注册占位
  - 为 orchestrator 增加了 preflight report、placeholder task result、run/task ledger 占位模型
  - 实现了 `neotrade3/issue_center/` 最小骨架:
    - `models.py`
    - `collector.py`
  - `issue_center` 已可消费 orchestrator placeholder task results 与 task ledger，生成 issue events / issue cases 占位快照
  - 实现了 `neotrade3/learning/` 最小骨架:
    - `models.py`
    - `pipeline.py`
  - `learning` 已可消费 orchestrator / issue_center 占位输出，生成 metrics、adjustment candidates、audit records 占位快照
  - 实现了 `apps/worker/main.py` 最小启动入口，可串联 data_control、orchestration、issue_center、learning 的 bootstrap 快照生成
  - worker 已约定最小落盘路径:
    - `var/ledgers/bootstrap_runs/<date>/`
    - `var/artifacts/bootstrap_runs/<date>/`
  - 实现了 `apps/api/main.py` 最小只读入口，可通过 HTTP 暴露 healthz、bootstrap summary、bootstrap snapshot
  - `apps/api/main.py` 已补充细粒度只读域接口:
    - `data-control`
    - `orchestration`
    - `labs`
    - `issue-center`
    - `learning`
  - `apps/api/main.py` 已增加 `source=stored` 快照读取模式，可直接读取 `worker` 已落盘文件
  - `apps/api/main.py` 已补充统一错误返回结构，并加入最小内存缓存:
    - snapshot 读取缓存
    - labs/source registry 读取缓存
  - `apps/api/main.py` 已补充最小 CORS 响应头，允许 dashboard 从独立本地端口读取只读 API
  - 实现了 `apps/dashboard/main.py` 最小只读入口骨架，已按域接口加载:
    - `Overview`
    - `Data Control`
    - `Labs`
    - `Daily Orchestration`
    - `Issue Center`
    - `Learning`
  - `apps/dashboard/main.py` 已支持 `live/stored` 读取模式切换，并透传到 API 各域接口
  - `apps/dashboard/` 已完成首轮静态资源拆分:
    - `main.py`
    - `static/dashboard.css`
    - `static/dashboard.js`
  - `apps/dashboard/` 已完成第二轮展示层收敛:
    - 首页增加 summary cards 与全局状态/错误条
    - 各域增加摘要行与 `_meta` 信息展示
    - 保留可展开的原始 JSON payload
    - 浏览器端已统一解析 API 结构化错误
  - `data-control` 视图已补齐 source registry 缓存，并在 `_meta` 中暴露 `source_registry_cache_status`
  - `labs_registry` 与 `daily_master_orchestrator` 的实验室任务 `outputs` 契约已重新对齐
  - `orchestration` 的 `PlannedTask` 已保留 `outputs`，避免实验室产物契约在 plan/snapshot 中丢失
  - 新增运行说明 `docs/operations/bootstrap_runbook.md`，明确 worker / api / dashboard 的启动与联调顺序
  - 更新了 `README.md` 的入口索引与运行说明入口
  - 添加并通过了骨架级单元测试 `tests/unit/test_bootstrap_skeleton.py`
  - `tests/unit/test_bootstrap_skeleton.py` 已补充 HTTP 级端到端回归基线:
    - API `live/stored` summary 路径
    - API `bad_request` 错误路径
    - dashboard 壳层对 API base URL 与静态资源的联通性
  - 新增 `neotrade3/config_contracts.py`，把配置契约校验收敛为独立模块
  - `labs` / `source_registry` / `orchestrator` loader 现在会在加载阶段执行配置校验并抛出 `ConfigContractError`
  - `apps/api/main.py` 已新增 `GET /api/config-contracts` 只读域接口，暴露当前配置契约状态与摘要
  - `tests/unit/test_bootstrap_skeleton.py` 已补充配置契约失败路径测试与 `config-contracts` HTTP 回归
  - 已基于 NeoTrade2 代码库形成第三版功能说明书与功能台账基线:
    - `docs/migration/neotrade2_feature_manual_v3.md`
    - `docs/migration/neotrade2_feature_inventory.v3.json`
  - `v3` 已在 `strategy_and_lab`、`assistant`、`operations` 域下继续拆分子项，当前功能台账总数已扩展到 68 项
  - 已新增 `docs/migration/neotrade3_independence_principle.md`，明确 3.0 与 2.0 的独立性原则立即生效
  - 已新增 `docs/migration/neotrade3_ui_design_principles.md`，明确 3.0 前端 UI 必须独立设计并服务实验中枢、结果导向与实验自动化
  - 已新增研究模型与模块重定义说明（用于在迁移前先理顺 2.0 模块关系与 3.0 归口逻辑）:
    - `docs/architecture/neotrade3_research_model_and_module_taxonomy_v1.md`
  - 已新增研究目标与关键定义参考文档（包含模块重定义附录）:
    - `docs/architecture/neotrade3_research_goal_and_definitions_v1.md`
  - 新增 `neotrade3/migration/feature_manual.py`，统一加载和校验 2.0 功能台账
  - `apps/api/main.py` 已新增 `GET /api/migration/feature-manual` 只读域接口，当前默认暴露 `v3` 功能台账摘要与条目
  - `tests/unit/test_bootstrap_skeleton.py` 已补充 2.0 功能台账结构测试与 `migration/feature-manual` 路由、HTTP 回归，并升级为校验 `strategy_and_lab` / `assistant` / `operations` 域的新子项
  - 已新增 `strategy_and_lab` 域迁移落点映射工件:
    - `docs/migration/mappings/neotrade3_feature_mapping_strategy_and_lab_v1.md`
    - `docs/migration/mappings/neotrade3_feature_mapping_strategy_and_lab_v1.json`
  - 已新增 `assistant` 域迁移落点映射工件:
    - `docs/migration/mappings/neotrade3_feature_mapping_assistant_v1.md`
    - `docs/migration/mappings/neotrade3_feature_mapping_assistant_v1.json`
  - 已新增 `operations` 域迁移落点映射工件:
    - `docs/migration/mappings/neotrade3_feature_mapping_operations_v1.md`
    - `docs/migration/mappings/neotrade3_feature_mapping_operations_v1.json`
    - `docs/migration/mappings/neotrade3_feature_mapping_screeners_v1.md`
    - `docs/migration/mappings/neotrade3_feature_mapping_screeners_v1.json`
  - `apps/api/main.py` 已新增 `GET /api/migration/feature-mapping?domain=strategy_and_lab` 只读域接口，暴露当前迁移映射摘要与条目
  - `apps/api/main.py` 已扩展 `GET /api/migration/feature-mapping?domain=assistant`，暴露 assistant 域迁移映射摘要与条目
  - `apps/api/main.py` 已扩展 `GET /api/migration/feature-mapping?domain=operations`，暴露 operations 域迁移映射摘要与条目
  - `apps/api/main.py` 已新增 `GET /api/migration/feature-mapping?domain=screeners`，暴露 screeners 域迁移映射摘要与条目
  - `apps/api/main.py` 已新增 `GET /api/migration/feature-mapping-coverage?domain=...`，用于逐项确认时核对 inventory 与 mapping 的覆盖率一致性
  - `tests/unit/test_bootstrap_skeleton.py` 已补充 `feature-mapping` 路由与 HTTP 回归
- 2026-05-22（本轮对话已落地的关键能力）：
  - 数据更新：已支持独立更新行情，并将质量检查与交易日历更新纳入“可见/可验收”的链路。
  - 筛选器：支持一键批量运行启用筛选器；并提供 CSV 下载（面向团队）。
  - 监控池：支持查看成员列表、成员变化、CSV 下载；并支持手工监控池快照写入。
  - 股票 CHECK：前端提供股票 CHECK 入口，可从监控池成员列表一键触发检查。
  - 实验室入口：选股主链下提供“杯柄/老鸭头五图”入口，支持当日运行与结果下载。
  - 可用性与术语：不再让用户手动控制“发布成功/闸门”；以“数据是否就绪（能不能跑）”的直白提示替代；聚焦为默认展示模式。
  - API 结构：HTTP Handler 从 `apps/api/main.py` 抽到 `apps/api/http.py`，集中管理 CORS/鉴权/响应编码。
- 2026-05-27（结构性拆分继续推进）：
  - API 结构：shared types 抽到 `apps/api/shared.py`；Router 抽到 `apps/api/router.py`；`apps/api/http.py` 改为依赖新模块，`apps/api/main.py` 保持兼容导出。
  - 回归：`./.venv/bin/python -m pytest -q`（42 passed）。
  - API 结构：新增 `apps/api/service.py` 作为 Service 的稳定导出入口（当前仍从 `apps/api/main.py` 兼容导入），为后续把 `BootstrapApiService` 真正迁出做准备。
  - 数据：`POST /api/data-control/sync-daily-prices` 支持传 `target_date`（或 `date`）进行历史补齐（例如补齐 2026-05-25）。
  - 低频控制台（前端）：`section-neotrade3-enhanced` 新增“模拟交易状态/全历史回测报告（PDF）”面板，并将“模型运行/筛选器运行”从 simulated 改为真实调用。
  - 低频模型（后端）：新增 `POST /api/model/run`（低频 v16 模拟交易推进）、`GET /api/sectors/hot` 返回人气板块 + 龙头/中军/跟随 + 买入/离场信号 + 模拟持仓汇总。
  - 回测报告（PDF）：引入 `reportlab` 生成 PDF；新增 `POST /api/lowfreq/backtest/run` 生成全历史回测报告，并提供 `/api/lowfreq/backtest/reports/<report_id>.pdf|.json` 下载。
-  - 仓库清理：低频当前权威引擎保留为根目录 `lowfreq_engine_v16_advanced.py`；历史根目录低频引擎已迁到 `legacy/lowfreq/`，其余旧脚本继续归档到 `scripts/archive/*`；删除重复文档 `NeoTrade3实施交接文档_副本.md`。

- 2026-06-06（本轮新增能力与交付物）：
  - A 股中市值审计（200—500 亿）：新增 `GET /api/ashare/midcap/audit?date=YYYY-MM-DD`（同时支持 `/api/v1/...`），输出 `qualified_clean / qualified_flagged / excluded` 三类结果，并给出每只股票的 `issues`（含 `risk_level` 与证据字段）。
  - 概念主线计算：API 已具备 `GET /api/concepts/mainline` 与 `GET /api/concepts/mainline/detail`（同样支持 `/api/v1/...`），对概念板块给出热度评分与主线排序所需字段（heat / MA20/60/90 / mainline_score 等）。
  - 低频研究报告交付（LaTeX）：已在 `var/tmp/lowfreq_research_report/latex/main.tex` 固化研究报告排版源文件，并可用 `tectonic` 编译为 `main.pdf`（同目录产出）。
  - 环境约束（重要）：当前执行环境对 `~/Downloads` 写入受限，报告交付建议以项目内路径为准（例如 `var/tmp/lowfreq_research_report/latex/main.pdf`），再由本机终端或 Finder 手工拷贝到 Downloads。
- 2026-07-07（M1 Phase 1 首批正式对象已进入实现态）：
  - 已完成 `Phase 0` 仓库现实审计，并固化为文档：
    - `docs/superpowers/specs/2026-07-07-m1-phase0-repo-audit.md`
  - 已完成 `D1 / D7 / D8` 首批正式契约定义：
    - `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-contract-definition.md`
  - 已完成 `Phase 1` 实施计划与任务清单：
    - `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-implementation-plan.md`
    - `docs/superpowers/specs/2026-07-07-m1-phase1-d1-d7-d8-task-list.md`
  - 已新增 `M1` 首批正式对象定义与投影/质量层：
    - `neotrade3/data_control/contracts.py`
    - `neotrade3/data_control/projections.py`
    - `neotrade3/data_control/quality.py`
  - 已在 `neotrade3/data_control/__init__.py` 导出首批正式对象、投影函数、`quality_status` / `freshness_proof` / `attention_item` 构造器。
  - 已在 API 暴露首批正式对象独立读取入口：
    - `GET /api/data-control/m1/d1/daily-price-facts?date=YYYY-MM-DD`
    - `GET /api/data-control/m1/d7/security-master?codes=...`
    - `GET /api/data-control/m1/d7/trading-day-status?date=YYYY-MM-DD`
    - `GET /api/data-control/m1/d8/trading-profiles?date=YYYY-MM-DD`
  - 上述四个正式入口当前统一返回：
    - `quality_status`
    - `freshness_proof`
    - `attention_items`
    - `_meta.formal_object`
  - `D8` 当前已按正式契约收紧窗口语义：
    - 5 日窗口不足返回 `null`
    - 20 日窗口不足返回 `null`
    - `return_20d` 只在完整 20 日窗口时输出
  - 当前已明确把以下对象留在 `M1` 正式契约之外：
    - `theme_momentum`
    - `market_phase`
    - `sector_rotation`
    - `stock_tiering`
    - `factor_matrix`
    - `config_leader_candidate`
    - `institutional_attention_candidate`
    - `trading_leader_candidate`
  - `/api/data-control` 总览当前已显式暴露：
    - `m1_formal_contracts`
    - `compatibility_boundaries`
    - 正式入口与兼容旧入口边界
  - `DataControlPipeline.capture/compose/publish` 当前写出的 ledger / artifact 已包含：
    - `m1_formal_artifacts.catalog`
    - `m1_formal_artifacts.objects`
    - `m1_formal_artifacts.summary`
  - `BootstrapWorkerApp._load_data_control_stage_summary()` 当前已把 `m1_formal_artifacts.summary` 带入 `snapshot["data_control"]["stage_summary"]`。
  - `IssueCenterCollector.collect()` 当前已可消费 `data_control.stage_summary`，并为 `freshness_verdict in {"partial", "not_ready", "unknown"}` 或 `attention_count > 0` 的正式对象追加 issue 事件。
  - `PreflightRunner.build_report()` 当前已新增 `m1_formal_contract_check`：
    - 若同日尚无 `data_control` 产物，则不阻塞首次运行
    - 若同日已有 `data_control` 产物且正式对象证据为 `not_ready / unknown`，则明确 fail
    - 若仅为 `partial`，则给 warning
  - 已新增并通过聚焦单元测试：
    - `tests/unit/test_m1_phase1_formal_objects.py`
  - 本轮代码级最小验证结果：
    - `python3 -m pytest -q tests/unit/test_m1_phase1_formal_objects.py` -> `8 passed`
    - `python3 -m py_compile ...` 已通过本轮涉及文件的语法校验
- 2026-07-13（M4/M5 基线推进实现态更新）：
  - `M4` 已完成 benchmark 主链接入统一运行路径：
    - `neotrade3/benchmark/cli.py`
    - `config/benchmark/validation_seed_manifest.json`
    - `config/benchmark/validation_seed_v2_manifest.json`
  - `M4` 已具备基准结果持久化与查询基线：
    - `neotrade3/benchmark/artifact_writer.py`
    - `neotrade3/benchmark/run_ledger.py`
    - 已支持 `write/read/list` benchmark run ledger
    - 已支持 persisted artifact raw readback
  - `M4` 已补齐 persisted artifact 的类型化回读基线：
    - `BenchmarkBatchRunResult.from_dict(...)`
    - `BenchmarkAssessmentResult.from_dict(...)`
    - `AssessmentSummary.from_dict(...)`
    - `GapRecord.from_dict(...)`
    - `TraceBundle.from_dict(...)`
    - `InteractionGuardrailBreach.from_dict(...)`
    - `read_benchmark_batch_run_result(...)`
  - `M5` 已完成治理对象核、`M4 -> M5` handoff、artifact、ledger/readback、runtime/CLI、orchestrator-fit 基线：
    - `neotrade3/governance/contracts.py`
    - `neotrade3/governance/handoff.py`
    - `neotrade3/governance/artifact_writer.py`
    - `neotrade3/governance/run_ledger.py`
    - `neotrade3/governance/runtime.py`
    - `neotrade3/governance/cli.py`
    - `apps/worker/main.py`
    - `config/orchestrator/daily_master_orchestrator.json`
  - `M5` 当前已在 worker/orchestrator 中注册显式 `GOVERNANCE` 阶段，且 `PlannedTask.args_template` 可透传到执行面。
  - `M5` 已完成 candidate validation outcome 的独立真值面与外部触发面：
    - persisted truth 位于 `governance_candidate_validations` 独立命名空间
    - governance CLI 已支持 `candidate-validation-outcome`
    - worker 已支持 `--mode governance_candidate_validation_outcome`
    - API 已支持 `mode="governance_candidate_validation_outcome"`
  - `M5 candidate validation outcome` 当前显式输入 contract 固定为：
    - `source_run_id`
    - `validation_result`
  - `M5` 已完成 `candidate outcome upstream -> candidate_validation_outcome` bridge owner，并进入 `worker/orchestrator` on-demand 与 `daily` scheduled adoption：
    - shared runtime 已支持 `run_governance_candidate_outcome_bridge(...)`
    - worker governance executor 已支持 `task_id="governance.candidate_outcome_bridge"`
    - `daily_master_orchestrator` 已注册 `governance.candidate_outcome_bridge`
    - 当前显式输入 contract 固定为 `source_run_id`
  - `M5` 已完成 final validation selection/projection 的独立真值面与 worker/orchestrator on-demand adoption：
    - persisted truth 位于 `governance_final_validations` 独立命名空间
    - shared runtime 已支持 `run_governance_final_validation_selection(...)`
    - worker governance executor 已支持 `task_id="governance.final_validation_selection"`
    - 当前显式输入 contract 固定为 `source_run_id`
    - 当前未暴露为独立 CLI / API mode，但已进入 `daily` scheduled adoption
  - `M5` 下游 `reject_execution` 与 `status_transition` 当前已消费 persisted outcome truth。
  - `M5` 已完成上游真值切换基线：
    - shared runtime 不再重跑 benchmark manifest
    - governance CLI 改为显式接收 `benchmark_run_id`
    - worker/orchestrator governance task 改为消费 `benchmark_run_id`
    - shared runtime 当前只消费 persisted typed `M4` benchmark artifact
  - `M3 backhalf` 已完成 position snapshot production carrier 基线：
    - `lowfreq_engine_v16_advanced.py` 当前会在正式 `sell_signal_audit` 事件中附带 canonical `position_contract_snapshot`
    - 该 carrier 已稳定暴露 `hold_state / exit_ready / exit_scope / exit_reason_type / current_stage / decision / next_action / last_transition`
    - `position_contract_snapshot` 当前也已显式暴露 `local_exit_semantics / global_thesis_end_semantics`
  - `M3 backhalf` 已完成 formal object/owner 补齐：
    - `neotrade3/decision_engine/contracts.py` 已具备 `HoldState / ExitState / DecisionLifecycleEvent / DecisionLifecycleLog`
    - `neotrade3/decision_engine/hold_exit_bridge.py` 已把 canonical snapshot 透传为 formal `HoldState / ExitState`
    - `neotrade3/decision_engine/decision_lifecycle_log.py` 已可把 `sell_signal_audit` formalize 为 per-stock lifecycle logs
  - 当前必须明确的边界：
    - `M4` 仍是 validation-seed benchmark 基线，不等于完整 benchmark 层
    - `M5` 仍是治理接线基线，不等于完整 validation/promotion/reject 闭环
    - `M5 candidate validation outcome` 的显式人工触发面当前仍是 on-demand contract；scheduler-facing `daily` 主链当前通过 `candidate_outcome_bridge -> final_validation_selection` 闭环，不等于更宽的 CLI / API adoption
    - `M3 backhalf` 当前 formal object/owner 已补齐，但下游消费面与状态文档此前存在滞后，不应再把 `decision_lifecycle_log` 和局部/全局退出显式语义记为未完成
  - 当前最直接下一步：
    - 审计 `reject_execution` 与 `status_transition` 是否需要 scheduler-facing adoption，并明确它们与 `daily` 主链的依赖与失败闭合语义
    - 决定 `final_validation_selection` 是否需要更宽的 CLI / API adoption
    - 继续推进 `M5` 完整闭环对象、`M4` 完整 benchmark、version unification、`M6 Delivery Ready`
- 2026-07-14（M5 治理收口与验收入口更新）：
  - `M5 candidate outcome upstream producer` 已完成，并以实验侧持久化真相作为唯一 `candidate_run_id` 来源：
    - shared runtime 已支持 `run_governance_candidate_outcome_upstream_producer(...)`
    - fail-closed 语义已收紧为：证据不足、pending 不唯一或 blocker 非 active 时禁止产出治理结果
  - `M5 candidate outcome bridge` 已形成 scheduler-facing 自动真相物化链：
    - `daily` 当前固定执行 `benchmark.materialize_run -> governance.materialize_handoff -> governance.candidate_outcome_bridge -> governance.final_validation_selection`
    - `config/benchmark/validation_seed_manifest.json` 已补齐 `candidate_run_context`，用于满足 `daily` 基线的治理真相输入要求
  - `M5 final validation selection` 当前边界已明确：
    - shared runtime 已支持 `run_governance_final_validation_selection(...)`
    - worker/orchestrator 已支持 explicit on-demand 与 `daily` scheduled adoption
    - 当前仍未暴露独立 CLI / API mode
  - `M5 reject_execution` 与 `status_transition` 的调度边界已明确：
    - 两者属于强副作用治理动作
    - 当前明确不进入 `daily` 主链
    - 当前仅允许在显式 on-demand 链路中触发，避免自动化误写治理结果
  - `M5` 已完成显式治理动作串联链：
    - shared runtime 已支持 `run_governance_reject_transition_chain(...)`
    - worker governance executor 已支持 `task_id="governance.reject_transition_chain"`
    - bootstrap worker 已支持 `run_governance_reject_transition_chain_on_demand(...)`
    - API 已支持 `mode="governance_reject_transition_chain"`
    - 当前显式输入 contract 固定为 `source_run_id`
    - 仅当 final validation outcome 为 `rejected` 时继续执行 `reject_execution -> status_transition`
  - `M5` 已补齐最小 HTTP 级端到端验收入口：
    - 已新增 integration smoke：`tests/integration/test_m5_governance_end_to_end_smoke.py`
    - 已新增 runner：`scripts/smoke_m5_governance_end_to_end.sh`
    - 当前可用单命令验收 `daily` 治理真相物化链与 `governance_reject_transition_chain` 显式链路
  - 当前必须明确的边界补充：
    - `daily` 只自动物化治理真相，不自动执行带强副作用的 reject/status transition
    - `M5` 当前已具备 scheduler-facing 真相物化与 on-demand 治理动作链，但仍不等于完整 promotion/reject 全闭环
    - 当前最新 smoke 仅覆盖 `validation_seed` 基线，不等于 `M4` 已完成正式 benchmark 扩展
- 2026-07-14（M4 replay manifest 最小切片更新）：
  - `M4` 已新增 `inline replay manifest` 输入模式（与 `validation_seed` 并行，不替代 seed 基线）：
    - `config/benchmark/formal_replay_manifest.json`
    - 当前 replay 样例固定为单样本最小载荷，用于验证 benchmark 可直接消费 `M2/M3` formal snapshot 形状
  - `M4` runner 已完成 seed/replay 双分支收口：
    - `BenchmarkRunManifest` 已支持 `replay_sample`
    - 有 `replay_sample` 时允许省略 `registry_path`（内部标记为 `inline_replay_manifest`）
    - replay 分支通过 payload 还原 `SmallCycle` 后复用现有 assembler，统一产出 `BenchmarkBatchRunResult` artifact/ledger
  - `M4` 已补齐 replay 聚焦回归：
    - `tests/unit/test_m4_benchmark_replay_manifest.py`
    - 覆盖 replay manifest 解析、materialize/readback、缺关键字段 fail-closed
  - 当前必须明确的边界补充：
    - 本次仍是 `inline replay`，未对接 persisted formal artifact refs
    - 不改 `daily`、API、worker、governance 触发面
    - replay 当前仅验证最小单样本 contract，不等于完整 benchmark 扩展完成
- 2026-07-14（M4 persisted refs resolver contract + mock/stub resolver 更新）：
  - `M4` 已新增 `resolver_refs` 输入 contract，用于把 replay 从 `inline payload` 向 `persisted refs` 演进：
    - `BenchmarkPersistedRef`
    - `BenchmarkReplayResolverRefs`
    - `config/benchmark/formal_replay_refs_manifest.json`
  - `M4` 当前已完成 `resolver_stub` 路径验证：
    - replay runner 可在 `benchmark` 子域内把 `resolver_refs` 解为与 `inline replay` 等价的 `m2_cycle / m2_shadow_bundle / m1_context / m3_context` payload
    - `resolver_stub` 当前仅用于验证 resolver 落点、类型校验与失败闭合语义，不等于已接入真实 persisted truth-source
  - `M4` 已补齐 resolver 聚焦回归：
    - `tests/unit/test_m4_benchmark_replay_manifest.py` 已覆盖 `resolver_refs` 解析成功、materialize/readback 成功、缺 ref 失败、`object_type mismatch` 失败
  - 当前必须明确的边界补充：
    - `resolver_refs` 当前只支持 `resolver_stub`，不支持真实 `M2/M3` persisted artifact/ledger/readback owner
    - 当前仍未新增独立 `M2/M3` persisted truth-source；`lowfreq sim state.formal_front` 仍只视为压缩投影，不视为 canonical truth-source
    - 本次仍只改 `benchmark` 子域输入解析层，不改 `BenchmarkBatchRunResult` 输出契约，不改 `G/M5` 消费面
- 2026-07-15（M4 persisted refs real truth-source / local projection 更新）：
  - `M4 resolver_refs` 当前四块输入都已具备真实路径：
    - `m2_cycle_ref(real)` -> `5d6b394 feat(m2): add small cycle persisted truth source`
    - `m2_shadow_bundle_ref(real)` -> `d90a3c6 feat(m2): add shadow bundle persisted truth source`
    - `m1_context_ref(real-local)` -> `ec8b1ce feat(m4): add m1 context local projection`
    - `m3_context_ref(real-local)` -> `50c5c4b feat(m4): add m3 context local projection`
  - 当前 `resolver_refs` 已不再只停留在 `resolver_stub`：
    - `m2_cycle_ref` 与 `m2_shadow_bundle_ref` 已接入 `M2` persisted truth-source
    - `m1_context_ref` 与 `m3_context_ref` 已接入 `benchmark` 子域 local persisted projection
  - `tests/unit/test_m4_benchmark_replay_manifest.py` 当前已覆盖 mixed mode success 与 fail-closed：
    - `real m2_cycle_ref + real m2_shadow_bundle_ref + real m1_context_ref + real m3_context_ref`
    - 缺失 ref / `object_type mismatch` / `object_version mismatch`
  - 当前必须明确的边界补充：
    - `m1_context_ref` 与 `m3_context_ref` 当前仍是 `benchmark local projection`，不是 `M2/M3` 全域 canonical truth-source
    - 本轮真实化仍只改 `benchmark` 输入解析层与局部 owner，不改 `BenchmarkBatchRunResult` 输出契约，不改 `G/M5` 消费面
    - `lowfreq sim state.formal_front` 仍只视为压缩投影，不视为 canonical truth-source
- 2026-07-15（M3 canonical owner / M1 semantic closure 更新）：
  - `m3_context` 已从 `benchmark local projection` 上提为 `decision_engine` canonical owner：
    - `DecisionM3FrontContext`
    - `24c38c8 feat(m3): add front context canonical owner`
  - `benchmark` replay 当前已兼容两类 `m3_context_ref` 来源：
    - `benchmark_m3_context_projection`
    - `decision_engine_m3_front_context`
  - `m1_context` 已明确不再推进 canonical owner：
    - `43df792 docs(spec): add m1 semantic closure design`
    - `9a228f9 refactor(m1): harden benchmark compatibility fail-closed`
  - 当前必须明确的边界补充：
    - `BenchmarkM1ContextProjection` 仅作为 `benchmark replay compatibility projection` 保留
    - `m1_context` 不再表述为正式 `M1` 对象或未来 canonical owner 候选
    - `m3_context` 当前仅前半段 `front-only` 形状具备 canonical owner，未扩展到 backhalf

## 文档一致性说明

- 本仓库存在 [NeoTrade3实施交接文档.md](file:///Users/mac/NeoTrade3/NeoTrade3实施交接文档.md) 作为历史交接材料，其中部分描述可能来自较早阶段或不同实现路径，未必与当前代码完全一致。
- 新会话续接以本文件为准：只记录“已经存在且可运行”的入口、约束与验收口径；其它文档仅作为背景参考，使用前需按代码现状核对。

## 当前项目进度总览

### 已完成部分

- `M1 Phase 1（首批正式对象）`
  - 已完成 `D1 / D7 / D8` 正式契约、API 独立读取入口、`quality_status / freshness_proof / attention_items`、data_control artifact 汇总、issue_center/preflight 最小消费。
- `M2/M3 前半段（formal front）`
  - 已完成 `small_cycle / identify_state / tracking_state / entry_state` 正式对象与组装器。
  - 已完成引擎 formal front 接线、API formal-front 消费切片、workbench 优先级修正、top200 attribution report 依赖的公共投影拆分。
- `M3 backhalf（最小主链）`
  - 已完成 `position_contract_snapshot` carrier、`HoldState / ExitState / DecisionLifecycleLog` formal object/owner、局部/全局退出显式语义。
- `M4 benchmark 基线`
  - 已完成 mainline runner、artifact/ledger、typed readback、`validation_seed` manifest 基线。
  - 已完成 `inline replay manifest` 最小切片（commit `0b84a4a`）。
  - 已完成 `resolver_refs` contract 与 `mock/stub resolver` 路径（commit `bca1876`），并验证其可在 `benchmark` 子域内解为 `inline replay` 等价 payload。
  - 已完成 `resolver_refs` 四块真实路径收口：
    - `m2_cycle_ref(real)`（commit `5d6b394`）
    - `m2_shadow_bundle_ref(real)`（commit `d90a3c6`）
    - `m1_context_ref(real-local)`（commit `ec8b1ce`）
    - `m3_context_ref(real-local)`（commit `50c5c4b`）
  - 已完成 `m3_context` 从 `benchmark local projection` 上提到 `decision_engine` canonical owner（commit `24c38c8`）。
  - 已完成 `m1_context` 语义收口：不再推进 canonical owner，仅保留 `benchmark` 兼容层并补齐 fail-closed 边界（commit `43df792`、`9a228f9`）。
- `M5 governance 基线`
  - 已完成 governance contracts / handoff / artifact / ledger / runtime / CLI / worker / orchestrator-fit 基线。
  - 已完成 `candidate validation outcome` persisted truth 与 `runtime -> CLI -> worker -> API` adoption。
  - 已完成 `candidate outcome upstream producer`、`candidate_outcome_bridge`、`final_validation_selection`，并形成 `daily` 真相物化链。
  - 已完成 `reject_transition_chain` 的 `runtime -> worker -> API` adoption；`reject_execution` 与 `status_transition` 保持 on-demand，不进入 `daily`。
  - 已完成最小 HTTP 级 end-to-end smoke 与 runner。

### 未完成部分

- `M1`
  - 仅首批正式对象已落地；`M1 Phase 1` 不是整体完成态。
- `M2/M3`
  - formal front 与 backhalf 主干已落地，但这不等于 `M2/M3` 全域完成；后续仍需继续按消费面与真相源收口。
- `M4`
  - 当前仍不是完整 benchmark 层。
  - 当前 `resolver_refs` 已具备真实路径，但其中：
    - `m1_context_ref` 仅为 `benchmark compatibility projection`，不是 `M1` canonical truth-source。
    - `m3_context_ref` 已具备 `decision_engine front-only canonical owner`，但这不等于 `M3` 全域 canonical truth-source。
  - 当前已新增 `M2` persisted truth-source（`small_cycle` / `shadow_bundle`），但 `lowfreq sim state.formal_front` 仍只视为压缩投影，不视为 canonical truth-source。
- `M5`
  - 当前已具备治理真相物化链与显式治理动作链，但仍不等于完整 `validation / promotion / reject` 全闭环。
  - `final_validation_selection` 当前仍未暴露独立 CLI / API mode。
- `M6 Delivery Ready`
  - 仍未启动最小正式交付与观测主链建设。
- `统一版本体系`
  - 当前脚本策略线与系统内 `analysis_version` 仍未统一为单一版本真相源。

### 当前建议下一步

- 优先更新后续设计与状态文档口径，显式区分：
  - `m1_context` 仅是 `benchmark` 兼容层
  - `m3_context` 已有 `decision_engine front-only canonical owner`
- 在此基础上，再决定下一刀是继续推进 `M4` benchmark 完整层，还是转向 `M5` / 统一版本体系等仍未收口主线。

## 2026-07-07 M2/M3 前半段最小消费切换实现态更新

- 已完成范围：
  - `M2 small_cycle`
  - `M3 identify_state`
  - `M3 tracking_state`
  - `M3 entry_state`
  - 引擎并行输出 `legacy + formal`
  - API formal 压缩投影
  - workbench `formal_front` 优先消费
  - top200 attribution report 快照层 `formal` 优先、旧字段兜底
- 已落地正式承载包：
  - `neotrade3/cycle_intelligence/`
  - `neotrade3/decision_engine/`
- 已实现正式组装入口：
  - `build_small_cycle_from_m1(...)`
  - `build_m1_constraints_ref(...)`
  - `build_identify_state_from_formal_inputs(...)`
  - `build_tracking_state_from_formal_inputs(...)`
  - `build_entry_state_from_formal_inputs(...)`
- 已有实现态验证：
  - `python3 -m pytest -q tests/unit/test_m2_m3_contract_skeleton.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_intent_conflicts.py tests/unit/test_lowfreq_formal_front_projection.py tests/unit/test_lowfreq_workbench_formal_consumption.py tests/unit/test_lowfreq_phase5_projection_sync.py` -> `73 passed`
  - `python3 -m py_compile ...` 已通过本轮涉及文件的最小语法校验
- 当前 git 边界状态：
  - 已提交对象层：`8ba2f84 feat(m2-m3): add formal front contracts and assemblers`
  - 已提交引擎层：`4c416e6 refactor(engine): add lowfreq signal structure baseline`、`3c9393b feat(engine): wire lowfreq formal front chain`、`a160796 feat(engine): expose lowfreq execution result summary`、`1ccb680 fix(engine): clamp invalid lowfreq annual return`、`0c39ca6 fix(engine): honor strong leader soft release flag`、`9ea8f33 feat(engine): enrich lowfreq execution audit events`
  - 已提交 API/workbench 层：`05d5c46 fix(api): enforce formal priority in lowfreq workbench`、`1b6e5ad feat(api): carry lowfreq formal front into hot sectors`、`30723fa feat(api): persist lowfreq formal front in signal memory`、`de8d08c feat(api): project lowfreq formal front into score pool`、`7a097c5 fix(api): add lowfreq formal front status helpers`、`8c36629 feat(api): project lowfreq formal front into next candidates`
  - 已提交 report/public projection 依赖：`753ede8 refactor(m3): extract shared lowfreq formal front projection`、`fb0a629 refactor(report): split candidate and entry attribution flow`
  - 当前应显式区分：上述 formal-front 主线已进入提交历史；working tree 中剩余脏改动并不等于“formal-front 主线整体仍未提交”
- 当前最重要的事实：
  - `M2/M3` 前半段 formal 消费切换在代码层面已经可运行、可测试
  - 且核心 consumer 链已通过多段窄提交进入历史
  - 后续继续工作时，必须显式区分“已提交的 formal-front 主线”与“当前 working tree 中其他未审计脏改动”

## 2026-07-22 仓库清理与单主线恢复（Kimi Work 首个工作周期）

- 协作方变化：TRAE Work 不可用（无法打开本地目录，历史记录丢失），项目转入 Kimi Work 协作；`CLAUDE.md` 工作规则继续生效。Kimi Work 侧另有持久记忆 `agents/main/memory/neotrade3-project.md`。
- 目标口径（owner 当面校准，覆盖 code-wiki 旧表述）：20–60 个交易日内有机会涨 30%+；100 个交易日内有希望涨 50%+。注意：rulebook `RB.M2.CERTAINTY_SHORT.001`（占位 10–20 日/+30%，标“待补齐”）与 owner 短档口径不一致，待下次更新 rulebook 时按 owner 口径回填（需先确认）。
- 混沌模型：owner 明确“需要单独专项讨论”；在那之前，不把 `chaos_rulebook.md` 的 SSOT 表述当作推进代码切换的依据，文档与代码现状保持原样。
- 仓库清理（5 个 commit，分支 `chore/repo-cleanup`，已合并并推送）：
  - `ba692df` 在途混沌快照脚本存检（py_compile 通过）
  - `de68ee7` 删除根目录残留（probe plist×2、0 字节 project_tree、egg-info）；未跟踪 `.uploads` 与 `var__repo_dir_20260721_165702` 移至 `/Volumes/NEO/NeoTrade3_attic/20260722_repo_cleanup/`
  - `ab99d43` 4 份规划 docx → `docs/archive/planning_v0/`；已闭环调度调试记录 → `docs/archive/`
  - `0124188` `.gitignore` 将 `var` 按外挂盘整体忽略（+attic/egg-info 规则）；清除失效 var .gitkeep
  - `c9d2896` 孤儿脚本（`run_autore.py`、根目录 `sector_rotation.py`、`generate_handover.js`）→ `scripts/archive/`（引用证据见提交信息）
  - `legacy/` 按文档定位保留（回退对照，无活代码依赖）
- 分支治理：`wip/20260721-workspace-snapshot` 积压的 128 文件 / ~1.7 万行真实工作随本轮回归；本地与 GitHub 均已恢复**单 main 主线**（origin 已同步至 `c9d2896`）。
- 测试基线（新基线）：`.venv/bin/python -m pytest tests -q --tb=line` → **974 passed in 39s**。
- 运行时状态：`.venv` 已重建（Homebrew python3.10.20 + `pip install -e ".[dev]"`），launchd 三个服务（`com.neotrade3.api`、`com.neotrade3.frontend_gateway` exit 78、系统域 `com.neotrade3.scheduler`）的解释器路径已恢复有效，但**服务尚未重启**（owner 暂缓）；`tushare`、`apscheduler` 未安装（pyproject 未声明，`tushare` 属缺失依赖）。
- 磁盘事实：系统盘 142GB 可用 / NEO 917GB 可用；仓库本体 ~55MB；此前撑满磁盘的真因是 TRAE ai-agent 目录（100+GB），已迁至 NEO。
- 下一步待办（按序）：specs 436 份引用闭包归档 → `scripts/` 一次性脚本梳理 → LaunchAgents 墓园（需 owner 确认）→ `apps/dashboard/` 死代码；专项：混沌模型讨论、运行时服务重启。


---

## 2026-07-22 specs 归档与 GitHub CI 修复（Kimi Work 第二工作周期）

- specs 归档：`b0c0c2b` 将 414 份历史 specs 移入 `docs/archive/specs/`（保留 21 份活文档，`docs/archive/specs/README.md` 说明归档口径）；`6f952f9` 为交接存检。
- GitHub CI 失败根因（三类，均已修复）：
  1. 后端 3 个测试依赖生产库/真实文件：CI 上 stock_db 为空或兄弟测试留下的 0 字节库，`/api/lowfreq/*` 返回 500；
  2. 前端 `eslint.config.js` 缺 node / vitest globals，构建期报错；
  3. wip 批次漏连前端 `api.js` 的 `getOpsCenterSummary`（后端 `/api/ops-center/summary` 早已存在）→ build 失败。
- 后端修复（`17d30d6`）：`labs/runtime.py::_enrich_from_db` 加表存在性守卫（空库降级而非 500）；`data_control/pipeline.py` 的 `_project_root()`/`_stock_db_path()` 改为实例方法并支持 `project_root=` 注入（`from_registry_file` 同参），`apps/worker/main.py` 传入 `project_root=self.project_root`——同时消除了"测试用种子库时把日历覆盖写到 NEO 真实库"的隐患；`tests/integration/test_http_smoke.py` 新增 `_prepare_seeded_project_root`（复制 labs/orchestrator/source_registry 配置 + 种子 daily_prices/stocks，口径：pct 百分制、amount/volume≈close）；`tests/unit/test_bootstrap_skeleton.py` 用 `NEOTRADE3_STOCK_DB_PATH` 指向种子库、stub `_lowfreq_next_trading_day`。
- 前端修复（`6a81bbe`）：`eslint.config.js` 增加 node（vite.config/server）与 vitest+node（*.test）两个 globals 块；清理 Lowfreq.jsx / OpsCenter.jsx / Screeners.jsx 未用符号；`StockCodeLink.jsx` 辅助函数抽到 `src/components/stockCodeUtils.js`；`api.js` 补 `getOpsCenterSummary`。
- 验证基线（双环境，均本地亲测）：后端 `.venv/bin/python -m pytest tests -q` 有 NEO 974 passed (29s) / 无 NEO 类 CI 环境 974 passed (21s)；前端 neotrade3-dashboard 四步全过（npm ci ✓、lint 0 error 1 warning ✓、78 tests ✓、build 794ms ✓）。GitHub Actions 实际结果未直接核验（`gh` 未登录），以 owner 邮件确认为准。
- 环境陷阱（长期有效）：`var` 是指向 `/Volumes/NEO/NeoTradeDB/var` 的符号链接；**checkout 清理前旧 commit 会用 tracked 的 var 目录挤掉该链接**；恢复：`ln -s /Volumes/NEO/NeoTradeDB/var var`。对 `var` 禁用 `rm -rf`；类 CI 模拟用 `mv var /tmp` 暂存再还原，事后 `readlink var` 验证。
- 下一步待办（按序）：确认 GitHub CI 转绿 → `scripts/` 一次性脚本梳理 → LaunchAgents 墓园（需 owner 确认清单后执行 bootout）→ `apps/dashboard/` 死代码；专项：混沌模型讨论、运行时服务重启（owner 暂缓）。


---

## v1 Priorities

1. data control skeleton
2. daily master orchestrator skeleton
3. lab registry skeleton
4. learning loop scaffold
5. issue center scaffold

## Non-Goals For Current Phase

- 不切换 NeoTrade2 生产写入责任
- 不立即迁移旧 cron 或旧 dashboard
- 不在 bootstrap 阶段实现完整业务逻辑
- 不把 2.0 的历史目录结构原样带入 3.0

## Session Resume Entry

新会话开始时，按以下顺序读取:

1. `CLAUDE.md`
2. `PROJECT_STATUS.md`
3. `docs/handoffs/2026-07-07_m2_m3_minimal_consumption_switch_handoff.md`
4. `docs/handoffs/2026-07-07_m1_phase1_formal_objects_handoff.md`
5. `docs/handoffs/2026-05-19_session_resume_handoff.md`
6. `docs/architecture/neotrade3_master_architecture_and_migration_plan_v1.md`
7. `NeoTrade3实施交接文档.md`（背景参考；以代码现状核对）
8. `config/orchestrator/daily_master_orchestrator.json`
9. `config/labs/labs_registry.json`
