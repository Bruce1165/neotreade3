# 2026-05-19 NeoTrade3 Session Resume Handoff

## 1. 这份文档的用途

给新会话或新 agent 使用。

目标:

- 不依赖此前对话历史
- 直接恢复 `NeoTrade3` 当前工作上下文
- 明确下一步该做什么
- 明确哪些事不能做

## 2. 当前状态

当前主开发项目已经切换为:

- `/Users/mac/NeoTrade3`

当前 `NeoTrade3` 已完成的事实:

- 已创建独立项目根目录
- 已创建独立 `CLAUDE.md`
- 已创建独立 `PROJECT_STATUS.md`
- 已创建 `docs/architecture/`、`docs/handoffs/`、`config/`、`apps/`、`neotrade3/`、`tests/`、`var/` 骨架
- 已创建最小 orchestrator 配置:
  - `config/orchestrator/daily_master_orchestrator.json`
- 已创建实验室注册骨架:
  - `config/labs/labs_registry.json`
- 已播种 3.0 架构总方案:
  - `docs/architecture/neotrade3_master_architecture_and_migration_plan_v1.md`

## 3. 已确认决策

以下决策已经确认，不应在新会话中重新猜测:

1. `NeoTrade2` 保持运行基线，不做大爆炸式重写
2. `NeoTrade3` 为并行新系统，独立作为 IDE 项目
3. `NeoTrade3` 与 `NeoTrade2` 必须完全独立；该独立性要求立即生效
4. `Python orchestrator` 最终要统一协调所有每日必跑工作
5. `NeoTrade3 v1` 首批目标包括:
   - 数据主链
   - Daily Master Orchestrator
   - 四个实验室统一注册
   - 学习闭环最小版本
6. `BaoStock` 先不进入同日例行编排

## 4. 当前最重要的目标

当前不是迁移旧逻辑，也不是切换生产责任。

当前最重要的目标是:

- 开始实现 `NeoTrade3` 的最小骨架代码

优先顺序:

1. `data_control` skeleton
2. `orchestration` skeleton
3. `labs` registry skeleton
4. `learning` scaffold
5. `issue_center` scaffold

## 5. 当前明确不做的事

新会话中不要直接做以下事情，除非用户重新明确要求:

- 不切换 `NeoTrade2` 的生产写入责任
- 不把 2.0 的旧 cron / scheduler 直接复制进 3.0
- 不开始大规模迁移旧脚本
- 不声称 3.0 已具备完整业务能力
- 不把已设计的 learning loop 说成已实现

## 6. 新会话开始后应先读哪些文件

按顺序阅读:

1. `CLAUDE.md`
2. `PROJECT_STATUS.md`
3. `docs/handoffs/2026-05-19_session_resume_handoff.md`
4. `docs/architecture/neotrade3_master_architecture_and_migration_plan_v1.md`
5. `config/orchestrator/daily_master_orchestrator.json`
6. `config/labs/labs_registry.json`

## 7. 推荐的下一步实现入口

建议从以下位置开始实现:

- `neotrade3/data_control/`
- `neotrade3/orchestration/`
- `config/orchestrator/`
- `config/labs/`

最合理的首个代码任务是:

- 定义 `Daily Master Orchestrator` 的最小 Python 接口骨架
- 同时定义任务注册与实验室注册的数据结构

## 8. 与 NeoTrade2 的关系

如需参考旧系统，只把 `NeoTrade2` 当作:

- 运行基线
- 迁移参考
- 回退对照

不要在 3.0 中直接继承 2.0 的目录和项目级规则，也不要形成运行时依赖。

## 9. 对新 agent 的一句话提醒

你现在工作的主项目是 `NeoTrade3`，不是 `NeoTrade2`。
当前工作阶段是“3.0 骨架实现起步”，不是“2.0 修补”。
