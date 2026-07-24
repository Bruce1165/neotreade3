# NeoTrade3 Cleanup Candidates

## 边界

- 本文只输出“清理候选清单”，不执行任何删除
- 所有候选项均以“可核验证据 + 重建方式 + 风险分级”为最小闭环

## 证据快照（2026-07-19，仓库根目录 du 摘要）

- `neotrade3-dashboard/` ≈ 194M
- `./.venv/` ≈ 164M
- `./.git/` ≈ 41M
- `var/` 为符号链接：`var -> /Volumes/NEO/NeoTradeDB/var`（2026-07-22 起；2026-07-19 快照中的 /Volumes/Data 路径已失效）

## 候选清单

### 低风险（可再生缓存/构建产物）

- `neotrade3-dashboard/node_modules/`
  - 理由：前端依赖缓存，可通过 npm 重建
  - 重建证据：前端部署文档提供 `npm install` 与 `npm run build`（见 [DEPLOY.md](file:///Users/mac/NeoTrade3/neotrade3-dashboard/DEPLOY.md#L18-L26)）
  - 风险：重建会消耗时间与网络；不会影响 Python 主链路
- `neotrade3-dashboard/dist/`
  - 理由：前端构建输出目录，可重建
  - 重建证据：同上（见 [DEPLOY.md](file:///Users/mac/NeoTrade3/neotrade3-dashboard/DEPLOY.md#L18-L26)）
  - 风险：若当前网关依赖 dist 提供静态资源，清理前需确认不在服务中
- `__pycache__/`（仓库根与包内）
  - 理由：Python 字节码缓存，可重建
  - 风险：无功能风险
- `.pytest_cache/`
  - 理由：pytest 缓存，可重建
  - 风险：无功能风险
- `.DS_Store`
  - 理由：Finder 元数据文件，可重建
  - 风险：无功能风险

### 中风险（可再生，但重建口径需进一步固化）

- `./.venv/`
  - 理由：Python 虚拟环境理论上可重建，但“依赖可确定性”必须有证据
  - 现有证据：
    - 当前运行/运维文档以 `./.venv/bin/python` 作为解释器入口（见 [bootstrap_runbook.md](file:///Users/mac/NeoTrade3/docs/operations/bootstrap_runbook.md#L45-L57)）
    - 历史交接文档给出了 `.venv` 创建流程（见 [HandOver20260530_Detailed.md](file:///Users/mac/NeoTrade3/docs/archive/handover/HandOver20260530_Detailed.md#L128-L139)）
  - 风险：
    - 若依赖锁定不充分（例如第三方依赖未被统一声明/锁定），删除后可能导致短期不可运行
  - 建议后续补证据（不在本次范围内）：
    - 明确可重建的依赖清单与版本锁定策略，并把“重建命令”固化到运维文档中

### 高风险（运行态数据/证据资产，默认不建议清理）

- `var/log/`、`var/ledgers/`、`var/artifacts/`、`var/db/`
  - 理由：运行日志、台账、产物与数据库是运行态证据与复现基础
  - 现状证据：当前环境中 `var` 指向外置盘（见仓库根目录符号链接信息）
  - 风险：清理会直接破坏可追溯性与复现；并可能导致 API/readback 缺失数据
  - 建议后续（需要单独决策）：
    - 只做“按时间窗口归档/压缩/轮转”，并保留最近 N 天（N 由排障需求决定）

## 不纳入清理的“过期资产”说明（本次仅标注，不建议删除）

- `docs/archive/`：历史交接/归档文档
  - 理由：通常体积不大，但属于审计与历史证据资产
  - 若确需清理：优先考虑迁移到外部归档仓库而不是直接删除

