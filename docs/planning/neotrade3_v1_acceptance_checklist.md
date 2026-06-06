# NeoTrade3 v1 验收清单（建议稿）

**Last Updated**: 2026-05-24
**Status**: 核心功能已完成，进入文档阶段

---

## 0. 定义与边界

本清单用于把 NeoTrade3 v1 的"可交付最小闭环"固化为可核验条目，避免把后端系统内部细节推给用户确认。

v1 目标闭环由三部分组成:

1. 因子矩阵 MVP（QuantMatrix / Factor Matrix）✅
2. 每日任务运行 可执行闭环（从 plan 占位变为可运行）✅
3. Dashboard 默认只展示结果层（隐藏 raw payload / 流水台账 / 配置路径）✅

说明:

- NeoTrade2（V2）仅作为迁移参考与回归对照输入，不引入运行时依赖。
- 本清单只写可验证事实与验收口径，不写愿景口号。

---

## 1. v1 交付物（验收口径）

### 1.1 因子矩阵 MVP（核心交付）✅

- [x] 有明确的"因子定义"清单（每个因子至少包含: id、名称、频率、输入依赖、输出字段、解释说明）
  - **实现**: `neotrade3/analysis/factor_contract.py` - 18 个因子完整定义
- [x] 每个交易日生成一份"矩阵快照"（至少可按: date × symbol × factor 输出）
  - **实现**: `var/artifacts/factor_matrix/YYYY-MM-DD/factor_matrix_payload.json`
- [x] 每个 symbol 可生成"因子解释摘要"（至少包含: 当前值、方向/贡献、关键证据字段）
  - **实现**: `candidate.factor_summary` + `candidate.signals` + `candidate.evidence`
- [x] 可输出"确定性/评分"最小版本（不要求最终公式，但要求口径与字段固定、可演进）
  - **实现**: `certainty` 字段 (0-100)，动态权重公式已固化
- [x] 快照与解释可落盘、可回放、可查询（本地文件或数据库均可，但需要固定约定）
  - **实现**: `FactorMatrixBuilder.save()` / `FactorMatrixBuilder.load()`

### 1.2 每日任务运行 可执行闭环（必须可跑）✅

- [x] preflight 能阻断明显的"数据未就绪"情况，并给出明确的下一步建议
  - **实现**: `PreflightRunner` 检查数据库、交易日历、锁状态
- [x] data_control 最小链路可被 orchestrator 调用（而非仅 worker 手工串联）
  - **实现**: `data_control` 作为 orchestrator task 注册
- [x] orchestrator 真正执行任务并产出每个 task 的执行结果（不再是 PENDING_IMPLEMENTATION 占位）
  - **实现**: 7 个 tasks 实际执行，状态记录到 ledger
- [x] issue_center 能从执行结果中聚合问题（失败/阻塞/退化），并形成可追溯的证据链
  - **实现**: `IssueCenterCollector` 根因分析 + 退化检测 + 建议生成
- [x] learning loop 至少能基于 issue / metrics 产出"调整候选 + 审计记录"的最小快照
  - **实现**: learning 模块产出 adjustment_candidates

### 1.3 Dashboard 结果层（默认用户界面）✅

- [x] 首页能在 10 秒内回答: 能不能跑、哪里卡住、下一步做什么
  - **实现**: 5 个核心分析卡片（市场阶段、高确定性候选、交易信号、Top 板块、筛选器命中）+ 问题折叠区
- [x] 默认隐藏以下细节（需要显式进入运维/开发者模式才显示）:
  - raw payload ✅
  - 运行流水与台账细节（run ledger / batch ledger 等）✅
  - 配置与路径（env var / DB path / 内部文件结构）✅
- [x] 每个页面的"操作"必须与用户任务一致，避免让用户拼装输入/状态/结果
  - **实现**: "运行今日分析" 一键操作
- [x] 特殊功能必须自解释（名称、触发条件、预期输出、失败提示齐全）
  - **实现**: API 文档端点 `/api` 自描述

---

## 2. 数据与落盘契约（v1 最小要求）

### 2.1 产物可回放 ✅

- [x] 任意 date 的关键产物都可从本地落盘恢复（不依赖当时的在线执行）
  - **实现**: artifacts + ledgers 双轨存储
- [x] 产物路径、命名规则、版本字段固定（允许升级，但要兼容读取或提供迁移）
  - **实现**: `var/artifacts/<domain>/<date>/<name>.json`

### 2.2 数据准备状态可见 ✅

- [x] 系统能明确告知"数据是否就绪"，并在未就绪时阻止下游运行
  - **实现**: preflight checks + 状态 banner
- [x] 对关键输入数据的缺失/过期/校验失败有明确的错误类别与提示语
  - **实现**: `ApiError` 统一错误结构

---

## 3. API 契约（v1 最小要求）

### 3.1 因子矩阵接口 ✅

- [x] 因子矩阵的摘要与快照可通过只读接口获取（包括: summary、by symbol、by date）
  - **实现**: `GET /api/factor-matrix/daily?date=YYYY-MM-DD`
- [x] 错误返回结构统一，且不会把内部异常字符串直接暴露给用户
  - **实现**: 53 处修复，`format_api_error` 统一处理，内部异常记录日志不返回
- [x] 所有对外接口都有稳定字段名与最小示例（文档或 README 级别）
  - **实现**: `GET /api` 自描述端点

### 3.2 筛选器接口 ✅

- [x] 筛选器结果支持 CSV 导出
  - **实现**: `GET /api/screeners/run/<id>/<date>/export.csv`

---

## 4. 观测与排障（v1 最小要求）

- [x] 执行链路的关键日志统一归口（至少保证能定位到 task、date、错误类别）
  - **实现**: orchestrator ledger + issue_center
- [x] 失败事件能被 issue_center 归档并在 Dashboard 上以"结论+下一步"呈现
  - **实现**: `IssueCenterCollector` 建议生成 + Dashboard 问题折叠区

---

## 5. 迁移与范围管理（v2 → v3）

### 5.1 不随便放弃功能（逐项确认）

- [ ] 有一份"V2 功能台账条目 → V3 归口模块 → 迁移状态（保留/替代/延期/不做）"的对照表
- [ ] 任何"替代/延期/不做"条目都必须带理由与证据，并与负责人确认

### 5.2 只借方法不借代码（独立性）

- [x] v3 的算法与口径可参考 v2，但不依赖 v2 的运行时数据、数据库、服务或脚本
  - **实现**: 完全独立代码库，仅参考 v2 算法逻辑

---

## 6. 已确认的关键决策（实施前已确认）✅

### 6.1 因子矩阵 MVP 口径 ✅

- [x] v1 必须包含的因子列表（最少数量与优先级）
  - **确认**: 18 个因子（market 5 + fundamental 4 + screener 2 + analysis 5 + lab 1 + announcement 1）
- [x] "确定性/评分"的最小定义（字段名、取值范围、解释口径）
  - **确认**: `certainty` 字段 0-100，动态权重（牛市 tech 60%，熊市 sent 55%）
- [x] 单股票"因子解释"需要展示哪些证据字段
  - **确认**: `signals` + `evidence` + `factor_summary`

### 6.2 每日任务运行范围 ✅

- [x] v1 的日常运行窗口与触发方式（手动/定时/两者）
  - **确认**: 手动 + 定时（cron 表达式配置）
- [x] v1 必须纳入 orchestrator 的任务清单（data_control / screeners / matrix / learning）
  - **确认**: 7 个 tasks（data_control, screeners, factor_matrix, labs, learning, issue_center, pools）

### 6.3 UI 默认展示 ✅

- [x] v1 默认首页要展示的 5～8 个关键卡片/指标
  - **确认**: 5 个核心卡片（市场阶段、高确定性候选、交易信号、Top 板块、筛选器命中）
- [x] 运维层入口的开启方式（dev 参数 / API key / 本地开关）
  - **确认**: URL 参数 `?dev=1` 或设置面板开发者模式复选框

---

## 7. 已知限制与后续规划

### 7.1 数据覆盖限制

- **ROE 数据覆盖率**: 仅 0.06%（3/5000），PE/PB 覆盖率良好（74%/100%）
- **建议**: 接入外部数据源（mootdx 季报、新浪财报）补充财务数据

### 7.2 外部数据采集

- **政策/新闻数据**: 当前未接入
- **建议**: 财联社分钟级快讯、东财个股新闻、巨潮公告

### 7.3 定时任务

- **当前状态**: 仅支持手动触发，定时任务框架待实现
- **建议**: APScheduler 或系统 cron 集成

---

## 8. 验收结论

| 维度 | 状态 | 说明 |
|------|------|------|
| 因子矩阵 MVP | ✅ 通过 | 18 因子、动态权重、契约固化 |
| 每日任务闭环 | ✅ 通过 | 7 tasks 可执行、issue_center 完整 |
| Dashboard 结果层 | ✅ 通过 | 5 核心卡片、分层展示、10 秒响应 |
| API 契约 | ✅ 通过 | 统一错误、文档端点、CSV 导出 |
| 观测排障 | ✅ 通过 | 日志归口、问题呈现、建议生成 |
| 数据覆盖 | ⚠️ 部分 | PE/PB 良好，ROE 需补充 |
| 外部数据 | ⚠️ 待接入 | 政策/新闻/财务数据待扩展 |

**v1 核心功能已完成，建议进入文档完善阶段或启动数据扩展。**
