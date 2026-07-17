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

- [x] 周期对象契约已冻结（字段、语义、版本、可追溯来源）
  - 证据：SmallCycle 契约对象（含 object_type/object_version）与强校验 from_dict：[contracts.py:L37-L105](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/contracts.py#L37-L105)
- [x] 周期识别入口已存在（可调用/可复现），且依赖清单明确（M1 事实输入范围）
  - 证据：识别入口（仅依赖 formal M1 inputs）：
    - build_small_cycle_from_m1(d1_fact, security_master, trading_day_status, trading_profile)：[assembler.py:L134-L240](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/assembler.py#L134-L240)
    - build_shadow_cycle_intelligence_from_m1(cycle, security_master, trading_profile)：[assembler.py:L584-L650](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/assembler.py#L584-L650)
  - 证据：可复现单测（构造 M1 对象并断言输出质量状态/原因与门禁分支）：
    - [test_m2_m3_contract_skeleton.py:L225-L330](file:///Users/mac/NeoTrade3/tests/unit/test_m2_m3_contract_skeleton.py#L225-L330)
  - 边界：当前证据覆盖“识别算法入口（函数）+ 依赖清单（签名）+ 单测复现”；尚未形成独立 CLI/Worker 阶段入口。
- [x] 周期结果可读回（只读 API 或内部入口），支持按 key 查询与列表检索
  - 证据：按 record_id 的内部读回函数（read artifact / read domain / read ledger）：
    - read_small_cycle_artifact / read_small_cycle / read_small_cycle_ledger：[run_ledger.py:L111-L162](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/run_ledger.py#L111-L162)
    - read_shadow_cycle_intelligence_bundle_artifact / read_shadow_cycle_intelligence_bundle / read_shadow_cycle_intelligence_bundle_ledger：[shadow_bundle.py:L288-L342](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/shadow_bundle.py#L288-L342)
  - 证据：列表检索（按 written_at 倒序 + limit）：
    - list_small_cycle_ledgers：[run_ledger.py:L164-L203](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/run_ledger.py#L164-L203)
    - list_shadow_cycle_intelligence_bundle_ledgers：[shadow_bundle.py:L344-L383](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/shadow_bundle.py#L344-L383)
  - 证据：列表检索单测（排序 + limit）：
    - [test_m2_cycle_intelligence_list_ledgers.py:L71-L109](file:///Users/mac/NeoTrade3/tests/unit/test_m2_cycle_intelligence_list_ledgers.py#L71-L109)
- [x] 周期质量状态可输出（例如数据不足、模型未收敛、输入缺失等原因枚举）
  - 证据：SmallCycle v2 冻结 quality_status/quality_reasons 枚举（allowlist + fail-closed 校验），并拒绝 v1 payload：[contracts.py:L9-L163](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/contracts.py#L9-L163)
  - 证据：build_small_cycle / build_small_cycle_from_m1(...) 按 invalidation/state_stability_level 生成质量状态与原因（blocked/invalidated/insufficient_evidence/ok）：[assembler.py:L150-L380](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/assembler.py#L150-L380)
  - 证据：解析 fail-closed 单测（拒绝 v1、拒绝非法 quality_status、非 ok 必须有 reasons）：[test_m2_small_cycle_quality_enum.py:L8-L45](file:///Users/mac/NeoTrade3/tests/unit/test_m2_small_cycle_quality_enum.py#L8-L45)
  - 边界：原因枚举仅覆盖当前已实现的门禁/失效原因集合；不包含“模型未收敛”等未来原因判定。
- [x] 失败策略明确：关键契约/解析失败 fail-closed；展示可降级 degraded
  - 证据：M2 read/list 入口对坏文件采用 fail-closed（读失败/JSON 非法/JSON 顶层非 object/契约不满足即抛错；文件不存在返回 None）：
    - read_small_cycle_artifact / read_small_cycle_ledger / list_small_cycle_ledgers：[run_ledger.py:L111-L203](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/run_ledger.py#L111-L203)
    - read_shadow_cycle_intelligence_bundle_artifact / read_shadow_cycle_intelligence_bundle_ledger / list_shadow_cycle_intelligence_bundle_ledgers：[shadow_bundle.py:L288-L383](file:///Users/mac/NeoTrade3/neotrade3/cycle_intelligence/shadow_bundle.py#L288-L383)
  - 证据：fail-closed 单测（坏 JSON / JSON 顶层非 object / read ledger 顶层非 object）：
    - [test_m2_cycle_intelligence_list_ledgers.py:L112-L169](file:///Users/mac/NeoTrade3/tests/unit/test_m2_cycle_intelligence_list_ledgers.py#L112-L169)
  - 证据：fail-closed 单测（read artifact JSON 顶层非 object）：
    - [test_m2_small_cycle_persistence.py:L55-L63](file:///Users/mac/NeoTrade3/tests/unit/test_m2_small_cycle_persistence.py#L55-L63)
    - [test_m2_shadow_bundle_persistence.py:L96-L107](file:///Users/mac/NeoTrade3/tests/unit/test_m2_shadow_bundle_persistence.py#L96-L107)
  - 证据：异常透传单测（read domain 透传 artifact 解析失败）：
    - [test_m2_small_cycle_persistence.py:L66-L74](file:///Users/mac/NeoTrade3/tests/unit/test_m2_small_cycle_persistence.py#L66-L74)
    - [test_m2_shadow_bundle_persistence.py:L110-L121](file:///Users/mac/NeoTrade3/tests/unit/test_m2_shadow_bundle_persistence.py#L110-L121)
  - 边界：尚未定位到“对外 API 层”的 degraded 展示契约；当前证据覆盖内部读回入口的 fail-closed 语义与异常透传。

## 4. M3 决策引擎层（Decision Layer）

### 4.1 Checklist

- [x] 决策对象契约已冻结（聚合项）
  - [x] front_context 契约冻结（显式版本 + 未知字段拒绝，fail-closed）
    - 证据：front_context 顶层契约已收敛为“显式版本 + 未知字段拒绝”（fail-closed）：[front_context_store.py:L57-L111](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/front_context_store.py#L57-L111)
    - 证据：单测覆盖（缺 object_type/object_version、未知字段均拒绝）：[test_m3_front_context_store.py:L170-L309](file:///Users/mac/NeoTrade3/tests/unit/test_m3_front_context_store.py#L170-L309)
  - [x] state 契约冻结（Identify/Tracking/Entry/Hold/Exit）
    - 证据：存在形式化对象 skeleton（IdentifyState/EntryState 等）：[contracts.py:L1-L120](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L1-L120)
    - 证据：Identify/Tracking/Entry/Hold/Exit 顶层契约冻结（显式 object_type/object_version + 未知字段拒绝 + 字段类型/必填校验）：[contracts.py:L37-L470](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L37-L470)
    - 证据：state 合同 fail-closed 单测（header 缺失/未知字段/list 非法等）：[test_m3_decision_state_contracts.py:L1-L167](file:///Users/mac/NeoTrade3/tests/unit/test_m3_decision_state_contracts.py#L1-L167)
  - [x] lifecycle 契约冻结（DecisionLifecycleEvent/Log）
    - 证据：DecisionLifecycleEvent/Log 顶层契约冻结（from_dict + unknown-fields + events 策略）：[contracts.py:L37-L600](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/contracts.py#L37-L600)
    - 证据：DecisionLifecycleEvent/Log 合同单测：[test_m3_decision_lifecycle_contracts.py:L1-L81](file:///Users/mac/NeoTrade3/tests/unit/test_m3_decision_lifecycle_contracts.py#L1-L81)
  - [x] copy helpers 契约冻结（contracts + assembler/hold_exit_bridge；去除静默 {} / []）
    - 证据：contracts 内部 `_copy_*` 族统一 fail-closed（拒绝非 dict/list 的静默降级）：[test_m3_contract_copy_helpers_fail_closed.py:L1-L81](file:///Users/mac/NeoTrade3/tests/unit/test_m3_contract_copy_helpers_fail_closed.py#L1-L81)
    - 证据：assembler/hold_exit_bridge 内部 `_copy_*` 同口径 fail-closed（去除静默 {} / []）：
      - [assembler.py:L33-L63](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L33-L63)
      - [hold_exit_bridge.py:L17-L34](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/hold_exit_bridge.py#L17-L34)
      - [test_m3_assembler_copy_helpers_fail_closed.py:L1-L43](file:///Users/mac/NeoTrade3/tests/unit/test_m3_assembler_copy_helpers_fail_closed.py#L1-L43)
      - [test_m3_hold_exit_bridge.py:L1-L114](file:///Users/mac/NeoTrade3/tests/unit/test_m3_hold_exit_bridge.py#L1-L114)
- [x] 决策生成入口可复现（运行参数、依赖输入、输出落点明确）
  - 证据：CLI 入口（materialize-front-contexts），显式输入 target_date + codes + run_id/source_run_id，并落盘到 var/artifacts + var/ledgers：[cli.py:L1-L209](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/cli.py#L1-L209)
  - 证据：单测覆盖（成功落盘 + 缺 code 全量 fail-closed 不落盘）：[test_m3_decision_engine_cli_repro_entry.py:L1-L190](file:///Users/mac/NeoTrade3/tests/unit/test_m3_decision_engine_cli_repro_entry.py#L1-L190)
  - 边界：当前入口仅覆盖 `m3_front_context` 这一类 M3 产物的可复现生成与落盘。
- [x] 决策结果具备 readback/list/download 能力（对外 API 或内部入口）
  - 证据：内部 front_context store 提供 artifact/ledger read + ledger list 入口：[front_context_store.py:L235-L364](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/front_context_store.py#L235-L364)
  - 证据：对外 API 路由分发（read/list/download/download-ledger）：[router.py:L1690-L1729](file:///Users/mac/NeoTrade3/apps/api/router.py#L1690-L1729)
  - 证据：Service 层 read/list/download 实现（含 record_id 校验与 root 限制）：[main.py:L3063-L3294](file:///Users/mac/NeoTrade3/apps/api/main.py#L3063-L3294)
  - 证据：API 单测（read/list/download/download-ledger）：[test_m3_front_context_api_readback.py:L1-L193](file:///Users/mac/NeoTrade3/tests/unit/test_m3_front_context_api_readback.py#L1-L193)
  - 边界：仅覆盖 `m3_front_context` 这一类 M3 产物；其它 M3 产物未纳入本切片。
- [x] 决策失败语义明确（输入缺失/契约不满足 fail-closed；展示可降级 degraded）
  - 证据：读回缺文件返回 404；读回/列表遇到非法 ledger/artifact/契约不满足 fail-closed 并转为 500（Service 层捕获并封装）：[main.py:L3101-L3294](file:///Users/mac/NeoTrade3/apps/api/main.py#L3101-L3294)
  - 证据：下载路径防护（record_id 归一化 + resolve + relative_to(root)）：[main.py:L3063-L3099](file:///Users/mac/NeoTrade3/apps/api/main.py#L3063-L3099)
  - 证据：路径穿越与坏 JSON fail-closed 单测：[test_m3_front_context_api_readback.py:L147-L193](file:///Users/mac/NeoTrade3/tests/unit/test_m3_front_context_api_readback.py#L147-L193)
  - 边界：展示层 degraded 策略未形成对外统一契约；当前证据覆盖 API 与内部读回的 fail-closed 语义。
- [x] 决策可审计（至少包含输入引用与关键派生/中间状态的定位线索）
  - 证据：m3_front_context ledger 写入审计索引字段（状态摘要 + 输入引用摘要）并包含 artifact_sha256：[front_context_store.py:L296-L425](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/front_context_store.py#L296-L425)
  - 证据：单测覆盖（ledger 字段齐全 + sha256 可比对）：[test_m3_front_context_store.py:L131-L183](file:///Users/mac/NeoTrade3/tests/unit/test_m3_front_context_store.py#L131-L183)
  - 证据：m3_lifecycle_log store（artifact+ledger 双写 + 审计摘要 + artifact_sha256）：[lifecycle_log_store.py:L1-L332](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/lifecycle_log_store.py#L1-L332)
  - 证据：lifecycle log API（list/read/download/download-ledger）与 fail-closed 单测：[test_m3_lifecycle_log_api_readback.py:L1-L213](file:///Users/mac/NeoTrade3/tests/unit/test_m3_lifecycle_log_api_readback.py#L1-L213)

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
