Status: reference
Owner: platform / model taxonomy
Scope: Snapshot checklist for current repo implementation status against M1~M6 template
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-16

# M1~M6 分层验收 Checklist（当前实现状态快照）

日期：2026-07-16

模板来源：[2026-07-16-m1-m6-checklist-template.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-16-m1-m6-checklist-template.md)

## 1. 口径与边界

- 本文件仅勾选“能在仓库中直接定位到证据”的项；无法定位证据的项保持未勾选。
- 证据优先使用代码位置（文件+行号范围）；仅在代码证据不足时引用 design 文档。

## 2. M1 事实层（Fact Layer）

### 2.1 Checklist

- [ ] 事实对象清单已冻结（至少包含核心事实表/派生事实表的范围与命名）
  - 证据：未在当前切片内定位到“事实对象清单冻结”的单一真相源文档/清单文件（仅定位到设计文档与若干事实写入/管线代码）。
- [x] 主事实链路的刷新契约已定义（输入/输出/依赖/频率/完成条件）
  - 证据：DataControl capture/compose/publish 步骤定义：[pipeline.py:L27-L63](file:///Users/mac/NeoTrade3/neotrade3/data_control/pipeline.py#L27-L63)
  - 证据：Worker 将 DataControl 纳入 daily 运行计划并执行：[main.py:L737-L781](file:///Users/mac/NeoTrade3/apps/worker/main.py#L737-L781)
- [x] 数据质量证明可输出（完整性、新鲜度、时点一致性、口径稳定性）
  - 证据：权威行情更新结果包含质量门禁与格式门禁状态（quality_gate/format_gate）：[main.py:L11345-L11433](file:///Users/mac/NeoTrade3/apps/api/main.py#L11345-L11433)
  - 证据：DataControl 汇总包含 freshness/attention 槽位（freshness_proof/attention_items）：[pipeline.py:L97-L118](file:///Users/mac/NeoTrade3/neotrade3/data_control/pipeline.py#L97-L118)
- [ ] 缺失与异常可见（Attention 或等价机制，能指向缺口原因与定位线索）
  - 证据：存在 attention_items 槽位但未在当前切片内定位到“对外输出/端点/稳定落盘形态”的统一证据：[pipeline.py:L97-L118](file:///Users/mac/NeoTrade3/neotrade3/data_control/pipeline.py#L97-L118)
- [ ] 关键事实读取具备只读 API 或内部稳定访问入口（含错误语义）
  - 证据：本切片仅定位到“事实写入/更新”接口与管线；未定位到“关键事实只读查询 API”的统一入口。

## 3. M2 周期识别层（Cycle Layer）

### 3.1 Checklist

- [ ] 周期对象契约已冻结（字段、语义、版本、可追溯来源）
  - 证据：存在形式化对象 skeleton 与校验入口（SmallCycle 等）：[contracts.py:L1-L106](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/contracts.py#L1-L106)
- [ ] 周期识别入口已存在（可调用/可复现），且依赖清单明确（M1 事实输入范围）
  - 证据：未在当前切片内定位到明确的“周期识别 runtime/CLI/API 入口”与调用示例。
- [ ] 周期结果可读回（只读 API 或内部入口），支持按 key 查询与列表检索
  - 证据：未定位到对外 read/list/download API；仓库内存在 contracts，但缺少对外读回证据。
- [ ] 周期质量状态可输出（例如数据不足、模型未收敛、输入缺失等原因枚举）
  - 证据：未在当前切片内定位到“质量状态枚举/输出契约”的统一证据。
- [ ] 失败策略明确：关键契约/解析失败 fail-closed；展示可降级 degraded
  - 证据：未在当前切片内定位到“对外错误语义/门禁策略”的统一证据。

## 4. M3 决策引擎层（Decision Layer）

### 4.1 Checklist

- [ ] 决策对象契约已冻结（信号、理由、约束、版本、run_id/source_run_id）
  - 证据：存在形式化对象 skeleton（IdentifyState/EntryState 等）：[contracts.py:L1-L120](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L1-L120)
- [ ] 决策生成入口可复现（运行参数、依赖输入、输出落点明确）
  - 证据：未在当前切片内定位到“决策引擎独立运行入口”的可复现执行方式。
- [ ] 决策结果具备 readback/list/download 能力（对外 API 或内部入口）
  - 证据：未定位到对外 read/list/download API；仓库内存在 decision_engine contracts，但缺少对外读回证据。
- [ ] 决策失败语义明确（输入缺失/契约不满足 fail-closed；展示可降级 degraded）
  - 证据：未在当前切片内定位到“对外错误语义/门禁策略”的统一证据。
- [ ] 决策可审计（至少包含输入引用与关键派生/中间状态的定位线索）
  - 证据：contracts 中存在 evidence_ref/m2_cycle_ref/m1_constraints_ref 槽位，但缺少端到端落盘/读回证据：[contracts.py:L37-L62](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L37-L62)

## 5. M4 基准评估层（Benchmark Layer）

### 5.1 Checklist

- [ ] Benchmark 对象契约已冻结（评分、对比基准、时间窗口、版本、证据引用）
  - 证据：存在形式化对象定义（BenchmarkSample/AssessmentSummary 等）：[contracts.py:L64-L120](file:///Users/mac/NeoTrade3/neotrade3/benchmark/contracts.py#L64-L120)
- [x] Benchmark 生成入口可复现（输入范围、时间窗口、输出落点）
  - 证据：Worker BENCHMARK executor 调用 `run_benchmark_for_manifest(...)` 并返回 ledger/artifact refs：[main.py:L304-L338](file:///Users/mac/NeoTrade3/apps/worker/main.py#L304-L338)
  - 证据：Daily orchestrator phases 显式包含 BENCHMARK 阶段：[main.py:L758-L769](file:///Users/mac/NeoTrade3/apps/worker/main.py#L758-L769)
- [ ] Benchmark 结果可读回（read/list/download 或内部入口）
  - 证据：未在当前切片内定位到对外 read/list/download API 端点。
- [ ] 解释与证据引用可追溯（能定位到 M3/M1 输入或运行产物）
  - 证据：未在当前切片内定位到“对外解释/证据引用解析”的统一输出。
- [ ] 失败策略明确：契约与解析 fail-closed；展示可降级 degraded
  - 证据：未在当前切片内定位到“对外错误语义/门禁策略”的统一证据。

## 6. M5 治理层（Evolution Controller / Governance Layer）

### 6.1 Checklist

- [ ] 治理对象契约已冻结（candidate、final_validation、rejection、status_transition、handoff 等）
  - 证据：存在治理 ledger/artifact 读回底座，但“契约冻结”需单独文档明确（本切片未补充该文档）：[run_ledger.py:L701-L982](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L701-L982)
- [x] 治理只读 API 三件套齐备（read/list/download，必要时 +download-ledger）
  - 证据：final-validations read/list/download/download-ledger 路由分发：[router.py:L1387-L1433](file:///Users/mac/NeoTrade3/apps/api/router.py#L1387-L1433)
  - 证据：rejections、status-transitions、handoffs、candidate-validations 路由分发（含 download/download-ledger）：[router.py:L1480-L1674](file:///Users/mac/NeoTrade3/apps/api/router.py#L1480-L1674)
- [x] 聚合索引能力存在（按 source_run_id 等关键键一站式查看链路可用性）
  - 证据：`GET /api/governance/index` 路由分发：[router.py:L1675-L1678](file:///Users/mac/NeoTrade3/apps/api/router.py#L1675-L1678)
- [x] fail-closed 语义一致（空参 400、缺文件 404、非法/内部错误不泄露细节；按系统约定返回 500/4xx）
  - 证据：路由层对非法 path 与空 id 做 400 fail-closed（示例：final-validations）：[router.py:L1400-L1427](file:///Users/mac/NeoTrade3/apps/api/router.py#L1400-L1427)
- [x] 下载路径具备 root 限制，防 path traversal
  - 证据：治理 token 归一化（拒绝绝对路径、多段路径、`.`/`..`）：[main.py:L1689-L1712](file:///Users/mac/NeoTrade3/apps/api/main.py#L1689-L1712)
  - 证据：治理下载文件 root 限制（resolve + relative_to(root)）：[main.py:L1714-L1731](file:///Users/mac/NeoTrade3/apps/api/main.py#L1714-L1731)
  - 证据：路径穿越单测（`../` 直接 400）：[test_m5_governance_api_readback.py:L439-L462](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_api_readback.py#L439-L462)

## 7. M6 交付与可观测层（Delivery & Observability Layer）

### 7.1 Checklist

- [x] 关键状态汇总入口存在（例如 ops-center/summary 或等价端点）
  - 证据：路由分发 `GET /api/ops-center/summary`：[router.py:L411-L414](file:///Users/mac/NeoTrade3/apps/api/router.py#L411-L414)
  - 证据：实现 `ops_center_summary_view(...)`：[main.py:L23442-L23844](file:///Users/mac/NeoTrade3/apps/api/main.py#L23442-L23844)
- [x] 状态透传齐备（strategy_id/version/status、data_freshness、运行门禁等）
  - 证据：ops-center evidence 与 checklist 包含 data_freshness / strategy_config（status+version）：[main.py:L23583-L23631](file:///Users/mac/NeoTrade3/apps/api/main.py#L23583-L23631)
  - 证据：workbench meta 透传 strategy_id/version/status + 配置链接：[main.py:L23924-L23940](file:///Users/mac/NeoTrade3/apps/api/main.py#L23924-L23940)
- [x] next_action 为门禁驱动（仅在门禁满足时输出可执行指令/示例）
  - 证据：根据 data_freshness 与 strategy_config_status 生成 next_action，并在 OK 时输出可复制 curl 示例：[main.py:L23798-L23810](file:///Users/mac/NeoTrade3/apps/api/main.py#L23798-L23810)
- [x] degraded 路径不阻塞主功能，但能明确提示风险与定位线索
  - 证据：workbench strategy_config 读取失败进入 degraded，但仍返回 `_meta.status=ok`：[main.py:L23912-L23924](file:///Users/mac/NeoTrade3/apps/api/main.py#L23912-L23924)
  - 证据：ops-center summary_text 明确“策略配置降级”提示：[main.py:L23792-L23798](file:///Users/mac/NeoTrade3/apps/api/main.py#L23792-L23798)
- [x] 对外输出包含必要的证据引用（可跳转的 URL、可下载的配置或产物）
  - 证据：workbench meta 暴露策略配置 read/download URL：[main.py:L23935-L23936](file:///Users/mac/NeoTrade3/apps/api/main.py#L23935-L23936)
  - 证据：策略配置只读 API（list/read/download）实现并强制校验策略文件路径生成（防非法 strategy_id）：[main.py:L2922-L3061](file:///Users/mac/NeoTrade3/apps/api/main.py#L2922-L3061)
