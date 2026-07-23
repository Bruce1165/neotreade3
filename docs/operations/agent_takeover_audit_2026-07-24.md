# NeoTrade3 全面接管审查章程（Agent Takeover Audit）

> 日期：2026-07-24
> 授权：owner 于 2026-07-24 00:26 正式授予全面接管权（TRAE 侧 Agent 已停）
> 执行：Kimi Work Agent（唯一在管 Agent）
> 状态：Phase 0 进行中

## 1. 授权口径（owner 原话要点）

- 不是"按照指令去 coding"，而是**全面接管**：全局意识、目标意识
- 主动找出问题、提出建议，经 owner 确认后执行
- **第一硬要求：建立 robust 的数据抓取机制** —— "没有及时的数据更新，其它都是瞎扯"

## 2. 终极目标锚点（owner 校准口径 2026-07-22）

- 20–60 个交易日内有机会涨 30% 以上；100 个交易日内有希望涨 50% 以上
- 工作顺序：先跟踪池质量，后入场/离场择时
- Backtest oracle = 历史 Top200，绝不反向框定宇宙

一切审查结论必须回锚到这个目标：每个问题都要回答"它离目标有多远"。

## 3. 审查原则

1. 不猜测、不扩大范围、不把"已设计"表述成"已实现"（CLAUDE.md 铁律）
2. 每个结论附证据（文件:行 / 命令输出 / 测试基线）
3. 只读优先；任何写操作先沟通后执行
4. 生产调度归 launchd，Agent Automation 只做一次性/需判断任务（owner 已批准）
5. 问题分级：P0 阻断目标 / P1 威胁数据或资金语义 / P2 工程债 / P3 卫生项

## 4. Phase 划分

### Phase 0 — 基线确认（2026-07-24 上午）

- [ ] 验证夜间两个一次性任务：7/21–7/22 补采行数、8600 万行大表 quick_check
- [ ] 确认 7/24 15:45 例行调度全绿（tushare 修复的最终证明）
- [ ] 测试基线 971 passed、CI run #13+ 全绿复核
- [ ] PROJECT_STATUS.md 过时条目修订（NeoTrade2 Non-Goal 已失效）

### Phase 1 — 数据抓取机制 robustness（最高优先级）

直接回应 owner 第一硬要求。审查范围：

- 数据源链路：Tushare 主 / Tencent safety-net 的真实 fallback 行为、限流与重试语义
- 依赖治理：tushare 未声明事故的同类隐患扫描（所有运行时 import vs pyproject 声明比对）
- 失败可观测性：7/21–22 断了两天才被人工发现 —— 为什么没有任何告警？需要补什么
- 自动 catch-up：调度器补跑逻辑的覆盖边界（历史日 vs 当日 realtime 路径分叉）
- 数据质量门：行数/字段完整性/新鲜度校验是否在每个写入点就位
- 交易日历一致性：trading_day_check 与各路数据源的口径统一
- 磁盘水位：NEO 盘容量、var 增长速率、快照策略的执行成本
- 产出：**数据抓取健壮性报告 + 告警/监控补齐方案**（交 owner 确认后实施）

### Phase 2 — 架构与代码健康

- apps/api/main.py 30.6k 行 god class（最大结构债）与 main_modular.py 烂尾拆分
- 策略版本混乱：v16 文件名 / v17 打印 / labs v2_enhanced 三口径
- 混沌模型专项（等 owner 发起讨论后并入；含 5 个零引用混沌脚本去留）
- 测试质量：971 passed 的覆盖率分布、化石测试成因
- 死代码二次扫描（housekeeping 后的残余）

### Phase 3 — 运维与可观测性

- launchd 版图与注册表文档的一致性复核（含系统域 scheduler）
- 日志治理：err.log 单文件无轮转（scheduler err 已 5.8MB+123KB 两处）
- ledger 完整性：daily_runs 是否有断档、是否有自动审计
- 备份策略：分层快照落地后的恢复演练（从未真正恢复过一次）
- env.secrets 管理与轮换路径

### Phase 4 — 目标对齐验证

- rulebook §1.2 RB.M2.CERTAINTY_SHORT.001 与 owner 口径不一致的回填
- 跟踪池质量度量是否真的能回答"20–60 日 +30%"
- 回测与模拟盘闭环的证据链
- handbook（PROJECT_STATUS.md）与实际状态的偏差清理

### Phase 5 — 收尾与接管确认

- 汇总问题清单（P0–P3）+ 路线图建议，交 owner 评审
- 修订 PROJECT_STATUS.md / production_task_registry.md 等权威文档
- owner 确认后正式进入"接管态"日常协作

## 5. 已知问题预登记（审查前已确认，直接进入清单）

| # | 问题 | 初判级别 | 证据 |
|---|---|---|---|
| K1 | 数据断更 2 天无任何告警（7/21–22，.venv 死亡 + tushare 未声明） | P0 | var/ledgers/daily_runs/2026-07-2[12].json；本仓库 pyproject 修复提交 |
| K2 | apps/api/main.py 30.6k 行 god class | P2 | 2026-07-22 架构审查 |
| K3 | 策略版本三口径（v16/v17/v2_enhanced） | P1 | lowfreq_engine_v16_advanced.py 头部 vs 打印输出 |
| K4 | 系统域 scheduler 日志无轮转 | P3 | ~/Library/Logs/NeoTrade3/neotrade3_scheduler.err.log |
| K5 | 快照策略已定但从未做过恢复演练 | P1 | docs/operations/db_integrity_baseline_2026-07-23.md |
| K6 | PROJECT_STATUS.md NeoTrade2 Non-Goal 已过时 | P3 | owner 2026-07-23 确认 v2 故意清空 |
| K7 | `_tmp_seed_test.db` 403MB 疑似垃圾（NEO var/db） | P3 | 2026-07-23 基线检查，待 owner 确认 |

## 6. 产出物

每个 Phase 一份带证据的报告（写入 `docs/operations/audit/` 或并入本文件），
最终产出：**问题清单 + 优先级路线图**，由 owner 逐项裁决。
