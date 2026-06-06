# NeoTrade3.0 架构与迁移方案 v1

> 版本: v1
> 日期: 2026-05-19
> 当前决策:
> - `NeoTrade2` 保持运行基线，不做大爆炸式重写
> - 新建 `NeoTrade3` 目录，按新架构并行建设
> - `NeoTrade3` 目标是“数据管理驱动的统一运行、学习、调整体系”
> - `BaoStock` 先不进入同日例行编排
> - `Python orchestrator` 负责所有每日必跑任务的统一协调

---

## 1. 背景与问题

当前 `NeoTrade2` 已经具备不少真实能力，但这些能力分散在不同层面:

- 数据管理:
  - 已形成 `capture -> compose -> publish`
  - 已形成质量闸门、来源冲突台账、发布台账
- 任务运行:
  - 同时存在 `Cron/launchd`、后端内置 scheduler、脚本直跑、局部队列
- 实验室:
  - `杯柄实验室`
  - `量化模拟交易实验室`
  - `老鸭头五图`
  - `量化交易实验室`
  均有局部自动化，但没有统一编排和统一学习闭环
- 界面:
  - 已有数据健康与任务状态视图
  - 但整体仍是旧结构叠加出来的页面，不是按“全链路运营系统”设计

当前主要问题不是“功能不够多”，而是:

1. 数据、任务、实验室、学习四层没有统一主链
2. 每日运行不是单一入口，无法做到全面协调
3. 各实验室运行结果没有进入统一学习与问题闭环
4. 旧结构历史包袱较重，继续叠加会让系统越来越难治理

因此，继续只在 `NeoTrade2` 上做局部修补，已经不再匹配目标。

---

## 2. 为什么要新建 NeoTrade3

### 2.1 不建议继续在 NeoTrade2 上无限叠加

原因不是“2.0 完全不可用”，而是:

- `NeoTrade2` 已经适合承担:
  - 当前生产/半生产能力基线
  - 真实规则与真实问题样本沉淀
  - 迁移参考与回归对照
- 但它不再适合作为“最终理想架构”的直接承载体

### 2.2 为什么不是直接重写 NeoTrade2

不建议直接在 `NeoTrade2` 原位大重构，原因:

- 现有运行链路仍需维持
- 当前数据治理成果已经在运行中，应保留回退路径
- 多实验室的真实业务边界需要有一个稳定参考系

### 2.3 建议的定位

- `NeoTrade2`
  - 定位: 运行基线 / 迁移对照 / 真实规则来源
- `NeoTrade3`
  - 定位: 新架构系统 / 统一运行与学习中枢 / 新界面与新编排承载体

结论:

- 应该新建 `NeoTrade3`
- 不应直接复制 `NeoTrade2` 后继续修补
- 应重新建骨架，再按域迁移能力

---

## 3. NeoTrade3 的目标

`NeoTrade3` 不是“新 UI 工程”，而是一个新的统一系统。

### 3.1 核心目标

1. 数据管理驱动所有实验室
2. 所有每日必跑工作由单一 orchestrator 统一协调
3. 所有运行结果进入统一日志、台账和问题池
4. 所有实验室结果进入统一学习与评估闭环
5. 系统支持“自运行、受约束自调整、可审计自进化”

### 3.2 对“自进化”的约束定义

`NeoTrade3` 中的“自进化”必须满足:

- 基于真实数据
- 基于统一运行结果采集
- 基于明确指标触发
- 以候选变更形式进入评估
- 保留版本与审计记录
- 可回滚

不允许:

- 黑箱自动改参数直接上线
- 未经验证的自发漂移

---

## 4. NeoTrade3 v1 的范围

`v1` 不追求全量迁移，只做新系统骨架和首批核心域。

### 4.1 v1 必须纳入的能力

1. 日线数据主链
   - source registry
   - capture
   - compose
   - publish
   - 质量闸门
   - 冲突仲裁
   - 批次台账

2. Daily Master Orchestrator
   - 收盘后唯一入口
   - 全部每日必跑任务统一协调
   - 统一日志
   - 统一问题聚合

3. 四个实验室统一注册
   - 杯柄实验室
   - 量化模拟交易实验室
   - 老鸭头五图
   - 量化交易实验室

4. 学习闭环最小版本
   - 结果采集
   - 指标评估
   - 候选调整提案
   - 审计记录

5. 新 Dashboard 骨架
   - 数据生命周期
   - 每日总编排
   - 实验室运行态
   - 问题池
   - 学习闭环状态

### 4.2 v1 明确不做的事

- 一次性迁移全部历史脚本
- 把所有旧 UI 页面立即重做完
- `BaoStock` 同日例行编排
- 所有模型自动改参并直接上线
- 所有候选源一次性接入

---

## 5. NeoTrade3 顶层目录建议

建议新建并行目录:

- `/Users/mac/NeoTrade3`

建议骨架:

```text
NeoTrade3/
  README.md
  PROJECT_STATUS.md
  docs/
    architecture/
    handoffs/
    operations/
  config/
    environments/
    orchestrator/
    labs/
  apps/
    api/
    dashboard/
    worker/
  neotrade3/
    data_control/
    orchestration/
    labs/
    learning/
    issue_center/
    common/
  scripts/
    bootstrap/
    maintenance/
  tests/
    unit/
    integration/
    smoke/
  var/
    logs/
    artifacts/
    ledgers/
```

设计原则:

- `apps/` 承载服务入口
- `neotrade3/` 承载核心域逻辑
- `config/` 承载注册表与编排配置
- `docs/` 承载方案、handoff、操作说明
- `var/` 承载运行产物与本地台账

---

## 6. NeoTrade3 核心域

### 6.1 `data_control`

职责:

- 数据源注册
- capture / compose / publish
- 质量闸门
- 来源冲突仲裁
- 字段台账
- 发布批次台账

最重要的约束:

- 数据必须先进入 `capture`
- 正式表只能由 `publish` 写入
- 字段级来源差异必须有台账

### 6.2 `orchestration`

职责:

- Daily Master Orchestrator
- 阶段编排
- 任务依赖图
- 单次运行批次台账
- 统一日志与统一失败收集

它是整个系统的中枢，不只是任务调度器。

### 6.3 `labs`

职责:

- 统一注册实验室
- 统一定义每日任务入口
- 统一定义输入依赖、输出产物、状态规则

首批实验室:

- `cup_handle_lab`
- `paper_simulation_lab`
- `five_flags_lab`
- `quant_trading_lab`

说明:

- 这里的名字是 3.0 内部域名，不强制和 2.0 文件命名完全一致

### 6.4 `learning`

职责:

- 运行结果归集
- 指标评估
- 参数/策略候选调整生成
- 对比评估
- 版本审计
- 回滚记录

### 6.5 `issue_center`

职责:

- 集中收集每日问题
- 汇总各阶段失败
- 生成待处理问题池
- 关联具体批次、具体任务、具体实验室、具体证据

### 6.6 `dashboard`

职责:

- 面向运营而不是面向零散工具
- 统一展示:
  - 数据
  - 编排
  - 实验室
  - 学习
  - 问题池

---

## 7. Daily Master Orchestrator

### 7.1 定位

这是 `NeoTrade3` 的唯一收盘后调度入口。

建议入口文件:

- `neotrade3/orchestration/daily_master_orchestrator.py`

### 7.2 它要处理的对象

不只是数据发布后的两个任务，而是所有每日必跑工作。

首批至少纳入:

- 日线数据主链
- 杯柄实验室日常运行
- 量化模拟交易实验室日常运行
- 老鸭头五图日常运行
- 量化交易实验室日常运行

### 7.3 建议阶段

#### Phase 0: Preflight

- 交易日判断
- 运行锁检查
- 环境/数据库/配置校验
- 防止重复运行

#### Phase 1: Data Pipeline

- capture
- compose
- publish

#### Phase 2: Publish-Gated Jobs

仅在正式发布成功后触发:

- 量化模拟交易实验室
- 老鸭头五图
- 依赖日线正式数据的交易实验任务

#### Phase 3: Daily Lab Jobs

纳入统一窗口管理的实验室任务:

- 杯柄实验室日常评估/回放/重训
- 量化交易实验室非直接依赖 publish success 的日常分析任务

#### Phase 4: Learning Loop

- 采集各实验室结果
- 评估关键指标
- 生成候选调整提案
- 写入学习台账

#### Phase 5: Issue Aggregation And Closeout

- 汇总失败/跳过/退化
- 生成每日问题池
- 生成运行摘要
- 更新 Dashboard

---

## 8. 统一注册模型

`NeoTrade3` 中所有每日任务都必须注册，而不是散落在 cron、线程、脚本里。

### 8.1 实验室注册表示意

每个实验室至少登记:

- `lab_id`
- `display_name`
- `domain`
- `owner`
- `enabled`
- `input_dependencies`
- `daily_jobs`
- `artifacts`
- `health_checks`
- `learning_inputs`

### 8.2 每日任务注册表示意

每个任务至少登记:

- `task_id`
- `lab_id`
- `trigger_type`
- `phase`
- `entrypoint`
- `args_template`
- `depends_on`
- `requires_publish_status`
- `outputs`
- `failure_policy`
- `retry_policy`
- `issue_tags`

### 8.3 支持的触发类型

- `scheduled_entry`
- `post_publish_trigger`
- `daily_lab_trigger`
- `manual_event_trigger`

说明:

- 并不是所有任务都应该仅由 `publish success` 触发
- 但所有每日必跑任务都必须由同一 orchestrator 协调

---

## 9. 统一台账

`NeoTrade3` 需要的不只是数据台账，还需要运行与学习台账。

### 9.1 数据台账

继承 2.0 已验证的思路:

- source registry
- capture batches
- compose candidates
- publish batches
- source conflicts

### 9.2 编排台账

建议新增:

- `orchestrator_runs`
- `orchestrator_task_runs`

最少字段:

- `orchestrator_run_id`
- `target_date`
- `phase`
- `task_id`
- `lab_id`
- `status`
- `started_at`
- `finished_at`
- `exit_code`
- `dependency_refs`
- `issue_summary`
- `artifact_paths`

### 9.3 学习台账

建议新增:

- `learning_evaluations`
- `adjustment_candidates`
- `model_version_audits`

最少字段:

- `evaluation_id`
- `lab_id`
- `target_date`
- `metric_snapshot`
- `baseline_version`
- `candidate_version`
- `decision`
- `decision_reason`
- `approved_by`
- `rollback_ref`

### 9.4 问题池

建议新增:

- `issue_events`
- `issue_cases`

这样才能把:

- 数据失败
- 任务失败
- 学习退化
- 产物缺失

统一纳入闭环。

---

## 10. Learning Loop 最小模型

### 10.1 目标

不是“让系统自动瞎改”，而是:

- 让系统自动汇总结果
- 自动发现可疑退化
- 自动生成候选调整提案

### 10.2 最小闭环

1. 实验室任务运行完成
2. 统一归集产物
3. 计算核心指标
4. 对比基线版本
5. 生成候选变更
6. 写入审计台账
7. 进入人工或规则闸门审批

### 10.3 v1 的边界

`v1` 只做到:

- 候选调整生成
- 版本审计
- 回滚准备

不做到:

- 自动批准上线
- 无监督参数漂移

---

## 11. NeoTrade2 到 NeoTrade3 的迁移策略

### 11.1 总原则

- 2.0 保持运行
- 3.0 并行建设
- 按域迁移
- 小步切换
- 随时可回退

### 11.2 迁移阶段

#### Stage 0: Architecture Freeze

在 `NeoTrade2` 中冻结以下事实作为迁移输入:

- 数据主链约束
- 质量闸门
- 冲突仲裁规则
- 当前实验室真实入口
- 当前任务依赖

#### Stage 1: Build 3.0 Skeleton

在 `NeoTrade3` 中只建:

- 顶层目录
- 配置骨架
- 核心域空骨架
- 文档与 handoff 机制

#### Stage 2: Migrate Data Control

先迁移:

- source registry
- capture / compose / publish
- 批次台账
- 冲突台账

#### Stage 3: Build Master Orchestrator

再迁移:

- Daily Master Orchestrator
- 统一任务注册
- 统一日志与问题池

#### Stage 4: Register Four Labs

把四个实验室纳入统一注册体系，先做到:

- 有统一入口
- 有统一状态
- 有统一产物登记

#### Stage 5: Build Learning Loop

实现:

- 结果归集
- 指标评估
- 候选调整提案
- 审计记录

#### Stage 6: Cutover By Domain

按域切换，不做整体大切换。

优先顺序建议:

1. 数据主链
2. 每日编排
3. 实验室注册
4. 学习闭环
5. 新 Dashboard

---

## 12. 回退原则

任何阶段切换到 3.0，都必须满足:

- 有明确基线对照
- 有运行日志
- 有批次台账
- 有回退路径

禁止:

- 无法回退的整体切换
- 没有证据的“看起来差不多”

---

## 13. NeoTrade3 Dashboard 方向

3.0 的界面应该按“运营中枢”来设计，而不是旧页面拼接。

建议一级视图:

- `Overview`
- `Data Control`
- `Daily Orchestration`
- `Labs`
- `Learning`
- `Issue Center`

### 13.1 Data Control

展示:

- source registry
- capture / compose / publish
- 质量闸门
- 来源冲突

### 13.2 Daily Orchestration

展示:

- 当日总运行批次
- 各阶段状态
- 触发链
- 跳过/失败原因

### 13.3 Labs

展示:

- 四个实验室运行状态
- 当日产物
- 最近退化/异常

### 13.4 Learning

展示:

- 指标变化
- 候选调整
- 审计记录
- 回滚状态

### 13.5 Issue Center

展示:

- 今日问题
- 未闭环问题
- 关联批次
- 关联实验室

---

## 14. v1 交付物建议

`NeoTrade3 v1` 的第一批正式交付物建议是:

1. `NeoTrade3` 空骨架目录
2. `daily_master_orchestrator.py`
3. 实验室/任务注册配置
4. 统一运行台账
5. 统一问题池
6. 数据主链最小实现
7. 新 Dashboard 骨架页

---

## 15. 当前结论

结论明确:

- 需要新建 `NeoTrade3`
- 需要在新目录下重新构建
- 需要摆脱 `NeoTrade2` 的旧结构束缚
- 但不能抛弃 `NeoTrade2` 已沉淀的真实规则和运行经验

`NeoTrade3` 的正确起点不是“复制旧工程”，而是:

- 重新定义系统边界
- 建立统一主链
- 再分批把已验证能力迁移进去

这也是当前最符合“数据管理驱动、自运行、自调整、自进化”目标的路线。
