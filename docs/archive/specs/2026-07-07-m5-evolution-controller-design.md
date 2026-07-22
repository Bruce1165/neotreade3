# M5 演化控制层详细设计

日期：2026-07-07

## 1. 文档目标

本文档用于冻结 NeoTrade3 量化体系中 `M5 演化控制层` 的详细设计，明确其正式定义、职责边界、治理输入、治理对象、归因模型、优先级与门禁机制、实验闭环以及第一阶段实施范围。

本文档解决的问题：

- `M5` 到底是什么，不是什么。
- `M5` 应该拿什么做治理判断，输出什么正式治理对象。
- 单股问题如何形成正式归因链，而不是停留在模糊印象层。
- `M5` 如何把偏差转成正式治理路径，而不是直接改模型。
- 哪些问题必须阻断升级，哪些问题必须人工介入。
- `Change Request -> Experiment -> Validation -> Promotion/Reject` 如何被正式组织成闭环。

本文档不展开：

- `M3` 的具体规则重构方案。
- `M4` 的具体评分公式与样本工程实现。
- `M6` 的治理页面与前端展示细节。
- 各治理对象的最终数据库表结构与 API 细节。
- 自动实验执行器的底层实现机制。

## 2. 设计背景

顶层架构已经冻结为 `M1-M6` 六层结构，其中 `M5` 被定义为演化控制层，用于消费 `M1-M4` 提供的正式证据与正式差距对象，对系统偏差进行归因、治理分流、实验编排、升级门禁控制与人工关注组织。

当前项目中的现实基础包括：

- `M1` 已明确承担事实质量、Freshness、Coverage、Replay 与 Attention 输出职责。
- `M2` 首期已将 `small_cycle` 作为唯一正式生产周期主链，并冻结了若干关键保护约束。
- `M4` 已被定义为正式差距检验层，后续将向 `M5` 输出 `gap_record / trace_bundle / interaction_guardrail_breach` 等正式治理输入。
- 用户已明确要求：系统应面向每一只股票形成可回溯的体系性判断；当逻辑偏差、冲突或不连贯时，必须能清晰回溯整条逻辑链并形成有针对性的反馈。

用户已确认的关键方向：

- `M5` 不是报警中心，也不是自动调参器。
- `M5` 是单股全链路回溯、归因与定向反馈的治理中枢。
- 但 `M5` 之所以能成立，前提是 `M1-M4` 已经为每只股票提供逐日、逐状态、逐层级的正式证据链。
- 任何涉及关键概念、关键语义、层间契约、生产主链 guardrail 的治理动作，都必须谨慎、可回溯、可审批、可验证。

## 3. M5 的正式定义

`M5` 不是“看到问题就自动改模型”的自发演化器。

`M5` 的正式定义为：

- 在不静默改写上游真值、不绕过治理流程直接修改模型核心的前提下，
- 基于 `M1` 的质量状态、`M2` 的周期偏差、`M3` 的决策偏差、`M4` 的正式差距对象，
- 完成问题归因、变更请求生成、实验与升级门禁管理、以及人工关注事项组织的演化控制层。

`M5` 的核心承诺只有四个：

- 归因正式化
- 分流正式化
- 门禁正式化
- 闭环正式化

## 4. M5 的职责边界

### 4.1 M5 负责

- 接收并聚合来自 `M1-M4` 的正式治理输入。
- 对问题进行层级归因与链路回溯。
- 生成正式治理对象：
  - `Change Request`
  - `Attention Item`
  - `Experiment Request`
  - `Promotion Blocker`
  - `Governance Decision Record`
- 决定治理动作的优先级、处理路径和是否需要人工介入。
- 管理从“发现问题”到“验证修复”之间的闭环状态。

### 4.2 M5 不负责

- 不直接修改 `M1` 事实。
- 不直接改写 `M2` 周期真值。
- 不直接在线调整 `M3` 正式决策逻辑。
- 不用临时观察结果跳过验证流程推动升级。
- 不把展示层反馈或人工感受直接当作正式真值。

### 4.3 与其他层的关系

`M5` 不是独立知道一切的“超层”，它依赖上游证据链，同时又必须保持治理边界：

- `与 M1`
  - `M5` 不能重写事实，但可以根据 `M1` 的质量状态要求补数、补源、补派生或提升质量门禁。
- `与 M2`
  - `M5` 不决定周期真值，但可基于正式偏差与回溯链向 `M2` 发起识别逻辑、边界定义、状态机设计方面的改进请求。
- `与 M3`
  - `M5` 不直接做交易决策，但可要求 `M3` 修正对 `M2` 状态的翻译逻辑、低频行为链成熟度、持有与退出语义。
- `与 M4`
  - `M4` 是 `M5` 的正式差距输入层。没有 `M4` 的正式偏差对象，`M5` 很容易退化成经验性评论层。
- `与 M6`
  - `M6` 负责展示 `M5` 的治理状态、Attention Queue、Change Request 状态和阻塞信息，但不得代替 `M5` 做治理判断。

## 5. 正式输入对象、治理对象与处理路径

`M5` 不能只有治理使命，还必须有正式输入、正式输出和正式处理路径。

### 5.1 正式输入对象

首期应冻结五类输入：

- `I1` `M1` 数据质量与能力缺口对象
- `I2` `M2` 周期识别稳定性与失效相关对象
- `I3` `M3` 决策行为与执行审计对象
- `I4` `M4` 正式差距对象与回溯对象
- `I5` 系统级治理上下文对象

#### `I1` M1 输入边界

`M5` 从 `M1` 接收的正式治理输入至少包括：

- `Source Status`
- `Freshness Proof`
- `Coverage Status`
- `Consistency Status`
- `Replay Status`
- `Attention Item`
- `Data Capability Gap`

#### `I2` M2 输入边界

`M5` 从 `M2` 接收的正式对象至少包括：

- `cycle_state`
- `state_transition_log`
- `confidence`
- `invalidation`
- `state_stability_level`
- `recompute_reason`
- `rule_version`

#### `I3` M3 输入边界

`M5` 从 `M3` 接收的正式对象至少包括：

- `identify`
- `tracking`
- `entry`
- `hold`
- `exit`
- 生命周期事件
- 决策归因字段
- 执行约束命中情况

#### `I4` M4 输入边界

`M4` 是 `M5` 的正式差距输入层，至少应消费：

- `gap_record`
- `trace_bundle`
- `assessment_grade`
- `interaction_guardrail_breach`
- `sample_bucket_summary`
- `gap_group_distribution`

其中真正驱动治理动作的核心输入，不是摘要，而是：

- `gap_record`
- `trace_bundle`
- `interaction_guardrail_breach`

#### `I5` 系统级治理上下文

用于治理排序与升级门禁，至少包括：

- 问题复发频率
- 影响样本范围
- 涉及层级数量
- 是否影响生产主链
- 是否触发人工关注义务
- 当前是否已有进行中的实验或未关闭请求

### 5.2 正式治理对象

首期冻结五类正式治理对象：

- `G1` `Change Request`
- `G2` `Attention Item`
- `G3` `Experiment Request`
- `G4` `Promotion Blocker`
- `G5` `Governance Decision Record`

#### `G1` Change Request

表示某个问题已被正式归因，且需要对某一层发起有边界的改进请求。

最低字段建议包括：

- `cr_id`
- `target_layer`
- `source_gap_ids`
- `problem_statement`
- `suspected_root_cause`
- `evidence_refs`
- `expected_improvement`
- `risk_scope`
- `priority`
- `requires_human_approval`
- `status`

#### `G2` Attention Item

`Attention Item` 在 `M5` 中是治理编排后的人工关注对象，适用于：

- 无法自动推进
- 涉及跨层冲突
- 涉及关键概念修订
- 涉及生产主链风险
- 涉及人工审查或外部补数

#### `G3` Experiment Request

当问题已明确，但修复方向不能直接推入正式链路时，必须先形成：

- `Experiment Request`

它至少说明：

- 实验目标
- 目标层
- 假设问题
- 预期改善项
- 不允许恶化的 guardrail
- 比较样本范围
- 验证期限或退出条件

#### `G4` Promotion Blocker

用于声明：

- 在某个风险未解除前，某项能力不得被宣称正式成熟，不得进入更高发布等级。

#### `G5` Governance Decision Record

用于记录每次正式治理决定的依据、范围、预期影响、版本、审批状态与责任主体。

### 5.3 正式处理路径

`M5` 首期至少冻结六条处理路径：

- `P1 数据修复路径`
- `P2 识别修正路径`
- `P3 决策翻译修正路径`
- `P4 协同语义修正路径`
- `P5 实验验证路径`
- `P6 人工升级路径`

#### `P1 数据修复路径`

当问题根因在 `M1` 时进入，典型触发：

- Freshness 失败
- Coverage 不足
- Replay 不成立
- 数据源冲突
- 派生事实缺口

#### `P2 识别修正路径`

当问题主要在 `M2` 时进入，典型触发：

- `small_cycle` 切得过碎
- 状态迁移过敏
- `Exhausting` 与 `Invalidated` 混淆
- 历史边界重写过多

#### `P3 决策翻译修正路径`

当 `M2` 本身大致合理，但 `M3` 行为链不成熟时进入。

#### `P4 协同语义修正路径`

必须单列，用于处理：

- `M2` 输出局部后段
- `M3` 却理解成整轮结束
- 或 `M2` 失效语义不足导致 `M3` 误译

#### `P5 实验验证路径`

当问题存在，但修复方向尚不够确定时进入。

#### `P6 人工升级路径`

当问题涉及关键概念、跨层边界、生产门禁或高风险语义冲突时，必须人工升级。

### 5.4 路径选择规则

`M5` 必须先做“根因优先”分流，而不是“症状优先”分流。

正式顺序应是：

1. 先看 `M1` 是否满足正式消费前提
2. 再看 `M2` 状态是否合理成立
3. 再看 `M3` 是否正确翻译 `M2`
4. 再看是否存在 `M2-M3` 协同语义冲突
5. 最后再决定是否需要实验或人工升级

## 6. 层级归因模型与单股全链路诊断机制

`M5` 不能只说“这个问题看起来像是 M2/M3 的问题”，必须有正式归因模型。

### 6.1 归因的正式目标

`M5` 的归因目标不是寻找“唯一背锅层”，而是：

- 找到 `primary_root_layer`
- 识别 `secondary_amplifier_layers`
- 标记 `interaction_conflict_layers`
- 形成 `diagnostic_chain`

### 6.2 一级归因层

首期冻结五个一级归因层：

- `A1 Data Root`
- `A2 Recognition Root`
- `A3 Translation Root`
- `A4 Interaction Root`
- `A5 Governance Root`

#### `A1 Data Root`

问题源于 `M1` 事实缺陷、事实不足、质量失败或回放不成立。

#### `A2 Recognition Root`

问题源于 `M2` 周期识别本身的状态定义、边界判断、稳定性或失效语义。

#### `A3 Translation Root`

问题源于 `M3` 对 `M2` 状态的翻译与行为执行链。

#### `A4 Interaction Root`

问题主要源于层间语义契约不清、接口设计不稳或协同失真。

#### `A5 Governance Root`

问题本身早已被正式识别，但由于治理未升级、实验未闭环、门禁未设置、Attention 未被处理而持续存在。

### 6.3 单股全链路诊断对象

为每只股票的每个关键问题生成正式对象：

- `diagnostic_chain`

最低字段建议包括：

- `diagnostic_id`
- `symbol`
- `date_range`
- `primary_root_layer`
- `secondary_layers`
- `interaction_layers`
- `trigger_gap_ids`
- `trace_bundle_refs`
- `root_cause_statement`
- `amplification_path`
- `proposed_pathway`
- `governance_status`
- `decision_record_refs`

### 6.4 单股归因的正式顺序

归因顺序必须固定：

1. 先检查 `M1` 是否满足正式消费前提
2. 再检查 `M2` 状态是否合理成立
3. 再检查 `M3` 是否正确翻译 `M2`
4. 再检查是否存在 `M2-M3` 协同语义冲突
5. 最后检查是否存在治理失效导致问题长期未收敛

### 6.5 amplification_path

`amplification_path`：一个原本可局部控制的问题，是如何沿着层级链条被放大成最终偏差结果的正式路径对象。

### 6.6 interaction_conflict

`interaction_conflict`：两个或多个层的正式语义在接口处不能稳定对齐，导致问题不是单层能解释的正式冲突对象。

### 6.7 归因与修复分离

必须明确：

- `diagnostic_chain` 是问题真相对象
- `Change Request` 是治理动作对象

二者不得混写。

## 7. 优先级模型、升级门禁与人工介入规则

`M5` 如果只有归因，没有优先级和门禁，就会退化成问题收集器。

### 7.1 首期优先级判断维度

首期冻结六个优先级维度：

- `P1 风险严重度`
- `P2 影响范围`
- `P3 复发频率`
- `P4 根因层级`
- `P5 可修复性`
- `P6 守门风险`

### 7.2 优先级等级

首期输出四级优先级：

- `P0 Critical`
- `P1 High`
- `P2 Medium`
- `P3 Research`

### 7.3 P0 场景

至少以下场景应进入 `P0`：

- `M1` 正式数据门禁失效却仍被下游消费
- `M2` 历史状态大规模超窗口重写
- `M3` 持续将局部 `small_cycle` 结束误译为整轮结束
- `M4` 无法稳定产出正式差距对象
- 关键 guardrail 被反复突破但未进入治理处理
- 涉及关键概念重定义且影响生产语义

### 7.4 promotion_gate

`promotion_gate`：某项能力、规则、对象或输出，在满足既定验证条件前，是否允许进入更高成熟度、更高使用范围或更高信任等级的正式门禁机制。

### 7.5 Promotion Blocker 触发条件

首期建议至少以下情况触发 blocker：

- 上游事实门禁不稳定
- `M2` 状态机仍存在明显重写与漂移
- `M3` 低频风格明显失真
- `M4` 无法稳定区分 `Identify / Timing / Holding / Exit / Interaction`
- 同类问题在 `B4 协同风险样本` 中持续复发
- 关键问题只靠人工口头解释，无法结构化回溯

### 7.6 人工介入正式边界

首期建议以下情况强制人工介入：

- 涉及关键概念或正式术语重定义
- 涉及跨层语义契约修改
- 涉及生产主链 guardrail 破坏
- 涉及是否解除 blocker 的决定
- 涉及是否让研究输出升级为正式输出
- 涉及高风险样本上的治理豁免或压制

### 7.7 自动化分层

建议继承并扩展为：

- `A0 Auto-Resolve`
- `A1 Auto-Propose`
- `A2 Human-Approve`
- `A3 Human-Own`

其中：

- 任何涉及关键概念、正式语义、层间契约、生产口径的变更请求，默认至少进入 `A2 Human-Approve`
- 高风险时直接进入 `A3 Human-Own`

## 8. 实验、验证与变更闭环

`M5` 不能停留在“发现问题 -> 发个 CR”，必须形成真正闭环。

### 8.1 标准治理链

首期冻结一条标准治理链：

- `Gap / Diagnostic -> Change Request -> Experiment Request -> Validation Result -> Promotion Decision / Reject Decision`

这五段必须都是正式对象，不允许缺段。

### 8.2 Gap / Diagnostic

闭环从正式问题对象开始，而不是从想法开始。

起点至少应是：

- `gap_record`
- `diagnostic_chain`
- `interaction_guardrail_breach`

### 8.3 Change Request

`Change Request` 的作用是把问题从“诊断对象”转为“治理议题”。

### 8.4 Experiment Request

绝大多数有实质影响的改动，不应直接进入正式链路，必须先形成：

- `Experiment Request`

至少以下类型必须先实验：

- `M2` 状态机或关键语义调整
- `M3` 持有/退出翻译逻辑调整
- 涉及 `small_cycle` 长度、边界、衰竭语义的改动
- 涉及协同风险 guardrail 的修正
- 涉及 Benchmark 样本与目标状态口径变化的改动

### 8.5 Validation Result

实验完成后必须形成正式：

- `Validation Result`

它至少回答：

- 是否真的改善了目标偏差
- 是否引入了新的副作用
- 是否触碰新的 guardrail 风险
- 证据是否足够支持升级或拒绝

验证结果不能只看收益，必须同时看：

- 原始偏差是否缓解
- 是否引入新的识别漂移
- 是否加重持有碎片化
- 是否让某类样本改善但另一类明显恶化
- 是否破坏低频风格一致性

### 8.6 Promotion Decision / Reject Decision

在 `Validation Result` 之后，才能进入正式决策：

- `Promotion Decision`
- `Reject Decision`

`Reject Decision` 也必须是正式对象，至少记录：

- 拒绝原因
- 触发的风险点
- 是否可重开
- 重开条件
- 对应哪条 `CR / Experiment`

### 8.7 闭环 guardrail

每个实验与升级都必须绑定 guardrail：

- 不得加重 `small_cycle` 过碎识别
- 不得提高局部结束误译为整轮结束的频率
- 不得降低回放一致性
- 不得让低频行为链重新高频化

### 8.8 闭环状态模型

整个变更闭环至少有以下状态：

- `identified`
- `triaged`
- `cr_open`
- `experiment_pending`
- `experiment_running`
- `validation_pending`
- `approved_for_promotion`
- `rejected`
- `blocked`
- `closed`

### 8.9 重开机制

被关闭或被拒绝的问题只有在以下情况出现时才允许重开：

- 新证据出现
- 新样本显示旧判断不成立
- 上游能力变化导致原约束改变
- 关键概念已被正式修订

## 9. 第一阶段实施范围、非目标与验证等级

`M5` 首期的目标不是“自动优化模型”，而是先建立单股可回溯、分层可归因、路径可分流、变更可闭环、升级可拦截的正式治理主链。

### 9.1 第一阶段锚点

`M5` 首期边界必须锚定到四个前提：

- `M1` 能输出正式质量状态、Freshness/Attention/Capability Gap
- `M2` 首期只正式化 `small_cycle`
- `M3` 必须输出正式行为链和归因链
- `M4` 首期目标是 `Governance Ready`，能输出正式 `gap_record / trace_bundle / interaction_guardrail_breach`

### 9.2 第一阶段必须完成

- `P1` 正式治理输入收口
- `P2` 单股诊断链
- `P3` 正式治理对象
- `P4` 路径分流机制
- `P5` 优先级与门禁机制
- `P6` 基础闭环状态机

### 9.3 第一阶段聚焦的核心治理问题

- `Q1` 问题是否能被稳定归因到 `Data / Recognition / Translation / Interaction / Governance`
- `Q2` 单股问题是否能形成完整 `diagnostic_chain`
- `Q3` `small_cycle` 协同风险是否能被正式检测、阻断、追踪
- `Q4` `M4` 发现的问题能否真正转化为正式治理动作
- `Q5` 关键概念、关键语义、关键 guardrail 的变更是否被强制纳入人工审批与实验验证

### 9.4 第一阶段明确不做

- 不构建全自动参数调优系统
- 不允许 `M5` 自动在线修改 `M1/M2/M3` 正式逻辑
- 不追求完整的自治演化闭环
- 不尝试一次性覆盖所有问题类型和所有治理路径
- 不把研究想法、聊天结论、口头观察直接纳入正式治理主链
- 不把 `M5` 做成巨大的运维工单中心，吞掉 `M6` 的展示职责

### 9.5 验证等级

`M5` 首期采用三层验证等级：

- `V1 Observability Ready`
- `V2 Governance Ready`
- `V3 Controlled Evolution Ready`

`V1 Observability Ready`

- 已能聚合问题并做基础状态展示，但还不足以形成正式治理闭环。

`V2 Governance Ready`

- 已能输出正式诊断链、正式治理对象、正式路径分流与门禁决策。

`V3 Controlled Evolution Ready`

- 已能稳定驱动实验、验证与升级闭环，且长期运行证明不越权、不漂移。

### 9.6 首期目标等级与最低验收标准

首期目标定为：

- `V2 Governance Ready`

最低验收标准至少包括：

- `A1` 稳定消费 `M1-M4` 的正式治理输入
- `A2` 为单只股票生成正式 `diagnostic_chain`
- `A3` 能把问题归入五类正式根因层
- `A4` 能正式生成 `Change Request / Experiment Request / Promotion Blocker / Governance Decision Record`
- `A5` 能对关键概念、关键语义、关键 guardrail 变更强制人工审批
- `A6` 能对 `small_cycle` 局部结束被误译为整轮结束这类协同风险生成 blocker 或高优先级治理动作
- `A7` 能把至少一部分问题推进到 `CR -> Experiment -> Validation -> Promotion/Reject` 的正式闭环状态

## 10. 当前结论

本文档冻结以下结论：

- `M5` 是演化控制层，不是报警层、自动调参层或隐性改模层。
- `M5` 是单股全链路回溯、归因与定向反馈的治理中枢，但该能力建立在 `M1-M4` 已提供正式证据链的前提上。
- `M5` 必须基于正式输入对象生成结构化治理对象，并按根因优先原则将问题分流到正式处理路径。
- `M5` 必须以 `diagnostic_chain` 作为最小治理诊断单位，并按 `Data / Recognition / Translation / Interaction / Governance` 五类正式根因层完成归因。
- `M5` 必须将优先级判断、升级门禁与人工介入规则作为正式治理机制独立管理。
- `M5` 必须将任何正式治理动作纳入“诊断 -> 变更请求 -> 实验 -> 验证 -> 升级或拒绝”的版本化闭环。
- `M5` 首期应以 `Governance Ready` 为目标，而不是过早宣称自己具备正式演化能力。

## 11. 不在本文档中解决的问题

以下问题明确不在本文档中展开：

- 各治理对象的最终存储结构与 API 字段细节
- 自动实验执行器与任务调度的底层实现
- `M3` 的具体规则修正方案
- `M6` 的治理页面与交互设计
- 更高层级的自治演化与自动参数搜索策略

这些内容将进入后续子模块设计文档。
